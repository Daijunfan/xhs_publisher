"""Server-owned channel content. Never downloads a document while listing news."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import re
import shutil
import sqlite3
import time
import threading
from pathlib import Path
from channel_queries import ArchiveQueries, NO_EXPIRY, PLATFORM_BYTES
from channel_capacity import ArchiveCapacity

CONTENT_KEYS = {"posts": "id", "media": "id", "source_avatars": "source_id", "channel_messages": "id", "channel_message_attachments": "message_id", "channel_message_notices": "message_id", "channel_message_triggers": "message_id"}
WEEK_MS = 7 * 86400 * 1000


class ChannelContentStore:
    def __init__(self, root: Path, source_media: Path | None = None):
        self.root = root
        self.source_media = source_media
        (root / "assets").mkdir(parents=True, exist_ok=True, mode=0o700)
        self.db = sqlite3.connect(root / "content.sqlite3")
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS content(kind TEXT NOT NULL,item_key TEXT NOT NULL,expires_at INTEGER,data TEXT NOT NULL,PRIMARY KEY(kind,item_key));
        CREATE TABLE IF NOT EXISTS assets(id TEXT PRIMARY KEY,file TEXT NOT NULL,mime_type TEXT NOT NULL,sha256 TEXT NOT NULL,bytes INTEGER NOT NULL,created_at REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS pins(kind TEXT NOT NULL,item_key TEXT NOT NULL,PRIMARY KEY(kind,item_key));
        """)
        if "created_at" not in {row[1] for row in self.db.execute("PRAGMA table_info(assets)")}:
            self.db.execute("ALTER TABLE assets ADD COLUMN created_at REAL NOT NULL DEFAULT 0")
        self.db.commit()
        self.archive = ArchiveQueries(self)
        self.capacity = ArchiveCapacity(self)
        self.last_gc = 0

    @staticmethod
    def _now():
        return int(time.time() * 1000)

    def _expire(self):
        # Capacity, not age, governs the archive. Explicit saves/downloads stay pinned.
        if time.time() - self.last_gc < 30:
            return
        self.last_gc = time.time()
        try:
            self.enforce_capacity()
        except ValueError:
            pass  # A full protected archive must still accept reads and un-save requests.
        return

    def execute(self, operation: str, args: dict):
        if operation in {"configure", "summaries", "posts-page", "post-get", "reads-import", "read-mark", "read-states", "avatar-get", "history-page", "timeline-page"}:
            return self.archive.execute(operation, args)
        if operation == "capacity-status":
            return {"retentionDays": None, "platforms": self.capacity_usage()}
        if operation == "write":
            changes = args.get("changes", [])
            if not isinstance(changes, list) or len(changes) > 200:
                raise ValueError("Invalid content batch")
            with self.db:
                for change in changes:
                    kind, key, row = change["table"], change["key"], change["row"]
                    if kind not in CONTENT_KEYS or not isinstance(key, str):
                        raise ValueError("Unknown content identity")
                    if row is None:
                        if kind == "media":
                            asset = self.db.execute("SELECT file FROM assets WHERE id=?", (key,)).fetchone()
                            if asset:
                                (self.root/"assets"/asset[0]).unlink(missing_ok=True)
                                for preview in (self.root/"previews").glob(asset[0]+"-*.webp"): preview.unlink()
                            self.db.execute("DELETE FROM assets WHERE id=?", (key,))
                            self.db.execute("DELETE FROM storage_objects WHERE id=? OR id LIKE ?", ("asset:"+key,"preview:"+key+":%"))
                        self.db.execute("DELETE FROM content WHERE kind=? AND item_key=?", (kind, key))
                        if kind == "posts": self.db.execute("DELETE FROM post_index WHERE id=?", (key,))
                        self.capacity.content(kind, key, None)
                        continue
                    if str(row.get(CONTENT_KEYS[kind])) != key:
                        raise ValueError("Content identity mismatch")
                    stamp = row.get("published_at") or row.get("created_at") or row.get("updated_at") or self._now()
                    expires = None
                    if kind == "posts":
                        row["expires_at"] = NO_EXPIRY
                        if row.get("saved_at") is not None:
                            expires = None
                    self.db.execute("INSERT INTO content VALUES(?,?,?,?) ON CONFLICT(kind,item_key) DO UPDATE SET expires_at=excluded.expires_at,data=excluded.data", (kind, key, expires, json.dumps(row, ensure_ascii=False)))
                    if kind == "posts": self.archive.index(row)
                    self.capacity.content(kind, key, row)
                evicted = self.capacity.enforce()
            return {"written": len(changes), "evicted": evicted}
        if operation == "snapshot":
            self._expire()
            offset, limit = int(args.get("offset", 0)), int(args.get("limit", 100))
            if offset < 0 or not 1 <= limit <= 200:
                raise ValueError("Invalid content page")
            rows = self.db.execute("SELECT kind,data FROM content ORDER BY kind,item_key LIMIT ? OFFSET ?", (limit + 1, offset)).fetchall()
            return {"rows": [{"table": r["kind"], "row": json.loads(r["data"])} for r in rows[:limit]], "nextOffset": offset + limit if len(rows) > limit else None}
        if operation == "assets-import":
            values = args.get("assets", [])
            if not isinstance(values, list) or len(values) > 200:
                raise ValueError("Invalid existing asset batch")
            missing = []
            for asset in values:
                digest = asset.get("sha256", "")
                if not re.fullmatch(r"[a-f0-9]{64}", digest):
                    raise ValueError("Invalid existing asset hash")
                source = self.source_media / digest[:2] / digest if self.source_media else None
                if source is None or not source.is_file() or source.stat().st_size != asset["bytes"] or hashlib.sha256(source.read_bytes()).hexdigest() != digest:
                    missing.append(asset["id"])
                    continue
                file = hashlib.sha256(asset["id"].encode()).hexdigest()
                target = self.root / "assets" / file
                if args.get("verifyImage"):
                    from PIL import Image
                    with Image.open(source) as image:
                        expected = {"PNG":"image/png","JPEG":"image/jpeg","GIF":"image/gif","WEBP":"image/webp"}.get(image.format)
                        if expected != asset["mimeType"]: raise ValueError("Server image MIME does not match its original bytes")
                if not target.exists():
                    try:
                        os.link(source, target)
                    except OSError:
                        shutil.copyfile(source, target)
                with self.db:
                    self.db.execute("INSERT OR REPLACE INTO assets VALUES(?,?,?,?,?,?)", (asset["id"], file, asset["mimeType"], digest, asset["bytes"], time.time()))
            return {"missing": missing}
        if operation == "assets-verify":
            failures = []
            if not isinstance(args.get("ids"), list) or len(args["ids"]) > 200:
                raise ValueError("Invalid asset verification batch")
            for identifier in args["ids"]:
                row = self.db.execute("SELECT * FROM assets WHERE id=?", (identifier,)).fetchone()
                file = self.root / "assets" / row["file"] if row else None
                if file is None or not file.is_file() or file.stat().st_size != row["bytes"] or hashlib.sha256(file.read_bytes()).hexdigest() != row["sha256"]:
                    failures.append(identifier)
            return {"failed": failures}
        if operation == "rows-verify":
            failures = []
            values = args.get("rows", [])
            if not isinstance(values, list) or len(values) > 200:
                raise ValueError("Invalid content verification batch")
            for value in values:
                if value["table"] not in CONTENT_KEYS:
                    raise ValueError("Unknown content table")
                found = self.db.execute("SELECT data FROM content WHERE kind=? AND item_key=?", (value["table"], value["key"])).fetchone()
                row = json.loads(found[0]) if found else None
                if row is not None:
                    row.pop("expires_at", None)
                digest = hashlib.sha256(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
                if digest != value["sha256"]:
                    failures.append({"table": value["table"], "key": value["key"]})
            return {"failed": failures}
        if operation == "asset-put":
            data = base64.b64decode(args["data"], validate=True)
            if not data or len(data) > 8 * 1024 * 1024:
                raise ValueError("Invalid channel asset size")
            identifier = str(args["id"])
            digest = hashlib.sha256(data).hexdigest()
            file = hashlib.sha256(identifier.encode()).hexdigest()
            target = self.root / "assets" / file
            old = self.db.execute("SELECT sha256 FROM assets WHERE id=?", (identifier,)).fetchone()
            if not target.exists() or old is None or old[0] != digest:
                partial = target.with_suffix(".part")
                partial.write_bytes(data)
                partial.replace(target)
            with self.db:
                self.db.execute("INSERT INTO assets VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET file=excluded.file,mime_type=excluded.mime_type,sha256=excluded.sha256,bytes=excluded.bytes,created_at=excluded.created_at", (identifier, file, args["mimeType"], digest, len(data), time.time()))
            return {"bytes": len(data), "sha256": digest, "path": "assets/" + file}
        if operation in {"asset-read", "asset-info"}:
            row = self.db.execute("SELECT * FROM assets WHERE id=?", (args["id"],)).fetchone()
            if row is None:
                raise FileNotFoundError("Channel asset is unavailable")
            value = {"mimeType": row["mime_type"], "sha256": row["sha256"], "bytes": row["bytes"], "path": "assets/" + row["file"]}
            if operation == "asset-read":
                return self._finish_asset(dict(row),args,self._asset_payload(dict(row),args))
            return value
        if operation == "pin":
            kind, key = args["table"], args["key"]
            if kind not in CONTENT_KEYS:
                raise ValueError("Unknown saved content")
            if kind == "posts" and not args["saved"]:
                retained = self.db.execute("SELECT data FROM content WHERE kind='posts' AND item_key=?", (key,)).fetchone()
                if retained:
                    post = json.loads(retained[0])
                    if post.get("state","active") == "active" and any(file.get("serverPath") for file in json.loads(post.get("remote_files","[]"))):
                        return {"saved": False, "downloadRetained": True}
            with self.db:
                self.db.execute("INSERT OR IGNORE INTO pins VALUES(?,?)" if args["saved"] else "DELETE FROM pins WHERE kind=? AND item_key=?", (kind, key))
            return {"saved": bool(args["saved"])}
        if operation == "status":
            return {"retentionDays": None, "platforms": self.capacity_usage(), "rows": self.db.execute("SELECT COUNT(*) FROM content").fetchone()[0]}
        raise ValueError("Unsupported channel storage operation")

    def _asset_payload(self, row, args):
        value={"mimeType":row["mime_type"],"sha256":row["sha256"],"bytes":row["bytes"],"path":"assets/"+row["file"]}
        if args.get("maxEdge") in {96,640,1280}:
            from PIL import Image,ImageOps
            preview=self.root/"previews"/(row["file"]+"-"+row["sha256"]+"-"+str(args["maxEdge"])+".webp")
            if not preview.exists():
                preview.parent.mkdir(exist_ok=True,mode=0o700)
                partial=preview.with_suffix("."+str(threading.get_ident())+".part")
                with Image.open(self.root/"assets"/row["file"]) as original:
                    image=ImageOps.exif_transpose(original);image.thumbnail((args["maxEdge"],args["maxEdge"]))
                    image.convert("RGBA" if "A" in image.getbands() else "RGB").save(partial,"WEBP",quality=80)
                partial.replace(preview)
            data=preview.read_bytes();value["mimeType"]="image/webp";value["_previewBytes"]=len(data)
        else:data=(self.root/"assets"/row["file"]).read_bytes()
        value["data"]=base64.b64encode(data).decode()
        return value

    def _finish_asset(self,row,args,value):
        size=value.pop("_previewBytes",None)
        if size is not None:
            media=self.db.execute("SELECT data FROM content WHERE kind='media' AND item_key=?",(row["id"],)).fetchone()
            if media:
                owner=json.loads(media[0])
                with self.db:self.capacity.register("preview:"+row["id"]+":"+str(args["maxEdge"]),owner["source_id"],size,owner["post_id"])
        return value

    async def execute_async(self,operation,args):
        if operation!="asset-read":return self.execute(operation,args)
        row=self.db.execute("SELECT * FROM assets WHERE id=?",(args["id"],)).fetchone()
        if row is None:raise FileNotFoundError("Channel asset is unavailable")
        # Only file IO/decoding runs on threads; SQLite remains on the owning loop.
        payload=await asyncio.to_thread(self._asset_payload,dict(row),args)
        return self._finish_asset(dict(row),args,payload)

    def close(self):
        self.db.close()

    def capacity_usage(self):
        return self.capacity.usage()

    def enforce_capacity(self):
        with self.db: self.capacity.enforce()


async def serve_channel_storage(publisher, store: ChannelContentStore, stop: asyncio.Event, document_handler=None):
    """Use the existing authenticated reverse connection; no new public listener."""
    async def worker():
      while not stop.is_set():
        try:
            store._expire()
            message = await publisher._call("channel.storage-exchange", {"waitMs": 15000})
            for job in message.get("jobs", []):
                try:
                    result = await document_handler(job["operation"], job["args"]) if job["operation"].startswith("document-") and document_handler else await store.execute_async(job["operation"], job["args"])
                    reply = {"id": job["id"], "result": result}
                except Exception as error:
                    reply = {"id": job["id"], "error": str(error)}
                await publisher._call("channel.storage-result", reply)
        except (OSError, ValueError, RuntimeError):
            try:
                await asyncio.wait_for(stop.wait(), 2)
            except TimeoutError:
                pass
    await asyncio.gather(*(worker() for _ in range(8)))
