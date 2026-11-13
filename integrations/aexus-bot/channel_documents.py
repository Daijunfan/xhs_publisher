"""Requested and opt-in background Telegram document caching; listing stays metadata-only."""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import sqlite3
import time
from pathlib import Path

from xhs_local.plugins.contracts import CancellationToken


class ChannelDocumentRequests:
    def __init__(self, store, scheduler, publisher):
        self.store, self.scheduler, self.publisher = store, scheduler, publisher
        self.tasks = {}
        self.retained = set()
        self.limit = asyncio.Semaphore(2)
        store.db.execute("CREATE TABLE IF NOT EXISTS document_requests(id TEXT PRIMARY KEY,state TEXT NOT NULL,data TEXT,error TEXT)")
        if "updated_at" not in {row[1] for row in store.db.execute("PRAGMA table_info(document_requests)")}:
            store.db.execute("ALTER TABLE document_requests ADD COLUMN updated_at REAL NOT NULL DEFAULT 0")
        store.db.commit()
        (store.root / "documents").mkdir(exist_ok=True, mode=0o700)

    def _file(self, post_id, file_id):
        value = self.store.db.execute("SELECT data FROM content WHERE kind='posts' AND item_key=?", (post_id,)).fetchone()
        if value is None:
            raise FileNotFoundError("Channel document message is unavailable")
        post = json.loads(value[0])
        file = next((f for f in json.loads(post.get("remote_files", "[]")) if f["id"] == file_id), None)
        if file is None:
            raise FileNotFoundError("Unknown channel document")
        return post, file

    def status(self, identifier):
        row = self.store.db.execute("SELECT * FROM document_requests WHERE id=?", (identifier,)).fetchone()
        if row is None:
            raise FileNotFoundError("Unknown requested document")
        return {"id": identifier, "state": row["state"], **(json.loads(row["data"]) if row["data"] else {}), **({"error": row["error"]} if row["error"] else {})}

    async def handle(self, operation, args):
        if operation == "document-status":
            return self.status(args["id"])
        if operation != "document-prepare":
            raise ValueError("Unknown document operation")
        return await self.prepare(args["postId"], args["fileId"], retain=True)

    async def prepare(self, post_id, file_id, *, retain=False):
        post, file = self._file(post_id, file_id)
        identifier = hashlib.sha256((post_id + "/" + file_id).encode()).hexdigest()
        row = self.store.db.execute("SELECT state,data FROM document_requests WHERE id=?", (identifier,)).fetchone()
        if row and row[0] == "completed":
            data = json.loads(row[1])
            if (self.store.root / data["serverPath"]).is_file() and (self.store.root / data["serverPath"]).stat().st_size == data["bytes"]:
                if retain:
                    with self.store.db:
                        self.store.db.execute("INSERT OR IGNORE INTO pins VALUES('posts',?)", (post_id,))
                return self.status(identifier)
        if retain:
            self.retained.add(identifier)
        if identifier not in self.tasks:
            with self.store.db:
                self.store.db.execute("INSERT OR REPLACE INTO document_requests(id,state,data,error,updated_at) VALUES(?,'queued',NULL,NULL,?)", (identifier,time.time()))
            task = asyncio.create_task(self._download(identifier, post_id, post, file))
            self.tasks[identifier] = task
            task.add_done_callback(lambda _: self.tasks.pop(identifier, None))
        return self.status(identifier)

    async def _download(self, identifier, post_id, post, file):
        owned_plugin = None
        try:
            async with self.limit:
                with self.store.db:
                    self.store.db.execute("UPDATE document_requests SET state='running',updated_at=? WHERE id=?", (time.time(),identifier))
                digest = file.get("sha256")
                existing = self.store.source_media / digest[:2] / digest if digest and self.store.source_media else None
                if existing is not None and existing.is_file():
                    path = existing
                else:
                    target = next((t for t in self.publisher.targets.values() if t.sourceId == post["source_id"] and t.plugin == "telegram"), None)
                    if target is None:
                        raise ValueError("Telegram source is not available to this collector")
                    source = next(s for s in self.scheduler.snapshot.sources.sources if s.plugin == "telegram" and any(t.id == target.targetId for t in s.targets))
                    config = next(t for t in source.targets if t.id == target.targetId)
                    plugin = self.scheduler.plugins.get(source.id)
                    if plugin is None:
                        prepared = self.scheduler.registry.prepare(source, config_root=self.scheduler.snapshot.config_root, runtime_root=self.scheduler.snapshot.runtime_root)
                        plugin = self.scheduler.registry.create(prepared)
                        owned_plugin = plugin
                    token = CancellationToken()
                    peer, message = await plugin.transport.fetch_document(config, int(post["external_id"]), deadline=asyncio.get_running_loop().time() + 60, cancellation=token)
                    media = await plugin.transport.download_document(message, channel_id=peer, directory=self.store.root / "partial", deadline=asyncio.get_running_loop().time() + 900, cancellation=token)
                    path = Path(media.data)
                with path.open("rb") as stream:
                    actual_hash = await asyncio.to_thread(hashlib.file_digest, stream, "sha256")
                digest = actual_hash.hexdigest()
                if file.get("sha256") and file["sha256"] != digest or path.stat().st_size != file["bytes"]:
                    raise ValueError("Telegram document does not match its original metadata")
                destination = self.store.root / "documents" / digest
                if not destination.exists():
                    try:
                        os.link(path, destination)
                    except OSError:
                        await asyncio.to_thread(__import__('shutil').copyfile, path, destination)
                if path.parent == self.store.root / "partial":
                    path.unlink()
                result = {"sha256": digest, "bytes": destination.stat().st_size, "name": file["name"], "mimeType": file["mimeType"], "serverPath": "documents/" + digest}
                post, latest = self._file(post_id, file["id"])
                if latest["bytes"] != result["bytes"] or latest.get("sha256") and latest["sha256"] != digest:
                    raise ValueError("Channel document changed while downloading")
                descriptors = json.loads(post.get("remote_files", "[]"))
                post["remote_files"] = json.dumps([{**value, **result} if value["id"] == file["id"] else value for value in descriptors])
                with self.store.db:
                    self.store.db.execute("UPDATE document_requests SET state='completed',data=?,error=NULL,updated_at=? WHERE id=?", (json.dumps(result),time.time(),identifier))
                    self.store.db.execute("UPDATE content SET data=? WHERE kind='posts' AND item_key=?", (json.dumps(post), post_id))
                    if identifier in self.retained:
                        self.store.db.execute("INSERT OR IGNORE INTO pins VALUES('posts',?)", (post_id,))
                    self.store.capacity.register("document:"+digest,post["source_id"],destination.stat().st_size,post_id)
                    self.store.capacity.content("posts",post_id,post)
                    self.store.capacity.enforce()
        except asyncio.CancelledError:
            raise
        except Exception as error:
            with self.store.db:
                self.store.db.execute("UPDATE document_requests SET state='failed',error=?,updated_at=? WHERE id=?", (str(error),time.time(),identifier))
        finally:
            self.retained.discard(identifier)
            if owned_plugin is not None:
                await owned_plugin.close()

    async def prefetch_once(self):
        # One background job leaves the other native transfer slot for user requests.
        if self.tasks:
            return 0
        targets = {(source.plugin, target.id) for source in self.scheduler.snapshot.sources.sources
                   if source.plugin == "telegram" and source.enabled
                   for target in source.targets if target.enabled and target.options.get("prefetch_documents") is True}
        sources = [target.sourceId for target in self.publisher.targets.values()
                   if target.enabled and (target.plugin, target.targetId) in targets]
        if not sources:
            return 0
        placeholders = ",".join("?" for _ in sources)
        posts = self.store.db.execute("SELECT c.item_key,c.data FROM post_index p JOIN content c ON c.kind='posts' AND c.item_key=p.id WHERE p.state='active' AND p.source_id IN ("+placeholders+") ORDER BY p.published_at DESC", sources)
        for post_id, raw in posts:
            post = json.loads(raw)
            if post.get("state", "active") != "active":
                continue
            for file in json.loads(post.get("remote_files", "[]")):
                identifier = hashlib.sha256((post_id+"/"+file["id"]).encode()).hexdigest()
                row = self.store.db.execute("SELECT state,updated_at FROM document_requests WHERE id=?", (identifier,)).fetchone()
                if row and row["state"] == "failed" and row["updated_at"] > time.time()-300:
                    continue
                result = await self.prepare(post_id, file["id"])
                if result["state"] != "completed":
                    return 1
        return 0

    async def run_prefetch(self, stop):
        while not stop.is_set():
            try:
                await self.prefetch_once()
            except (OSError,ValueError,sqlite3.Error):
                logging.getLogger(__name__).exception("Document prefetch scan failed; will retry")
            try:
                await asyncio.wait_for(stop.wait(), timeout=3)
            except TimeoutError:
                pass

    async def close(self):
        for task in self.tasks.values():
            task.cancel()
        await asyncio.gather(*self.tasks.values(), return_exceptions=True)
