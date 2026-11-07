"""Conservative date precision checks and explicitly reviewed derived-data repairs.

This module never derives an occurrence date from a publication timestamp. The
repair rule only withdraws a single-day claim supported solely by a relative
week. Existing intervals and unknown dates are left untouched.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import UTC, datetime

REPAIR_VERSION = "event-time-week-precision-v1"
WEEK_NOTE = "原文只限定到周，未提供具体日期，无法确认事件发生在哪一天。"
REPAIR_NOTE = "原文只限定到周，未提供具体日期；此前的日级时间已撤回。"

_MONTH = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
)
_DAY = r"(?:0?[1-9]|[12]\d|3[01])(?:st|nd|rd|th)?"
MONTH_DAY_CUE = re.compile(
    rf"\b{_MONTH}\.?\s+{_DAY}\b|\b{_DAY}\s+{_MONTH}\.?\b", re.I
)
_WEEK_CUE = re.compile(
    r"\b(?:this|last|next|previous)\s+week\b|(?:本|这|上|下)(?:周|星期)", re.I
)
_DAY_CUE = re.compile(
    r"(?<!\d)(?:19|20|21)\d{2}[-/.](?:0?[1-9]|1[0-2])[-/.](?:0?[1-9]|[12]\d|3[01])(?!\d)|"
    r"(?<!\d)(?:0?[1-9]|1[0-2])[/.-](?:0?[1-9]|[12]\d|3[01])(?!\d)|"
    r"(?:0?[1-9]|1[0-2])\s*月\s*(?:0?[1-9]|[12]\d|3[01])\s*[日号號]|"
    r"\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|"
    r"Mon|Tue|Tues|Wed|Thu|Thur|Thurs|Fri|Sat|Sun|today|yesterday|tomorrow|tonight)\b|"
    r"\bthis\s+(?:morning|afternoon|evening)\b|"
    r"(?:周|星期)[一二三四五六日天]|今[天日晨晚]|昨[天日夜晚]|明[天日早晚]|前天|后天",
    re.I,
)


def week_point_without_day(data: dict) -> bool:
    """A week is insufficient evidence for a point date; do not guess its bounds."""
    if data.get("event_time_precision") not in {"day", "exact", "range"}:
        return False
    if data.get("event_time_status") not in {"explicit", "inferred", "scheduled"}:
        return False
    evidence = data.get("event_time_evidence") or ""
    if not _WEEK_CUE.search(evidence) or _DAY_CUE.search(evidence) or MONTH_DAY_CUE.search(evidence):
        return False
    start, end = data.get("event_time_start"), data.get("event_time_end")
    if not start:
        return False
    try:
        begin = datetime.fromisoformat(start.replace("Z", "+00:00"))
        finish = datetime.fromisoformat(end.replace("Z", "+00:00")) if end else begin
        return finish == begin
    except (TypeError, ValueError):
        return False


def withdraw_week_point(data: dict, *, existing: bool = False) -> dict:
    """Return a corrected copy; preserve the quote and every unrelated fact."""
    if not week_point_without_day(data):
        return dict(data)
    return {
        **data,
        "event_time_start": None,
        "event_time_end": None,
        "event_civil_start": None,
        "event_civil_end": None,
        "event_time_precision": "unknown",
        "event_time_status": "unknown",
        "event_timezone": None,
        "event_time_note": REPAIR_NOTE if existing else WEEK_NOTE,
    }


def _canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _source_snapshot(row) -> dict:
    value = {key: row[key] for key in ("record_id", "title", "text", "source_published_at")}
    return {"record_id": row["record_id"], "sha256": _digest(value),
            "source_published_at": row["source_published_at"]}


def _supports_quote(evidence: str, row) -> bool:
    compact = lambda value: re.sub(r"\s+", " ", value).strip().casefold()
    return len(evidence.strip()) >= 2 and compact(evidence) in compact(row["title"] + "\n" + row["text"])


def _after_row(before: dict, at: str) -> dict:
    data = json.loads(before["data"])
    if not week_point_without_day(data):
        raise ValueError("The proposed record does not match the narrow week precision rule")
    result = dict(before)
    result["data"] = json.dumps(withdraw_week_point(data, existing=True), ensure_ascii=False)
    result["event_time_start"] = None
    result["updated_at"] = at
    return result


def plan_week_repairs(connection: sqlite3.Connection) -> dict:
    """Read only. The caller stores this exact plan for inspection before apply."""
    connection.row_factory = sqlite3.Row
    at = datetime.now(UTC).isoformat(timespec="milliseconds")
    plan = {"version": REPAIR_VERSION, "generated_at": at, "records": [],
            "known_examined": 0, "unmatched_evidence_skipped": 0,
            "unknown_dates_unchanged": True, "original_database_access": "none"}
    for row in connection.execute("SELECT * FROM events WHERE event_time_start IS NOT NULL ORDER BY id"):
        data = json.loads(row["data"])
        plan["known_examined"] += 1
        if not week_point_without_day(data):
            continue
        sources = connection.execute(
            "SELECT record_id,title,text,source_published_at FROM raw_records WHERE event_id=? ORDER BY record_id",
            (row["id"],),
        ).fetchall()
        supports = [_source_snapshot(source) for source in sources
                    if _supports_quote(data["event_time_evidence"], source)]
        if not supports:
            plan["unmatched_evidence_skipped"] += 1
            continue
        before = dict(row)
        after = _after_row(before, at)
        plan["records"].append({"event_id": row["id"], "reason": "week_without_specific_day",
                                "before_sha256": _digest(before), "after_sha256": _digest(after),
                                "before": before, "after": after, "evidence_sources": supports})
    return plan


_JOURNAL_TABLE = """
CREATE TABLE IF NOT EXISTS event_time_repairs(
 version TEXT NOT NULL,event_id TEXT NOT NULL,applied_at TEXT NOT NULL,
 before_sha256 TEXT NOT NULL,after_sha256 TEXT NOT NULL,
 before_row TEXT NOT NULL,after_row TEXT NOT NULL,evidence_sources TEXT NOT NULL,
 plan_sha256 TEXT NOT NULL,PRIMARY KEY(version,event_id))
"""


def apply_week_repairs(connection: sqlite3.Connection, plan: dict, *, plan_sha256: str) -> dict:
    """CAS-protected, transactional and idempotent. Caller must first back up SQLite.

Only event JSON, its occurrence-date index column and updated_at can change.
Reading state, source rows, bookmarks, budgets and event identifiers are untouched.
An immutable journal retains the complete before and after event rows.
"""
    if plan.get("version") != REPAIR_VERSION or not isinstance(plan.get("records"), list):
        raise ValueError("Unsupported time repair plan")
    at = plan.get("generated_at")
    if not isinstance(at, str) or datetime.fromisoformat(at).tzinfo is None:
        raise ValueError("The time repair plan needs a timezone-aware generation timestamp")
    if not re.fullmatch(r"[a-f0-9]{64}", plan_sha256):
        raise ValueError("The reviewed plan SHA256 is required")
    connection.row_factory = sqlite3.Row
    with connection:
        connection.execute("BEGIN IMMEDIATE")
        journal_exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='event_time_repairs'"
        ).fetchone()
        pending, applied, ids = [], 0, set()
        # Validate the entire batch before the first schema or data mutation.
        for entry in plan["records"]:
            identity = entry["event_id"]
            if identity in ids:
                raise ValueError("Duplicate event in time repair plan")
            ids.add(identity)
            before, after = entry["before"], entry["after"]
            if before.get("id") != identity or _after_row(before, at) != after:
                raise ValueError("The time repair plan contains an out-of-scope change")
            if _digest(before) != entry["before_sha256"] or _digest(after) != entry["after_sha256"]:
                raise ValueError("Time repair row checksum mismatch")
            current = connection.execute("SELECT * FROM events WHERE id=?", (identity,)).fetchone()
            if current is None:
                raise RuntimeError("Reviewed time repair event no longer exists: " + identity)
            # Later additive schema columns do not invalidate an already applied
            # repair. All columns that existed in the reviewed row still use CAS.
            if not set(before).issubset(current.keys()):
                raise RuntimeError("The reviewed event schema has changed incompatibly")
            current_snapshot = {key: current[key] for key in before}
            journal = connection.execute(
                "SELECT * FROM event_time_repairs WHERE version=? AND event_id=?", (REPAIR_VERSION, identity)
            ).fetchone() if journal_exists else None
            if journal:
                if (journal["before_sha256"] != entry["before_sha256"]
                        or journal["after_sha256"] != entry["after_sha256"]
                        or _digest(current_snapshot) != journal["after_sha256"]):
                    raise RuntimeError("An already repaired event has changed since this plan: " + identity)
                applied += 1
                continue
            if _digest(current_snapshot) != entry["before_sha256"]:
                raise RuntimeError("Reviewed time repair event changed; generate and review a new plan: " + identity)
            if not entry.get("evidence_sources"):
                raise ValueError("Time repair requires original quote support")
            for expected in entry["evidence_sources"]:
                source = connection.execute(
                    "SELECT record_id,title,text,source_published_at FROM raw_records WHERE record_id=? AND event_id=?",
                    (expected["record_id"], identity),
                ).fetchone()
                if (source is None or _source_snapshot(source) != expected
                        or not _supports_quote(json.loads(before["data"])["event_time_evidence"], source)):
                    raise RuntimeError("Original quote context changed after time repair review: " + identity)
            pending.append(entry)
        if pending:
            # executescript implicitly commits, so each complete statement must
            # be executed separately to retain all-or-nothing repair semantics.
            for statement in (
                _JOURNAL_TABLE,
                "CREATE TRIGGER IF NOT EXISTS event_time_repairs_no_update BEFORE UPDATE ON event_time_repairs "
                "BEGIN SELECT RAISE(ABORT,'Time repair journal is immutable'); END",
                "CREATE TRIGGER IF NOT EXISTS event_time_repairs_no_delete BEFORE DELETE ON event_time_repairs "
                "BEGIN SELECT RAISE(ABORT,'Time repair journal is immutable'); END",
            ):
                connection.execute(statement)
            applied_at = datetime.now(UTC).isoformat(timespec="milliseconds")
            for entry in pending:
                before, after = entry["before"], entry["after"]
                connection.execute(
                    "UPDATE events SET data=?,event_time_start=?,updated_at=? WHERE id=?",
                    (after["data"], after["event_time_start"], after["updated_at"], entry["event_id"]),
                )
                connection.execute(
                    "INSERT INTO event_time_repairs(version,event_id,applied_at,before_sha256,after_sha256,"
                    "before_row,after_row,evidence_sources,plan_sha256) VALUES(?,?,?,?,?,?,?,?,?)",
                    (REPAIR_VERSION, entry["event_id"], applied_at, entry["before_sha256"], entry["after_sha256"],
                     _canonical(before), _canonical(after), _canonical(entry["evidence_sources"]), plan_sha256),
                )
    return {"version": REPAIR_VERSION, "changed": len(pending), "already_applied": applied,
            "event_ids": [entry["event_id"] for entry in pending]}
