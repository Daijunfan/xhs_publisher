#!/usr/bin/env python3
"""Frontier's read-only, server-owned news channel API.

The collector stays in Frontier. This adapter reads its SQLite database and
streams existing attachments without copying them, generating previews, or
contacting the original social networks. Bind through an SSH tunnel; the HTTP
listener is deliberately restricted to loopback.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import io
import json
import os
import re
import secrets
import sqlite3
import stat
from contextlib import closing, contextmanager
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit


PLATFORMS = ("telegram", "x", "youtube")
RETENTION_DAYS = 7
ID = re.compile(r"^[A-Za-z0-9_.-]{1,180}$")
PUBLISHED_SQL = "CAST(ROUND((julianday(COALESCE(NULLIF(r.occurred_at,''),r.observed_at))-2440587.5)*86400000) AS INTEGER)"


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code = status, code


def utc_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def milliseconds(value: object) -> int:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return round(parsed.timestamp() * 1000)
    except (TypeError, ValueError, OverflowError):
        return 0


def object_json(value: object) -> dict:
    try:
        result = json.loads(value or "{}")
        return result if isinstance(result, dict) else {}
    except (TypeError, ValueError):
        return {}


def safe_url(value: object) -> str | None:
    if not isinstance(value, str) or len(value) > 8192:
        return None
    try:
        parsed = urlsplit(value)
        if parsed.scheme in ("http", "https") and parsed.hostname and not parsed.username and not parsed.password:
            return value
    except ValueError:
        pass
    return None


def channel_id(platform: str, target: str) -> str:
    return "telegram:" + target if platform == "telegram" else platform


def read_token(file: Path) -> str:
    file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if file.is_symlink():
        raise RuntimeError("Channel token must be a regular private file")
    try:
        fd = os.open(file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        pass
    else:
        with os.fdopen(fd, "w", encoding="utf-8") as target:
            target.write(secrets.token_urlsafe(48) + "\n")
    info = file.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_size > 4096:
        raise RuntimeError("Channel token must be a regular private file")
    os.chmod(file, 0o600)
    value = file.read_text(encoding="utf-8").strip()
    if len(value) < 24 or len(value) > 1024 or any(c.isspace() for c in value):
        raise RuntimeError("Channel token is invalid")
    return value


class Provider:
    def __init__(self, root: Path, token_file: Path | None = None):
        self.root = root.resolve()
        self.runtime = (self.root / "runtime").resolve()
        self.media_root = (self.runtime / "media").resolve()
        self.database = self.runtime / "app.sqlite3"
        # Read receipts are server-side metadata, never a copy of news content.
        # Keep this database separate from the collector and its retention job.
        self.read_database = self.runtime / "aexus-channel-read-state.sqlite3"
        if self.read_database.is_symlink():
            raise RuntimeError("Channel read state must not be a symbolic link")
        fd = os.open(self.read_database, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
        try:
            os.fchmod(fd, 0o600)
        finally:
            os.close(fd)
        with closing(sqlite3.connect(self.read_database, timeout=5)) as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS read_cursors (channel_id TEXT PRIMARY KEY, collected_at TEXT NOT NULL, record_id TEXT NOT NULL, updated_at TEXT NOT NULL)")
            connection.commit()
        self.token = read_token(token_file or self.runtime / "secrets/aexus-channel.token")

    @contextmanager
    def connection(self, path: Path | None = None):
        selected = path or self.database
        try:
            connection = sqlite3.connect(selected.as_uri() + "?mode=ro", uri=True, timeout=5)
        except sqlite3.Error:
            raise ApiError(503, "COLLECTOR_UNAVAILABLE", "Frontier's collector database is unavailable") from None
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        try:
            yield connection
        finally:
            connection.close()

    @staticmethod
    def cutoff() -> str:
        # Retention is based on when a source item was first collected. A newly
        # collected newspaper can carry an older publication date and still be
        # useful. Re-polling an existing record does not renew its retention.
        return utc_iso(datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS))

    @staticmethod
    def base_where(connection: sqlite3.Connection) -> str:
        where = "r.plugin_id IN ('telegram','x','youtube') AND r.content_type IN ('tech_news','video_pending')"
        deleted = {row[1] for row in connection.execute("PRAGMA table_info(news_deleted)")}
        if "record_id" in deleted:
            where += " AND NOT EXISTS (SELECT 1 FROM news_deleted d WHERE d.record_id=r.record_id)"
        return where

    def read_cursors(self) -> dict[str, tuple[str, str]]:
        with closing(sqlite3.connect(self.read_database.as_uri() + "?mode=ro", uri=True, timeout=5)) as connection:
            return {row[0]: (row[1], row[2]) for row in connection.execute("SELECT channel_id,collected_at,record_id FROM read_cursors")}

    def unread_count(self, connection: sqlite3.Connection, key: str, cursor: tuple[str, str] | None) -> int:
        if key in ("x", "youtube"):
            platform, target = key, None
        elif key.startswith("telegram:") and ID.fullmatch(key[9:]):
            platform, target = "telegram", key[9:]
        else:
            raise ApiError(400, "INVALID_CHANNEL", "Choose a valid news channel")
        collected = "COALESCE(NULLIF(r.created_at,''),r.observed_at)"
        where = self.base_where(connection) + " AND r.plugin_id=? AND " + collected + ">=?"
        args: list = [platform, self.cutoff()]
        if target:
            where += " AND r.target_id=?"
            args.append(target)
        if cursor:
            where += " AND (" + collected + ">? OR (" + collected + "=? AND r.record_id>?))"
            args.extend((cursor[0], cursor[0], cursor[1]))
        return int(connection.execute("SELECT COUNT(*) FROM records r WHERE " + where, args).fetchone()[0])

    def acknowledge_read(self, value: object) -> dict:
        if not isinstance(value, dict) or set(value) != {"channelId", "postIds"}:
            raise ApiError(400, "INVALID_READ_RECEIPT", "Choose visible posts to mark as read")
        key, supplied = value["channelId"], value["postIds"]
        if not isinstance(key, str) or not isinstance(supplied, list) or not 1 <= len(supplied) <= 100 or any(not isinstance(item, str) or not ID.fullmatch(item) for item in supplied):
            raise ApiError(400, "INVALID_READ_RECEIPT", "Choose up to 100 visible posts")
        post_ids = list(dict.fromkeys(supplied))
        # Resolve the supplied identities against the real retained channel.
        # A client timestamp could incorrectly acknowledge posts not yet received.
        with self.connection() as connection:
            where = self.base_where(connection) + " AND r.plugin_id=? AND COALESCE(NULLIF(r.created_at,''),r.observed_at)>=?"
            args: list = ["telegram" if key.startswith("telegram:") else key, self.cutoff()]
            if key.startswith("telegram:") and ID.fullmatch(key[9:]):
                where += " AND r.target_id=?"
                args.append(key[9:])
            elif key not in ("x", "youtube"):
                raise ApiError(400, "INVALID_CHANNEL", "Choose a valid news channel")
            where += " AND r.record_id IN (" + ",".join("?" for _ in post_ids) + ")"
            rows = connection.execute("SELECT r.record_id,COALESCE(NULLIF(r.created_at,''),r.observed_at) AS collected_at FROM records r WHERE " + where, (*args, *post_ids)).fetchall()
        if len(rows) != len(post_ids):
            raise ApiError(409, "POSTS_CHANGED", "Some messages have expired; refresh the channel and try again")
        cursor = max((row["collected_at"], row["record_id"]) for row in rows)
        # SQLite serializes concurrent acknowledgements; an older frame can
        # never move the persisted watermark backwards over newer messages.
        with closing(sqlite3.connect(self.read_database, timeout=5)) as connection:
            connection.execute("INSERT INTO read_cursors(channel_id,collected_at,record_id,updated_at) VALUES(?,?,?,?) "
                               "ON CONFLICT(channel_id) DO UPDATE SET collected_at=excluded.collected_at,record_id=excluded.record_id,updated_at=excluded.updated_at "
                               "WHERE excluded.collected_at>read_cursors.collected_at OR (excluded.collected_at=read_cursors.collected_at AND excluded.record_id>read_cursors.record_id)",
                               (key, cursor[0], cursor[1], utc_iso(datetime.now(timezone.utc))))
            connection.commit()
        read_cursor = self.read_cursors()[key]
        with self.connection() as connection:
            unread = self.unread_count(connection, key, read_cursor)
        return {"channelId": key, "unreadCount": unread}

    def channels(self) -> dict:
        cutoff = self.cutoff()
        result: dict[str, dict] = {
            "x": {"id": "x", "name": "X", "platform": "x", "sourceCount": 0, "postCount": 0, "latestAt": 0},
            "youtube": {"id": "youtube", "name": "YouTube", "platform": "youtube", "sourceCount": 0, "postCount": 0, "latestAt": 0},
        }
        with self.connection() as connection:
            where = self.base_where(connection)
            rows = connection.execute(
                "SELECT r.plugin_id,r.target_id,COUNT(*) AS all_count,"
                "SUM(CASE WHEN COALESCE(NULLIF(r.created_at,''),r.observed_at)>=? THEN 1 ELSE 0 END) AS recent_count,"
                "MAX(CASE WHEN COALESCE(NULLIF(r.created_at,''),r.observed_at)>=? THEN " + PUBLISHED_SQL + " ELSE 0 END) AS latest "
                "FROM records r WHERE " + where + " GROUP BY r.plugin_id,r.target_id",
                (cutoff, cutoff),
            ).fetchall()
            for row in rows:
                platform, target = row["plugin_id"], row["target_id"]
                key = channel_id(platform, target)
                if key not in result:
                    latest = connection.execute(
                        "SELECT source_name FROM records WHERE plugin_id=? AND target_id=? ORDER BY updated_at DESC,record_id DESC LIMIT 1",
                        (platform, target),
                    ).fetchone()
                    result[key] = {"id": key, "name": latest[0] or target, "platform": platform, "sourceCount": 0, "postCount": 0, "latestAt": 0}
                item = result[key]
                item["sourceCount"] += 1
                item["postCount"] += row["recent_count"] or 0
                item["latestAt"] = max(item["latestAt"], row["latest"] or 0)
        # A configured Telegram source can have no records yet. Use its stable
        # subscription ID (the collector target ID) instead of its display name.
        subscriptions = self.runtime / "frontier/events.sqlite3"
        if subscriptions.is_file():
            try:
                with self.connection(subscriptions) as connection:
                    rows = connection.execute("SELECT id,platform,name,locator FROM subscriptions WHERE deleted_at IS NULL AND enabled=1").fetchall()
                for row in rows:
                    if row["platform"] not in PLATFORMS:
                        continue
                    key = channel_id(row["platform"], row["id"])
                    if row["platform"] == "telegram" and key not in result:
                        result[key] = {"id": key, "name": row["name"] or row["locator"], "platform": "telegram", "sourceCount": 1, "postCount": 0, "latestAt": 0}
            except (sqlite3.Error, ApiError):
                pass  # The original collector works without the optional web DB.
        cursors = self.read_cursors()
        with self.connection() as connection:
            for item in result.values():
                item["unreadCount"] = self.unread_count(connection, item["id"], cursors.get(item["id"]))
                platform = item["platform"]
                target = item["id"][9:] if platform == "telegram" else None
                clause = "plugin_id=?" + (" AND target_id=?" if target else "")
                args = (platform, target) if target else (platform,)
                latest = connection.execute("SELECT title,text FROM records WHERE " + clause + " ORDER BY observed_at DESC,record_id DESC LIMIT 1", args).fetchone()
                if latest:
                    item["preview"] = " ".join((latest["text"] or latest["title"] or "").split())[:140]
                if target:
                    try:
                        metadata, _data = self.channel_avatar(target)
                        item["avatarId"] = metadata["attachment_id"]
                    except ApiError:
                        pass
        channels = sorted(result.values(), key=lambda item: ({"x": 0, "youtube": 1}.get(item["platform"], 2), -item["latestAt"], item["name"].casefold(), item["id"]))
        return {"version": 1, "channels": channels, "retentionDays": RETENTION_DAYS}

    def channel_avatar(self, target: str):
        # Reuse the collector's current identity checkpoint. No new file/cache.
        if not ID.fullmatch(target):
            raise ApiError(400, "INVALID_MEDIA_ID", "Choose a valid channel")
        with self.connection() as connection:
            row = connection.execute("SELECT checkpoint_json FROM checkpoints WHERE target_id=? ORDER BY updated_at DESC LIMIT 1", (target,)).fetchone()
        avatar = object_json(row[0]).get("channel_avatar", {}) if row else {}
        encoded = avatar.get("data") if isinstance(avatar, dict) else None
        if not isinstance(encoded, str) or len(encoded) > 2 * 1024 * 1024:
            raise ApiError(410, "AVATAR_UNAVAILABLE", "The channel photo is not available")
        try:
            data = base64.b64decode(encoded, validate=True)
        except ValueError:
            raise ApiError(410, "AVATAR_UNAVAILABLE", "The channel photo is not available") from None
        if not data.startswith(b"\xff\xd8\xff"):
            raise ApiError(410, "AVATAR_UNAVAILABLE", "The channel photo is not available")
        metadata = {"attachment_id": "avatar." + target, "file_name": "channel-avatar.jpg", "mime_type": "image/jpeg", "byte_size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        return metadata, data

    def posts(self, values: dict[str, str]) -> dict:
        key = values.get("channelId", "")
        if key in ("x", "youtube"):
            platform, target = key, None
        elif key.startswith("telegram:") and ID.fullmatch(key[9:]):
            platform, target = "telegram", key[9:]
        else:
            raise ApiError(400, "INVALID_CHANNEL", "Choose a valid news channel")
        query = values.get("query", "").strip()
        if len(query) > 500:
            raise ApiError(400, "INVALID_QUERY", "Search is limited to 500 characters")
        try:
            limit = int(values.get("limit", "30"))
            if not 1 <= limit <= 100:
                raise ValueError()
        except ValueError:
            raise ApiError(400, "INVALID_LIMIT", "Choose a page size between 1 and 100") from None
        cursor = None
        if values.get("cursor"):
            try:
                raw = values["cursor"]
                if len(raw) > 2048:
                    raise ValueError()
                cursor = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
                if not isinstance(cursor, dict) or set(cursor) != {"v", "t", "id", "scope"} or cursor["v"] != 1 or type(cursor["t"]) is not int or not ID.fullmatch(cursor["id"]):
                    raise ValueError()
                if cursor["scope"] != hashlib.sha256((key + "\n" + query).encode()).hexdigest()[:24]:
                    raise ValueError()
            except (TypeError, ValueError, KeyError):
                raise ApiError(400, "INVALID_CURSOR", "Reload this channel before continuing") from None
        with self.connection() as connection:
            where = self.base_where(connection) + " AND r.plugin_id=? AND COALESCE(NULLIF(r.created_at,''),r.observed_at)>=?"
            arguments: list = [platform, self.cutoff()]
            if target:
                where += " AND r.target_id=?"
                arguments.append(target)
            if query:
                where += " AND (instr(lower(r.title),lower(?))>0 OR instr(lower(r.text),lower(?))>0 OR instr(lower(r.source_name),lower(?))>0)"
                arguments.extend((query, query, query))
            total = connection.execute("SELECT COUNT(*) FROM records r WHERE " + where, arguments).fetchone()[0]
            if cursor:
                where += " AND (" + PUBLISHED_SQL + "<? OR (" + PUBLISHED_SQL + "=? AND r.record_id<?))"
                arguments.extend((cursor["t"], cursor["t"], cursor["id"]))
            rows = connection.execute("SELECT r.*," + PUBLISHED_SQL + " AS sort_ms FROM records r WHERE " + where + " ORDER BY sort_ms DESC,r.record_id DESC LIMIT ?", (*arguments, limit + 1)).fetchall()
            has_more = len(rows) > limit
            rows = rows[:limit]
            derived = self.derived_media([row["record_id"] for row in rows])
            posts = [self.post(connection, row, derived.get(row["record_id"], [])) for row in rows]
            next_cursor = None
            if has_more and rows:
                last = rows[-1]
                payload = {"v": 1, "t": last["sort_ms"], "id": last["record_id"], "scope": hashlib.sha256((key + "\n" + query).encode()).hexdigest()[:24]}
                next_cursor = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
            return {"posts": posts, "nextCursor": next_cursor, "total": total}

    def media_path(self, row: sqlite3.Row) -> Path:
        relative = Path(row["relative_path"])
        if relative.is_absolute() or ".." in relative.parts or not relative.parts or relative.parts[0] != "media":
            raise ApiError(403, "MEDIA_PATH_FORBIDDEN", "This attachment has an invalid storage location")
        candidate = self.runtime / relative
        try:
            resolved = candidate.resolve(strict=True)
        except (FileNotFoundError, OSError):
            raise ApiError(410, "MEDIA_EXPIRED", "This server attachment has expired") from None
        if not resolved.is_relative_to(self.media_root) or candidate.is_symlink():
            raise ApiError(403, "MEDIA_PATH_FORBIDDEN", "This attachment has an invalid storage location")
        try:
            info = resolved.stat()
        except OSError:
            raise ApiError(410, "MEDIA_EXPIRED", "This server attachment has expired") from None
        if not stat.S_ISREG(info.st_mode) or info.st_size != row["byte_size"]:
            raise ApiError(410, "MEDIA_EXPIRED", "This server attachment is no longer available")
        return resolved

    def derived_media(self, record_ids: list[str] | None = None, identity: str | None = None) -> dict[str, list[sqlite3.Row]]:
        """Read Frontier's already cached media, without fetching origin URLs."""
        database = self.runtime / "frontier/events.sqlite3"
        if not database.is_file() or not record_ids and not identity:
            return {}
        with self.connection(database) as connection:
            if not connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='media_assets'").fetchone():
                return {}
            if identity:
                rows = connection.execute("SELECT * FROM media_assets WHERE id=? AND state='ready'", (identity,))
            else:
                slots = ",".join("?" for _ in record_ids)
                rows = connection.execute("SELECT * FROM media_assets WHERE state='ready' AND record_id IN (" + slots + ") ORDER BY position,id", record_ids)
            result: dict[str, list[sqlite3.Row]] = {}
            for row in rows:
                result.setdefault(row["record_id"], []).append(row)
            return result

    def derived_attachment(self, row: sqlite3.Row) -> tuple[dict, Path]:
        value = row["relative_path"]
        relative = Path(value) if isinstance(value, str) else Path()
        if relative.is_absolute() or ".." in relative.parts or relative.parts[:2] != ("frontier", "media"):
            raise ApiError(403, "MEDIA_PATH_FORBIDDEN", "This attachment has an invalid storage location")
        if not isinstance(row["sha256"], str) or not re.fullmatch(r"[a-f0-9]{64}", row["sha256"]):
            raise ApiError(410, "MEDIA_EXPIRED", "This server attachment is no longer available")
        candidate = self.runtime / relative
        try:
            resolved = candidate.resolve(strict=True)
        except (FileNotFoundError, OSError):
            raise ApiError(410, "MEDIA_EXPIRED", "This server attachment has expired") from None
        if not resolved.is_relative_to(self.runtime / "frontier/media") or candidate.is_symlink():
            raise ApiError(403, "MEDIA_PATH_FORBIDDEN", "This attachment has an invalid storage location")
        info = resolved.stat()
        if not stat.S_ISREG(info.st_mode):
            raise ApiError(410, "MEDIA_EXPIRED", "This server attachment is no longer available")
        mime = row["mime_type"] or "application/octet-stream"
        extension = {"image/webp": ".webp", "image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif"}.get(mime, "")
        metadata = {"attachment_id": row["id"], "record_id": row["record_id"], "relative_path": value, "file_name": (row["kind"] or "image") + extension, "mime_type": mime, "byte_size": info.st_size, "sha256": row["sha256"]}
        return metadata, resolved

    def post(self, connection: sqlite3.Connection, row: sqlite3.Row, derived: list[sqlite3.Row] | None = None) -> dict:
        payload = object_json(row["payload_json"])
        media = []
        for attachment in connection.execute("SELECT * FROM attachments WHERE record_id=? ORDER BY attachment_index,attachment_id", (row["record_id"],)):
            mime = attachment["mime_type"] or "application/octet-stream"
            index = attachment["attachment_index"]
            role = "avatar" if index == payload.get("avatar_attachment_index") else "thumbnail" if index == payload.get("document_thumbnail_index") else "image" if mime.startswith("image/") else "video" if mime.startswith("video/") else "audio" if mime.startswith("audio/") else "document"
            try:
                self.media_path(attachment)
                available = True
            except ApiError:
                available = False
            item = {"id": attachment["attachment_id"], "name": attachment["file_name"], "mimeType": mime, "bytes": attachment["byte_size"], "sha256": attachment["sha256"], "role": role, "available": available}
            for dimension in ("width", "height"):
                if attachment[dimension]:
                    item[dimension] = attachment[dimension]
            media.append(item)
        seen_ids = {item["id"] for item in media}
        seen_hashes = {item["sha256"] for item in media if item["sha256"]}
        for asset in derived or []:
            if asset["id"] in seen_ids or asset["attachment_id"] in seen_ids or asset["sha256"] in seen_hashes:
                continue
            try:
                attachment, _path = self.derived_attachment(asset)
            except ApiError:
                continue
            mime = attachment["mime_type"]
            role = "avatar" if asset["kind"] == "avatar" else "thumbnail" if asset["origin"] == "document_thumbnail" else "image" if mime.startswith("image/") else "video" if mime.startswith("video/") else "audio" if mime.startswith("audio/") else "document"
            media.append({"id": asset["id"], "name": attachment["file_name"], "mimeType": mime, "bytes": attachment["byte_size"], "sha256": attachment["sha256"], "role": role, "available": True})
            seen_ids.add(asset["id"])
            seen_hashes.add(attachment["sha256"])
        result = {"id": row["record_id"], "channelId": channel_id(row["plugin_id"], row["target_id"]), "sourceId": row["target_id"], "sourceName": row["source_name"], "platform": row["plugin_id"], "title": row["title"] or "", "body": row["text"] or "", "publishedAt": row["sort_ms"] or milliseconds(row["observed_at"]), "media": media}
        url = safe_url(row["source_url"])
        if url:
            result["url"] = url
        if row["plugin_id"] == "telegram":
            original = payload.get("publication_metadata", {})
            original = original.get("telegram", {}) if isinstance(original, dict) else {}
            original = original if isinstance(original, dict) else {}
            telegram = {}
            group = original.get("groupId") or payload.get("grouped_id") or row["group_id"]
            if group is not None:
                telegram["groupId"] = str(group)
            for field in ("views", "subscriberCount"):
                if type(original.get(field)) is int and original[field] >= 0:
                    telegram[field] = original[field]
            forwarded = original.get("forwardedFrom") or payload.get("forwarded_from")
            if isinstance(forwarded, str) and forwarded.strip():
                telegram["forwardedFrom"] = forwarded.strip()[:200]
            if original.get("editedAt"):
                telegram["editedAt"] = milliseconds(original["editedAt"])
            reactions = original.get("reactions")
            if isinstance(reactions, list):
                telegram["reactions"] = [{"emoji": item["emoji"], "count": item["count"]} for item in reactions[:32] if isinstance(item, dict) and isinstance(item.get("emoji"), str) and len(item["emoji"]) < 80 and type(item.get("count")) is int and item["count"] >= 0]
            if telegram:
                result["telegram"] = telegram
        return result

    def attachment(self, identity: str):
        if identity.startswith("avatar."):
            return self.channel_avatar(identity[7:])
        if not ID.fullmatch(identity):
            raise ApiError(400, "INVALID_MEDIA_ID", "Choose a valid attachment")
        with self.connection() as connection:
            where = self.base_where(connection)
            row = connection.execute("SELECT a.* FROM attachments a JOIN records r ON r.record_id=a.record_id WHERE a.attachment_id=? AND " + where + " AND COALESCE(NULLIF(r.created_at,''),r.observed_at)>=?", (identity, self.cutoff())).fetchone()
        if row:
            return row, self.media_path(row)
        derived = self.derived_media(identity=identity)
        for record_id, assets in derived.items():
            with self.connection() as connection:
                visible = connection.execute("SELECT 1 FROM records r WHERE r.record_id=? AND " + self.base_where(connection) + " AND COALESCE(NULLIF(r.created_at,''),r.observed_at)>=?", (record_id, self.cutoff())).fetchone()
            if visible:
                return self.derived_attachment(assets[0])
        raise ApiError(410, "MEDIA_EXPIRED", "This server attachment has expired or is unavailable")

    def status(self) -> dict:
        collector = {}
        try:
            file = self.runtime / "frontier/collector-status.json"
            if file.stat().st_size <= 2 * 1024 * 1024:
                saved = object_json(file.read_text(encoding="utf-8"))
                collector = {key: saved[key] for key in ("ready", "started_at", "updated_at", "mode", "external_publication") if isinstance(saved.get(key), (str, bool, int, float))}
                collector["statusUpdatedAt"] = round(file.stat().st_mtime * 1000)
        except (OSError, ValueError):
            pass
        with self.connection() as connection:
            latest = connection.execute("SELECT MAX(observed_at) FROM records WHERE plugin_id IN ('telegram','x','youtube')").fetchone()[0]
        return {"service": "frontier-channels", "version": 1, "available": True, "retentionDays": RETENTION_DAYS, "latestCollectedAt": milliseconds(latest), "collector": collector}


def byte_range(value: str | None, size: int) -> tuple[int, int, int]:
    if not value:
        return 0, size - 1, 200
    match = re.fullmatch(r"bytes=(\d{0,20})-(\d{0,20})", value.strip())
    if not match or size <= 0 or not any(match.groups()):
        raise ApiError(416, "INVALID_RANGE", "The requested byte range is unavailable")
    left, right = match.groups()
    if not left:
        suffix = int(right)
        if suffix <= 0:
            raise ApiError(416, "INVALID_RANGE", "The requested byte range is unavailable")
        start, end = max(0, size - suffix), size - 1
    else:
        start, end = int(left), min(int(right), size - 1) if right else size - 1
        if start >= size or end < start:
            raise ApiError(416, "INVALID_RANGE", "The requested byte range is unavailable")
    return start, end, 206


class ChannelServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, provider: Provider):
        self.provider = provider
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    server: ChannelServer
    protocol_version = "HTTP/1.1"
    server_version = "FrontierChannels/1"

    def log_message(self, *_args):
        pass  # Do not log bearer credentials, queries, or news contents.

    def setup(self):
        super().setup()
        self.connection.settimeout(45)

    def send_headers(self, status: int, content_type: str, size: int, extra=None):
        self.send_response(status)
        for key, value in {"Content-Type": content_type, "Content-Length": str(size), "Cache-Control": "no-store, private", "Pragma": "no-cache", "X-Content-Type-Options": "nosniff", **(extra or {})}.items():
            self.send_header(key, value)
        self.end_headers()

    def json(self, value, status=200, extra=None):
        encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()
        self.send_headers(status, "application/json; charset=utf-8", len(encoded), extra)
        if self.command != "HEAD":
            self.wfile.write(encoded)

    def do_GET(self):
        try:
            if len(self.path) > 16384:
                raise ApiError(414, "URL_TOO_LONG", "The request is too long")
            supplied = self.headers.get("Authorization", "")
            expected = "Bearer " + self.server.provider.token
            if not hmac.compare_digest(supplied.encode(), expected.encode()):
                raise ApiError(401, "UNAUTHORIZED", "Channel authentication is required")
            url = urlsplit(self.path)
            parsed = parse_qs(url.query, keep_blank_values=True, max_num_fields=12)
            if any(len(values) != 1 for values in parsed.values()):
                raise ApiError(400, "INVALID_QUERY", "Repeated query parameters are not supported")
            values = {key: value[0] for key, value in parsed.items()}
            provider = self.server.provider
            if url.path == "/v1/channels" and not values:
                self.json(provider.channels())
            elif url.path == "/v1/status" and not values:
                self.json(provider.status())
            elif url.path == "/v1/posts" and set(values) <= {"channelId", "cursor", "limit", "query"}:
                self.json(provider.posts(values))
            elif url.path.startswith("/v1/media/") and not values:
                self.send_media(unquote(url.path[len("/v1/media/"):]))
            else:
                raise ApiError(404, "NOT_FOUND", "Unknown channel endpoint")
        except ApiError as error:
            self.json({"error": str(error), "code": error.code}, error.status)
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            self.close_connection = True
        except (sqlite3.Error, OSError):
            self.json({"error": "Frontier is temporarily unavailable", "code": "PROVIDER_UNAVAILABLE"}, 503)
        except ValueError:
            self.json({"error": "Invalid channel request", "code": "INVALID_REQUEST"}, 400)

    def do_HEAD(self):
        self.do_GET()

    def do_POST(self):
        try:
            supplied = self.headers.get("Authorization", "")
            expected = "Bearer " + self.server.provider.token
            if not hmac.compare_digest(supplied.encode(), expected.encode()):
                raise ApiError(401, "UNAUTHORIZED", "Channel authentication is required")
            url = urlsplit(self.path)
            if url.path != "/v1/read" or url.query:
                raise ApiError(404, "NOT_FOUND", "Unknown channel endpoint")
            size = self.headers.get("Content-Length", "")
            if not size.isascii() or not size.isdecimal() or not 1 <= int(size) <= 32768:
                raise ApiError(413, "INVALID_LENGTH", "Read receipt is too large")
            if self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
                raise ApiError(415, "INVALID_CONTENT_TYPE", "Read receipt must be JSON")
            try:
                payload = json.loads(self.rfile.read(int(size)))
            except (UnicodeDecodeError, json.JSONDecodeError):
                raise ApiError(400, "INVALID_JSON", "Invalid read receipt JSON") from None
            self.json(self.server.provider.acknowledge_read(payload))
        except ApiError as error:
            self.json({"error": str(error), "code": error.code}, error.status)
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            self.close_connection = True
        except (sqlite3.Error, OSError):
            self.json({"error": "Channel read status is temporarily unavailable", "code": "READ_STATE_UNAVAILABLE"}, 503)


    def send_media(self, identity: str):
        row, path = self.server.provider.attachment(identity)
        source = io.BytesIO(path) if isinstance(path, bytes) else os.fdopen(os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)), "rb")
        with source:
            size = row["byte_size"]
            if not isinstance(path, bytes):
                info = os.fstat(source.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_size != size:
                    raise ApiError(410, "MEDIA_EXPIRED", "This server attachment is no longer available")
            etag = '"' + row["sha256"] + '"'
            requested = self.headers.get("Range")
            if self.headers.get("If-Range") not in (None, etag):
                requested = None
            try:
                start, end, status = byte_range(requested, size)
            except ApiError as error:
                self.json({"error": str(error), "code": error.code}, 416, {"Content-Range": f"bytes */{size}", "Accept-Ranges": "bytes"})
                return
            count = max(0, end - start + 1)
            extra = {"Accept-Ranges": "bytes", "ETag": etag}
            if status == 206:
                extra["Content-Range"] = f"bytes {start}-{end}/{size}"
            # Never trust collector-provided strings as raw HTTP headers.
            mime = row["mime_type"] or "application/octet-stream"
            if not re.fullmatch(r"[\w.+-]+/[\w.+-]+", mime):
                mime = "application/octet-stream"
            from urllib.parse import quote
            extra["Content-Disposition"] = "inline; filename*=UTF-8''" + quote(Path(row["file_name"]).name, safe="")
            self.send_headers(status, mime, count, extra)
            if self.command == "HEAD":
                return
            source.seek(start)
            while count:
                chunk = source.read(min(128 * 1024, count))
                if not chunk:
                    self.close_connection = True
                    return
                self.wfile.write(chunk)
                count -= len(chunk)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8091)
    parser.add_argument("--token-file", type=Path)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("Choose a port between 1024 and 65535")
    provider = Provider(args.root, args.token_file)
    server = ChannelServer(("127.0.0.1", args.port), provider)
    print(f"Frontier channels listening on 127.0.0.1:{args.port}", flush=True)
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
