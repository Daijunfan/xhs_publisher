"""Evidence-backed image metadata and a bounded same-origin thumbnail cache."""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
import logging
import re
import time
from contextlib import suppress
from pathlib import Path
from urllib.parse import urlsplit

import aiohttp
from PIL import Image

from .models import now_iso

LOG = logging.getLogger(__name__)
IMAGE_MIMES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_IMAGE_BYTES = 8 * 1024 * 1024


def allowed_image_url(value, platform: str) -> str | None:
    if not isinstance(value, str) or len(value) > 2048:
        return None
    try:
        parsed = urlsplit(value)
        if parsed.scheme != "https" or parsed.username or parsed.password or parsed.port not in (None, 443):
            return None
        if platform == "youtube":
            valid = parsed.hostname in {"i.ytimg.com", "i9.ytimg.com", "img.youtube.com"} and parsed.path.startswith(("/vi/", "/vi_webp/"))
        elif platform == "x":
            valid = parsed.hostname == "pbs.twimg.com" and parsed.path.startswith(("/media/", "/amplify_video_thumb/", "/ext_tw_video_thumb/", "/tweet_video_thumb/"))
        else:
            valid = False
        return value if valid else None
    except ValueError:
        return None


def _json(value):
    try:
        result = json.loads(value or "{}")
        return result if isinstance(result, dict) else {}
    except (ValueError, TypeError):
        return {}


def collect_media(source, rows: list, runtime: Path) -> dict[str, list[dict]]:
    """Attach only article media; album grouping is scoped to its source and target."""
    runtime = Path(runtime).resolve()
    record_columns = {row[1] for row in source.execute("PRAGMA table_info(records)")}
    attachment_columns = {row[1] for row in source.execute("PRAGMA table_info(attachments)")}
    if not attachment_columns:
        return {}
    optional = lambda name, default: "r." + name if name in record_columns else default
    index = "a.attachment_index" if "attachment_index" in attachment_columns else "0"
    identities = [row["record_id"] for row in rows]
    metadata = []
    # Each refresh inspects only changed records and their already-expanded album siblings.
    # Chunking keeps this portable to SQLite builds with a 999-parameter limit.
    for start in range(0, len(identities), 400):
        chunk = identities[start:start + 400]
        query = (
            "SELECT a.record_id,a.attachment_id,a.mime_type,a.relative_path,"
            + ("a.sha256" if "sha256" in attachment_columns else "NULL") + " AS sha256,"
            + index + " AS attachment_index,r.plugin_id,r.payload_json,r.occurred_at,"
            + optional("external_id", "''") + " AS external_id,"
            + optional("group_id", "NULL") + " AS group_id,"
            + optional("source_id", "''") + " AS source_id,"
            + optional("target_id", "''") + " AS target_id "
            "FROM attachments a JOIN records r ON r.record_id=a.record_id "
            "WHERE a.mime_type IN ('image/png','image/jpeg','image/webp','image/gif') "
            "AND a.record_id IN (" + ",".join("?" for _ in chunk) + ")"
        )
        metadata.extend(source.execute(query, chunk).fetchall())
    metadata.sort(key=lambda row: (row["source_id"], row["target_id"], row["occurred_at"] or "",
                                  str(row["external_id"]).zfill(40), row["attachment_index"]))
    groups: dict[tuple, list[dict]] = {}
    own: dict[str, list[dict]] = {}
    for row in metadata:
        payload = _json(row["payload_json"])
        if isinstance(payload.get("avatar_attachment_index"), int) and row["attachment_index"] == payload["avatar_attachment_index"]:
            continue
        path = (runtime / row["relative_path"]).resolve()
        exists = path.is_relative_to(runtime) and path.is_file() and path.stat().st_size > 0
        kind = "thumbnail" if row["plugin_id"] == "youtube" or row["attachment_index"] == payload.get("document_thumbnail_index") else "image"
        origin = "video_thumbnail" if row["plugin_id"] == "youtube" else "source_attachment"
        item = {"attachment_id": row["attachment_id"], "origin_url": None,
                "relative_path": row["relative_path"] if exists else None, "mime_type": row["mime_type"],
                "sha256": row["sha256"],
                "kind": kind, "origin": origin, "platform": row["plugin_id"],
                "state": "ready" if exists else "failed", "error": None if exists else "source_image_missing"}
        own.setdefault(row["record_id"], []).append(item)
        if row["plugin_id"] == "telegram" and row["group_id"]:
            groups.setdefault((row["source_id"], row["target_id"], row["group_id"]), []).append(item)
    result = {}
    for raw in rows:
        row = dict(raw)
        payload = _json(row.get("payload_json"))
        platform, identity = row["plugin_id"], row["record_id"]
        values = own.get(identity, [])
        if platform == "telegram" and row.get("group_id"):
            values = groups.get((row.get("source_id", ""), row.get("target_id", ""), row["group_id"]), values)
        values = list(values)
        remote = []
        if platform == "youtube" and not any(value["state"] == "ready" for value in values):
            video = payload.get("video_metadata") or {}
            if not isinstance(video, dict):
                video = {}
            thumbnail = allowed_image_url(video.get("thumbnail"), platform)
            video_id = video.get("id") or row.get("external_id")
            if not thumbnail and isinstance(video_id, str) and re.fullmatch(r"[\w-]{11}", video_id):
                thumbnail = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
            if thumbnail:
                remote.append(thumbnail)
        if platform == "x":
            saved = payload.get("downloaded_image_urls", [])
            if not isinstance(saved, list):
                saved = []
            urls = payload.get("image_urls", [])
            if isinstance(urls, list):
                remote.extend(url for url in urls[:8] if allowed_image_url(url, platform) and url not in saved)
        for url in dict.fromkeys(remote):
            values.append({"attachment_id": None, "origin_url": url, "relative_path": None,
                           "mime_type": None, "sha256": None, "kind": "thumbnail" if platform == "youtube" else "image",
                           "origin": "video_thumbnail" if platform == "youtube" else "source_image",
                           "platform": platform, "state": "pending", "error": None})
        unique = []
        seen = set()
        for value in values:
            key = value["attachment_id"] or value["origin_url"]
            if key in seen:
                continue
            seen.add(key)
            media_id = "m" + hashlib.sha256((identity + ":" + key).encode()).hexdigest()
            unique.append({**value, "id": media_id, "record_id": identity, "position": len(unique)})
        result[identity] = unique
    return result


def upsert_media(c, identity: str, assets: list[dict]) -> None:
    keep = {asset["id"] for asset in assets}
    existing = {row[0] for row in c.execute("SELECT id FROM media_assets WHERE record_id=?", (identity,))}
    for removed in existing - keep:
        # Cache files are content addressed and can be reused; never delete source media.
        c.execute("DELETE FROM media_assets WHERE id=?", (removed,))
    for asset in assets:
        c.execute(
            "INSERT INTO media_assets(id,record_id,attachment_id,origin_url,relative_path,mime_type,sha256,kind,"
            "origin,platform,state,position,error,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET attachment_id=excluded.attachment_id,"
            "relative_path=CASE WHEN excluded.attachment_id IS NOT NULL THEN excluded.relative_path ELSE media_assets.relative_path END,"
            "mime_type=CASE WHEN excluded.attachment_id IS NOT NULL THEN excluded.mime_type ELSE media_assets.mime_type END,"
            "state=CASE WHEN excluded.attachment_id IS NOT NULL THEN excluded.state ELSE media_assets.state END,"
            "error=CASE WHEN excluded.attachment_id IS NOT NULL THEN excluded.error ELSE media_assets.error END,"
            "kind=excluded.kind,origin=excluded.origin,position=excluded.position,sha256=coalesce(excluded.sha256,media_assets.sha256)",
            (asset["id"], identity, asset["attachment_id"], asset["origin_url"], asset["relative_path"],
             asset["mime_type"], asset.get("sha256"), asset["kind"], asset["origin"], asset["platform"], asset["state"], asset["position"], asset["error"], now_iso()),
        )


def media_for(c, identities: list[str]) -> list[dict]:
    if not identities:
        return []
    placeholders = ",".join("?" for _ in identities)
    rows = c.execute("SELECT * FROM media_assets WHERE record_id IN (" + placeholders + ")", identities).fetchall()
    ranks = {identity: index for index, identity in enumerate(identities)}
    rows.sort(key=lambda row: (ranks[row["record_id"]], row["position"], row["id"]))
    result, seen, hashes = [], set(), {}
    for row in rows:
        key = row["relative_path"] or row["origin_url"] or row["attachment_id"]
        if key in seen or (row["sha256"] and row["sha256"] in hashes):
            continue
        seen.add(key)
        if row["sha256"]:
            hashes.setdefault(row["sha256"], row["record_id"])
        ready = row["state"] == "ready"
        result.append({"id": row["id"], "url": "/api/media/" + row["id"] if ready else None,
                       "kind": row["kind"], "platform": row["platform"], "status": row["state"],
                       "mime_type": row["mime_type"], "origin": row["origin"], "error": row["error"]})
    return result


class MediaCache:
    def __init__(self, store, runtime: Path, *, cache_namespace="frontier/media"):
        self.store, self.runtime = store, Path(runtime).resolve()
        self.cache_namespace = Path(cache_namespace)
        if self.cache_namespace.is_absolute() or ".." in self.cache_namespace.parts:
            raise ValueError("invalid_media_cache_namespace")
        self.stop = asyncio.Event()

    def _pending(self, platform=None) -> list[dict]:
        if platform not in (None, "x", "youtube"):
            raise ValueError("invalid_media_platform")
        with self.store.connect() as c:
            where = "m.origin_url IS NOT NULL AND m.state IN ('pending','failed') AND m.attempts<4 AND m.next_attempt<=?"
            args = [time.time()]
            if platform:
                where += " AND m.platform=?"
                args.append(platform)
            return [dict(row) for row in c.execute(
                "SELECT * FROM (SELECT m.*,r.first_ingested_at,row_number() OVER(PARTITION BY m.platform "
                "ORDER BY r.first_ingested_at DESC,m.id) AS platform_rank "
                "FROM media_assets m JOIN raw_records r ON r.record_id=m.record_id WHERE " + where + ") "
                "ORDER BY platform_rank,first_ingested_at DESC,id LIMIT 8", args
            )]

    def _save(self, row, data, mime):
        digest = hashlib.sha256(data).hexdigest()
        relative = self.cache_namespace / digest[:2] / digest
        path = self.runtime / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            temp = path.with_name("." + digest + "-" + row["id"] + ".tmp")
            temp.write_bytes(data)
            temp.chmod(0o600)
            temp.replace(path)
        with self.store.connect() as c:
            c.execute("UPDATE media_assets SET relative_path=?,mime_type=?,sha256=?,state='ready',error=NULL,updated_at=? WHERE id=?", (relative.as_posix(), mime, digest, now_iso(), row["id"]))

    def _fail(self, row, code):
        with self.store.connect() as c:
            c.execute("UPDATE media_assets SET attempts=attempts+1,state='failed',error=?,next_attempt=?,updated_at=? WHERE id=?", (code, time.time() + min(3600, 60 * 2**row["attempts"]), now_iso(), row["id"]))

    async def fetch(self, session, row):
        url = allowed_image_url(row["origin_url"], row["platform"])
        if not url:
            await asyncio.to_thread(self._fail, row, "image_origin_rejected")
            return
        try:
            async with session.get(url, allow_redirects=False) as response:
                if response.status != 200:
                    await asyncio.to_thread(self._fail, row, "image_http_" + str(response.status))
                    return
                mime = response.headers.get("Content-Type", "").split(";", 1)[0].lower()
                if mime not in IMAGE_MIMES:
                    await asyncio.to_thread(self._fail, row, "unsupported_image_type")
                    return
                data = bytearray()
                async for chunk in response.content.iter_chunked(65536):
                    data.extend(chunk)
                    if len(data) > MAX_IMAGE_BYTES:
                        await asyncio.to_thread(self._fail, row, "image_too_large")
                        return
                def validate():
                    with Image.open(io.BytesIO(data)) as decoded:
                        if decoded.width * decoded.height > 50_000_000:
                            raise ValueError("image_dimensions")
                        actual = Image.MIME.get(decoded.format)
                        decoded.verify()
                        if actual not in IMAGE_MIMES:
                            raise ValueError("image_type")
                        return actual
                actual_mime = await asyncio.to_thread(validate)
                await asyncio.to_thread(self._save, row, bytes(data), actual_mime)
        except (aiohttp.ClientError, TimeoutError, OSError, ValueError, Image.DecompressionBombError):
            await asyncio.to_thread(self._fail, row, "image_download_failed")

    async def run(self):
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=20), trust_env=True,
            connector=aiohttp.TCPConnector(limit=3), headers={"User-Agent": "Frontier/2.0 image cache"},
        ) as session:
            while not self.stop.is_set():
                try:
                    pending = await asyncio.to_thread(self._pending)
                    for start in range(0, len(pending), 3):
                        await asyncio.gather(*(self.fetch(session, row) for row in pending[start:start + 3]))
                except Exception as error:
                    LOG.warning("Media cache batch failed: %s", type(error).__name__)
                with suppress(TimeoutError):
                    await asyncio.wait_for(self.stop.wait(), timeout=5)
