"""Original platform author images, cached on the server and sent to Mac RAM."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import re
import time
from urllib.parse import urlparse

import aiohttp


class ChannelAuthorAvatars:
    def __init__(self, publisher, scheduler, records, content_store=None):
        self.publisher, self.scheduler, self.records = publisher, scheduler, records
        self.content_store = content_store

    def _recent_x(self):
        with self.records.database.locked() as connection:
            rows = connection.execute("SELECT record_id,target_id,payload_json FROM records WHERE plugin_id='x' ORDER BY observed_at DESC").fetchall()
        result = {}
        for row in rows:
            result.setdefault(row["target_id"], row["record_id"])
        return result

    async def _x(self, target, cached):
        if self.content_store:
            rows = self.content_store.db.execute("SELECT data FROM content WHERE kind='posts' AND json_extract(data,'$.source_id')=? AND json_extract(data,'$.avatar_media_id') IS NOT NULL ORDER BY json_extract(data,'$.published_at') DESC LIMIT 8", (target.sourceId,)).fetchall()
            expected = target.locator.rstrip("/").rsplit("/", 1)[-1].removeprefix("@").lower()
            for row in rows:
                post = json.loads(row[0])
                handle = str(post.get("author_url") or "").rstrip("/").rsplit("/", 1)[-1].removeprefix("@").lower()
                if handle == expected:
                    try:
                        image = self.content_store.execute("asset-read", {"id": post["avatar_media_id"]})
                        return base64.b64decode(image["data"]), image["mimeType"]
                    except FileNotFoundError:
                        continue
        record_id = cached.get(target.targetId)
        if record_id:
            stored = await asyncio.to_thread(self.records.get, record_id)
            index = stored.record.payload.get("avatar_attachment_index")
            handle = stored.record.payload.get("author_handle", "").lower().removeprefix("@")
            expected = target.locator.rstrip("/").rsplit("/", 1)[-1].removeprefix("@").lower()
            if handle == expected:
                attachment = next((item for item in stored.attachments if item.index == index), None)
                if attachment:
                    file = self.records.media.resolve(attachment.relative_path)
                    if file.is_file():
                        return await asyncio.to_thread(file.read_bytes), attachment.mime_type
        for source in self.scheduler.snapshot.sources.sources:
            if source.plugin != "x":
                continue
            config = next((item for item in source.targets if item.id == target.targetId), None)
            plugin = self.scheduler.plugins.get(source.id)
            if config is not None and plugin is not None:
                deadline = asyncio.get_running_loop().time() + 30
                url = await plugin.client.fetch_avatar_url(config.locator, deadline=deadline)
                if url:
                    image = await plugin.client.download_image(url, post_id="avatar", index=0, deadline=deadline)
                    return image.data, image.mime_type
        return None

    async def _youtube(self, session, target):
        url = target.locator if target.locator.startswith("https://") else "https://www.youtube.com/" + target.locator
        if urlparse(url).hostname not in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
            raise ValueError("Invalid YouTube profile")
        async with session.get(url) as response:
            response.raise_for_status()
            text = await response.text()
        match = re.search(r'"channelMetadataRenderer"\s*:\s*', text)
        if not match:
            return None
        metadata = json.JSONDecoder().raw_decode(text[match.end():])[0]
        thumbnails = metadata.get("avatar", {}).get("thumbnails", [])
        if not thumbnails:
            return None
        image_url = thumbnails[-1]["url"]
        host = urlparse(image_url).hostname or ""
        if not (host.endswith(".googleusercontent.com") or host.endswith(".ggpht.com")):
            raise ValueError("Unexpected native YouTube avatar host")
        async with session.get(image_url) as response:
            response.raise_for_status()
            data = await response.read()
            if len(data) > 8 * 1024 * 1024:
                raise ValueError("Author avatar is too large")
            return data, response.headers.get("content-type", "image/jpeg").split(";")[0]

    async def run(self, stop):
        # A separate session never sends the Core collector Authorization header to a platform.
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30), trust_env=True, headers={"User-Agent": "Mozilla/5.0"}) as session:
            while not stop.is_set():
                recent = await asyncio.to_thread(self._recent_x)
                limit = asyncio.Semaphore(4)

                async def update(target):
                    if stop.is_set() or not target.enabled or target.plugin not in {"x", "youtube"}:
                        return
                    previous = self.publisher.checkpoints.get("channel-author-avatars", target.sourceId)
                    if previous and time.time() - previous.get("updated", 0) < 7 * 86400:
                        return
                    async with limit:
                        if stop.is_set():
                            return
                        try:
                            value = await self._x(target, recent) if target.plugin == "x" else await self._youtube(session, target)
                            if value:
                                data, mime = value
                                await self.publisher._call("channel.source-avatar-put", {"sourceId": target.sourceId, "name": "platform-author-avatar", "mimeType": mime, "data": base64.b64encode(data).decode()})
                                self.publisher.checkpoints.put("channel-author-avatars", target.sourceId, {"sha256": hashlib.sha256(data).hexdigest(), "updated": time.time()})
                        except (OSError, ValueError, RuntimeError, aiohttp.ClientError):
                            pass

                targets = sorted(self.publisher.targets.values(), key=lambda target: target.plugin != "youtube")
                await asyncio.gather(*(update(target) for target in targets))
                try:
                    await asyncio.wait_for(stop.wait(), 300)
                except TimeoutError:
                    pass
