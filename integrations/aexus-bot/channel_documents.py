"""Explicitly requested Telegram downloads; listing/snapshotting never fetches file bytes."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path

from xhs_local.plugins.contracts import CancellationToken


class ChannelDocumentRequests:
    def __init__(self, store, scheduler, publisher):
        self.store, self.scheduler, self.publisher = store, scheduler, publisher
        self.tasks = {}
        self.limit = asyncio.Semaphore(2)
        store.db.execute("CREATE TABLE IF NOT EXISTS document_requests(id TEXT PRIMARY KEY,state TEXT NOT NULL,data TEXT,error TEXT)")
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
        post, file = self._file(args["postId"], args["fileId"])
        identifier = hashlib.sha256((args["postId"] + "/" + args["fileId"]).encode()).hexdigest()
        row = self.store.db.execute("SELECT state,data FROM document_requests WHERE id=?", (identifier,)).fetchone()
        if row and row[0] == "completed":
            data = json.loads(row[1])
            if (self.store.root / data["serverPath"]).is_file():
                return self.status(identifier)
        if identifier not in self.tasks:
            with self.store.db:
                self.store.db.execute("INSERT OR REPLACE INTO document_requests VALUES(?,'queued',NULL,NULL)", (identifier,))
            task = asyncio.create_task(self._download(identifier, args["postId"], post, file))
            self.tasks[identifier] = task
            task.add_done_callback(lambda _: self.tasks.pop(identifier, None))
        return self.status(identifier)

    async def _download(self, identifier, post_id, post, file):
        owned_plugin = None
        try:
            async with self.limit:
                with self.store.db:
                    self.store.db.execute("UPDATE document_requests SET state='running' WHERE id=?", (identifier,))
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
                descriptors = json.loads(post.get("remote_files", "[]"))
                post["remote_files"] = json.dumps([{**value, **result} if value["id"] == file["id"] else value for value in descriptors])
                with self.store.db:
                    self.store.db.execute("UPDATE document_requests SET state='completed',data=?,error=NULL WHERE id=?", (json.dumps(result), identifier))
                    self.store.db.execute("UPDATE content SET data=? WHERE kind='posts' AND item_key=?", (json.dumps(post), post_id))
                    self.store.db.execute("INSERT OR IGNORE INTO pins VALUES('posts',?)", (post_id,))
                    self.store.capacity.register("document:"+digest,post["source_id"],destination.stat().st_size,post_id)
                    self.store.capacity.content("posts",post_id,post)
                    self.store.capacity.enforce()
        except asyncio.CancelledError:
            raise
        except Exception as error:
            with self.store.db:
                self.store.db.execute("UPDATE document_requests SET state='failed',error=? WHERE id=?", (str(error), identifier))
        finally:
            if owned_plugin is not None:
                await owned_plugin.close()

    async def close(self):
        for task in self.tasks.values():
            task.cancel()
        await asyncio.gather(*self.tasks.values(), return_exceptions=True)
