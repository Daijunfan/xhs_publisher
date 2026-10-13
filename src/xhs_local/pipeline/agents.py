"""Outbound-only bridge from committed news to an Agents Company Core."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
import re
from collections.abc import Awaitable, Callable
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

import aiohttp

from xhs_local.configuration.loader import ConfigSnapshot
from xhs_local.configuration.models import AgentsTarget
from xhs_local.configuration.subscriptions import source_homepage
from xhs_local.storage.checkpoints import CheckpointRepository
from xhs_local.storage.records import RecordsRepository, StoredRecord

IMAGE_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp"}
MAX_IMAGE_BYTES = 8 * 1024 * 1024
PUBLISH_HOURS = 48
DOCUMENT_HOURS = 7 * 24


class CollectorRequestError(RuntimeError):
    """A failed Core request, with no credentials or response body in its message."""

    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(message)
        self.code = code


class AgentsPublisher:
    def __init__(
        self,
        snapshot: ConfigSnapshot,
        records: RecordsRepository,
        apply_targets: Callable[[list[AgentsTarget]], Awaitable[None]],
        update_status: Callable[..., object],
    ) -> None:
        self.settings = snapshot.app.agents
        self.endpoint = self.settings.endpoint.rstrip("/")
        parsed = urlsplit(self.endpoint)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username:
            raise ValueError("Agents endpoint must be an HTTP(S) URL without credentials")
        self.token_path = snapshot.resolve(self.settings.token_file)
        self.records = records
        self.source_plugins = {source.id: source.plugin for source in snapshot.sources.sources}
        self.checkpoints = CheckpointRepository(records.database)
        self.apply_targets = apply_targets
        self.update_status = update_status
        self.log = logging.getLogger(__name__)
        self.session: aiohttp.ClientSession | None = None
        self.revision: str | int | None = None
        self.targets: dict[tuple[str, str], AgentsTarget] = {}
        self.last_refresh = 0.0
        self.state: dict = {"enabled": True, "connected": False}

    def _status(self, **fields: object) -> None:
        self.state.update(fields)
        self.update_status(agents=dict(self.state))

    async def _call(self, cmd: str, args: dict) -> dict:
        if self.session is None:
            raise RuntimeError("Agents publisher is not started")
        try:
            async with self.session.post(
                self.endpoint + "/api/channels/collector",
                json={"cmd": cmd, "args": args},
                allow_redirects=False,
            ) as response:
                data = await response.json()
                if (
                    response.status != 200
                    or not isinstance(data, dict)
                    or data.get("ok") is not True
                ):
                    code = data.get("code") if isinstance(data, dict) else None
                    if not isinstance(code, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", code):
                        code = None
                    raise CollectorRequestError(
                        f"Core rejected {cmd} (HTTP {response.status})", code
                    )
        except (aiohttp.ClientError, TimeoutError, ValueError) as error:
            raise CollectorRequestError(f"Core request failed: {cmd}") from error
        if not isinstance(data.get("data"), dict):
            raise CollectorRequestError(f"Core returned invalid data for {cmd}")
        return data["data"]

    @staticmethod
    def _targets(values: list) -> list[AgentsTarget]:
        targets = [AgentsTarget.model_validate(value) for value in values]
        if len({(t.plugin, t.targetId) for t in targets}) != len(targets) or len(
            {t.sourceId for t in targets}
        ) != len(targets):
            raise ValueError("Core returned duplicate subscription identities")
        return targets

    async def start(self) -> None:
        token = self.token_path.read_text().strip()
        if not token:
            raise ValueError("Agents collector token file is empty")
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=20),
            headers={"Authorization": "Bearer " + token},
        )
        try:
            await self.refresh_config(force=True)
        except (CollectorRequestError, ValueError):
            saved = self.checkpoints.get("agents-company", "config")
            if not saved or saved.get("endpoint") != self.endpoint:
                raise
            targets = self._targets(saved["targets"])
            await self.apply_targets(targets)
            self.targets = {(t.plugin, t.targetId): t for t in targets}
            self.revision = saved["revision"]
            self._status(
                connected=False,
                revision=self.revision,
                error="Core unavailable; using the last confirmed subscription configuration",
            )
            self.log.warning("Using last confirmed Agents subscriptions while Core is unavailable")

    async def refresh_config(self, *, force: bool = False) -> None:
        args = {"sinceRevision": self.revision} if self.revision is not None and not force else {}
        data = await self._call("channel.collector-config", args)
        if not isinstance(data.get("revision"), (str, int)) or not isinstance(
            data.get("changed"), bool
        ):
            raise ValueError("Core returned an invalid subscription revision")
        if data["changed"]:
            if not isinstance(data.get("targets"), list):
                raise ValueError("Core returned invalid subscriptions")
            targets = self._targets(data["targets"])
            await self.apply_targets(targets)
            self.checkpoints.put(
                "agents-company",
                "config",
                {
                    "endpoint": self.endpoint,
                    "revision": data["revision"],
                    "targets": [t.model_dump(mode="json") for t in targets],
                },
            )
            self.targets = {(t.plugin, t.targetId): t for t in targets}
        elif self.revision is None:
            raise ValueError("Core omitted the initial subscription configuration")
        self.revision = data["revision"]
        self.last_refresh = asyncio.get_running_loop().time()
        self._status(connected=True, revision=self.revision, error=None)

    async def _publish(self, stored: StoredRecord, target: AgentsTarget) -> str:
        record = stored.record
        published_at = int(record.occurred_at.timestamp() * 1000)
        base = {
            "sourceId": target.sourceId,
            "externalId": record.external_id,
            "publishedAt": published_at,
        }
        media_ids = []
        files = []
        avatar_id = None
        thumbnail_id = None
        avatar_index = record.payload.get("avatar_attachment_index")
        for attachment in stored.attachments:
            if attachment.mime_type not in IMAGE_TYPES:
                if not target.collectFiles:
                    continue
                document = self.records.media.resolve(attachment.relative_path)
                if not document.is_file():
                    raise CollectorRequestError("Collected cloud document is unavailable")
                files.append(
                    {
                        "id": f"file-{attachment.index}",
                        "name": attachment.file_name,
                        "mimeType": attachment.mime_type,
                        "bytes": attachment.byte_size,
                        "sha256": attachment.sha256,
                    }
                )
                continue
            if attachment.byte_size > MAX_IMAGE_BYTES:
                self.log.warning("Skipping oversized collected image")
                continue
            path = self.records.media.resolve(attachment.relative_path)
            try:
                data = await asyncio.to_thread(path.read_bytes)
            except FileNotFoundError:
                self.log.warning("Collected image no longer exists; publishing available content")
                continue
            if len(data) > MAX_IMAGE_BYTES:
                self.log.warning("Skipping oversized collected image")
                continue
            avatar = attachment.index == avatar_index
            try:
                result = await self._call(
                    "channel.media-put",
                    {
                        **base,
                        "mediaKey": ("avatar" if avatar else f"image-{attachment.index}")
                        + "-"
                        + attachment.sha256,
                        "name": attachment.file_name,
                        "mimeType": attachment.mime_type,
                        "data": base64.b64encode(data).decode("ascii"),
                    },
                )
            except CollectorRequestError as error:
                if error.code not in {"POST_DELETED", "POST_EXPIRED"}:
                    raise
                # Ask publish for the authoritative terminal receipt; never revive the item.
                break
            media_id = result.get("media", {}).get("id")
            if not isinstance(media_id, str) or not media_id:
                raise CollectorRequestError("Core returned an invalid media receipt")
            if attachment.index == record.payload.get("document_thumbnail_index"):
                thumbnail_id = media_id
            if avatar:
                avatar_id = media_id
            else:
                media_ids.append(media_id)
        args = {
            **(record.payload.get("publication_metadata", {}) if target.collectFiles else {}),
            **base,
            "title": record.title,
            "body": record.text,
            "contentHash": stored.content_hash,
            "authorName": record.source_name,
            "authorUrl": source_homepage(target.plugin, target.locator),
            "mediaIds": media_ids,
        }
        if files:
            if thumbnail_id:
                files[0]["thumbnailMediaId"] = thumbnail_id
                origin = record.payload.get("document_thumbnail_origin")
                if origin:
                    files[0]["thumbnailOrigin"] = origin
            args["files"] = files
        if record.source_url:
            args["url"] = record.source_url
        if avatar_id:
            args["avatarMediaId"] = avatar_id
        result = await self._call("channel.publish", args)
        status = result.get("status")
        if status not in {"created", "updated", "duplicate", "deleted", "expired"}:
            raise CollectorRequestError("Core returned an invalid publication receipt")
        await asyncio.to_thread(
            self.records.mark_agents_news,
            record.record_id,
            target.sourceId,
            stored.content_hash,
            status,
        )
        self._status(
            connected=True,
            error=None,
            last_published_at=datetime.now(UTC).isoformat(),
            last_result=status,
        )
        return status

    async def publish_avatars(self, stop: asyncio.Event) -> None:
        """Synchronize source identity even when a source has no recent posts."""
        checkpoints = await asyncio.to_thread(self.checkpoints.list_all)
        failures = 0
        synced = 0
        for entry in checkpoints:
            if stop.is_set():
                return
            avatar = entry["checkpoint"].get("channel_avatar")
            target = self.targets.get(
                (self.source_plugins.get(entry["source_id"]), entry["target_id"])
            )
            if not target or not target.enabled or not avatar or not avatar.get("data"):
                continue
            mark_id = "avatar:" + target.sourceId
            previous = self.checkpoints.get("agents-company", mark_id)
            if previous == {"endpoint": self.endpoint, "sha256": avatar.get("sha256")}:
                synced += 1
                continue
            try:
                data = base64.b64decode(avatar["data"], validate=True)
                if (
                    not data
                    or len(data) > MAX_IMAGE_BYTES
                    or avatar.get("mime_type") not in IMAGE_TYPES
                    or hashlib.sha256(data).hexdigest() != avatar.get("sha256")
                ):
                    raise ValueError("Invalid cached channel avatar")
                result = await self._call(
                    "channel.source-avatar-put",
                    {
                        "sourceId": target.sourceId,
                        "name": avatar["name"],
                        "mimeType": avatar["mime_type"],
                        "data": avatar["data"],
                    },
                )
                if (
                    result.get("sourceId") != target.sourceId
                    or result.get("sha256") != avatar["sha256"]
                ):
                    raise CollectorRequestError("Core returned an invalid source avatar receipt")
                await asyncio.to_thread(
                    self.checkpoints.put,
                    "agents-company",
                    mark_id,
                    {"endpoint": self.endpoint, "sha256": avatar["sha256"]},
                )
                synced += 1
            except (CollectorRequestError, ValueError, KeyError) as error:
                failures += 1
                if isinstance(error, CollectorRequestError) and error.code in {
                    "SOURCE_DISABLED",
                    "SOURCE_FORBIDDEN",
                    "SOURCE_NOT_FOUND",
                }:
                    await self.refresh_config(force=True)
                self.log.warning("One source avatar remains pending: %s", type(error).__name__)
        self._status(avatars_synced=synced, avatar_errors=failures)

    async def publish_pending(self, stop: asyncio.Event) -> None:
        sources = {key: t.sourceId for key, t in self.targets.items() if t.enabled}
        pending = await asyncio.to_thread(
            self.records.pending_agents_news,
            sources,
            datetime.now(UTC) - timedelta(hours=PUBLISH_HOURS),
            document_since=datetime.now(UTC) - timedelta(hours=DOCUMENT_HOURS),
        )
        for record_id, source_id in pending:
            if stop.is_set():
                return
            if asyncio.get_running_loop().time() - self.last_refresh >= self.settings.poll_seconds:
                await self.refresh_config()
            stored = await asyncio.to_thread(self.records.get, record_id)
            if stored is None or stored.record.occurred_at < datetime.now(UTC) - timedelta(
                hours=DOCUMENT_HOURS
                if stored.record.payload.get("cloud_document_channel")
                else PUBLISH_HOURS
            ):
                continue
            target = self.targets.get((stored.record.plugin_id, stored.record.target_id))
            if target is None or not target.enabled or target.sourceId != source_id:
                continue
            try:
                await self._publish(stored, target)
            except CollectorRequestError as error:
                # Refresh revoked sources; one rejected item must not block other news.
                await self.refresh_config(force=True)
                self._status(error=str(error))
                self.log.warning("One Agents news delivery failed; it remains pending")

    async def run(self, stop: asyncio.Event) -> None:
        while not stop.is_set():
            try:
                await self.refresh_config()
                await self.publish_avatars(stop)
                await self.publish_pending(stop)
            except (CollectorRequestError, ValueError, OSError) as error:
                self._status(connected=False, error=str(error))
                self.log.warning("Agents publication/sync failed: %s", type(error).__name__)
            with suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=self.settings.poll_seconds)

    async def close(self) -> None:
        if self.session is not None:
            await self.session.close()
            self.session = None
