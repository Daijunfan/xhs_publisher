"""Metadata-only discovery: durable video jobs own all expensive processing."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

from xhs_local.core.contracts import CollectBatch, SourceRecord
from xhs_local.core.identifiers import stable_record_id
from xhs_local.core.states import WorkTopic
from xhs_local.plugins.contracts import (
    CollectRequest,
    HealthReport,
    PluginContractError,
    PluginTarget,
    SourcePluginContext,
)

from .client import VideoClient, channel_avatar, video_entries


class VideoSourcePlugin:
    platform: str

    def __init__(self, context: SourcePluginContext, *, client: VideoClient | None = None) -> None:
        self.context = context
        self.client = client or VideoClient(cookie_file=context.options.get("cookie_file"))

    @classmethod
    def validate_target(cls, target: PluginTarget) -> None:
        parsed = urlsplit(target.locator)
        host = parsed.netloc.lower()
        allowed = {"youtube.com", "www.youtube.com"}
        if host not in allowed or not target.id or not target.name:
            raise PluginContractError(
                "video target must be a creator homepage on its configured platform"
            )
        pattern = r"/(?:@[\w.-]+|channel/UC[\w-]+|(?:c/|user/)?[\w.-]+)/?"
        if not re.fullmatch(pattern, parsed.path) or parsed.path.rstrip("/") in {
            "/watch",
            "/playlist",
            "/shorts",
            "/live",
            "/feed",
        }:
            raise PluginContractError(
                "video targets must be creator homepages, not individual videos"
            )

    async def healthcheck(
        self, target: PluginTarget, deadline: float | None = None
    ) -> HealthReport:
        self.validate_target(target)
        return HealthReport(
            ok=True, message="configuration valid; network checked during discovery"
        )

    async def collect(self, request: CollectRequest) -> CollectBatch:
        self.validate_target(request.target)
        request.ensure_active()
        if request.source_id != self.context.source_id:
            raise PluginContractError("video source context mismatch")
        activation = request.checkpoint.get("activated_at")
        if not activation:
            raise PluginContractError(
                "video discovery requires a persisted first-activation timestamp"
            )
        activated_at = datetime.fromisoformat(activation).astimezone(UTC)
        cursor = datetime.fromisoformat(request.checkpoint.get("last_polled_at", activation))
        scan_from = max(activated_at, cursor - timedelta(days=1))
        info = await self.client.discover(request.target.locator, scan_from)
        avatar = channel_avatar(info)
        records = []
        errors = 0
        seen = set(request.checkpoint.get("seen_video_ids", []))
        pending = []
        attempted = set()
        entries = [*request.checkpoint.get("pending_metadata", []), *video_entries(info)]
        for entry in entries:
            request.ensure_active()
            video_id = str(entry["id"])
            if video_id in seen or video_id in attempted:
                continue
            attempted.add(video_id)
            if entry.get("live_status") in {"is_live", "is_upcoming"}:
                pending.append(entry)
                continue
            timestamp = entry.get("timestamp")
            if timestamp and timestamp < (activated_at - timedelta(days=7)).timestamp():
                continue
            url = f"https://www.youtube.com/watch?v={video_id}"
            try:
                metadata = entry.get("video_metadata")
                if not metadata or not isinstance(
                    metadata.get("release_timestamp") or metadata.get("timestamp"), (int, float)
                ):
                    metadata = await self.client.metadata(url)
                published = metadata.get("release_timestamp") or metadata.get("timestamp")
                if not isinstance(published, (int, float)):
                    raise ValueError("missing publication timestamp")
                if metadata.get("live_status") in {"is_live", "is_upcoming", "post_live"}:
                    pending.append(entry)
                    continue
                seen.add(video_id)
                if published < activated_at.timestamp():
                    continue
                metadata = {
                    key: metadata.get(key)
                    for key in (
                        "id",
                        "title",
                        "timestamp",
                        "release_timestamp",
                        "duration",
                        "webpage_url",
                        "uploader",
                        "uploader_id",
                        "thumbnail",
                        "live_status",
                    )
                }
            except Exception as error:
                errors += 1
                pending.append(entry)
                self.context.log(
                    "video_metadata_failed",
                    {
                        "target_id": request.target.id,
                        "video_id": video_id,
                        "error_class": type(error).__name__,
                    },
                )
                continue
            records.append(
                SourceRecord(
                    record_id=stable_record_id(self.platform, self.platform, video_id),
                    source_id=request.source_id,
                    target_id=request.target.id,
                    plugin_id=self.platform,
                    external_id=video_id,
                    content_type="video_pending",
                    occurred_at=request.observed_at,
                    observed_at=request.observed_at,
                    title=entry.get("title") or video_id,
                    text="",
                    source_name=entry.get("uploader")
                    or info.get("uploader")
                    or request.target.name,
                    source_url=url,
                    payload={
                        "activated_at": activation,
                        "creator_url": request.target.locator,
                        "creator_id": entry.get("channel_id")
                        or entry.get("uploader_id")
                        or info.get("channel_id")
                        or request.target.name,
                        "avatar_url": avatar,
                        **({"video_metadata": metadata} if metadata else {}),
                    },
                )
            )
            seen.add(video_id)
        return CollectBatch(
            source_id=request.source_id,
            target_id=request.target.id,
            records=tuple(records),
            checkpoint={
                "activated_at": activation,
                "seen_video_ids": sorted(seen),
                "last_polled_at": request.observed_at.isoformat(),
                "pending_metadata": pending,
            },
            messages_seen=len(records),
            errors=errors,
            work_topic=WorkTopic.VIDEO_PREPARE,
            preserve_existing=True,
        )

    async def close(self) -> None:
        return None
