from __future__ import annotations

import asyncio
import json
import urllib.error
from pathlib import Path

import pytest

from xhs_local.core.errors import ErrorClass, PipelineError
from xhs_local.processing import (
    CodexCliProvider,
    DeepSeekHttpError,
    DeepSeekProvider,
    DeepSeekTransportError,
    FailoverProvider,
)
from xhs_local.processing.provider import HttpResponse, default_request


def completion(content: str = "{}") -> HttpResponse:
    return HttpResponse(
        200,
        json.dumps({"choices": [{"finish_reason": "stop", "message": {"content": content}}]}),
    )


def test_provider_sends_non_thinking_json_request_and_retries_server_errors() -> None:
    calls: list[dict[str, object]] = []
    sleeps: list[float] = []

    async def request(
        _endpoint: str,
        headers: object,
        payload: dict[str, object],
        timeout: float,
    ) -> HttpResponse:
        assert "Bearer test-key" in str(headers)
        assert timeout == 12
        calls.append(payload)
        return HttpResponse(503, "unavailable") if len(calls) == 1 else completion("done")

    async def sleep(seconds: float) -> None:
        sleeps.append(seconds)

    provider = DeepSeekProvider(
        api_key="test-key",
        attempts=2,
        timeout_seconds=12,
        request=request,  # type: ignore[arg-type]
        sleep=sleep,
    )
    result = asyncio.run(
        provider.complete([{"role": "user", "content": "hello"}], model="deepseek-v4-flash")
    )
    assert result == "done"
    assert sleeps == [2]
    assert len(calls) == 2
    assert calls[0]["thinking"] == {"type": "disabled"}
    assert calls[0]["response_format"] == {"type": "json_object"}
    assert calls[0]["max_tokens"] == 6_000


def test_provider_does_not_retry_authentication_failure() -> None:
    calls = 0

    async def request(*_args: object) -> HttpResponse:
        nonlocal calls
        calls += 1
        return HttpResponse(401, "unauthorized")

    provider = DeepSeekProvider(api_key="bad-key", attempts=3, request=request)  # type: ignore[arg-type]
    with pytest.raises(DeepSeekHttpError, match="HTTP 401") as failure:
        asyncio.run(provider.complete([], model="deepseek-v4-flash"))
    assert failure.value.retryable is False
    assert calls == 1


def test_provider_rejects_token_exhaustion() -> None:
    async def request(*_args: object) -> HttpResponse:
        return HttpResponse(
            200,
            json.dumps({"choices": [{"finish_reason": "length", "message": {}}]}),
        )

    provider = DeepSeekProvider(api_key="key", attempts=1, request=request)  # type: ignore[arg-type]
    with pytest.raises(Exception, match="token budget"):
        asyncio.run(provider.complete([], model="deepseek-v4-flash"))


def test_network_failure_is_a_retryable_pipeline_error(monkeypatch) -> None:
    def fail(*_args: object, **_kwargs: object) -> None:
        raise urllib.error.URLError("TLS connection closed")

    class FailingOpener:
        open = staticmethod(fail)

    monkeypatch.setattr("urllib.request.urlopen", fail)
    monkeypatch.setattr(
        "urllib.request.build_opener",
        lambda *_args: FailingOpener(),
    )
    with pytest.raises(DeepSeekTransportError) as failure:
        asyncio.run(default_request("https://example.test", {}, {}, 1))

    assert isinstance(failure.value, PipelineError)
    assert failure.value.retryable is True
    assert failure.value.error_class is ErrorClass.TRANSIENT_NETWORK


def test_network_failure_falls_back_to_a_direct_connection(monkeypatch) -> None:
    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        @staticmethod
        def read() -> bytes:
            return b'{"ok":true}'

    class DirectOpener:
        @staticmethod
        def open(*_args: object, **_kwargs: object) -> Response:
            return Response()

    class RoutedOpener:
        @staticmethod
        def open(*_args: object, **_kwargs: object) -> Response:
            raise urllib.error.URLError("Tunnel connection failed: 503 Service Unavailable")

    def fail_proxy(*_args: object, **_kwargs: object) -> None:
        raise urllib.error.URLError("Tunnel connection failed: 503 Service Unavailable")

    monkeypatch.setattr("urllib.request.urlopen", fail_proxy)
    monkeypatch.setattr(
        "urllib.request.build_opener",
        lambda *handlers: DirectOpener() if handlers else RoutedOpener(),
    )

    response = asyncio.run(default_request("https://example.test", {}, {}, 1))
    assert response == HttpResponse(200, '{"ok":true}')


@pytest.mark.parametrize("client", ["deepseek", "x"])
def test_requests_refresh_proxy_settings_in_the_same_process(monkeypatch, client) -> None:
    from xhs_local.plugins.sources.x.client import public_request

    settings = {"https": "http://127.0.0.1:1082"}
    seen = []
    monkeypatch.setattr("urllib.request.getproxies", lambda: dict(settings))

    class Response:
        status = 200
        headers = {"Content-Type": "application/json"}

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def read(self, *_args):
            return b"{}"

    def build(*_handlers):
        proxy = urllib.request.ProxyHandler().proxies["https"]

        class Opener:
            def open(self, *_args, **_kwargs):
                seen.append(proxy)
                return Response()

        return Opener()

    monkeypatch.setattr("urllib.request.build_opener", build)
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *_args, **_kwargs: pytest.fail("must not reuse the cached global opener"),
    )
    for port in (1082, 7890):
        settings["https"] = f"http://127.0.0.1:{port}"
        if client == "deepseek":
            asyncio.run(default_request("https://example.test", {}, {}, 1))
        else:
            public_request("https://example.test", 1, 1024)
    assert seen == ["http://127.0.0.1:1082", "http://127.0.0.1:7890"]




def test_codex_cli_provider_uses_isolated_json_prompt() -> None:
    captured = {}

    def runner(executable: Path, model: str, prompt: str, timeout: float) -> str:
        captured.update(
            executable=executable,
            model=model,
            prompt=prompt,
            timeout=timeout,
        )
        return '{"approved":[1]}'

    provider = CodexCliProvider(
        executable="/opt/local/bin/codex",
        model="gpt-test",
        timeout_seconds=15,
        runner=runner,
    )
    result = asyncio.run(
        provider.complete(
            [{"role": "system", "content": "review"}, {"role": "user", "content": "item"}],
            model="deepseek-ignored",
        )
    )

    assert result == '{"approved":[1]}'
    assert captured["model"] == "gpt-test"
    assert captured["timeout"] == 15
    assert '"role":"system"' in str(captured["prompt"])
    assert "Do not use tools" in str(captured["prompt"])


def test_failover_provider_uses_codex_for_invalid_deepseek_content() -> None:
    class Primary:
        async def check_configuration(self) -> bool:
            return True

        async def complete(self, _messages, *, model: str) -> str:
            del model
            return "not json"

    class Fallback:
        calls = 0

        async def check_configuration(self) -> bool:
            return True

        async def complete(self, _messages, *, model: str) -> str:
            del model
            self.calls += 1
            return '{"approved":[1]}'

    fallback = Fallback()
    provider = FailoverProvider(Primary(), fallback)  # type: ignore[arg-type]
    result = asyncio.run(provider.complete([], model="deepseek-v4-flash"))

    assert result == '{"approved":[1]}'
    assert fallback.calls == 1


def test_failover_provider_defers_immediately_on_transient_network_failure() -> None:
    class Primary:
        async def check_configuration(self) -> bool:
            return True

        async def complete(self, _messages, *, model: str) -> str:
            del model
            raise DeepSeekTransportError("offline")

    class Fallback:
        calls = 0

        async def check_configuration(self) -> bool:
            return True

        async def complete(self, _messages, *, model: str) -> str:
            del model
            self.calls += 1
            return '{"approved":[1]}'

    fallback = Fallback()
    provider = FailoverProvider(Primary(), fallback)  # type: ignore[arg-type]
    with pytest.raises(DeepSeekTransportError, match="offline"):
        asyncio.run(provider.complete([], model="deepseek-v4-flash"))
    assert fallback.calls == 0
