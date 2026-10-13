"""Bounded, checkpoint-driven Telegram SourcePlugin."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import os
import re
from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from xhs_local.core.contracts import CollectBatch
from xhs_local.core.errors import AuthenticationRequired
from xhs_local.plugins.contracts import (
    CollectRequest,
    HealthReport,
    PluginContractError,
    PluginTarget,
    SourcePluginContext,
)

from .client import ClientFactory, TelegramTransport
from .mapper import document_message, is_eligible_message, map_message

HANDLE_PATTERN = re.compile(r"^[A-Za-z0-9_]{5,}$")


class TelegramSourcePlugin:
    """Collect one configured Telegram channel per call."""

    def __init__(
        self,
        context: SourcePluginContext,
        *,
        client_factory: ClientFactory | None = None,
        peer_id_factory=None,
        environment: Mapping[str, str] = os.environ,
    ) -> None:
        self.context = context
        options = context.options
        api_id = environment.get("USER_API_ID", options["api_id"])
        api_hash = environment.get("USER_API_HASH", options["api_hash"])
        dependencies: dict[str, Any] = {}
        if client_factory is not None:
            dependencies["client_factory"] = client_factory
        if peer_id_factory is not None:
            dependencies["peer_id_factory"] = peer_id_factory
        self.default_post_limit = int(options["default_post_limit"])
        self.lookback_hours = float(options.get("lookback_hours", 24))
        self.transport = TelegramTransport(
            session_path=options["session_path"],
            api_id=api_id,
            api_hash=api_hash,
            max_image_bytes=int(options["max_image_bytes"]),
            fetch_timeout_seconds=float(options["fetch_timeout_seconds"]),
            media_timeout_seconds=float(options["media_timeout_seconds"]),
            **dependencies,
        )

    @classmethod
    def validate_target(cls, target: PluginTarget) -> None:
        if not target.id.strip() or not target.name.strip():
            raise PluginContractError("Telegram target id/name must be non-empty")
        locator = target.locator.removeprefix("@").strip()
        if not HANDLE_PATTERN.fullmatch(locator):
            raise PluginContractError(
                f"Telegram target {target.id} locator must be a public channel handle"
            )
        unknown = set(target.options) - {
            "max_items",
            "collect_documents",
            "lookback_hours",
            "max_documents",
            "collect_timeout_seconds",
        }
        if unknown:
            raise PluginContractError(
                f"Telegram target {target.id} has unknown options: {', '.join(sorted(unknown))}"
            )
        max_items = target.options.get("max_items")
        if max_items is not None and (
            isinstance(max_items, bool) or not isinstance(max_items, int) or max_items < 1
        ):
            raise PluginContractError(f"Telegram target {target.id} max_items must be positive")

    async def healthcheck(
        self, target: PluginTarget, deadline: float | None = None
    ) -> HealthReport:
        self.validate_target(target)
        channel_id = await self.transport.healthcheck(target, deadline)
        return HealthReport(
            ok=True,
            detail={"target_id": target.id, "channel_id": channel_id},
        )

    @staticmethod
    def _checkpoint(request: CollectRequest) -> int | None:
        locator = request.checkpoint.get("locator")
        normalized_locator = request.target.locator.removeprefix("@").casefold()
        if locator is not None and str(locator).casefold() != normalized_locator:
            raise PluginContractError(
                f"checkpoint for {request.target.id} belongs to another locator"
            )
        value = request.checkpoint.get("max_message_id")
        if value is None:
            return None
        if isinstance(value, bool):
            raise PluginContractError("Telegram checkpoint max_message_id is invalid")
        try:
            result = int(value)
        except (TypeError, ValueError) as error:
            raise PluginContractError("Telegram checkpoint max_message_id is invalid") from error
        if result < 1:
            raise PluginContractError("Telegram checkpoint max_message_id is invalid")
        return result

    async def collect(self, request: CollectRequest) -> CollectBatch:
        if request.source_id != self.context.source_id:
            raise PluginContractError("CollectRequest source_id does not match plugin context")
        self.validate_target(request.target)
        request.ensure_active()
        previous_id = self._checkpoint(request)
        limit = int(request.target.options.get("max_items", self.default_post_limit))
        channel_id, messages = await self.transport.fetch_messages(
            request.target,
            min_message_id=previous_id,
            limit=limit,
            deadline=request.deadline,
            cancellation=request.cancellation,
        )
        observed_at = request.observed_at
        if observed_at.tzinfo is None:
            raise PluginContractError("CollectRequest observed_at must include timezone")
        observed_at = observed_at.astimezone(UTC)
        documents = bool(request.target.options.get("collect_documents", False))
        cutoff = observed_at - timedelta(
            hours=float(request.target.options.get("lookback_hours", self.lookback_hours))
        )
        details = {}
        if documents:
            try:
                details = await self.transport.channel_details(
                    request.target, deadline=request.deadline
                )
            except Exception:
                self.context.log("telegram_channel_details_error", {"target_id": request.target.id})
        eligible = []
        for message in messages:
            occurred_at = getattr(message, "date", None)
            if not isinstance(occurred_at, datetime):
                continue
            if occurred_at.tzinfo is None:
                occurred_at = occurred_at.replace(tzinfo=UTC)
            if cutoff <= occurred_at.astimezone(UTC) <= observed_at and is_eligible_message(
                message, documents=documents
            ):
                eligible.append(message)
        records = []
        errors = 0
        if documents:
            eligible.sort(key=lambda message: int(message.id))
        handled_id = previous_id
        document_count = 0
        for message in eligible:
            request.cancellation.raise_if_cancelled()
            media = None
            thumbnail = None
            try:
                if documents and document_message(message):
                    if document_count >= int(request.target.options.get("max_documents", 1)):
                        break
                    media = await self.transport.download_document(
                        message,
                        channel_id=channel_id,
                        directory=self.context.runtime_root / "cache" / "source_media",
                        deadline=request.deadline,
                        cancellation=request.cancellation,
                    )
                    document_count += 1
                    try:
                        thumbnail = await self.transport.document_preview(
                            message,
                            channel_id=channel_id,
                            deadline=request.deadline,
                            cancellation=request.cancellation,
                            document=media.data if isinstance(media.data, Path) else None,
                        )
                    except Exception:
                        self.context.log(
                            "telegram_document_preview_error",
                            {"target_id": request.target.id, "message_id": int(message.id)},
                        )
                else:
                    media = await self.transport.download_image(
                        message,
                        channel_id=channel_id,
                        deadline=request.deadline,
                        cancellation=request.cancellation,
                    )
            except asyncio.CancelledError:
                raise
            except AuthenticationRequired:
                raise
            except Exception as error:  # media failure must not discard the text record
                errors += 1
                self.context.log(
                    "telegram_media_error",
                    {
                        "source_id": request.source_id,
                        "target_id": request.target.id,
                        "message_id": int(message.id),
                        "error": " ".join(str(error).split())[:300],
                    },
                )
                if documents and document_message(message):
                    break
            handled_id = int(message.id)
            records.append(
                map_message(
                    message,
                    source_id=request.source_id,
                    target=request.target,
                    channel_id=channel_id,
                    observed_at=request.observed_at,
                    media=media,
                    thumbnail=thumbnail,
                )
            )
        if details:
            records = [
                replace(
                    record,
                    payload={
                        **record.payload,
                        "publication_metadata": {
                            **record.payload.get("publication_metadata", {}),
                            "telegram": {
                                **record.payload.get("publication_metadata", {}).get(
                                    "telegram", {}
                                ),
                                **details,
                            },
                        },
                    },
                )
                for record in records
            ]
        records.sort(key=lambda record: (record.occurred_at, int(record.external_id)))
        max_id = max(
            (int(message.id) for message in messages if int(message.id) > 0),
            default=previous_id,
        )
        if documents:
            max_id = handled_id if eligible else max_id
        checkpoint = dict(request.checkpoint)
        checkpoint.update(
            {
                "locator": request.target.locator.removeprefix("@").casefold(),
                "channel_id": channel_id,
                "max_message_id": max_id,
            }
        )
        if max_id is None:
            checkpoint.pop("max_message_id", None)
        # Identity metadata lives in the source checkpoint, independently of news retention.
        previous_avatar = checkpoint.get("channel_avatar") or {}
        try:
            photo_id, data = await self.transport.channel_avatar(
                request.target,
                known_photo_id=previous_avatar.get("photo_id")
                if previous_avatar.get("data")
                else None,
                deadline=request.deadline,
                cancellation=request.cancellation,
            )
            checked_at = observed_at.isoformat()
            if photo_id is None:
                checkpoint["channel_avatar"] = {"photo_id": None, "checked_at": checked_at}
            elif data is None:
                checkpoint["channel_avatar"] = {**previous_avatar, "checked_at": checked_at}
            else:
                checkpoint["channel_avatar"] = {
                    "photo_id": photo_id,
                    "checked_at": checked_at,
                    "name": "channel-avatar.jpg",
                    "mime_type": "image/jpeg",
                    "data": base64.b64encode(data).decode("ascii"),
                    "sha256": hashlib.sha256(data).hexdigest(),
                }
        except asyncio.CancelledError:
            raise
        except Exception as error:
            errors += 1
            self.context.log(
                "telegram_avatar_error",
                {
                    "source_id": request.source_id,
                    "target_id": request.target.id,
                    "error": type(error).__name__,
                },
            )
        return CollectBatch(
            source_id=request.source_id,
            target_id=request.target.id,
            records=tuple(records),
            checkpoint=checkpoint,
            messages_seen=len(messages),
            errors=errors,
        )

    async def close(self) -> None:
        await self.transport.close()
