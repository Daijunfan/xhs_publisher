"""Aexus Bot's server-applied subscription receipts over the existing scoped connection."""
from __future__ import annotations

import asyncio
import base64
import hashlib
from contextlib import suppress

from xhs_local.pipeline.agents import AgentsPublisher, CollectorRequestError


class CorePublisher(AgentsPublisher):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._subscription_lock = asyncio.Lock()
        self._acknowledged_revision = None

    async def _publish(self, stored, target):
        self._deferred_files = {(target.sourceId, stored.record.external_id): stored.record.payload.get("deferred_files", [])}
        try:
            return await super()._publish(stored, target)
        finally:
            self._deferred_files = {}

    async def _call(self, command, args):
        if command == "channel.media-put" and getattr(self, "server_owned_media", False):
            data = base64.b64decode(args["data"], validate=True)
            reference = {key: value for key, value in args.items() if key != "data"}
            reference.update(sha256=hashlib.sha256(data).hexdigest(), bytes=len(data))
            return await super()._call("channel.media-register", reference)
        files = getattr(self, "_deferred_files", {}).get((args.get("sourceId"), args.get("externalId")))
        if command == "channel.publish" and files:
            args = {**args, "files": [*args.get("files", []), *files]}
        return await super()._call(command, args)

    async def refresh_config(self, *, force: bool = False) -> None:
        async with self._subscription_lock:
            await super().refresh_config(force=force)
            if self._acknowledged_revision != self.revision:
                receipt = await self._call("channel.collector-ack", {"revision": self.revision})
                if receipt.get("revision") != self.revision:
                    raise ValueError("Core returned an unexpected subscription receipt")
                self._acknowledged_revision = self.revision
                self._status(applied_revision=self.revision, applied_at=receipt.get("appliedAt"))

    async def watch_subscriptions(self, stop: asyncio.Event) -> None:
        """News/image deliveries cannot delay management changes from the Mac."""
        while not stop.is_set():
            try:
                await self.refresh_config()
            except (CollectorRequestError, ValueError, OSError) as error:
                self._status(connected=False, error=str(error))
            with suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=self.settings.poll_seconds)
