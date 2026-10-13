"""Async project adapter over the standalone stable Safari publisher."""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from typing import Any

from xhs_local.core.contracts import PublishNote, PublishResult

from .backend import SafariAppleScriptBackend
from .errors import (
    PublishPreflightError,
    SafariAutomationError,
    SubmissionRejectedError,
    SubmissionUncertainError,
)
from .models import BackendPublishRequest


class SafariPublishError(RuntimeError):
    def __init__(
        self,
        stage: str,
        cause: BaseException,
        *,
        submission_started: bool,
        code: str | None = None,
    ) -> None:
        super().__init__(f"{stage}: {cause}")
        self.stage = stage
        self.cause = cause
        self.submission_started = submission_started
        self.code = code


class SafariSession:
    """Shared account lock and compatibility settings for composition."""

    def __init__(
        self,
        *,
        background: bool = True,
        persistent: bool = True,
        state_path: Path | None = None,
    ) -> None:
        self.background = background
        self.persistent = persistent
        self.state_path = state_path
        self.lock = asyncio.Lock()
        self.backend = SafariAppleScriptBackend()

    async def close(self) -> None:
        with suppress(SafariAutomationError):
            await asyncio.to_thread(self.backend.close)


def _rejection_code(error: SubmissionRejectedError) -> str:
    detail = str(error)
    if "今日发布" in detail or "发布次数已达上限" in detail:
        return "XHS_DAILY_LIMIT"
    if "操作频繁" in detail or "461" in detail:
        return "XHS_ANTI_BOT"
    return "XHS_REMOTE_REJECTED"


class SafariPublisher:
    """Publish through the stable component-event Safari backend."""

    def __init__(
        self,
        *,
        max_images: int,
        keep_window_open: bool = False,
        background: bool = True,
        report: Callable[[str], None] | None = None,
        session: SafariSession | None = None,
    ) -> None:
        if not isinstance(max_images, int) or max_images < 1 or max_images > 18:
            raise TypeError("max_images must be an integer from 1 to 18")
        self.max_images = max_images
        self.keep_window_open = keep_window_open
        self.background = background
        self.report = report or (lambda _message: None)
        self.session = session or SafariSession(background=background)

    def _request(
        self,
        note: PublishNote,
        *,
        require_new_title_occurrence: bool,
    ) -> BackendPublishRequest:
        request = BackendPublishRequest(
            title=note.title.strip(),
            body=" ".join(note.body.split()) if sys.platform == "linux" else note.body.strip(),
            image_paths=tuple(Path(path).expanduser().resolve() for path in note.images),
            topics=note.topics,
            allow_empty_text=note.allow_empty_text,
            require_new_title_occurrence=require_new_title_occurrence,
            max_images=self.max_images,
        )
        request.validate()
        return request

    async def publish(
        self,
        note: PublishNote,
        *,
        require_new_title_occurrence: bool = False,
    ) -> PublishResult:
        if not isinstance(require_new_title_occurrence, bool):
            raise TypeError("require_new_title_occurrence must be a boolean")
        try:
            request = self._request(
                note,
                require_new_title_occurrence=require_new_title_occurrence,
            )
        except PublishPreflightError as error:
            raise SafariPublishError(
                "validate note",
                error,
                submission_started=False,
            ) from error
        self.report("Publishing through Safari")
        async with self.session.lock:
            try:
                result = await asyncio.shield(
                    asyncio.to_thread(self.session.backend.publish, request)
                )
            except SubmissionRejectedError as error:
                raise SafariPublishError(
                    "submit note",
                    error,
                    submission_started=True,
                    code=_rejection_code(error),
                ) from error
            except SubmissionUncertainError as error:
                raise SafariPublishError(
                    "confirm note",
                    error,
                    submission_started=True,
                ) from error
            except SafariAutomationError as error:
                with suppress(SafariAutomationError):
                    await asyncio.to_thread(self.session.backend.close)
                raise SafariPublishError(
                    "prepare note",
                    error,
                    submission_started=False,
                ) from error
        return PublishResult(
            ok=True,
            confirmed_in_note_manager=True,
            submission_started=True,
            detail={
                "backend": "applescript-component-event",
                "page_url": result.page_url,
                "message": result.message,
                "excerpt": result.excerpt,
            },
        )

    async def probe_submission(self, *, title: str, body: str, created_at: str) -> dict[str, Any]:
        async with self.session.lock:
            try:
                return await asyncio.to_thread(
                    self.session.backend.probe_submission,
                    title=title,
                    body=body,
                    created_at=created_at,
                )
            finally:
                await asyncio.to_thread(self.session.backend.close)

    async def recover_confirmation(
        self,
        title: str,
        *,
        minimum_total: int | None,
    ) -> dict[str, Any]:
        async with self.session.lock:
            return await asyncio.to_thread(
                self.session.backend.recover_confirmation,
                title,
                minimum_total=minimum_total,
            )

    async def preflight(self) -> dict[str, Any]:
        async with self.session.lock:
            try:
                return await asyncio.to_thread(self.session.backend.preflight)
            except (PublishPreflightError, SafariAutomationError) as error:
                with suppress(SafariAutomationError):
                    await asyncio.to_thread(self.session.backend.close)
                raise SafariPublishError(
                    "preflight",
                    error,
                    submission_started=False,
                ) from error

    async def close(self) -> None:
        await self.session.close()
