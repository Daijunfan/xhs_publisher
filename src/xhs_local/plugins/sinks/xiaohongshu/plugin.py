"""Xiaohongshu SinkPlugin facade over the Mac Safari publisher."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from xhs_local.core.contracts import PublishNote, PublishResult
from xhs_local.plugins.contracts import HealthReport

from .browser import SafariPublisher


class XiaohongshuSinkPlugin:
    def __init__(self, publisher: SafariPublisher) -> None:
        self.publisher = publisher

    async def preflight(self) -> HealthReport:
        result = await self.publisher.preflight()
        return HealthReport(ok=bool(result.get("ok")), detail=result)

    async def publish(
        self,
        note: PublishNote,
        *,
        require_new_title_occurrence: bool = False,
    ) -> PublishResult:
        return await self.publisher.publish(
            note,
            require_new_title_occurrence=require_new_title_occurrence,
        )

    async def reconcile(self, operation: Mapping[str, Any]) -> PublishResult | None:
        title = str(operation.get("title") or "")
        if operation.get("created_at"):
            confirmation = await self.publisher.probe_submission(
                title=title,
                body=str(operation.get("body") or ""),
                created_at=str(operation["created_at"]),
            )
            if confirmation["found"] is None:
                return None
            return PublishResult(
                ok=confirmation["found"],
                confirmed_in_note_manager=confirmation["found"],
                detail={"reconciled": True, **confirmation},
            )
        minimum_total = operation.get("minimum_total")
        confirmation = await self.publisher.recover_confirmation(
            title,
            minimum_total=int(minimum_total) if minimum_total is not None else None,
        )
        return PublishResult(
            ok=bool(confirmation.get("found")),
            confirmed_in_note_manager=bool(confirmation.get("found")),
            submission_started=True,
            detail={"reconciled": True, "excerpt": confirmation.get("excerpt", "")},
        )

    async def close(self) -> None:
        await self.publisher.close()
