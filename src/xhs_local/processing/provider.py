"""DeepSeek chat-completion transport with the legacy retry contract."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import tempfile
import urllib.error
import urllib.request
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlparse

from xhs_local.core.errors import ErrorClass, PipelineError

DEFAULT_ENDPOINT = "https://api.deepseek.com/chat/completions"
DEFAULT_API_KEY_PATH = Path(__file__).resolve().parents[3] / "runtime/secrets/deepseek-api-key"
DEFAULT_TIMEOUT_SECONDS = 90.0
DEFAULT_ATTEMPTS = 2
DEFAULT_RETRY_BASE_DELAY_SECONDS = 2.0
DEFAULT_MAX_TOKENS = 6_000


class DeepSeekError(PipelineError):
    """Base provider failure.

    Non-HTTP failures are retryable, matching the old provider's behavior.
    """

    retryable = True


class DeepSeekTransportError(DeepSeekError):
    """A request failed before DeepSeek returned an HTTP response."""

    error_class = ErrorClass.TRANSIENT_NETWORK


class DeepSeekResponseError(DeepSeekError):
    """The provider returned a response that cannot satisfy the contract."""


class DeepSeekHttpError(DeepSeekError):
    """An HTTP response rejected the request."""

    def __init__(
        self,
        message: str,
        *,
        status: int,
        retryable: bool,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.retryable = retryable
        self.error_class = (
            ErrorClass.RATE_LIMITED
            if status == 429
            else ErrorClass.TRANSIENT_NETWORK
            if retryable
            else ErrorClass.PERMANENT_REMOTE
        )


class CodexCliError(PipelineError):
    """The local ChatGPT-authenticated Codex CLI fallback failed."""

    retryable = True
    error_class = ErrorClass.TRANSIENT_NETWORK


@dataclass(frozen=True, slots=True)
class HttpResponse:
    """Small response value used by the injectable HTTP boundary."""

    status: int
    body: str


Request = Callable[
    [str, Mapping[str, str], Mapping[str, Any], float],
    Awaitable[HttpResponse],
]
CodexRunner = Callable[[Path, str, str, float], str]


class ChatCompletionProvider(Protocol):
    """Stateless completion boundary consumed by content processing."""

    async def check_configuration(self) -> bool: ...

    async def complete(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        model: str,
    ) -> str: ...


def _blocking_request(
    endpoint: str,
    headers: Mapping[str, str],
    payload: Mapping[str, Any],
    timeout_seconds: float,
) -> HttpResponse:
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(),
        headers=dict(headers),
        method="POST",
    )

    def read_response(response: Any) -> HttpResponse:
        with response:
            return HttpResponse(response.status, response.read().decode("utf-8", "replace"))

    try:
        # urlopen caches proxy settings process-wide; refresh them after network changes.
        return read_response(urllib.request.build_opener().open(request, timeout=timeout_seconds))
    except urllib.error.HTTPError as error:
        return HttpResponse(error.code, error.read().decode("utf-8", "replace"))
    except (urllib.error.URLError, ConnectionError, OSError) as routed_error:
        direct = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            return read_response(direct.open(request, timeout=timeout_seconds))
        except urllib.error.HTTPError as error:
            return HttpResponse(error.code, error.read().decode("utf-8", "replace"))
        except (urllib.error.URLError, ConnectionError, OSError) as direct_error:
            raise direct_error from routed_error


async def default_request(
    endpoint: str,
    headers: Mapping[str, str],
    payload: Mapping[str, Any],
    timeout_seconds: float,
) -> HttpResponse:
    """Perform one request without blocking the application's event loop."""

    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_blocking_request, endpoint, headers, payload, timeout_seconds),
            timeout=timeout_seconds + 1,
        )
    except TimeoutError as error:
        raise DeepSeekTransportError(
            f"DeepSeek request timed out after {round(timeout_seconds * 1000)}ms"
        ) from error
    except (urllib.error.URLError, ConnectionError, OSError) as error:
        raise DeepSeekTransportError(f"DeepSeek transport failed: {error}") from error


def _validate_endpoint(endpoint: str) -> str:
    parsed = urlparse(endpoint)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise TypeError("endpoint must be an HTTP(S) URL")
    return endpoint


def _load_api_key(explicit_key: str | None, api_key_path: Path) -> str:
    if explicit_key and explicit_key.strip():
        return explicit_key.strip()
    environment_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if environment_key:
        return environment_key
    try:
        file_key = api_key_path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        file_key = ""
    if file_key:
        return file_key
    raise DeepSeekError("DeepSeek API key is not configured")


def _json_object_content(content: str) -> bool:
    candidate = content.strip()
    if candidate.startswith("```"):
        candidate = candidate.removeprefix("```json").removeprefix("```")
        candidate = candidate.removesuffix("```").strip()
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start < 0 or end < start:
        return False
    try:
        return isinstance(json.loads(candidate[start : end + 1]), dict)
    except json.JSONDecodeError:
        return False


def _run_codex_cli(executable: Path, model: str, prompt: str, timeout_seconds: float) -> str:
    try:
        with tempfile.TemporaryDirectory(prefix="xhs-codex-fallback-") as temporary:
            root = Path(temporary)
            output = root / "response.txt"
            result = subprocess.run(
                [
                    str(executable),
                    "exec",
                    "--ephemeral",
                    "--ignore-user-config",
                    "--ignore-rules",
                    "--skip-git-repo-check",
                    "--sandbox",
                    "read-only",
                    "--model",
                    model,
                    "--color",
                    "never",
                    "--output-last-message",
                    str(output),
                    "-",
                ],
                input=prompt,
                text=True,
                capture_output=True,
                cwd=root,
                timeout=timeout_seconds,
                check=False,
            )
            if result.returncode != 0:
                detail = " ".join(result.stderr.split())[-300:]
                raise CodexCliError(f"Codex CLI exited {result.returncode}: {detail}")
            if not output.is_file():
                raise CodexCliError("Codex CLI returned no final response")
            content = output.read_text(encoding="utf-8").strip()
            if not _json_object_content(content):
                raise CodexCliError("Codex CLI fallback did not return a JSON object")
            return content
    except subprocess.TimeoutExpired as error:
        raise CodexCliError(f"Codex CLI fallback timed out after {timeout_seconds:g}s") from error
    except OSError as error:
        raise CodexCliError(f"Codex CLI fallback could not start: {error}") from error


class CodexCliProvider:
    """Last-resort JSON completion through the user's local ChatGPT Codex login."""

    def __init__(
        self,
        *,
        executable: str | Path,
        model: str,
        timeout_seconds: float = 60,
        runner: CodexRunner = _run_codex_cli,
    ) -> None:
        self.executable = Path(executable).expanduser().resolve()
        self.model = model.strip()
        self.timeout_seconds = float(timeout_seconds)
        self.runner = runner
        if not self.model:
            raise TypeError("Codex fallback model must be non-empty")
        if self.timeout_seconds <= 0:
            raise ValueError("Codex fallback timeout must be positive")

    async def check_configuration(self) -> bool:
        if not self.executable.is_file() or not os.access(self.executable, os.X_OK):
            raise CodexCliError(f"Codex executable is unavailable: {self.executable}")
        return True

    async def complete(self, messages: Sequence[Mapping[str, Any]], *, model: str) -> str:
        del model
        prompt = (
            "Act only as a stateless JSON completion backend. "
            "Do not use tools, browse, read files, "
            "or explain your answer. Follow the ordered chat messages below and return only the "
            "assistant JSON object requested by them.\n\n"
            + json.dumps(list(messages), ensure_ascii=False, separators=(",", ":"))
        )
        return await asyncio.wait_for(
            asyncio.to_thread(
                self.runner,
                self.executable,
                self.model,
                prompt,
                self.timeout_seconds,
            ),
            timeout=self.timeout_seconds + 2,
        )


class FailoverProvider:
    """Use DeepSeek first and fail over only after its own retry budget is exhausted."""

    def __init__(
        self,
        primary: ChatCompletionProvider,
        fallback: ChatCompletionProvider | None,
    ) -> None:
        self.primary = primary
        self.fallback = fallback
        self.log = logging.getLogger(__name__)

    async def check_configuration(self) -> bool:
        await self.primary.check_configuration()
        if self.fallback is not None:
            await self.fallback.check_configuration()
        return True

    async def complete(self, messages: Sequence[Mapping[str, Any]], *, model: str) -> str:
        try:
            content = await self.primary.complete(messages, model=model)
            if _json_object_content(content):
                return content
            raise DeepSeekResponseError("DeepSeek completion content is not a JSON object")
        except DeepSeekError as error:
            if self.fallback is None or error.error_class is ErrorClass.TRANSIENT_NETWORK:
                raise
            self.log.warning(
                "DeepSeek exhausted; using Codex CLI fallback",
                extra={"context": {"error_class": type(error).__name__}},
            )
            return await self.fallback.complete(messages, model=model)


class DeepSeekProvider:
    """Provider-specific HTTP boundary used by content processors."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        api_key_path: Path = DEFAULT_API_KEY_PATH,
        endpoint: str = DEFAULT_ENDPOINT,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        attempts: int = DEFAULT_ATTEMPTS,
        retry_base_delay_seconds: float = DEFAULT_RETRY_BASE_DELAY_SECONDS,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        thinking: str = os.environ.get("DEEPSEEK_THINKING", "disabled"),
        request: Request = default_request,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if not isinstance(attempts, int) or isinstance(attempts, bool) or attempts < 1:
            raise ValueError("attempts must be >= 1")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if retry_base_delay_seconds <= 0:
            raise ValueError("retry_base_delay_seconds must be positive")
        if not isinstance(max_tokens, int) or isinstance(max_tokens, bool) or max_tokens < 1:
            raise ValueError("max_tokens must be a positive integer")
        if thinking not in {"enabled", "disabled"}:
            raise ValueError("thinking must be 'enabled' or 'disabled'")
        if not callable(request):
            raise TypeError("request must be callable")
        self.api_key = api_key
        self.api_key_path = Path(api_key_path)
        self.endpoint = _validate_endpoint(endpoint)
        self.timeout_seconds = float(timeout_seconds)
        self.attempts = attempts
        self.retry_base_delay_seconds = float(retry_base_delay_seconds)
        self.max_tokens = max_tokens
        self.thinking = thinking
        self.request = request
        self.sleep = sleep

    async def check_configuration(self) -> bool:
        """Prove a key is available without making a remote request."""

        _load_api_key(self.api_key, self.api_key_path)
        return True

    async def complete(self, messages: Sequence[Mapping[str, Any]], *, model: str) -> str:
        if not isinstance(model, str) or not model.strip():
            raise TypeError("model must be non-empty")
        api_key = _load_api_key(self.api_key, self.api_key_path)
        last_error: BaseException | None = None
        for attempt in range(1, self.attempts + 1):
            try:
                response = await self.request(
                    self.endpoint,
                    {
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {api_key}",
                    },
                    {
                        "model": model,
                        "max_tokens": self.max_tokens,
                        "thinking": {"type": self.thinking},
                        "response_format": {"type": "json_object"},
                        "messages": list(messages),
                    },
                    self.timeout_seconds,
                )
                if response.status < 200 or response.status >= 300:
                    detail = " ".join(response.body.split())[:200]
                    retryable = response.status in {408, 429} or response.status >= 500
                    raise DeepSeekHttpError(
                        f"DeepSeek HTTP {response.status}: {detail}",
                        status=response.status,
                        retryable=retryable,
                    )
                try:
                    body = json.loads(response.body)
                except json.JSONDecodeError as error:
                    raise DeepSeekResponseError(
                        "DeepSeek returned invalid response JSON"
                    ) from error
                choices = body.get("choices") if isinstance(body, dict) else None
                choice = choices[0] if isinstance(choices, list) and choices else None
                if not isinstance(choice, dict):
                    raise DeepSeekResponseError("DeepSeek returned no choices")
                if choice.get("finish_reason") == "length":
                    raise DeepSeekResponseError("DeepSeek response exhausted its token budget")
                message = choice.get("message")
                return str(message.get("content") or "") if isinstance(message, dict) else ""
            except BaseException as error:
                if isinstance(error, (KeyboardInterrupt, SystemExit, asyncio.CancelledError)):
                    raise
                if isinstance(error, DeepSeekTransportError):
                    # The durable worker owns outage retries; do not sleep inside a request.
                    raise
                last_error = error
                retryable = not isinstance(error, DeepSeekHttpError) or error.retryable
                if attempt < self.attempts and retryable:
                    await self.sleep(self.retry_base_delay_seconds * attempt)
                    continue
                break
        assert last_error is not None
        raise last_error
