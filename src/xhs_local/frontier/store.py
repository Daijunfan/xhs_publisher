"""Durable event storage. The original collector database is read through SQLite mode=ro."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .media import collect_media, media_for, upsert_media
from .migrations import migrate
from .models import event_key, iso_time, now_iso, raw_fingerprint, safe_url
from .preferences import Preferences, ProductError, validate_days

SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS schema_version(version INTEGER NOT NULL);
INSERT INTO schema_version SELECT 1 WHERE NOT EXISTS(SELECT 1 FROM schema_version);
CREATE TABLE IF NOT EXISTS events(
 id TEXT PRIMARY KEY, title TEXT NOT NULL, summary TEXT NOT NULL, category TEXT NOT NULL,
 importance INTEGER NOT NULL, event_time_start TEXT, location_status TEXT NOT NULL,
 data TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS events_importance ON events(importance DESC,id);
CREATE INDEX IF NOT EXISTS events_time ON events(event_time_start DESC,id);
CREATE TABLE IF NOT EXISTS raw_records(
 record_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, content_hash TEXT NOT NULL,
 plugin_id TEXT NOT NULL, source_name TEXT NOT NULL, source_url TEXT,
 title TEXT NOT NULL, text TEXT NOT NULL, source_published_at TEXT, ingested_at TEXT NOT NULL,
 images TEXT NOT NULL DEFAULT '[]', state TEXT NOT NULL DEFAULT 'pending',
 attempts INTEGER NOT NULL DEFAULT 0, next_attempt REAL NOT NULL DEFAULT 0,
 lease_until REAL NOT NULL DEFAULT 0, error TEXT,
 event_id TEXT REFERENCES events(id) ON DELETE SET NULL, updated_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS raw_pending ON raw_records(state,next_attempt,ingested_at DESC);
CREATE INDEX IF NOT EXISTS raw_event ON raw_records(event_id);
CREATE INDEX IF NOT EXISTS raw_fingerprint ON raw_records(fingerprint,state);
CREATE TABLE IF NOT EXISTS bookmarks(
 owner TEXT NOT NULL, event_id TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
 created_at TEXT NOT NULL, PRIMARY KEY(owner,event_id));
CREATE TABLE IF NOT EXISTS sessions(
 token_hash TEXT PRIMARY KEY, owner TEXT NOT NULL, csrf TEXT NOT NULL,
 expires_at REAL NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS usage(
 day TEXT PRIMARY KEY, items INTEGER NOT NULL DEFAULT 0, requests INTEGER NOT NULL DEFAULT 0,
 prompt_tokens INTEGER NOT NULL DEFAULT 0, completion_tokens INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS audit(
 id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, owner TEXT NOT NULL,
 action TEXT NOT NULL, target TEXT, details TEXT NOT NULL DEFAULT '{}');
CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
"""

# This lane only changes *which existing pending originals get a model turn*.
# It intentionally shares Radar's raw-preview horizon, not its editorial scores:
# importance cannot be known until after enrichment. Bounds limit work per batch
# regardless of how many older messages or subscriptions have accumulated.
_PRIORITY_RECENT_HOURS = 48
_PRIORITY_SCAN_CAP = 1200
_PRIORITY_MAX_PER_BATCH = 2
_PRIORITY_PLAN_TOPICS = {"free": 1, "pro": 10, "analyst": 30}
_PRIORITY_PLATFORMS = frozenset(("telegram", "x", "youtube"))
_PRIORITY_CURSOR_KEY = "radar_priority_cursor_v4"

# Use exactly the Radar SQL `lower()` keyword comparison: ASCII A-Z only.
# Do not normalize NFKC or map traditional/simplified Chinese: an item must
# satisfy the same literal terms after enrichment, avoiding misleading picks.
_PRIORITY_ASCII_LOWER = str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz")


def _priority_fold(text: str) -> str:
    """Mirror SQLite lower() on ordinary UTF-8 strings (ASCII case only)."""
    return text.translate(_PRIORITY_ASCII_LOWER)


class Store:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        with self.connect() as c:
            c.execute("PRAGMA journal_mode=WAL")
            c.executescript(SCHEMA)
            migrate(c)

    @contextmanager
    def connect(self):
        with self.lock:
            c = sqlite3.connect(self.path, timeout=15)
            c.row_factory = sqlite3.Row
            c.execute("PRAGMA foreign_keys=ON")
            try:
                with c:
                    yield c
            finally:
                c.close()

    def set_meta(self, key: str, value: Any):
        with self.connect() as c:
            c.execute(
                "INSERT INTO metadata VALUES(?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, json.dumps(value, ensure_ascii=False)),
            )

    def get_meta(self, key: str, default=None):
        with self.connect() as c:
            row = c.execute("SELECT value FROM metadata WHERE key=?", (key,)).fetchone()
            return json.loads(row[0]) if row else default

    @staticmethod
    def _sync_reads(c):
        c.execute("INSERT OR IGNORE INTO event_reads(owner,event_id,read_at) "
                  "SELECT rr.owner,r.event_id,min(rr.read_at) FROM raw_reads rr "
                  "JOIN raw_records r ON r.record_id=rr.record_id WHERE r.event_id IS NOT NULL "
                  "GROUP BY rr.owner,r.event_id")
        c.execute("INSERT OR IGNORE INTO raw_reads(owner,record_id,read_at) "
                  "SELECT er.owner,r.record_id,er.read_at FROM event_reads er "
                  "JOIN raw_records r ON r.event_id=er.event_id")

    def import_records(self, source_path: Path, limit: int = 10000) -> int:
        if not Path(source_path).is_file():
            self.set_meta("import_error", "collector_database_missing")
            return 0
        source = sqlite3.connect(
            Path(source_path).resolve().as_uri() + "?mode=ro", uri=True, timeout=8
        )
        source.row_factory = sqlite3.Row
        # A media algorithm upgrade replays originals once, then resumes the
        # incremental cursor. This repairs prior truncated galleries without
        # resetting reading state or re-enriching unchanged text.
        cursor = self.get_meta("collector_cursor_v2") if self.get_meta("collector_media_revision") == 2 else None
        next_cursor = None
        try:
            source.execute("BEGIN")
            columns = {r[1] for r in source.execute("PRAGMA table_info(records)")}
            optional = lambda name, fallback: name if name in columns else fallback + " AS " + name
            fields = (
                "record_id,content_hash,plugin_id,source_name,source_url,title,text,"
                "occurred_at,observed_at,payload_json,content_type,"
                + optional("target_id", "''") + "," + optional("source_id", "''") + ","
                + optional("group_id", "NULL") + "," + optional("created_at", "observed_at") + ","
                + optional("external_id", "''")
            )
            where = "content_type IN ('tech_news','video_pending') AND plugin_id IN ('telegram','x','youtube')"
            args = []
            if "updated_at" in columns:
                fields += ",updated_at"
                if cursor:
                    where += " AND (updated_at>? OR (updated_at=? AND record_id>?))"
                    args += [cursor["updated_at"], cursor["updated_at"], cursor["record_id"]]
                order = "updated_at,record_id"
            else:
                order = "observed_at DESC,record_id"
            rows = source.execute(
                "SELECT " + fields + " FROM records WHERE " + where + " ORDER BY " + order + " LIMIT ?",
                (*args, min(50000, max(1, int(limit)))),
            ).fetchall()
            if rows and "updated_at" in columns:
                next_cursor = {"updated_at": rows[-1]["updated_at"], "record_id": rows[-1]["record_id"]}
            # A newly received album member must refresh media for earlier caption records too.
            groups = {(r["source_id"], r["target_id"], r["group_id"]) for r in rows
                      if r["plugin_id"] == "telegram" and r["group_id"]}
            by_id = {r["record_id"]: r for r in rows}
            for source_id, target_id, group_id in groups:
                for sibling in source.execute("SELECT " + fields + " FROM records WHERE source_id=? AND target_id=? AND group_id=? AND plugin_id='telegram'",
                                              (source_id, target_id, group_id)):
                    by_id[sibling["record_id"]] = sibling
            rows = list(by_id.values())
            assets = collect_media(source, rows, Path(source_path).resolve().parent) if rows else {}
        finally:
            source.close()
        count = 0
        stamp = now_iso()
        with self.connect() as c:
            for row in rows:
                raw = dict(row)
                fp = raw_fingerprint(raw)
                published_at = iso_time(raw["occurred_at"])
                ingested_at = iso_time(raw["observed_at"])
                first_at = iso_time(raw["created_at"]) or ingested_at or stamp
                source_url = safe_url(raw["source_url"])
                images = json.dumps([
                    "/api/media/" + a["id"] for a in assets.get(raw["record_id"], []) if a["state"] == "ready"
                ])
                existing = c.execute("SELECT * FROM raw_records WHERE record_id=?", (raw["record_id"],)).fetchone()
                ingested_at = ingested_at or (existing["ingested_at"] if existing else stamp)
                if existing and "created_at" not in columns:
                    first_at = min(first_at, existing["first_ingested_at"] or existing["ingested_at"])
                # Exact-text metadata and media corrections do not consume another model request.
                if existing and existing["fingerprint"] == fp and existing["content_type"] == raw["content_type"]:
                    incoming = (raw["content_hash"], raw["plugin_id"], raw["source_name"], source_url,
                                published_at, ingested_at, first_at, raw["target_id"], raw["title"], raw["text"], images)
                    previous = tuple(existing[k] for k in ("content_hash", "plugin_id", "source_name", "source_url",
                                                          "source_published_at", "ingested_at", "first_ingested_at", "target_id", "title", "text", "images"))
                    changed = incoming != previous
                    c.execute(
                        "UPDATE raw_records SET content_hash=?,plugin_id=?,source_name=?,source_url=?,"
                        "source_published_at=?,ingested_at=?,first_ingested_at=?,target_id=?,"
                        "title=?,text=?,images=?,updated_at=? WHERE record_id=?",
                        (raw["content_hash"], raw["plugin_id"], raw["source_name"], source_url,
                         published_at, ingested_at, first_at, raw["target_id"], raw["title"], raw["text"],
                         images, stamp, raw["record_id"]),
                    )
                    upsert_media(c, raw["record_id"], assets.get(raw["record_id"], []))
                    count += int(changed)
                    continue
                duplicate = c.execute(
                    "SELECT event_id FROM raw_records WHERE fingerprint=? AND state='completed' LIMIT 1", (fp,)
                ).fetchone()
                event_id = duplicate[0] if duplicate else None
                state = "completed" if event_id else "pending"
                if raw["content_type"] == "video_pending":
                    state, event_id = "awaiting_video", None
                elif not (raw["title"] + raw["text"]).strip():
                    state = "filtered"
                c.execute(
                    "INSERT INTO raw_records(record_id,fingerprint,content_hash,plugin_id,source_name,source_url,"
                    "title,text,source_published_at,ingested_at,first_ingested_at,target_id,content_type,"
                    "images,state,event_id,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
                    "ON CONFLICT(record_id) DO UPDATE SET fingerprint=excluded.fingerprint,"
                    "content_hash=excluded.content_hash,plugin_id=excluded.plugin_id,source_name=excluded.source_name,"
                    "source_url=excluded.source_url,source_published_at=excluded.source_published_at,"
                    "ingested_at=excluded.ingested_at,first_ingested_at=excluded.first_ingested_at,"
                    "target_id=excluded.target_id,content_type=excluded.content_type,title=excluded.title,"
                    "text=excluded.text,images=excluded.images,state=excluded.state,attempts=0,next_attempt=0,"
                    "lease_until=0,error=NULL,event_id=excluded.event_id,updated_at=excluded.updated_at",
                    (raw["record_id"], fp, raw["content_hash"], raw["plugin_id"], raw["source_name"], source_url,
                     raw["title"], raw["text"], published_at, ingested_at, first_at, raw["target_id"],
                     raw["content_type"], images, state, event_id, stamp),
                )
                upsert_media(c, raw["record_id"], assets.get(raw["record_id"], []))
                count += 1
            self._sync_reads(c)
            # A source can be edited or enriched, so use the current earliest source timestamp.
            c.execute(
                "UPDATE events SET first_ingested_at=coalesce((SELECT min(first_ingested_at) "
                "FROM raw_records r WHERE r.event_id=events.id),first_ingested_at,created_at)"
            )
            c.execute(
                "DELETE FROM events WHERE id NOT IN (SELECT event_id FROM raw_records WHERE event_id IS NOT NULL) "
                "AND id NOT IN (SELECT event_id FROM bookmarks) AND id NOT IN (SELECT event_id FROM event_reads)"
            )
        if next_cursor:
            self.set_meta("collector_cursor_v2", next_cursor)
        self.set_meta("collector_media_revision", 2)
        self.set_meta("last_import_at", stamp)
        self.set_meta("import_error", None)
        return count

    @staticmethod
    def _priority_topics(c) -> list[tuple[str, frozenset[str], tuple[str, ...]]]:
        """Only the canonical single-user owner's *entitled* topic prefix.

        Plan matches Radar's server-side FRONTIER_PLAN configuration. Topics
        beyond the current plan's oldest-first limit stay saved but suspended.
        Malformed local topic data cannot break the normal enrichment queue.
        """
        plan = os.getenv("FRONTIER_PLAN", "analyst").strip().lower()
        allowed = _PRIORITY_PLAN_TOPICS.get(plan, 0)
        if not allowed:
            return []
        rows = c.execute(
            "SELECT id,query,platforms FROM radar_topics WHERE owner=? "
            "ORDER BY created_at,id LIMIT ?", ("owner", allowed),
        ).fetchall()
        topics = []
        for row in rows:
            try:
                platforms = json.loads(row["platforms"])
            except (TypeError, ValueError):
                continue
            if (not isinstance(platforms, list) or not platforms
                    or len(set(str(item) for item in platforms)) != len(platforms)
                    or any(type(item) is not str or item not in _PRIORITY_PLATFORMS
                           for item in platforms)):
                continue
            query = row["query"]
            if not isinstance(query, str):
                continue
            terms = tuple(_priority_fold(item) for item in query.split())
            if not 1 <= len(terms) <= 8:
                continue
            topics.append((row["id"], frozenset(platforms), terms))
        return topics

    @staticmethod
    def _priority_ids(c, stamp: float, limit: int) -> list[str]:
        """Find at most two conservatively relevant *originals* per batch.

        No joins to derived events, no inferred importance and no full backlog
        scan: the existing first-ingestion index bounds the 48-hour candidate
        pool to 1200 eligible rows. Matching is on the first 12k text characters
        the worker actually sends, plus the title; not source names or URLs.
        """
        slots = min(_PRIORITY_MAX_PER_BATCH, max(1, limit // 3))
        topics = Store._priority_topics(c)
        if not topics:
            return []
        now = datetime.now(UTC)
        rows = c.execute(
            "SELECT record_id,plugin_id,title,substr(text,1,12000) AS text "
            "FROM raw_records INDEXED BY raw_first_ingested "
            "WHERE first_ingested_at>=? AND first_ingested_at<=? "
            "AND event_id IS NULL AND state IN ('pending','retry') "
            "AND next_attempt<=? AND attempts<4 "
            "ORDER BY first_ingested_at DESC,record_id LIMIT ?",
            ((now - timedelta(hours=_PRIORITY_RECENT_HOURS)).isoformat(timespec="milliseconds"),
             now.isoformat(timespec="milliseconds"), stamp, _PRIORITY_SCAN_CAP),
        ).fetchall()
        if not rows:
            return []

        by_platform: dict[str, list[tuple[str, tuple[str, ...]]]] = {
            platform: [(topic_id, terms) for topic_id, platforms, terms in topics
                       if platform in platforms]
            for platform in _PRIORITY_PLATFORMS
        }
        # Each topic/platform needs only two possible picks. Capture their
        # original recency rank so an alternate platform need not be stale.
        candidates: dict[str, list[tuple[int, str, str]]] = {
            topic_id: [] for topic_id, _, _ in topics
        }
        per_platform: dict[tuple[str, str], int] = {}
        for rank, row in enumerate(rows):
            platform = row["plugin_id"]
            tests = [
                (topic_id, terms)
                for topic_id, terms in by_platform.get(platform, ())
                if per_platform.get((topic_id, platform), 0) < slots
            ]
            if not tests:
                continue
            content = _priority_fold(row["title"] + " " + row["text"])
            for topic_id, terms in tests:
                key = (topic_id, platform)
                if all(term in content for term in terms):
                    candidates[topic_id].append((rank, row["record_id"], platform))
                    per_platform[key] = per_platform.get(key, 0) + 1
        if not any(candidates.values()):
            return []

        ids = [topic_id for topic_id, _, _ in topics]
        cursor_row = c.execute(
            "SELECT value FROM metadata WHERE key=?", (_PRIORITY_CURSOR_KEY,)
        ).fetchone()
        try:
            cursor = json.loads(cursor_row[0]) if cursor_row else None
        except ValueError:
            cursor = None
        start = (ids.index(cursor) + 1) % len(ids) if cursor in ids else 0
        order = ids[start:] + ids[:start]
        selected: list[str] = []
        used: set[str] = set()
        platforms_used: set[str] = set()
        last_topic = None
        while len(selected) < slots:
            progress = False
            for topic_id in order:
                options = sorted(
                    (item for item in candidates[topic_id] if item[1] not in used),
                    key=lambda item: item[0],
                )
                if not options:
                    continue
                # Prefer distinct platforms among priority picks without
                # sacrificing per-topic round-robin fairness.
                chosen = next((item for item in options if item[2] not in platforms_used),
                              options[0])
                selected.append(chosen[1])
                used.add(chosen[1])
                platforms_used.add(chosen[2])
                last_topic = topic_id
                progress = True
                if len(selected) == slots:
                    break
            if not progress:
                break
        if last_topic is not None:
            c.execute(
                "INSERT INTO metadata(key,value) VALUES(?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (_PRIORITY_CURSOR_KEY, json.dumps(last_topic)),
            )
        return selected

    def claim(self, limit: int = 6) -> list[dict]:
        stamp = time.time()
        with self.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            c.execute(
                "UPDATE raw_records SET state='pending',lease_until=0 "
                "WHERE state='processing' AND lease_until<?",
                (stamp,),
            )
            # Exact duplicates of an already analysed text cost no second model request.
            c.execute("""UPDATE raw_records SET state='completed',
                         event_id=(SELECT d.event_id FROM raw_records d
                         WHERE d.fingerprint=raw_records.fingerprint AND d.state='completed'
                         AND d.event_id IS NOT NULL LIMIT 1)
                         WHERE state='pending' AND EXISTS(
                         SELECT 1 FROM raw_records d WHERE d.fingerprint=raw_records.fingerprint
                         AND d.state='completed' AND d.event_id IS NOT NULL)""")
            self._sync_reads(c)
            # A zero-topic/disabled run takes precisely the V3 query and order.
            # The optional lane changes only which originals occupy up to two
            # slots, leaving at least four of a normal six for platform RR.
            priority_ids = (
                self._priority_ids(c, stamp, limit)
                if limit > 0 and os.getenv("FRONTIER_PRIORITY_ENRICHMENT", "1") != "0"
                else []
            )
            rows = c.execute(
                """SELECT * FROM (
                     SELECT *,row_number() OVER(PARTITION BY plugin_id
                     ORDER BY ingested_at DESC,record_id) AS platform_rank
                     FROM raw_records WHERE state IN (\'pending\',\'retry\')
                     AND next_attempt<=? AND attempts<4)
                   ORDER BY platform_rank,ingested_at DESC,record_id LIMIT ?""",
                (stamp, limit + len(priority_ids)),
            ).fetchall()
            if priority_ids:
                priority_set = set(priority_ids)
                normal = [r for r in rows if r["record_id"] not in priority_set]
                normal = normal[:limit - len(priority_ids)]
                pins = ",".join("?" for _ in priority_ids)
                matched = {r["record_id"]: r for r in c.execute(
                    "SELECT * FROM raw_records WHERE record_id IN (" + pins + ")",
                    priority_ids,
                )}
                rows = [matched[identity] for identity in priority_ids] + normal
            for row in rows:
                c.execute(
                    "UPDATE raw_records SET state='processing',attempts=attempts+1,lease_until=? "
                    "WHERE record_id=?",
                    (stamp + 300, row["record_id"]),
                )
            return [dict(row) | {"attempts": row["attempts"] + 1} for row in rows]

    def complete(self, raw: dict, analysis: dict):
        stamp = now_iso()
        with self.connect() as c:
            # Ignore an obsolete model result if the original text changed during the request.
            latest = c.execute(
                "SELECT content_hash,fingerprint FROM raw_records WHERE record_id=?",
                (raw["record_id"],),
            ).fetchone()
            if (
                latest is None
                or latest["content_hash"] != raw["content_hash"]
                or latest["fingerprint"] != raw["fingerprint"]
            ):
                return
            if not analysis["is_event"]:
                c.execute(
                    "UPDATE raw_records SET state='filtered',error=NULL,lease_until=0 "
                    "WHERE record_id=?",
                    (raw["record_id"],),
                )
                return
            identity = event_key(analysis, raw["fingerprint"])
            data = {k: v for k, v in analysis.items() if k != "is_event"}
            data.update(id=identity, enrichment_status="completed", analysed_at=stamp)
            c.execute(
                """INSERT INTO events(id,title,summary,category,importance,event_time_start,location_status,data,created_at,updated_at,first_ingested_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET title=excluded.title,summary=excluded.summary,
                   category=excluded.category,importance=excluded.importance,
                   event_time_start=excluded.event_time_start,location_status=excluded.location_status,
                   data=excluded.data,updated_at=excluded.updated_at,
                   first_ingested_at=min(events.first_ingested_at,excluded.first_ingested_at)""",
                (
                    identity,
                    data["title"],
                    data["summary"],
                    data["category"],
                    data["importance"],
                    data["event_time_start"],
                    data["location_status"],
                    json.dumps(data, ensure_ascii=False),
                    stamp,
                    stamp,
                    raw.get("first_ingested_at") or raw["ingested_at"],
                ),
            )
            c.execute(
                "UPDATE raw_records SET state='completed',event_id=?,lease_until=0,error=NULL "
                "WHERE record_id=?",
                (identity, raw["record_id"]),
            )
            c.execute(
                "INSERT OR IGNORE INTO event_reads(owner,event_id,read_at) "
                "SELECT owner,?,read_at FROM raw_reads WHERE record_id=?",
                (identity, raw["record_id"]),
            )
            self._sync_reads(c)

    def fail(self, raw_id: str, error: str, permanent: bool = False):
        with self.connect() as c:
            row = c.execute(
                "SELECT attempts FROM raw_records WHERE record_id=?", (raw_id,)
            ).fetchone()
            if row is None:
                return
            attempts = row[0]
            state = "failed" if permanent or attempts >= 4 else "retry"
            c.execute(
                "UPDATE raw_records SET state=?,error=?,next_attempt=?,lease_until=0 "
                "WHERE record_id=?",
                (state, error[:150], time.time() + min(3600, 30 * 2**attempts), raw_id),
            )

    def release(self, raw_ids: list[str]):
        with self.connect() as c:
            c.executemany(
                "UPDATE raw_records SET state='pending',attempts=max(0,attempts-1),lease_until=0 "
                "WHERE record_id=? AND state='processing'",
                [(x,) for x in raw_ids],
            )

    def reserve_budget(self, count: int, daily_limit: int) -> bool:
        day = datetime.now(UTC).strftime("%Y-%m-%d")
        with self.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            c.execute("INSERT OR IGNORE INTO usage(day) VALUES(?)", (day,))
            used = c.execute("SELECT items FROM usage WHERE day=?", (day,)).fetchone()[0]
            if used + count > daily_limit:
                return False
            c.execute(
                "UPDATE usage SET items=items+?,requests=requests+1 WHERE day=?", (count, day)
            )
        return True

    def record_usage(self, usage: dict):
        day = datetime.now(UTC).strftime("%Y-%m-%d")

        def number(k):
            value = usage.get(k, 0)
            return max(0, int(value)) if isinstance(value, (int, float)) else 0

        with self.connect() as c:
            c.execute(
                "UPDATE usage SET prompt_tokens=prompt_tokens+?, "
                "completion_tokens=completion_tokens+? "
                "WHERE day=?",
                (number("prompt_tokens"), number("completion_tokens"), day),
            )

    @staticmethod
    def _reading_policy(c, owner: str, filters: dict | None = None) -> dict:
        f = filters or {}
        preference = Preferences._read(c, owner)
        settings = preference["settings"]
        days = settings["retention_days"]
        if "window_days" in f:
            value = f["window_days"]
            if isinstance(value, str) and value.isdecimal():
                value = int(value)
            days = validate_days(value)
        scope = f.get("scope", "active")
        if scope not in {"active", "archive", "all"}:
            raise ProductError("invalid_scope", "请选择当前窗口、归档或全部历史")
        read = f.get("read")
        if read is None:
            saved = f.get("bookmarked") in (True, "1", "true")
            read = "unread" if settings["hide_read"] and not saved else "all"
        if read not in {"all", "unread", "read"}:
            raise ProductError("invalid_read_filter", "已读筛选值无效")
        cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat(timespec="milliseconds") if days else None
        return {"settings_version": preference["version"], "retention_days": days, "retention_basis": settings["retention_basis"],
                "retention_mode": "archive", "retain_bookmarks": settings["retain_bookmarks"],
                "hide_read": settings["hide_read"], "effective_read": read, "scope": scope,
                "cutoff": cutoff}

    @staticmethod
    def _retention_value(first: str, published: str | None, policy: dict) -> str:
        return published or first if policy["retention_basis"] == "published" else first

    @staticmethod
    def _is_archived(retention_at: str, bookmarked: bool, policy: dict) -> bool:
        return bool(policy["cutoff"] and retention_at < policy["cutoff"]
                    and not (bookmarked and policy["retain_bookmarks"]))

    @staticmethod
    def _apply_policy(clauses, args, policy, *, retention_sql, read_sql, bookmark_sql, owner):
        if policy["effective_read"] != "all":
            clauses.append(("NOT " if policy["effective_read"] == "unread" else "") + read_sql)
            args.append(owner)
        if policy["scope"] == "all":
            return
        if not policy["cutoff"]:
            if policy["scope"] == "archive":
                clauses.append("0=1")
            return
        active = policy["scope"] == "active"
        condition = retention_sql + (">=?" if active else "<?")
        args.append(policy["cutoff"])
        if policy["retain_bookmarks"]:
            condition = "(" + condition + (" OR " if active else " AND NOT ") + bookmark_sql + ")"
            args.append(owner)
        clauses.append(condition)

    def _items(self, c, rows, owner: str, *, full=False, policy=None) -> list[dict]:
        policy = policy or self._reading_policy(c, owner)
        results = []
        for row in rows:
            item = json.loads(row["data"])
            sources = c.execute(
                "SELECT record_id,plugin_id,target_id,source_name,source_url,source_published_at,"
                "ingested_at,first_ingested_at,text,images FROM raw_records "
                "WHERE event_id=? AND state='completed' ORDER BY source_published_at,record_id", (row["id"],)
            ).fetchall()
            item["sources"] = [{"id": s["record_id"], "platform": s["plugin_id"], "source_id": s["target_id"],
                                "name": s["source_name"], "url": s["source_url"], "published_at": s["source_published_at"],
                                "text": s["text"] if full else s["text"][:500]} for s in sources]
            item["source_published_at"] = min((s["source_published_at"] for s in sources if s["source_published_at"]), default=None)
            item["ingested_at"] = max((s["ingested_at"] for s in sources), default=row["created_at"])
            item["first_ingested_at"] = row["first_ingested_at"] or row["created_at"]
            item["media"] = media_for(c, [s["record_id"] for s in sources])
            item["images"] = [m["url"] for m in item["media"] if m["status"] == "ready"]
            item["source_count"] = len(sources)
            item["confidence"] = "single_source"
            item["bookmarked"] = c.execute("SELECT 1 FROM bookmarks WHERE owner=? AND event_id=?", (owner, row["id"])).fetchone() is not None
            read = c.execute("SELECT read_at FROM event_reads WHERE owner=? AND event_id=?", (owner, row["id"])).fetchone()
            item["read"], item["read_at"] = read is not None, read[0] if read else None
            item["retention_at"] = self._retention_value(item["first_ingested_at"], item["source_published_at"], policy)
            item["archived"] = self._is_archived(item["retention_at"], item["bookmarked"], policy)
            results.append(item)
        return results

    def list_events(self, filters: dict | None = None, owner: str = "owner") -> dict:
        f = filters or {}
        clauses, args = ["1=1"], []
        if f.get("q"):
            clauses.append("(instr(lower(e.title||' '||e.summary),lower(?))>0 OR EXISTS(SELECT 1 FROM raw_records r WHERE r.event_id=e.id AND instr(lower(r.text||' '||r.source_name),lower(?))>0))")
            args.extend([str(f["q"])[:200]] * 2)
        for key in ["category", "location_status"]:
            if f.get(key):
                clauses.append("e." + key + "=?")
                args.append(f[key])
        if f.get("source"):
            if f["source"] not in {"telegram", "x", "youtube"}:
                raise ProductError("invalid_platform_filter", "来源平台无效")
            clauses.append("EXISTS(SELECT 1 FROM raw_records r WHERE r.event_id=e.id AND r.plugin_id=?)")
            args.append(f["source"])
        if f.get("source_id"):
            clauses.append("EXISTS(SELECT 1 FROM raw_records r WHERE r.event_id=e.id AND r.target_id=?)")
            args.append(str(f["source_id"])[:150])
        for key, op in [("after", ">="), ("before", "<")]:
            if f.get(key):
                boundary = iso_time(f[key])
                clauses.append("e.event_time_start " + op + " ?")
                args.append(boundary)
        bookmark_sql = "EXISTS(SELECT 1 FROM bookmarks b WHERE b.event_id=e.id AND b.owner=?)"
        if f.get("bookmarked") in (True, "1", "true"):
            clauses.append(bookmark_sql)
            args.append(owner)
        if f.get("min_importance"):
            clauses.append("e.importance>=?")
            args.append(max(0, min(100, int(f["min_importance"]))))
        with self.connect() as c:
            policy = self._reading_policy(c, owner, f)
            sort = f.get("sort", Preferences._read(c, owner)["settings"]["default_sort"])
            orders = {"importance": "e.importance DESC,e.event_time_start DESC,e.id",
                      "event_time": "e.event_time_start IS NULL,e.event_time_start DESC,e.importance DESC,e.id",
                      "discovered": "e.first_ingested_at DESC,e.id"}
            if sort not in orders:
                raise ValueError("invalid_sort")
            limit = min(200, max(1, int(f.get("limit", 60))))
            offset = min(1000000, max(0, int(f.get("offset", 0))))
            first = "coalesce(e.first_ingested_at,e.created_at)"
            published = "coalesce((SELECT min(r.source_published_at) FROM raw_records r WHERE r.event_id=e.id)," + first + ")"
            self._apply_policy(clauses, args, policy, retention_sql=published if policy["retention_basis"] == "published" else first,
                               read_sql="EXISTS(SELECT 1 FROM event_reads er WHERE er.event_id=e.id AND er.owner=?)",
                               bookmark_sql=bookmark_sql, owner=owner)
            where = " AND ".join(clauses)
            total = c.execute("SELECT count(*) FROM events e WHERE " + where, args).fetchone()[0]
            rows = c.execute("SELECT e.* FROM events e WHERE " + where + " ORDER BY " + orders[sort] + " LIMIT ? OFFSET ?", (*args, limit, offset)).fetchall()
            items = self._items(c, rows, owner, policy=policy)
            cats = [dict(x) for x in c.execute("SELECT category AS value,count(*) AS count FROM events GROUP BY category ORDER BY count DESC")]
            sources = [dict(x) for x in c.execute("SELECT plugin_id AS value,count(DISTINCT event_id) AS count FROM raw_records WHERE event_id IS NOT NULL GROUP BY plugin_id")]
        return {"items": items, "total": total, "limit": limit, "offset": offset,
                "facets": {"categories": cats, "sources": sources}, "stats": self.stats(),
                "policy": policy, "generated_at": now_iso()}

    def get_event(self, event_id: str, owner: str = "owner") -> dict | None:
        with self.connect() as c:
            rows = c.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchall()
            return self._items(c, rows, owner, full=True)[0] if rows else None

    @staticmethod
    def _validate_read_ids(ids, value):
        if type(value) is not bool:
            raise ProductError("invalid_read_state", "已读状态必须为 true 或 false")
        if not isinstance(ids, list) or not 1 <= len(ids) <= 200 or any(not isinstance(x, str) or not 1 <= len(x) <= 150 for x in ids):
            raise ProductError("invalid_read_ids", "每次可标记 1–200 条有效资讯")
        return list(dict.fromkeys(ids))

    def mark_read(self, ids, owner: str, value: bool, *, raw=False) -> dict:
        ids = self._validate_read_ids(ids, value)
        stamp = now_iso()
        placeholders = ",".join("?" for _ in ids)
        with self.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            table, id_field = ("raw_records", "record_id") if raw else ("events", "id")
            found = c.execute("SELECT " + id_field + " FROM " + table + " WHERE " + id_field + " IN (" + placeholders + ")", ids).fetchall()
            if len(found) != len(ids):
                raise ProductError("read_item_missing", "部分资讯不存在，未更改任何阅读状态", 404)
            event_ids = [r[0] for r in c.execute("SELECT DISTINCT event_id FROM raw_records WHERE record_id IN (" + placeholders + ") AND event_id IS NOT NULL", ids)] if raw else ids
            raw_ids = set(ids if raw else [])
            if event_ids:
                ep = ",".join("?" for _ in event_ids)
                raw_ids.update(r[0] for r in c.execute("SELECT record_id FROM raw_records WHERE event_id IN (" + ep + ")", event_ids))
            for target, field, values in (("event_reads", "event_id", event_ids), ("raw_reads", "record_id", raw_ids)):
                for identity in values:
                    if value:
                        c.execute("INSERT OR IGNORE INTO " + target + "(owner," + field + ",read_at) VALUES(?,?,?)", (owner, identity, stamp))
                    else:
                        c.execute("DELETE FROM " + target + " WHERE owner=? AND " + field + "=?", (owner, identity))
            c.execute("INSERT INTO audit(at,owner,action,details) VALUES(?,?,?,?)", (stamp, owner, "read.marked" if value else "read.cleared", json.dumps({"count": len(ids), "kind": "source_record" if raw else "event"})))
            first_table, first_key = ("raw_reads", "record_id") if raw else ("event_reads", "event_id")
            first_read = c.execute("SELECT read_at FROM " + first_table + " WHERE owner=? AND " + first_key + "=?", (owner, ids[0])).fetchone()
        return {"updated": len(ids), "read": value, "read_at": first_read[0] if first_read else None}

    def _raw_items(self, c, rows, owner, *, full=False, policy=None):
        policy = policy or self._reading_policy(c, owner)
        items = []
        for row in rows:
            read = c.execute("SELECT read_at FROM raw_reads WHERE owner=? AND record_id=?", (owner, row["record_id"])).fetchone()
            bookmarked = row["event_id"] is not None and c.execute("SELECT 1 FROM bookmarks WHERE owner=? AND event_id=?", (owner, row["event_id"])).fetchone() is not None
            first = row["first_ingested_at"] or row["ingested_at"]
            retention_at = self._retention_value(first, row["source_published_at"], policy)
            media = media_for(c, [row["record_id"]])
            state = "video_processing" if row["content_type"] == "video_pending" else "pending" if row["state"] == "retry" else row["state"]
            items.append({"id": row["record_id"], "kind": "source_record", "platform": row["plugin_id"],
                          "source_id": row["target_id"], "name": row["source_name"], "title": row["title"],
                          "text": row["text"] if full else row["text"][:1200], "url": row["source_url"],
                          "source_published_at": row["source_published_at"], "first_ingested_at": first,
                          "ingested_at": row["ingested_at"], "retention_at": retention_at,
                          "archived": self._is_archived(retention_at, bookmarked, policy),
                          "images": [m["url"] for m in media if m["status"] == "ready"], "media": media,
                          "state": state, "event_id": row["event_id"], "read": read is not None,
                          "read_at": read[0] if read else None, "bookmarked": bool(bookmarked),
                          "error": row["error"]})
        return items

    def list_inbox(self, filters=None, owner="owner"):
        f, clauses, args = filters or {}, ["1=1"], []
        for key, column in (("source", "plugin_id"), ("source_id", "target_id")):
            if f.get(key):
                if key == "source" and f[key] not in {"telegram", "x", "youtube"}:
                    raise ProductError("invalid_platform_filter", "来源平台无效")
                clauses.append("r." + column + "=?")
                args.append(str(f[key])[:150])
        if f.get("q"):
            clauses.append("instr(lower(r.title||' '||r.text||' '||r.source_name),lower(?))>0")
            args.append(str(f["q"])[:200])
        state = f.get("state", "all")
        if state == "video_processing":
            clauses.append("r.content_type='video_pending'")
        elif state == "pending":
            clauses.append("r.state IN ('pending','retry')")
        elif state in {"completed", "processing", "filtered", "failed"}:
            clauses.append("r.state=?")
            args.append(state)
        elif state != "all":
            raise ProductError("invalid_inbox_state", "原文整理状态无效")
        orders = {"discovered": "r.first_ingested_at DESC,r.record_id", "published": "r.source_published_at IS NULL,r.source_published_at DESC,r.record_id"}
        sort = f.get("sort", "discovered")
        if sort not in orders:
            raise ProductError("invalid_inbox_sort", "原文排序值无效")
        limit = min(200, max(1, int(f.get("limit", 60))))
        offset = min(1000000, max(0, int(f.get("offset", 0))))
        with self.connect() as c:
            policy = self._reading_policy(c, owner, f)
            first = "coalesce(r.first_ingested_at,r.ingested_at)"
            retention_sql = "coalesce(r.source_published_at," + first + ")" if policy["retention_basis"] == "published" else first
            self._apply_policy(clauses, args, policy, retention_sql=retention_sql,
                               read_sql="EXISTS(SELECT 1 FROM raw_reads rr WHERE rr.record_id=r.record_id AND rr.owner=?)",
                               bookmark_sql="EXISTS(SELECT 1 FROM bookmarks b WHERE b.event_id=r.event_id AND b.owner=?)", owner=owner)
            where = " AND ".join(clauses)
            total = c.execute("SELECT count(*) FROM raw_records r WHERE " + where, args).fetchone()[0]
            rows = c.execute("SELECT r.* FROM raw_records r WHERE " + where + " ORDER BY " + orders[sort] + " LIMIT ? OFFSET ?", (*args, limit, offset)).fetchall()
            items = self._raw_items(c, rows, owner, policy=policy)
        return {"items": items, "total": total, "limit": limit, "offset": offset, "policy": policy, "generated_at": now_iso()}

    def get_raw(self, identity: str, owner="owner"):
        with self.connect() as c:
            rows = c.execute("SELECT * FROM raw_records WHERE record_id=?", (identity,)).fetchall()
            return self._raw_items(c, rows, owner, full=True)[0] if rows else None

    def bookmark(self, event_id: str, owner: str, value: bool) -> bool:
        with self.connect() as c:
            if c.execute("SELECT 1 FROM events WHERE id=?", (event_id,)).fetchone() is None:
                return False
            if value:
                c.execute(
                    "INSERT OR IGNORE INTO bookmarks VALUES(?,?,?)", (owner, event_id, now_iso())
                )
            else:
                c.execute("DELETE FROM bookmarks WHERE owner=? AND event_id=?", (owner, event_id))
            c.execute(
                "INSERT INTO audit(at,owner,action,target) VALUES(?,?,?,?)",
                (now_iso(), owner, "bookmark.add" if value else "bookmark.remove", event_id),
            )
        return True

    def stats(self) -> dict:
        with self.connect() as c:
            stats = dict(
                c.execute("""SELECT count(*) total,
                 coalesce(sum(location_status='located'),0) located,
                 coalesce(sum(event_time_start IS NULL),0) undated FROM events""").fetchone()
            )
            stats["latest_ingested_at"] = c.execute(
                "SELECT max(ingested_at) FROM raw_records"
            ).fetchone()[0]
            stats["latest_source_published_at"] = c.execute(
                "SELECT max(source_published_at) FROM raw_records"
            ).fetchone()[0]
            states = {
                x["state"]: x["n"]
                for x in c.execute("SELECT state,count(*) n FROM raw_records GROUP BY state")
            }
            stats["enrichment"] = {
                "pending": states.get("pending", 0) + states.get("retry", 0),
                "processing": states.get("processing", 0),
                "completed": states.get("completed", 0),
                "filtered": states.get("filtered", 0),
                "failed": states.get("failed", 0),
                "awaiting_video": states.get("awaiting_video", 0),
            }
            stats["sources"] = [
                dict(x)
                for x in c.execute(
                    """SELECT plugin_id platform,count(*) records,
                   max(ingested_at) latest_ingested_at,
                   max(source_published_at) latest_published_at
                   FROM raw_records GROUP BY plugin_id"""
                )
            ]
            usage = c.execute(
                "SELECT * FROM usage WHERE day=?", (datetime.now(UTC).strftime("%Y-%m-%d"),)
            ).fetchone()
            stats["usage"] = (
                dict(usage)
                if usage
                else {"items": 0, "requests": 0, "prompt_tokens": 0, "completion_tokens": 0}
            )
        return stats

    def create_session(self, token: str, csrf: str, expires: float, owner="owner"):
        with self.connect() as c:
            c.execute("DELETE FROM sessions WHERE expires_at<?", (time.time(),))
            c.execute(
                "INSERT INTO sessions VALUES(?,?,?,?,?)",
                (hashlib.sha256(token.encode()).hexdigest(), owner, csrf, expires, now_iso()),
            )
            c.execute(
                "INSERT INTO audit(at,owner,action) VALUES(?,?,'session.created')",
                (now_iso(), owner),
            )

    def session(self, token: str) -> dict | None:
        if not token or len(token) > 200:
            return None
        with self.connect() as c:
            row = c.execute(
                "SELECT owner,csrf,expires_at FROM sessions WHERE token_hash=? AND expires_at>?",
                (hashlib.sha256(token.encode()).hexdigest(), time.time()),
            ).fetchone()
            return dict(row) if row else None

    def revoke_session(self, token: str):
        with self.connect() as c:
            c.execute(
                "DELETE FROM sessions WHERE token_hash=?",
                (hashlib.sha256(token.encode()).hexdigest(),),
            )

    def backup(self, destination: Path) -> dict:
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as source:
            target = sqlite3.connect(destination)
            try:
                source.backup(target)
                check = target.execute("PRAGMA integrity_check").fetchone()[0]
            finally:
                target.close()
        destination.chmod(0o600)
        if check != "ok":
            raise RuntimeError("backup_integrity_check_failed")
        return {"path": str(destination), "integrity": check}
