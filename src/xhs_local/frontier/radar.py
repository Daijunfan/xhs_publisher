"""Evidence-linked, owner-scoped topic radar over the existing derived SQLite.

Search terms are whitespace-separated AND substrings (max 8); all must occur
within ONE completed original title/text on a selected platform. A model's
editorial title/summary cannot create an unsupported source-backed match.
Separately, a capped 48-hour read-only raw lane searches titles and original
texts before event enrichment; these unverified leads never become scored
or triageable events. Trends remain UTC first-ingestion *event* counts.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
import uuid
from datetime import UTC, date, datetime, time, timedelta, timezone
from typing import Any

from .models import now_iso, iso_time
from .dossier import evidence_url
from .preferences import ProductError

PLATFORMS = ("telegram", "x", "youtube")
MAX_TERMS = 8
MAX_HIGHLIGHTS = 8
# The Radar client initially displays only its first 4 matching event cards;
# positions 5..8 require a deliberate “expand” action.
INITIAL_VISIBLE_HIGHLIGHTS = 4
# Display at most 12 original records. If those are all unlinkable, scan at
# most 240 more SAME-query completed originals for one safe clickable link;
# never borrow an unrelated association or promise the URL is still live.
MAX_SOURCES = 12
MAX_MATCHING_URL_FALLBACK = 240
MAX_GLOBAL_SIGNALS = 5
MAX_REVIEW_DUE = 50
# The dossier's review_on is a calendar date, never an inferred UTC instant.
# Use the product's explicitly displayed Beijing (UTC+08:00) calendar day.
REVIEW_DAY_ZONE = timezone(timedelta(hours=8))
# Raw-only lead lane: 48h rolling UTC window; bounded *before* title/text LIKE
# matching. Capped across all topics to keep SQLite work predictable even when
# enrichment falls weeks behind. Neither an event nor an editorial score.
RAW_LEAD_HOURS = 48
RAW_SCAN_CAP = 2400
RAW_LEADS_PER_TOPIC = 4
RAW_LEAD_STATES = ("pending", "retry", "processing", "awaiting_video", "failed")
DECISIONS = ("dismiss", "watch", "research")
# Per sampled event; over-cap history is insufficient to claim a revived
# cluster is novel. Long copies are literal text, NOT semantic event matching.
DAILY_REPOST_SCAN_CAP = 800
DAILY_LONG_COPY_CHARS = 120
DAILY_FEEDBACK_DAYS = 90
_DAILY_ASCII_LOWER = str.maketrans(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"
)

# USD per month is an unvalidated PRICING HYPOTHESIS only. No invoices,
# checkout, payment collection, membership activation or recurring billing exists.
_PLANS = {
    "free": ("免费", 1, 7, 7, 0),
    "pro": ("Pro", 10, 30, 30, 19),
    "analyst": ("Analyst", 30, 90, 30, 79),
}


def plan_details(identity: str) -> dict:
    if identity not in _PLANS:
        raise ValueError("FRONTIER_PLAN must be free, pro, or analyst")
    label, max_topics, history_days, trend_days, suggestion = _PLANS[identity]
    return {
        "id": identity,
        "label": label,
        "capabilities": [
            "按空格分词 AND 主题检索",
            "已关联原始来源的可追溯事件",
            "已读、收藏、复盘后新增追踪",
            "按首次入库日统计趋势",
        ] + (["审阅后保留有原文出处的不可变简报", "可保存和导出个人证据研判版本"]
             if identity in ("pro", "analyst") else ["可更新复盘水位，历史高级简报不开放"])
        + (["按北京时间日界显示个人研判复查队列（无推送）"] if identity == "analyst" else []),
        "limits": {
            "max_topics": max_topics,
            "history_days": history_days,
            "trend_days": trend_days,
            "highlights_per_topic": MAX_HIGHLIGHTS,
            "raw_leads_per_topic": RAW_LEADS_PER_TOPIC,
            "raw_recent_scan_cap": RAW_SCAN_CAP,
            "raw_lookback_hours": RAW_LEAD_HOURS,
            "max_keyword_terms": MAX_TERMS,
            "saved_brief_enabled": identity in ("pro", "analyst"),
            "dossier_write_enabled": identity in ("pro", "analyst"),
            "review_due_enabled": identity == "analyst",
        },
        "pricing": {
            "suggested_monthly_usd": suggestion,
            "status": "internal_suggestion_unverified",
            "billing_active": False,
        },
        "access_status": "single_user_internal_preview",
        "query_semantics": {
            "operator": "AND",
            "tokenization": "whitespace",
            "match": "substring",
            "case": "ASCII-insensitive",
            "scope": "one completed original title/text on a selected platform (all terms together; not model titles or summaries)",
        },
    }


def plan_comparison(current: str) -> dict:
    return {
        "plans": [plan_details(key) | {"is_current": key == current} for key in _PLANS],
        "current_plan": plan_details(current),
        "current_plan_id": current,
        "billing_enabled": False,
        "pricing_disclaimer": "价格仅为内部建议、尚未验证，未开通外部计费或付费订阅。",
        "generated_at": now_iso(),
    }


def _topic_payload(value: Any, *, partial: bool) -> dict:
    if not isinstance(value, dict):
        raise ProductError("invalid_radar_topic", "请提交 JSON 对象", 400)
    allowed = {"name", "query", "platforms", "min_importance"}
    if not value or set(value) - allowed:
        raise ProductError(
            "invalid_radar_topic", "请提供有效主题字段（name、query、platforms、min_importance）"
        )
    if not partial and not {"name", "query"} <= set(value):
        raise ProductError("radar_topic_required", "主题名称和查询关键词不能为空")
    cleaned = {}
    for key, item in value.items():
        if key in {"name", "query"}:
            maximum = 48 if key == "name" else 160
            if not isinstance(item, str) or any(
                (ord(char) < 32 and not char.isspace()) or ord(char) == 127 for char in item
            ):
                raise ProductError("invalid_radar_text", "主题名称或查询词必须是有效文本")
            normalized = " ".join(item.split())
            if not 1 <= len(normalized) <= maximum:
                raise ProductError("invalid_radar_length", f"{key} 长度必须在 1–{maximum} 字符之间")
            if key == "query" and len(normalized.split()) > MAX_TERMS:
                raise ProductError(
                    "too_many_radar_terms", f"查询最多支持 {MAX_TERMS} 个空格分隔的 AND 关键词"
                )
            cleaned[key] = normalized
        elif key == "platforms":
            if (
                not isinstance(item, list)
                or not 1 <= len(item) <= len(PLATFORMS)
                or any(type(p) is not str or p not in PLATFORMS for p in item)
                or len(set(item)) != len(item)
            ):
                raise ProductError(
                    "invalid_radar_platforms", "请选择不重复的 telegram、x 或 youtube 平台"
                )
            cleaned[key] = [p for p in PLATFORMS if p in item]
        elif key == "min_importance":
            if type(item) is not int or not 0 <= item <= 100:
                raise ProductError("invalid_radar_importance", "重要性必须为 0–100 的整数")
            cleaned[key] = item
    if not partial:
        cleaned.setdefault("platforms", list(PLATFORMS))
        cleaned.setdefault("min_importance", 0)
    return cleaned


def _topic_name_key(name: str) -> str:
    return unicodedata.normalize("NFKC", name).casefold().strip()


def _expected_topic_version(value: Any) -> int:
    if type(value) is not int or not 1 <= value <= 2147483647:
        raise ProductError("radar_topic_version_required", "请携带最新主题版本后再操作", 422)
    return value


def _check_topic_version(row, expected: int) -> None:
    if row["version"] != expected:
        raise ProductError(
            "radar_topic_conflict", "此主题已经在另一窗口发生变化，请刷新后重新编辑", 409
        )


def _topic(row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "query": row["query"],
        "platforms": json.loads(row["platforms"]),
        "min_importance": row["min_importance"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "last_reviewed_at": row["last_reviewed_at"],
        "version": row["version"],
    }


class Radar:
    """Owner isolation, atomic CRUD/audit, bounded analytics. No collection or AI."""

    def __init__(self, store, plan: str = "analyst"):
        self.store = store
        self.plan = plan
        self.details = plan_details(plan)

    @staticmethod
    def _owner_revision(c, owner: str) -> int:
        # Monotonic only within one append-only derived SQLite / owner.
        # Read through the SAME transaction as the decisions and aggregates.
        return c.execute(
            "SELECT coalesce(max(id),0) FROM audit WHERE owner=?", (owner,)
        ).fetchone()[0]

    def _require_active_entitlement(self, c, owner: str, identity: str) -> None:
        entitled = {
            row["id"]
            for row in c.execute(
                "SELECT id FROM radar_topics WHERE owner=? ORDER BY created_at,id LIMIT ?",
                (owner, self.details["limits"]["max_topics"]),
            )
        }
        if identity not in entitled:
            raise ProductError(
                "radar_topic_suspended", "当前档位已暂停此主题分析，配置和既有记录仍保留", 403
            )

    @staticmethod
    def _require_unique_name(c, owner: str, name: str, *, excluded_id: str = "") -> None:
        target = _topic_name_key(name)
        for row in c.execute("SELECT id,name FROM radar_topics WHERE owner=?", (owner,)):
            if row["id"] != excluded_id and _topic_name_key(row["name"]) == target:
                raise ProductError(
                    "radar_topic_duplicate", "你已经有同名雷达主题，请编辑已有主题", 409
                )

    def create(self, owner: str, value: Any) -> dict:
        fields = _topic_payload(value, partial=False)
        # Microseconds keep creation order stable when two topics are made
        # within the same millisecond; downgrade priority must not be random.
        stamp, identity = datetime.now(UTC).isoformat(timespec="microseconds"), uuid.uuid4().hex
        with self.store.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            count = c.execute(
                "SELECT count(*) FROM radar_topics WHERE owner=?", (owner,)
            ).fetchone()[0]
            if count >= self.details["limits"]["max_topics"]:
                raise ProductError(
                    "radar_topic_limit",
                    f"当前计划最多可创建 {self.details['limits']['max_topics']} 个主题",
                    403,
                )
            self._require_unique_name(c, owner, fields["name"])
            c.execute(
                "INSERT INTO radar_topics(id,owner,name,query,platforms,min_importance,"
                "created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                (
                    identity,
                    owner,
                    fields["name"],
                    fields["query"],
                    json.dumps(fields["platforms"]),
                    fields["min_importance"],
                    stamp,
                    stamp,
                ),
            )
            c.execute(
                "INSERT INTO audit(at,owner,action,target,details) VALUES(?,?,?,?,?)",
                (
                    stamp,
                    owner,
                    "radar.topic.created",
                    identity,
                    json.dumps({"fields": sorted(fields)}),
                ),
            )
            row = c.execute(
                "SELECT * FROM radar_topics WHERE id=? AND owner=?", (identity, owner)
            ).fetchone()
            owner_revision = self._owner_revision(c, owner)
        # Additive POST201 receipt for the independent D0 first-topic UI patch.
        return {"topic": _topic(row), "created": True, "owner_revision": owner_revision}

    def update(self, owner: str, identity: str, value: Any) -> dict:
        if not isinstance(value, dict):
            raise ProductError("invalid_radar_topic", "请提交 JSON 对象", 400)
        expected = _expected_topic_version(value.get("version"))
        fields = _topic_payload(
            {key: field for key, field in value.items() if key != "version"}, partial=True
        )
        with self.store.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute(
                "SELECT * FROM radar_topics WHERE id=? AND owner=?", (identity, owner)
            ).fetchone()
            if row is None:
                raise ProductError("radar_topic_missing", "主题不存在", 404)
            _check_topic_version(row, expected)
            original = _topic(row)
            desired = dict(original)
            desired.update(fields)
            if all(desired[key] == original[key] for key in fields):
                return {"topic": original, "updated": False}
            if "name" in fields:
                self._require_unique_name(c, owner, desired["name"], excluded_id=identity)
            stamp = now_iso()
            c.execute(
                "UPDATE radar_topics SET name=?,query=?,platforms=?,min_importance=?,"
                "updated_at=?,version=version+1 WHERE id=? AND owner=?",
                (
                    desired["name"],
                    desired["query"],
                    json.dumps(desired["platforms"]),
                    desired["min_importance"],
                    stamp,
                    identity,
                    owner,
                ),
            )
            c.execute(
                "INSERT INTO audit(at,owner,action,target,details) VALUES(?,?,?,?,?)",
                (
                    stamp,
                    owner,
                    "radar.topic.updated",
                    identity,
                    json.dumps({"fields": sorted(k for k in fields if desired[k] != original[k])}),
                ),
            )
            row = c.execute(
                "SELECT * FROM radar_topics WHERE id=? AND owner=?", (identity, owner)
            ).fetchone()
        return {"topic": _topic(row), "updated": True}

    def delete(self, owner: str, identity: str, payload: Any) -> dict:
        expected = self._required_version_body(payload)
        with self.store.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute(
                "SELECT version FROM radar_topics WHERE id=? AND owner=?", (identity, owner)
            ).fetchone()
            if row is None:
                raise ProductError("radar_topic_missing", "主题不存在", 404)
            _check_topic_version(row, expected)
            c.execute(
                "DELETE FROM radar_topics WHERE id=? AND owner=? AND version=?",
                (identity, owner, expected),
            )
            c.execute(
                "INSERT INTO audit(at,owner,action,target) VALUES(?,?,?,?)",
                (now_iso(), owner, "radar.topic.deleted", identity),
            )
        return {"id": identity, "deleted": True}

    @staticmethod
    def _required_version_body(payload: Any) -> int:
        if not isinstance(payload, dict) or set(payload) != {"version"}:
            raise ProductError("radar_topic_version_required", "请仅提交最新主题 version", 422)
        return _expected_topic_version(payload["version"])

    def review(self, owner: str, identity: str, payload: Any) -> dict:
        """Atomically freeze a bounded brief, then advance the CAS review watermark.

        The brief records exactly what was visible at this round. It never marks
        events as read and later incoming stories/triage cannot rewrite it.
        """
        expected = self._required_version_body(payload)
        now = datetime.now(UTC)
        stamp = now.isoformat(timespec="microseconds")
        with self.store.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute(
                "SELECT * FROM radar_topics WHERE id=? AND owner=?", (identity, owner)
            ).fetchone()
            if row is None:
                raise ProductError("radar_topic_missing", "主题不存在", 404)
            _check_topic_version(row, expected)
            self._require_active_entitlement(c, owner, identity)
            topic = _topic(row)
            policy = self.store._reading_policy(c, owner)
            details = self._details_for_topic(c, topic, owner, now, policy)
            brief = {
                "id": uuid.uuid4().hex,
                "generated_at": stamp,
                "topic_name": topic["name"],
                "query": topic["query"],
                "platforms": topic["platforms"],
                "topic_version": expected,
                "metrics": {
                    key: details["metrics"][key] for key in (
                        "total", "unread", "new_since_review", "today_added",
                        "triaged", "today_triaged", "pending_triage", "with_event_time",
                        "with_location", "decided"
                    )
                },
                "items": [
                    {
                        key: item[key] for key in (
                            "id", "title", "importance", "personal_relevance",
                            "decision", "first_ingested_at", "archived", "source_count"
                        )
                    } | {"sources": item["sources"][:3]}
                    for item in details["highlights"]
                ],
                "scope": "仅限该主题当前时间窗口内、已关联完成原文的事件；原文数不等于独立证实",
            }
            # Free keeps the V3 review watermark without creating the premium
            # immutable research brief. Downgrades never delete old snapshots.
            save_brief = self.plan in ("pro", "analyst")
            if save_brief:
                # Keep legacy brief fields, but put this round's navigable
                # changes FIRST. Old clusters revived by a new matching original
                # would otherwise vanish from event-first-ingestion highlights.
                changed, changes, review_window = self._review_change_snapshot(
                    c, topic, owner, now, policy
                )
                changed_ids = {item["id"] for item in changed}
                brief["items"] = (
                    changed + [item for item in brief["items"] if item["id"] not in changed_ids]
                )[:MAX_HIGHLIGHTS]
                brief["changes"] = changes
                brief["review_window"] = review_window
                brief["scope"] = (
                    "旧指标按事件首次入库窗口统计；简报线索另包含窗口内新关联的"
                    "同题完成原文所重新激活的旧事件。变更出处仅引用本轮符合时间门槛的"
                    "安全原文链接；不推断事件发生时间，不代表事实或独立性已核实。"
                )
                c.execute(
                    "INSERT INTO radar_briefs(id,owner,topic_id,generated_at,topic_version,data) "
                    "VALUES(?,?,?,?,?,?)",
                    (brief["id"], owner, identity, stamp, expected,
                     json.dumps(brief, ensure_ascii=False)),
                )
            c.execute(
                "UPDATE radar_topics SET last_reviewed_at=?,version=version+1 "
                "WHERE id=? AND owner=? AND version=?",
                (stamp, identity, owner, expected),
            )
            c.execute(
                "INSERT INTO audit(at,owner,action,target,details) VALUES(?,?,?,?,?)",
                (stamp, owner, "radar.topic.reviewed", identity,
                 json.dumps({"brief_id": brief["id"] if save_brief else None,
                             "items": len(brief["items"]) if save_brief else 0,
                             "saved_brief_enabled": save_brief})),
            )
        return {
            "id": identity,
            "last_reviewed_at": stamp,
            "reviewed": True,
            "version": expected + 1,
            "brief_id": brief["id"] if save_brief else None,
            "brief_items": len(brief["items"]) if save_brief else 0,
        }

    @staticmethod
    def _valid_event_id(event_id: Any) -> str:
        """The exact event-id rules used by the original decide endpoint."""
        if (
            not isinstance(event_id, str)
            or not 1 <= len(event_id) <= 128
            or any(ord(character) < 33 or ord(character) == 127 for character in event_id)
        ):
            raise ProductError("invalid_radar_event", "请选择有效的事件 ID", 422)
        return event_id

    def _require_matching_event(self, c, topic: dict, event_id: str, now: datetime) -> None:
        """Share decide's authoritative eligibility/window/evidence predicate."""
        first = datetime.combine(
            now.date() - timedelta(days=self.details["limits"]["history_days"] - 1),
            time.min,
            UTC,
        ).isoformat(timespec="milliseconds")
        # A newly linked original can revive an older event cluster. Decisions
        # offered by /api/radar/daily must pass the same recent-original gate.
        where, args = self._daily_recent_event_match(topic, first, now.isoformat())
        matching = c.execute(
            "SELECT e.id FROM events e WHERE e.id=? AND " + where,
            (event_id, *args),
        ).fetchone()
        if matching is None:
            raise ProductError(
                "radar_event_not_matched", "该事件已不在主题的检索范围，请刷新主题后重试", 409
            )

    def decide(self, owner: str, identity: str, payload: Any) -> dict:
        """Explicit, reversible triage; does not touch read, bookmark or raw rows."""
        if not isinstance(payload, dict) or set(payload) != {"event_id", "decision"}:
            raise ProductError("invalid_radar_decision", "请提交 event_id 和 decision", 422)
        event_id, decision = payload["event_id"], payload["decision"]
        self._valid_event_id(event_id)
        if decision is not None and (not isinstance(decision, str) or decision not in DECISIONS):
            raise ProductError(
                "invalid_radar_decision", "分诊应为 dismiss、watch、research 或 null", 422
            )
        now = datetime.now(UTC)
        stamp = now.isoformat()
        with self.store.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute(
                "SELECT * FROM radar_topics WHERE id=? AND owner=?", (identity, owner)
            ).fetchone()
            if row is None:
                raise ProductError("radar_topic_missing", "主题不存在", 404)
            self._require_active_entitlement(c, owner, identity)
            topic = _topic(row)
            self._require_matching_event(c, topic, event_id, now)
            previous = c.execute(
                "SELECT decision,decided_at FROM radar_decisions "
                "WHERE owner=? AND topic_id=? AND event_id=?",
                (owner, identity, event_id),
            ).fetchone()
            if previous is None and decision is None:
                return {
                    "topic_id": identity,
                    "event_id": event_id,
                    "decision": None,
                    "decided_at": None,
                    "updated": False,
                    "owner_revision": self._owner_revision(c, owner),
                }
            if previous is not None and previous["decision"] == decision:
                return {
                    "topic_id": identity,
                    "event_id": event_id,
                    "decision": decision,
                    "decided_at": previous["decided_at"],
                    "updated": False,
                    "owner_revision": self._owner_revision(c, owner),
                }
            if decision is None:
                c.execute(
                    "DELETE FROM radar_decisions WHERE owner=? AND topic_id=? AND event_id=?",
                    (owner, identity, event_id),
                )
            else:
                c.execute(
                    "INSERT INTO radar_decisions(owner,topic_id,event_id,decision,decided_at) "
                    "VALUES(?,?,?,?,?) ON CONFLICT(owner,topic_id,event_id) DO UPDATE SET "
                    "decision=excluded.decision,decided_at=excluded.decided_at",
                    (owner, identity, event_id, decision, stamp),
                )
            c.execute(
                "INSERT INTO audit(at,owner,action,target,details) VALUES(?,?,?,?,?)",
                (
                    stamp,
                    owner,
                    "radar.event.decided",
                    identity,
                    json.dumps({"event_id": event_id, "decision": decision}),
                ),
            )
            return {
                "topic_id": identity,
                "event_id": event_id,
                "decision": decision,
                "decided_at": stamp if decision is not None else None,
                "updated": True,
                "owner_revision": self._owner_revision(c, owner),
            }

    def usefulness(self, owner: str, identity: str, payload: Any) -> dict:
        """Set/revoke a person's explicit useful/noise label independently of triage.

        No inferred labels, writes to events/reads/bookmarks, or frozen-brief
        updates. A repeated value, including an already-empty value, is a true
        no-op and does not create a misleading audit activity day.
        """
        if not isinstance(payload, dict) or set(payload) != {"event_id", "value"}:
            raise ProductError(
                "invalid_radar_usefulness", "请仅提交 event_id 和 value", 422
            )
        event_id = self._valid_event_id(payload["event_id"])
        value = payload["value"]
        if value is not None and (type(value) is not str or value not in ("useful", "noise")):
            raise ProductError(
                "invalid_radar_usefulness", "价值反馈应为 useful、noise 或 null", 422
            )
        now = datetime.now(UTC)
        stamp = now.isoformat(timespec="microseconds")
        with self.store.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute(
                "SELECT * FROM radar_topics WHERE id=? AND owner=?", (identity, owner)
            ).fetchone()
            if row is None:
                raise ProductError("radar_topic_missing", "主题不存在", 404)
            self._require_active_entitlement(c, owner, identity)
            self._require_matching_event(c, _topic(row), event_id, now)
            previous = c.execute(
                "SELECT value,rated_at FROM radar_usefulness "
                "WHERE owner=? AND topic_id=? AND event_id=?",
                (owner, identity, event_id),
            ).fetchone()
            old_value = previous["value"] if previous else None
            if old_value == value:
                return {
                    "topic_id": identity, "event_id": event_id, "value": value,
                    "rated_at": previous["rated_at"] if previous else None,
                    "updated": False,
                    "owner_revision": self._owner_revision(c, owner),
                }
            if value is None:
                c.execute(
                    "DELETE FROM radar_usefulness "
                    "WHERE owner=? AND topic_id=? AND event_id=?",
                    (owner, identity, event_id),
                )
            else:
                c.execute(
                    "INSERT INTO radar_usefulness(owner,topic_id,event_id,value,rated_at) "
                    "VALUES(?,?,?,?,?) ON CONFLICT(owner,topic_id,event_id) DO UPDATE SET "
                    "value=excluded.value,rated_at=excluded.rated_at",
                    (owner, identity, event_id, value, stamp),
                )
            c.execute(
                "INSERT INTO audit(at,owner,action,target,details) VALUES(?,?,?,?,?)",
                (
                    stamp, owner, "radar.event.usefulness", identity,
                    json.dumps({"event_id": event_id, "value": value, "previous": old_value}),
                ),
            )
            return {
                "topic_id": identity, "event_id": event_id, "value": value,
                "rated_at": stamp if value is not None else None, "updated": True,
                "owner_revision": self._owner_revision(c, owner),
            }

    @staticmethod
    def _original_keyword_predicate(topic: dict) -> tuple[str, list]:
        """A completed primary original must support all AND terms.

        An LLM title/summary and a source's display name are not evidence.
        This predicate is also used for the preview's clickable origin link.
        """
        platforms = topic["platforms"]
        pins = ",".join("?" for _ in platforms)
        predicates = ["r.state='completed'", "r.plugin_id IN (" + pins + ")"]
        terms = topic["query"].split()
        predicates.extend(
            "instr(lower(r.title||' '||r.text),lower(?))>0" for _ in terms
        )
        return " AND ".join(predicates), [*platforms, *terms]

    @staticmethod
    def _matched_clause(topic: dict, start: str, end: str) -> tuple[str, list]:
        first = "coalesce(e.first_ingested_at,e.created_at)"
        primary, primary_args = Radar._original_keyword_predicate(topic)
        # A single original must contain the entire AND query: neither
        # hallucinated derived text nor fragments across posts prove it.
        clauses = [
            first + ">=?", first + "<=?", "e.importance>=?",
            "EXISTS(SELECT 1 FROM raw_records r WHERE r.event_id=e.id AND "
            + primary + ")",
        ]
        return " AND ".join(clauses), [
            start, end, topic["min_importance"], *primary_args
        ]

    @staticmethod
    def _matching_original_sources(c, topic: dict, event_id: str) -> list[dict]:
        """Bounded original citations satisfying the topic's entire AND query.

        A linked original can provide context without containing a search term.
        Do not turn that unrelated link into evidence on a personal topic card.
        The associated-original count and earliest publication clock are
        computed separately from ALL eligible records, not from this subset.
        """
        primary, args = Radar._original_keyword_predicate(topic)
        sql = (
            "SELECT r.source_name,r.plugin_id,r.source_url FROM raw_records r "
            "WHERE r.event_id=? AND " + primary +
            " ORDER BY r.first_ingested_at,r.record_id LIMIT ?"
        )
        # The first three links, not merely the first twelve DB records, are
        # what the existing Web card exposes. Reposted identical safe URLs
        # must not crowd out a different same-query original at #13 or #14.
        # Prefer *distinct navigable addresses*, not presumed trustworthy or
        # independent publishers. This is a bounded lexical/link policy only:
        # no DNS, HTTP, citation fact check, semantic entailment or user label.
        seen_urls: set[str] = set()
        safe_sources: list[dict] = []
        unavailable: list[dict] = []
        for row in c.execute(
            sql, (event_id, *args, MAX_SOURCES + MAX_MATCHING_URL_FALLBACK)
        ):
            url = evidence_url(row["source_url"])
            if url:
                if url not in seen_urls:
                    seen_urls.add(url)
                    safe_sources.append({
                        "name": row["source_name"], "platform": row["plugin_id"],
                        "url": url,
                    })
                    if len(safe_sources) == MAX_SOURCES:
                        break
            elif len(unavailable) < MAX_SOURCES:
                unavailable.append({
                    "name": row["source_name"], "platform": row["plugin_id"],
                    "url": None,
                })
        # Keep the existing name/platform/url schema. Dead links are fallbacks
        # only; visible duplicate URLs are omitted, not counted as confirmation.
        # source_count and earliest publication clock still use ALL associated
        # completed originals, including unrelated contextual records.
        return safe_sources + unavailable[:MAX_SOURCES - len(safe_sources)]

    @staticmethod
    def _matching_preview_source(c, topic: dict, event_id: str) -> dict | None:
        """Return the same evidence subset as saved personal cards.

        Without a safe URL among the bounded matching originals, fail closed.
        Neither path may borrow a safe but unrelated original's link.
        """
        for original in Radar._matching_original_sources(c, topic, event_id):
            if original["url"] is not None:
                return original
        return None

    @staticmethod
    def _why(item: dict, reviewed_at: str | None, source_count: int, *, global_rank=False) -> str:
        state = "未读" if not item["read"] else "已读"
        if reviewed_at is None:
            review = "该主题尚未复盘"
        elif item["first_ingested_at"] > reviewed_at:
            review = "首次入库时间晚于上次复盘"
        else:
            review = "首次入库时间不晚于上次复盘"
        gaps = []
        if item["event_time_start"] is None:
            gaps.append("事件发生时间未知")
        if item["location_status"] != "located":
            gaps.append("地点缺少明确定位证据")
        uncertainty = "；".join(gaps) + "；" if gaps else ""
        if global_rank:
            rank = ("全站今日高重要度候选，按既有编辑重要性评分降序；"
                    "不按你的主题或个人匹配度筛选，不能代表全部全球事件；")
        else:
            rank = (
                "主题内未分诊优先、忽略置后；个人规则匹配分 "
                f"{item['personal_relevance']}/100（标题词命中权重70、摘要50、"
                "已完成原文25；深入研判+20、持续关注+12、忽略-70、阅后新增+6、未读+4）；"
                "同分按编辑重要性评分和收录时间排序；"
                f"{review}；"
            )
        # V93: The existing saved-card "为何进入重点列表" disclosure is a
        # visible-on-demand place for a decision-grade next step, even with no
        # frontend changes. Lexical AND is NOT semantic support/claim truth.
        # The publication clock remains the earliest *associated* original,
        # which can be different from the safe link on the personal card.
        next_action = ""
        if not global_rank:
            if any(source.get("url") for source in item.get("sources", ())):
                next_action = (
                    "下一步：原文外链仅通过本地安全地址校验，未验证404或当前可达；"
                    "亲读本主题词项命中原文，核对肯定/否定语境、"
                    "中英异体与同名歧义，并主动找反证；分别对照事件发生候选、"
                    "全部关联原文最早标记发表、本站首次收录三钟（可点原文未必最早发表），"
                    "再由本人独立选择分诊与是否有用。"
                )
            else:
                next_action = (
                    "下一步：当前没有可安全打开的词项命中原文，不要借用事件其他"
                    "无关来源链接；在合法范围另寻可信一手原文及反证，"
                    "时间不明处保持未知，不要仅凭编辑摘要定论。"
                )
        return (
            f"{rank}本条{state}，数据库已有重要性评分 {item['importance']}/100（不代表事实概率）；"
            f"{uncertainty}关联 {source_count} 条已完成原始记录"
            "（记录数量不代表独立来源确认，未进行交叉核实）。"
            + next_action
        )

    @staticmethod
    def _personal_score_sql(topic: dict, reviewed_at: str | None) -> tuple[str, list]:
        """Parameter-only explanation score, independent of editor importance."""
        terms = topic["query"].split()
        parts, args = [], []
        for term in terms:
            parts.append(
                "(CASE WHEN instr(lower(e.title),lower(?))>0 THEN 70 "
                "WHEN instr(lower(e.summary),lower(?))>0 THEN 50 ELSE 25 END)"
            )
            args.extend((term, term))
        base = "(" + "+".join(parts) + ")/" + str(len(terms))
        discovery = "coalesce(e.first_ingested_at,e.created_at)"
        sql = (
            "max(0,min(100,CAST(" + base + " AS INTEGER)"
            "+CASE WHEN d.decision='research' THEN 20 "
            "WHEN d.decision='watch' THEN 12 WHEN d.decision='dismiss' THEN -70 ELSE 0 END"
            "+CASE WHEN " + discovery + ">? THEN 6 ELSE 0 END"
            "+CASE WHEN er.event_id IS NULL THEN 4 ELSE 0 END))"
        )
        return sql, [*args, reviewed_at or ""]

    def _decorate_event(
        self, c, row, platforms: list[str], reviewed_at: str | None,
        policy: dict, *, topic: dict | None = None, global_rank=False
    ) -> dict:
        item = dict(row)
        item["read"] = bool(item["read"])
        item["bookmarked"] = bool(item["bookmarked"])
        pins = ",".join("?" for _ in platforms)
        sources = c.execute(
            "SELECT source_name AS name,plugin_id AS platform,source_url AS url,"
            "count(*) OVER () AS source_count,"
            "min(source_published_at) OVER () AS eligible_published_at "
            "FROM raw_records WHERE event_id=? AND state='completed' "
            "AND plugin_id IN (" + pins + ") ORDER BY first_ingested_at,record_id LIMIT ?",
            (item["id"], *platforms, MAX_SOURCES),
        ).fetchall()
        count = sources[0]["source_count"] if sources else 0
        # Retention and the displayed source list must share exactly the same
        # evidentiary universe: completed originals on selected platforms.
        # Window MIN is computed before LIMIT, so the 12-link display cap does
        # not hide an older *eligible* publication timestamp. Unknown stays NULL
        # and the established first-ingestion fallback remains in force.
        item["source_published_at"] = sources[0]["eligible_published_at"] if sources else None
        item["retention_at"] = self.store._retention_value(
            item["first_ingested_at"], item["source_published_at"], policy
        )
        item["archived"] = self.store._is_archived(
            item["retention_at"], item["bookmarked"], policy
        )
        item["source_count"] = count
        item["sources"] = (
            self._matching_original_sources(c, topic, item["id"]) if topic is not None
            else [
                {"name": source["name"], "platform": source["platform"],
                 "url": evidence_url(source["url"])}
                for source in sources
            ]
        )
        # This flag describes omitted associated originals, which includes
        # keyword-unmatched context on personal cards. The count and clocks
        # retain their previous all-eligible-originals semantics.
        item["sources_truncated"] = count > len(item["sources"])
        # The saved personal and global highlight cards must use the SAME
        # validated civil-date evidence as the first unsaved preview, otherwise
        # month/day/range events can change to a false calendar date on Save.
        # Bound: at most 8 per topic + 5 global. Pure SELECT, no raw excerpts.
        item.update(self._preview_occurrence_quality(c, item))
        item["why"] = self._why(item, reviewed_at, count, global_rank=global_rank)
        return item

    def _details_for_topic(self, c, topic: dict, owner: str, now: datetime, policy: dict) -> dict:
        history = self.details["limits"]["history_days"]
        trend_days = self.details["limits"]["trend_days"]
        today = now.date()
        first_day = today - timedelta(days=history - 1)
        earliest = datetime.combine(first_day, time.min, UTC).isoformat(timespec="milliseconds")
        ending = now.isoformat(timespec="milliseconds")
        where, args = self._matched_clause(topic, earliest, ending)
        reviewed_at = topic["last_reviewed_at"]
        discovery = "coalesce(e.first_ingested_at,e.created_at)"
        utc_day = today.isoformat()
        grouped = c.execute(
            "SELECT substr(" + discovery + ",1,10) AS day,count(*) AS total,"
            "sum(CASE WHEN er.event_id IS NULL THEN 1 ELSE 0 END) AS unread,"
            "sum(CASE WHEN " + discovery + ">? THEN 1 ELSE 0 END) AS fresh,"
            "sum(CASE WHEN substr(" + discovery + ",1,10)=? THEN 1 ELSE 0 END) AS today_added,"
            "sum(CASE WHEN rd.decision IS NOT NULL THEN 1 ELSE 0 END) AS triaged,"
            "sum(CASE WHEN substr(" + discovery + ",1,10)=? "
            "AND rd.decision IS NOT NULL THEN 1 ELSE 0 END) AS today_triaged,"
            "sum(CASE WHEN e.event_time_start IS NOT NULL THEN 1 ELSE 0 END) AS dated,"
            "sum(CASE WHEN e.location_status='located' THEN 1 ELSE 0 END) AS located "
            "FROM events e LEFT JOIN event_reads er ON er.event_id=e.id AND er.owner=? "
            "LEFT JOIN radar_decisions rd ON rd.event_id=e.id "
            "AND rd.owner=? AND rd.topic_id=? "
            "WHERE " + where + " GROUP BY day",
            (reviewed_at or "", utc_day, utc_day, owner, owner, topic["id"], *args),
        ).fetchall()
        totals = {
            key: 0
            for key in ("total", "unread", "new_since_review", "today_added",
                        "triaged", "today_triaged", "with_event_time", "with_location")
        }
        per_day = {}
        for row in grouped:
            for key, column in (
                ("total", "total"),
                ("unread", "unread"),
                ("new_since_review", "fresh"),
                ("today_added", "today_added"),
                ("triaged", "triaged"),
                ("today_triaged", "today_triaged"),
                ("with_event_time", "dated"),
                ("with_location", "located"),
            ):
                totals[key] += row[column]
            per_day[row["day"]] = row["total"]
        totals["trend"] = [
            {
                "day": (today - timedelta(days=offset)).isoformat(),
                "count": per_day.get((today - timedelta(days=offset)).isoformat(), 0),
            }
            for offset in range(trend_days - 1, -1, -1)
        ]
        decision_counts = c.execute(
            "SELECT d.decision,count(*) AS count FROM radar_decisions d "
            "JOIN events e ON e.id=d.event_id WHERE d.owner=? AND d.topic_id=? AND "
            + where
            + " GROUP BY d.decision",
            (owner, topic["id"], *args),
        ).fetchall()
        totals["decided"] = {
            key: next((row["count"] for row in decision_counts if row["decision"] == key), 0)
            for key in DECISIONS
        }
        totals["pending_triage"] = totals["total"] - totals["triaged"]
        totals["today_pending_triage"] = totals["today_added"] - totals["today_triaged"]
        totals["progress_pct"] = (
            round(100 * totals["triaged"] / totals["total"]) if totals["total"] else 0
        )
        totals["today_progress_pct"] = (
            round(100 * totals["today_triaged"] / totals["today_added"])
            if totals["today_added"] else 0
        )
        personal_sql, personal_args = self._personal_score_sql(topic, reviewed_at)
        # When the topic has more than 4 matches, temporarily pin AT MOST
        # the two most recent one-axis actions so their second buttons remain
        # in the DEFAULT V46/V79 visible lane, not hidden behind “expand”.
        # The complete returned top-8 still reserves >=6 ordinary slots.
        # Timestamps and the 1-hour bound come only from server-side UTC writes.
        # Negative Julian dates sort the two recent handoffs newest first;
        # ORDER BY-only expressions never appear in the public event JSON.
        handoff_start = (now - timedelta(hours=1)).isoformat()
        handoff_end = now.isoformat()
        records = c.execute(
            "SELECT e.id,e.title,e.summary,e.importance,e.category,"
            + discovery
            + " AS first_ingested_at,e.event_time_start,e.location_status,"
            "CASE WHEN er.event_id IS NOT NULL THEN 1 ELSE 0 END AS read,"
            "CASE WHEN b.event_id IS NOT NULL THEN 1 ELSE 0 END AS bookmarked,"
            "d.decision AS decision,d.decided_at AS decided_at,"
            "u.value AS usefulness,"
            + personal_sql + " AS personal_relevance "
            "FROM events e LEFT JOIN event_reads er ON er.event_id=e.id AND er.owner=? "
            "LEFT JOIN bookmarks b ON b.event_id=e.id AND b.owner=? "
            "LEFT JOIN radar_decisions d ON d.event_id=e.id AND d.owner=? AND d.topic_id=? "
            "LEFT JOIN radar_usefulness u ON u.event_id=e.id AND u.owner=? AND u.topic_id=? "
            "WHERE " + where + " ORDER BY "
            "CASE WHEN ?=1 AND ((d.decision IS NULL) <> (u.value IS NULL)) "
            "AND julianday(coalesce(d.decided_at,u.rated_at)) "
            "BETWEEN julianday(?) AND julianday(?) "
            "AND ROW_NUMBER() OVER (ORDER BY "
            "CASE WHEN ((d.decision IS NULL) <> (u.value IS NULL)) "
            "AND julianday(coalesce(d.decided_at,u.rated_at)) "
            "BETWEEN julianday(?) AND julianday(?) "
            "THEN julianday(coalesce(d.decided_at,u.rated_at)) END DESC,e.id)<=2 "
            "THEN -julianday(coalesce(d.decided_at,u.rated_at)) "
            "WHEN d.decision IS NULL AND u.value IS NULL THEN 0 "
            "WHEN d.decision IS NULL THEN 1 "
            "WHEN d.decision='dismiss' THEN 3 ELSE 2 END,"
            "personal_relevance DESC,e.importance DESC,"
            + discovery + " DESC,e.id LIMIT ?",
            (*personal_args, owner, owner, owner, topic["id"], owner, topic["id"],
             *args, int(totals["total"] > INITIAL_VISIBLE_HIGHLIGHTS),
             handoff_start, handoff_end, handoff_start, handoff_end, MAX_HIGHLIGHTS),
        ).fetchall()
        highlights = [
            self._decorate_event(
                c, row, topic["platforms"], reviewed_at, policy, topic=topic
            )
            for row in records
        ]
        return topic | {"metrics": totals, "highlights": highlights}

    @staticmethod
    def _raw_leads_for_topic(c, topic: dict, now: datetime) -> dict:
        """Separate read-only glimpse of *unlinked* originals, never scored events.

        The materialized inner query takes at most RAW_SCAN_CAP most-recent raw
        rows using raw_first_ingested before applying expensive substring terms.
        Index traversal is constrained to 48h; at most 2400 records reach the
        expensive title/text substring tests. This is intentionally a recent
        sample, not an exhaustive match count. Each AND
        term may occur anywhere in the full title/text combined (ASCII-insensitive).
        No source_name/importance/derived event summary contributes to a match.
        """
        start = (now - timedelta(hours=RAW_LEAD_HOURS)).isoformat(timespec="milliseconds")
        end = now.isoformat(timespec="milliseconds")
        recent_states = ",".join("?" for _ in RAW_LEAD_STATES)
        all_platforms = ",".join("?" for _ in PLATFORMS)
        selected_platforms = ",".join("?" for _ in topic["platforms"])
        terms = topic["query"].split()
        sql = (
            "WITH recent_raw AS MATERIALIZED ("
            "SELECT record_id FROM raw_records INDEXED BY raw_first_ingested "
            "WHERE first_ingested_at>=? AND first_ingested_at<=? "
            "AND event_id IS NULL AND state IN (" + recent_states + ") "
            "AND plugin_id IN (" + all_platforms + ") "
            "ORDER BY first_ingested_at DESC,record_id LIMIT ?) "
            "SELECT r.record_id,r.title,substr(r.text,1,520) AS preview,"
            "r.source_name,r.source_url,r.plugin_id,r.state,r.content_type,"
            "r.first_ingested_at "
            "FROM recent_raw recent JOIN raw_records r ON r.record_id=recent.record_id "
            "WHERE r.plugin_id IN (" + selected_platforms + ") "
            + "".join(
                "AND instr(lower(r.title||' '||r.text),lower(?))>0 " for _ in terms
            )
            + "ORDER BY r.first_ingested_at DESC,r.record_id LIMIT ?"
        )
        args = (
            start, end, *RAW_LEAD_STATES, *PLATFORMS, RAW_SCAN_CAP,
            *topic["platforms"], *terms, RAW_LEADS_PER_TOPIC,
        )
        rows = c.execute(sql, args).fetchall()
        return {
            "items": [
                {
                    "id": row["record_id"],
                    "kind": "unprocessed_original",
                    "title": row["title"][:300],
                    "preview": row["preview"],
                    "source_name": row["source_name"][:120],
                    "platform": row["plugin_id"],
                    "state": row["state"],
                    "content_type": row["content_type"],
                    "first_ingested_at": row["first_ingested_at"],
                    "url": evidence_url(row["source_url"]),
                }
                for row in rows
            ],
            "lookback_hours": RAW_LEAD_HOURS,
            "scan_cap": RAW_SCAN_CAP,
            "display_cap": RAW_LEADS_PER_TOPIC,
            "scope": (
                "仅近48小时 UTC 首次收录、尚未关联事件的原文；"
                "在最近最多2400条待整理原文中按标题/全文 AND 关键词及所选平台抽样。"
                "排除已整理与已过滤内容；不是事件、编辑评分或独立核实，"
                "未命中不代表没有新消息。"
            ),
        }

    def _coverage_today(self, c, now: datetime) -> dict:
        start = datetime.combine(now.date(), time.min, UTC).isoformat(timespec="milliseconds")
        rows = c.execute(
            "SELECT plugin_id,state,count(*) AS total FROM raw_records "
            "WHERE coalesce(first_ingested_at,ingested_at)>=? "
            "AND coalesce(first_ingested_at,ingested_at)<=? "
            "GROUP BY plugin_id,state",
            (start, now.isoformat(timespec="milliseconds")),
        ).fetchall()
        result = {
            "utc_day": now.date().isoformat(), "raw_new": 0, "completed": 0,
            "filtered": 0, "pending": 0, "awaiting_video": 0,
            "failed": 0, "other": 0,
            "by_platform": {platform: 0 for platform in PLATFORMS},
            "scope": (
                "按原始记录首次收录的 UTC 日统计派生库处理状态；已完成不等于"
                "独立事实核实。此处不包含采集目标轮询失败/未采到的消息。"
            ),
        }
        for row in rows:
            count = row["total"]
            result["raw_new"] += count
            state = row["state"]
            result[state if state in {"completed", "filtered", "pending", "awaiting_video", "failed"} else "other"] += count
            if row["plugin_id"] in PLATFORMS:
                result["by_platform"][row["plugin_id"]] += count
        return result

    def _global_signals(self, c, owner: str, now: datetime, policy: dict) -> list[dict]:
        discovery = "coalesce(e.first_ingested_at,e.created_at)"
        start = datetime.combine(now.date(), time.min, UTC).isoformat(timespec="milliseconds")
        rows = c.execute(
            "SELECT e.id,e.title,e.summary,e.importance,e.category,"
            + discovery + " AS first_ingested_at,e.event_time_start,e.location_status,"
            "CASE WHEN er.event_id IS NOT NULL THEN 1 ELSE 0 END AS read,"
            "CASE WHEN b.event_id IS NOT NULL THEN 1 ELSE 0 END AS bookmarked,"
            "NULL AS decision,NULL AS decided_at,NULL AS personal_relevance "
            "FROM events e LEFT JOIN event_reads er ON er.event_id=e.id AND er.owner=? "
            "LEFT JOIN bookmarks b ON b.event_id=e.id AND b.owner=? "
            "WHERE " + discovery + ">=? AND " + discovery + "<=? AND e.importance>=85 "
            "AND EXISTS(SELECT 1 FROM raw_records r WHERE r.event_id=e.id "
            "AND r.state='completed' AND r.plugin_id IN ('telegram','x','youtube')) "
            "ORDER BY e.importance DESC," + discovery + " DESC,e.id LIMIT ?",
            (owner, owner, start, now.isoformat(timespec="milliseconds"), MAX_GLOBAL_SIGNALS),
        ).fetchall()
        return [
            self._decorate_event(c, row, list(PLATFORMS), None, policy, global_rank=True)
            for row in rows
        ]

    @staticmethod
    def _latest_brief(c, owner: str, identity: str) -> dict | None:
        row = c.execute(
            "SELECT data FROM radar_briefs WHERE owner=? AND topic_id=? "
            "ORDER BY generated_at DESC,id DESC LIMIT 1", (owner, identity)
        ).fetchone()
        return json.loads(row["data"]) if row else None

    def _review_due(self, c, owner: str, now: datetime) -> dict:
        """Read only the latest version per owner/event, never historical reminders.

        Calendar review_on uses Beijing midnight, unlike UTC ingestion statistics.
        This is a bounded, SELECT-only derived-SQLite view; no AI or notification.
        """
        today = now.astimezone(REVIEW_DAY_ZONE).date()
        through = today + timedelta(days=7)
        queue = {
            "enabled": self.plan == "analyst", "timezone": "Asia/Shanghai",
            "day_boundary": "Beijing UTC+08:00", "today": today.isoformat(),
            "through": through.isoformat(), "limit": MAX_REVIEW_DUE,
            "items": [], "has_revisions": False,
        }
        # Server-side entitlement. A plan downgrade never touches prior revisions:
        # Free/Pro may still read them through the original event dossier route.
        if self.plan != "analyst":
            return queue
        if not c.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='dossier_revisions'"
        ).fetchone():
            return queue  # Legacy stores without any personal revisions.
        queue["has_revisions"] = bool(c.execute(
            "SELECT 1 FROM dossier_revisions WHERE owner=? LIMIT 1", (owner,)
        ).fetchone())
        rows = c.execute(
            "WITH latest AS ("
            " SELECT event_id, MAX(version) AS version FROM dossier_revisions "
            " WHERE owner=? GROUP BY event_id"
            ") SELECT d.event_id, d.version, d.created_at, "
            "substr(e.title,1,240) AS title, "
            "json_extract(d.data,'$.fields.review_on') AS review_on, "
            "substr(json_extract(d.data,'$.fields.judgment'),1,181) AS judgment, "
            "substr(json_extract(d.data,'$.fields.support'),1,121) AS support, "
            "substr(json_extract(d.data,'$.fields.falsification'),1,121) AS falsification "
            "FROM latest JOIN dossier_revisions d ON d.owner=? "
            "AND d.event_id=latest.event_id AND d.version=latest.version "
            "JOIN events e ON e.id=d.event_id "
            "WHERE json_type(d.data,'$.fields.review_on')='text' "
            "AND json_extract(d.data,'$.fields.review_on')!='' "
            "AND json_extract(d.data,'$.fields.review_on')<=? "
            "ORDER BY review_on ASC, d.event_id ASC LIMIT ?",
            (owner, owner, through.isoformat(), MAX_REVIEW_DUE),
        ).fetchall()
        for row in rows:
            try:
                due_day = date.fromisoformat(row["review_on"])
                if due_day.isoformat() != row["review_on"]:
                    continue  # Do not interpret malformed or non-ISO saved dates.
            except (TypeError, ValueError):
                continue
            days_until = (due_day - today).days
            queue["items"].append({
                "event_id": row["event_id"], "title": row["title"],
                "version": row["version"], "created_at": row["created_at"],
                "review_on": row["review_on"], "days_until": days_until,
                "status": "overdue" if days_until < 0 else "today" if days_until == 0 else "upcoming",
                "judgment": row["judgment"] or "",
                "support": row["support"] or "",
                "falsification": row["falsification"] or "",
                "evidence_independence": "unknown",
            })
        return queue

    @staticmethod
    def _preview_occurrence_quality(c, event: dict) -> dict:
        """Whitelist real stored, still-consistent event time quality only.

        V87 fail closed: a timestamp in events.event_time_start alone cannot
        prove second precision. Never ship the full events.data, a model quote
        or personal source text in an unsaved trial response. The caller's
        query_only SQLite transaction contains both checks and projection.
        """
        unknown = {
            "event_time_precision": "unknown",
            "event_time_status": "unknown",
            "event_time_end": None,
            "event_civil_start": None,
            "event_civil_end": None,
        }
        start = event.get("event_time_start")
        if not isinstance(start, str) or not start:
            return unknown
        row = c.execute(
            "SELECT event_time_start,data FROM events WHERE id=?",
            (event["id"],)
        ).fetchone()
        if row is None or row["event_time_start"] != start:
            return unknown
        try:
            data = json.loads(row["data"])
        except (TypeError, ValueError):
            return unknown
        if not isinstance(data, dict) or data.get("event_time_start") != start:
            return unknown
        precision = data.get("event_time_precision")
        status = data.get("event_time_status")
        if precision not in ("exact", "day", "month", "range") or status not in (
            "explicit", "inferred", "scheduled"
        ):
            return unknown
        raw_end = data.get("event_time_end")
        if raw_end is not None and not isinstance(raw_end, str):
            return unknown
        try:
            normalized_start = iso_time(start)
            normalized_end = iso_time(raw_end)
        except (ValueError, TypeError, OverflowError):
            return unknown
        if normalized_start is None:
            return unknown
        # A range MUST have a real later end. Other kinds may optionally
        # include one but may never point to an earlier time.
        if precision == "range" and (
            normalized_end is None or normalized_end <= normalized_start
        ):
            return unknown
        if normalized_end is not None and normalized_end < normalized_start:
            return unknown
        civil_start = None
        civil_end = None
        if precision != "exact":
            def trusted_civil_day(value, stamp):
                if type(value) is not str or len(value) != 10 or stamp is None:
                    return None
                try:
                    raw_day = date.fromisoformat(value)
                    utc_day = date.fromisoformat(stamp[:10])
                except ValueError:
                    return None
                # Timezone offsets can cross ONE day, not more. Do not accept
                # arbitrary fake source-calendar strings from historical JSON.
                return value if raw_day.isoformat() == value and abs(
                    (raw_day - utc_day).days
                ) <= 1 else None

            civil_start = trusted_civil_day(
                data.get("event_civil_start"), normalized_start
            )
            if civil_start is None:
                return unknown
            raw_civil_end = data.get("event_civil_end")
            if normalized_end is None:
                if raw_civil_end is not None:
                    return unknown
            else:
                civil_end = trusted_civil_day(raw_civil_end, normalized_end)
                if civil_end is None:
                    return unknown
                if civil_end < civil_start:
                    return unknown
            if precision == "range" and civil_end is None:
                return unknown
        elif data.get("event_civil_start") is not None or data.get("event_civil_end") is not None:
            return unknown
        return {
            "event_time_precision": precision,
            "event_time_status": status,
            "event_time_end": raw_end,
            "event_civil_start": civil_start,
            "event_civil_end": civil_end,
        }

    def preview(self, owner: str, value: Any) -> dict:
        """Unsaved topic trial: one read-only SQLite snapshot, no topic or audit.

        Validate the exact form fields through the same normalizer as topic
        creation. The synthetic identity exists only as a SELECT parameter for
        existing per-topic joins; no row, review waterline or decision is made.
        """
        if not isinstance(value, dict):
            raise ProductError("invalid_radar_preview", "请提交 JSON 对象", 400)
        if set(value) != {"query", "platforms", "min_importance"}:
            raise ProductError(
                "invalid_radar_preview",
                "试查须完整提交 query、platforms、min_importance，且不能包含其他字段",
            )
        fields = _topic_payload({"name": "未保存试查", **value}, partial=False)
        topic = {
            "id": "__unsaved_radar_preview__",
            "query": fields["query"],
            "platforms": fields["platforms"],
            "min_importance": fields["min_importance"],
            "last_reviewed_at": None,
        }
        with self.store.connect() as c:
            # Store.connect() is normally read/write for CRUD. Restrict this
            # connection itself before BEGIN, so even an accidental INSERT in
            # either reused helper fails rather than silently changing state.
            c.execute("PRAGMA query_only=ON")
            c.execute("BEGIN")
            now = datetime.now(UTC)
            policy = self.store._reading_policy(c, owner)
            details = self._details_for_topic(c, topic, owner, now, policy)
            raw = self._raw_leads_for_topic(c, topic, now)
            # The event and time-quality metadata must be read from the same
            # read-only SQLite snapshot; never open a new writable connection
            # just to populate a preview.
            samples = []
            for event in details["highlights"][:3]:
                samples.append({
                    **{key: event[key] for key in (
                        "id", "title", "importance", "event_time_start",
                        "source_published_at", "first_ingested_at", "source_count"
                    )},
                    **self._preview_occurrence_quality(c, event),
                    "source": self._matching_preview_source(c, topic, event["id"]),
                })
        raw_samples = [
            {
                **{key: item[key] for key in (
                    "id", "title", "platform", "state", "first_ingested_at"
                )},
                "url": item["url"],
            }
            for item in raw["items"]
        ]
        days = self.details["limits"]["history_days"]
        return {
            "preview": True,
            "saved": False,
            "query": fields["query"],
            "platforms": fields["platforms"],
            "min_importance": fields["min_importance"],
            "window_days": days,
            "matched_events": details["metrics"]["total"],
            "today_events": details["metrics"]["today_added"],
            "event_samples": samples,
            "raw_sample_count": len(raw_samples),
            "raw_samples": raw_samples,
            "raw_lookback_hours": raw["lookback_hours"],
            "raw_scan_cap": raw["scan_cap"],
            "raw_display_cap": raw["display_cap"],
            "scope": (
                f"已整理事件仅统计当前计划近{days}天 UTC 首次入库、符合平台与重要度门槛、"
                "且同一条所选平台已完成原文标题/全文满足全部 AND 关键词；最多展示3条事件样例。"
                "试查是按条件的当前已收录覆盖，示例排序不保证与正式主题个性化分诊相同"
                "（临时主题不继承已保存主题的决策和复盘水位）。"
                "事件是编辑整理的候选，重要度不是事实概率，来源记录数也不代表独立核实。"
                "另列近48小时待整理原文（不受重要度门槛限制），"
                "仅扫描最新最多2400条并显示至多4条；raw_sample_count 是展示样本条数，"
                "不是全部原文命中数。两类均不代表全网覆盖，未命中不代表没有消息。"
            ),
        }

    def review_due(self, owner: str) -> dict:
        """Independent authenticated GET lane; leave the existing V3 overview shape intact."""
        with self.store.connect() as c:
            c.execute("BEGIN")
            return self._review_due(c, owner, datetime.now(UTC))

    @staticmethod
    def _value_feedback(c, owner: str, now: datetime) -> dict:
        """14 inclusive Beijing calendar days, from explicit owner actions only.

        Rated samples are *current rows* most recently rated in the window.
        Feedback days come from actual changes in audit (including withdrawals),
        so withdrawing a label reduces the sample but cannot erase an action day.
        Neither query derives labels from views, triage or event importance.
        """
        today = now.astimezone(REVIEW_DAY_ZONE).date()
        first_day = (today - timedelta(days=13)).isoformat()
        last_day = today.isoformat()
        cutoff = now.isoformat()
        totals = c.execute(
            "SELECT count(*) AS rated_count,"
            "count(CASE WHEN value='useful' THEN 1 END) AS useful_count,"
            "count(CASE WHEN value='noise' THEN 1 END) AS noise_count "
            "FROM radar_usefulness WHERE owner=? "
            "AND date(rated_at,'+8 hours') BETWEEN ? AND ? "
            "AND julianday(rated_at)<=julianday(?)",
            (owner, first_day, last_day, cutoff),
        ).fetchone()
        days = c.execute(
            "SELECT count(DISTINCT date(at,'+8 hours')) AS feedback_days "
            "FROM audit WHERE owner=? AND action='radar.event.usefulness' "
            "AND date(at,'+8 hours') BETWEEN ? AND ? "
            "AND julianday(at)<=julianday(?)",
            (owner, first_day, last_day, cutoff),
        ).fetchone()["feedback_days"]
        rated = totals["rated_count"]
        return {
            "window_days": 14,
            "rated_count": rated,
            "useful_count": totals["useful_count"],
            "noise_count": totals["noise_count"],
            "useful_ratio": totals["useful_count"] / rated if rated else None,
            "feedback_days": days,
            "day_timezone": "Asia/Shanghai",
            "scope": (
                "近14个北京时间自然日（含今天）本人主动明确评价的现存主题-事件行，"
                "且最近一次标注在窗口内；相同事件在不同主题分别计数。"
                "有用比例仅指被评价样本中的比例，样本不足10条不具代表性；"
                "真实反馈日数只统计发生有效标注/改判/撤销的日期，"
                "撤销保留操作日但不计入现存评价；不是阅读留存率、全站准确率或隐式评分。"
            ),
        }

    @staticmethod
    def _daily_raw_counts(c, topic: dict, start: str, end: str, start_op: str) -> dict:
        """Actual derived-DB rows in this topic/time window; never inferred collection."""
        pins = ",".join("?" for _ in topic["platforms"])
        raw_sql = (
            "FROM raw_records r INDEXED BY raw_first_ingested "
            "WHERE r.first_ingested_at" + start_op + "? AND r.first_ingested_at<=? "
            "AND r.plugin_id IN (" + pins + ")"
        )
        base_args = (start, end, *topic["platforms"])
        # One bounded range/index scan rather than two for each unique topic.
        # Group *all* selected raw states; matching_count applies the EXACT
        # completed-original ASCII-insensitive AND terms, not e.summary.
        # Count nonmatches for the status's platform coverage without an
        # additional unfiltered COUNT scan.
        terms = topic["query"].split()
        match_condition = " AND ".join(
            "instr(lower(r.title||' '||r.text),lower(?))>0" for _ in terms
        )
        rows = c.execute(
            "SELECT r.state,(r.event_id IS NOT NULL) AS linked,"
            "count(*) AS raw_count,"
            "sum(CASE WHEN " + match_condition + " THEN 1 ELSE 0 END) AS n "
            + raw_sql + " GROUP BY r.state,linked",
            (*terms, *base_args),
        ).fetchall()
        ingested = sum(row["raw_count"] for row in rows)
        states = {
            key: 0 for key in (
                "completed", "pending", "retry", "processing",
                "awaiting_video", "filtered", "failed", "other"
            )
        }
        linked_completed = 0
        for row in rows:
            states[row["state"] if row["state"] in states else "other"] += row["n"]
            if row["state"] == "completed" and row["linked"]:
                linked_completed += row["n"]
        return {
            "raw_ingested_on_selected_platforms": ingested,
            "matching_originals": sum(states.values()),
            "matching_by_state": states,
            "completed_linked_to_event": linked_completed,
            "completed_without_event": states["completed"] - linked_completed,
            "pending_or_processing": sum(states[k] for k in (
                "pending", "retry", "processing", "awaiting_video"
            )),
            "scope": (
                "所选平台在所示 UTC 对照窗口内首次入库的派生库原始记录；"
                "查询命中需同一条原文标题/全文包含全部 AND 词项；"
                "原文条数≠独立证实，completed≠已核实真假，"
                "不包含采集端未抓到的内容。"
            ),
        }

    @staticmethod
    def _daily_raw_samples(
        c, topic: dict, start: str, end: str, start_op: str
    ) -> list[dict]:
        """Only genuine unlinked, not-yet-completed keyword-matched raw records."""
        pins = ",".join("?" for _ in topic["platforms"])
        states = ",".join("?" for _ in RAW_LEAD_STATES)
        sql = (
            "SELECT r.record_id,r.title,r.plugin_id,r.state,r.source_name,"
            "r.source_url,r.first_ingested_at FROM raw_records r "
            "INDEXED BY raw_first_ingested WHERE r.first_ingested_at"
            + start_op + "? AND r.first_ingested_at<=? AND r.event_id IS NULL "
            "AND r.plugin_id IN (" + pins + ") AND r.state IN (" + states + ") "
            + "".join(
                "AND instr(lower(r.title||' '||r.text),lower(?))>0 "
                for _ in topic["query"].split()
            )
            + "ORDER BY r.first_ingested_at DESC,r.record_id LIMIT 3"
        )
        rows = c.execute(
            sql, (start, end, *topic["platforms"], *RAW_LEAD_STATES,
                  *topic["query"].split())
        ).fetchall()
        return [
            {
                "id": row["record_id"], "title": row["title"][:240],
                "platform": row["plugin_id"], "state": row["state"],
                "source_name": row["source_name"][:120],
                "url": evidence_url(row["source_url"]),
                "first_ingested_at": row["first_ingested_at"],
                "kind": "unprocessed_original_not_an_event",
            }
            for row in rows
        ]

    @staticmethod
    def _daily_recent_event_match(topic: dict, start: str, end: str) -> tuple[str, list]:
        """Match recent *completed originals*, not merely recently born events.

        Old event clusters may receive a fresh original after the last review;
        filtering by the event's first_ingested_at would silently lose those
        changes. Bound matches by the plan's history window and the UTC cutoff.
        """
        primary, args = Radar._original_keyword_predicate(topic)
        sql = (
            "e.importance>=? AND coalesce(e.first_ingested_at,e.created_at)<=? "
            "AND EXISTS(SELECT 1 FROM raw_records r WHERE r.event_id=e.id "
            "AND r.first_ingested_at>=? AND r.first_ingested_at<=? "
            "AND " + primary + ")"
        )
        return sql, [topic["min_importance"], end, start, end, *args]

    def _daily_event_rows(
        self, c, topic: dict, owner: str, now: datetime, earliest: str,
        *, include_handled: bool = False, daily_source_only: bool = False,
    ) -> list:
        """Recent topic changes; daily suppresses handled actions, review freezes them."""
        reviewed_at = topic["last_reviewed_at"]
        where, where_args = self._daily_recent_event_match(
            topic, earliest, now.isoformat()
        )
        primary, primary_args = self._original_keyword_predicate(topic)
        discovery = "coalesce(e.first_ingested_at,e.created_at)"
        latest = (
            "(SELECT max(r.first_ingested_at) FROM raw_records r "
            "WHERE r.event_id=e.id AND r.first_ingested_at<=? AND " + primary + ")"
        )
        # The older review/overview snapshot contract retains its historical
        # editorial-text heuristic. Daily shortlist selection MUST NOT use
        # derived e.title/e.summary; rank only after actual original evidence.
        relevance, relevance_args = (
            ("0", []) if daily_source_only
            else self._personal_score_sql(topic, reviewed_at)
        )
        clauses = [where]
        extra_args: list = []
        # Future-dated originals must not establish today's eligibility.
        clauses.append(
            "EXISTS(SELECT 1 FROM raw_records r WHERE r.event_id=e.id "
            "AND r.first_ingested_at<=? AND " + primary + ")"
        )
        extra_args.extend((now.isoformat(), *primary_args))
        if reviewed_at is not None:
            clauses.append(
                "(" + discovery + ">? OR EXISTS("
                "SELECT 1 FROM raw_records r WHERE r.event_id=e.id "
                "AND r.first_ingested_at>? AND r.first_ingested_at<=? AND " + primary + "))"
            )
            extra_args.extend((reviewed_at, reviewed_at, now.isoformat(), *primary_args))
        # A completed decision is not a daily action again until a matching
        # original arrived AFTER that decision. The immutable review instead
        # records all changes since its previous watermark, even if triaged.
        if not include_handled:
            clauses.append(
                "(d.decision IS NULL OR " + discovery + ">d.decided_at OR EXISTS("
                "SELECT 1 FROM raw_records r WHERE r.event_id=e.id "
                "AND r.first_ingested_at>d.decided_at "
                "AND r.first_ingested_at<=? AND " + primary + "))"
            )
            extra_args.extend((now.isoformat(), *primary_args))
        sql = (
            "SELECT e.id,e.title,e.summary,e.importance,e.category,"
            + discovery + " AS first_ingested_at,e.event_time_start,e.location_status,"
            "CASE WHEN er.event_id IS NULL THEN 0 ELSE 1 END AS read,"
            "CASE WHEN b.event_id IS NULL THEN 0 ELSE 1 END AS bookmarked,"
            "d.decision,d.decided_at,"
            + relevance + " AS personal_relevance,"
            + latest + " AS matching_original_latest_at "
            "FROM events e LEFT JOIN event_reads er ON er.event_id=e.id AND er.owner=? "
            "LEFT JOIN bookmarks b ON b.event_id=e.id AND b.owner=? "
            "LEFT JOIN radar_decisions d ON d.event_id=e.id AND d.owner=? AND d.topic_id=? "
            "WHERE " + " AND ".join(clauses)
            + (" ORDER BY CASE WHEN d.decision IS NULL THEN 0 ELSE 1 END,"
               "matching_original_latest_at DESC,e.importance DESC,e.id LIMIT ?"
               if daily_source_only else
               " ORDER BY CASE WHEN d.decision IS NULL THEN 0 ELSE 1 END,"
               "personal_relevance DESC,e.importance DESC,"
               "matching_original_latest_at DESC,e.id LIMIT ?")
        )
        return c.execute(
            sql,
            (
                *relevance_args, now.isoformat(), *primary_args,
                owner, owner, owner, topic["id"],
                *where_args, *extra_args, 24,
            ),
        ).fetchall()

    def _review_change_snapshot(
        self, c, topic: dict, owner: str, now: datetime, policy: dict
    ) -> tuple[list[dict], list[dict], dict]:
        """Freeze daily-equivalent newly linked originals, not old safe fallbacks.

        Keep the traditional brief's items/sources schema for the current UI.
        Distinct record IDs and the three separate clocks live in additive
        fields; an earlier saved brief is never updated.
        """
        reviewed_at = topic["last_reviewed_at"]
        earliest = datetime.combine(
            now.date() - timedelta(days=self.details["limits"]["history_days"] - 1),
            time.min, UTC,
        ).isoformat(timespec="milliseconds")
        truncated = reviewed_at is not None and reviewed_at < earliest
        window = {
            "kind": (
                "first_review_baseline" if reviewed_at is None else
                "history_limited" if truncated else "since_review"
            ),
            "from": earliest if reviewed_at is None or truncated else reviewed_at,
            "from_operator": ">=" if reviewed_at is None or truncated else ">",
            "through": now.isoformat(timespec="microseconds"),
            "previous_review_at": reviewed_at,
            "history_truncated": truncated,
            "evidence_clock": "raw_records.first_ingested_at (UTC)",
        }
        items, changes = [], []
        for event in self._daily_event_rows(
            c, topic, owner, now, earliest, include_handled=True
        ):
            # Exactly as in daily: an existing cluster MUST cite a matching,
            # completed, safely navigable original first ingested AFTER the
            # previous review. Never promote a historical safe URL as new.
            revived = reviewed_at is not None and event["first_ingested_at"] <= reviewed_at
            originals = self._daily_evidence(
                c, topic, event["id"], reviewed_at, now.isoformat(),
                new_after=reviewed_at if revived else None,
            )
            if not originals:
                continue
            decorated = self._decorate_event(
                c, event, topic["platforms"], reviewed_at, policy, topic=topic
            )
            kind = (
                "initial_baseline" if reviewed_at is None else
                "new_original_on_existing_event" if revived else "new_event"
            )
            # Only validated occurrence precision can reveal the event clock.
            # An ingestion or publication date cannot fill an unknown event date.
            occurred = (
                decorated["event_time_start"]
                if decorated["event_time_precision"] != "unknown" else None
            )
            item = {
                key: decorated[key] for key in (
                    "id", "title", "importance", "personal_relevance",
                    "decision", "first_ingested_at", "archived", "source_count",
                )
            } | {
                "sources": [
                    {"name": src["source_name"], "platform": src["platform"], "url": src["url"]}
                    for src in originals
                ],
                "change_kind": kind,
                "change_originals": originals,
                "event_occurred_at": occurred,
                "event_time_status": decorated["event_time_status"],
                "event_time_precision": decorated["event_time_precision"],
                "event_time_end": decorated["event_time_end"],
                "event_civil_start": decorated["event_civil_start"],
                "event_civil_end": decorated["event_civil_end"],
                "source_published_at": decorated["source_published_at"],
            }
            items.append(item)
            changes.append({
                "event_id": event["id"],
                "kind": kind,
                "event_first_ingested_at": event["first_ingested_at"],
                "event_occurred_at": occurred,
                "event_time_status": item["event_time_status"],
                "event_time_precision": item["event_time_precision"],
                "source_published_at": item["source_published_at"],
                "latest_matching_original_at": event["matching_original_latest_at"],
                "originals": originals,
            })
            if len(items) == MAX_HIGHLIGHTS:
                break
        return items, changes, window

    @staticmethod
    def _daily_evidence(
        c, topic: dict, event_id: str, reviewed_at: str | None, upper: str,
        *, new_after: str | None = None,
    ) -> list[dict]:
        """Only safely navigable *matching* completed originals; no network check."""
        primary, args = Radar._original_keyword_predicate(topic)
        sql = (
            "SELECT r.record_id,r.source_name,r.source_url,r.plugin_id,"
            "r.first_ingested_at,r.source_published_at FROM raw_records r "
            "WHERE r.event_id=? AND r.first_ingested_at<=? AND " + primary
            + (" AND r.first_ingested_at>?" if new_after is not None else "")
            + " ORDER BY r.first_ingested_at DESC,r.record_id LIMIT ?"
        )
        seen: set[str] = set()
        evidence = []
        for row in c.execute(
            sql, (event_id, upper, *args,
                  *((new_after,) if new_after is not None else ()),
                  MAX_SOURCES + MAX_MATCHING_URL_FALLBACK)
        ):
            url = evidence_url(row["source_url"])
            if not url or url in seen:
                continue
            seen.add(url)
            evidence.append({
                "record_id": row["record_id"], "platform": row["plugin_id"],
                "source_name": row["source_name"], "url": url,
                "source_published_at": row["source_published_at"],
                "first_ingested_at": row["first_ingested_at"],
                "new_since_review": (
                    row["first_ingested_at"] > reviewed_at
                    if reviewed_at is not None else None
                ),
            })
            if len(evidence) == 3:
                break
        return evidence


    @staticmethod
    def _daily_copy_keys(raw: dict) -> set[tuple[str, str]]:
        """Deduplicate exact safe URLs and substantial whitespace-identical text.

        Brief or generic snippets are NOT proof of a repost; no fuzzy story
        clustering, inferred original authorship or independent corroboration.
        """
        keys = set()
        literal = " ".join(raw["title"].split()) + "\n" + " ".join(raw["text"].split())
        # A permalink may legitimately be edited: same URL, CHANGED primary
        # prose is not proven to be a repost. Compare URL AND literal content.
        if url := evidence_url(raw["source_url"]):
            keys.add(("url_with_exact_content", hashlib.sha256(
                (url + "\n" + literal).encode("utf-8")
            ).hexdigest()))
        if len(literal) >= DAILY_LONG_COPY_CHARS:
            keys.add(("long_literal", hashlib.sha256(
                literal.encode("utf-8")
            ).hexdigest()))
        return keys

    @staticmethod
    def _daily_publication(value: str | None) -> tuple[str | None, str]:
        if not value:
            return None, "unknown"
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                return None, "unknown"
        except (TypeError, ValueError, OverflowError):
            return None, "unknown"
        return value, "publisher_reported_unverified"

    @staticmethod
    def _daily_utc_stamp(value: str | None) -> datetime | None:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed.astimezone(UTC) if parsed.tzinfo is not None else None
        except (AttributeError, ValueError, OverflowError):
            return None

    @classmethod
    def _daily_ranked_originals(
        cls, c, topic: dict, event_id: str, reviewed_at: str | None,
        through: str, *, new_after: str | None,
    ) -> tuple[list[dict], dict]:
        """Scan originals in ingestion order BEFORE deciding novelty.

        A newly collected exact-url/long-text replay is not new evidence
        against the same event. Keep the completed AND predicate and safe-url
        gate unchanged, and never fill unknown publication dates.
        """
        predicate, args = cls._original_keyword_predicate(topic)
        rows = c.execute(
            "SELECT r.record_id,r.source_name,r.source_url,r.plugin_id,"
            "r.first_ingested_at,r.source_published_at,r.title,r.text "
            "FROM raw_records r WHERE r.event_id=? AND r.first_ingested_at<=? "
            "AND " + predicate +
            " ORDER BY r.first_ingested_at DESC,r.record_id DESC LIMIT ?",
            (event_id, through, *args, DAILY_REPOST_SCAN_CAP + 1),
        ).fetchall()
        truncated = len(rows) > DAILY_REPOST_SCAN_CAP
        rows = rows[:DAILY_REPOST_SCAN_CAP]
        seen: set[tuple[str, str]] = set()
        novel: list[dict] = []
        duplicate_count = 0
        for row in reversed(rows):
            raw = dict(row)
            keys = cls._daily_copy_keys(raw)
            if keys and seen.intersection(keys):
                duplicate_count += 1
                continue
            seen.update(keys)
            novel.append(raw)
        permitted = []
        for raw in reversed(novel):
            if new_after is not None and raw["first_ingested_at"] <= new_after:
                continue
            if not (url := evidence_url(raw["source_url"])):
                continue
            published, publication_status = cls._daily_publication(
                raw["source_published_at"]
            )
            title = raw["title"].translate(_DAILY_ASCII_LOWER)
            hits = sum(term.translate(_DAILY_ASCII_LOWER) in title
                       for term in topic["query"].split())
            permitted.append({
                "record_id": raw["record_id"], "platform": raw["plugin_id"],
                "source_name": raw["source_name"], "url": url,
                "source_published_at": published,
                "source_published_status": publication_status,
                "first_ingested_at": raw["first_ingested_at"],
                "new_since_review": (
                    raw["first_ingested_at"] > reviewed_at
                    if reviewed_at is not None else None
                ),
                "_title_hits": hits,
                "_copy_keys": cls._daily_copy_keys(raw),
            })
        # We cannot check older copies if the oldest 800 matching records were
        # omitted. A historical change must not be re-offered as demonstrably
        # new without that information.
        if truncated and new_after is not None:
            permitted = []
        selected = permitted[:3]
        best = max(selected, key=lambda row: (
            row["_title_hits"], row["first_ingested_at"], row["record_id"]
        )) if selected else None
        result = [
            {k: v for k, v in row.items() if not k.startswith("_")}
            for row in selected
        ]
        return result, {
            "selected_title_hits": best["_title_hits"] if best else 0,
            "selected_record_id": best["record_id"] if best else None,
            "selected_ingested_at": best["first_ingested_at"] if best else None,
            "copy_keys": set().union(*(row["_copy_keys"] for row in selected)),
            "per_original_copy_keys": [row["_copy_keys"] for row in selected],
            "duplicate_original_rows": duplicate_count,
            "matching_original_rows_scanned": len(rows),
            "scan_truncated": truncated,
            "duplicate_only": bool(rows) and duplicate_count > 0 and not selected,
        }

    @staticmethod
    def _daily_feedback_counts(c, owner: str) -> tuple[dict, set]:
        """Per-owner explicit actions, also exact-no-decision cache membership."""
        by_topic: dict[str, dict[str, list[tuple[str, str]]]] = {}
        topics_with_decisions = set()
        for row in c.execute(
            "SELECT topic_id,event_id,decision,decided_at FROM radar_decisions "
            "WHERE owner=? ORDER BY topic_id,event_id", (owner,),
        ):
            topic_id = row["topic_id"]
            topics_with_decisions.add(topic_id)
            by_topic.setdefault(topic_id, {key: [] for key in DECISIONS})[
                row["decision"]
            ].append((row["event_id"], row["decided_at"]))
        return by_topic, topics_with_decisions

    @staticmethod
    def _daily_personal_priority(
        topic: dict, event: dict, source: dict, feedback: dict,
        now: datetime,
    ) -> tuple[int, dict, str]:
        """Deterministic original-only match plus explicit user decisions."""
        threshold = max(
            (now - timedelta(days=DAILY_FEEDBACK_DAYS)).isoformat(),
            topic["updated_at"],
        )
        feedback_counts = {
            kind: sum(
                1 for event_id, stamp in feedback.get(kind, ())
                if event_id != event["id"] and threshold <= stamp <= now.isoformat()
            )
            for kind in DECISIONS
        }
        topic_bonus = max(-21, min(21,
            7 * min(2, feedback_counts["research"])
            + 4 * min(3, feedback_counts["watch"])
            - 7 * min(3, feedback_counts["dismiss"])
        ))
        prior_bonus = {"research": 7, "watch": 4, "dismiss": -14, None: 0}[
            event["decision"]
        ]
        terms = len(topic["query"].split())
        hits = source["selected_title_hits"]
        title_bonus = (30 * hits) // terms
        stamp = Radar._daily_utc_stamp(source["selected_ingested_at"])
        recent_bonus = 6 if stamp is not None and (
            0 <= (now - stamp).total_seconds() <= 48 * 3600
        ) else 0
        unread_bonus = 4 if not event["read"] else 0
        total = max(0, min(
            100, 45 + title_bonus + topic_bonus + prior_bonus
            + recent_bonus + unread_bonus
        ))
        components = {
            "query_terms": terms, "original_title_terms": hits,
            "primary_original_base": 45, "original_title_bonus": title_bonus,
            "explicit_topic_feedback_counts": feedback_counts,
            "explicit_topic_feedback_bonus": topic_bonus,
            "same_event_previous_decision_bonus": prior_bonus,
            "recent_collection_bonus": recent_bonus,
            "unread_bonus": unread_bonus,
            "representative_original_record_id": source["selected_record_id"],
            "total": total,
        }
        why = (
            f"同一条可安全导航的已完成原文满足全部{terms}个AND词项；"
            f"其中原文标题命中{hits}/{terms}，原文位置分45+{title_bonus}；"
            f"本主题近90天本人主动研究{feedback_counts['research']}、"
            f"关注{feedback_counts['watch']}、忽略{feedback_counts['dismiss']}，"
            f"反馈加权{topic_bonus:+d}；本事件既有决定{prior_bonus:+d}、"
            f"近48小时首次收录+{recent_bonus}、未读+{unread_bonus}，"
            f"得到{total}/100；只是个人待查优先级，非独立证实或事实概率。"
        )
        return total, components, why

    def daily(self, owner: str) -> dict:
        """Single-user daily decision feed: a read-only, explicit-evidence snapshot.

        This is not a news truth classifier. All counts describe local derived
        records, all dates come from stored timestamps, and no new AI is run.
        """
        with self.store.connect() as c:
            c.execute("PRAGMA query_only=ON")
            c.execute("BEGIN")
            now = datetime.now(UTC)
            upper = now.isoformat()
            history_days = self.details["limits"]["history_days"]
            earliest = datetime.combine(
                now.date() - timedelta(days=history_days - 1), time.min, UTC
            ).isoformat(timespec="milliseconds")
            rows = c.execute(
                "SELECT * FROM radar_topics WHERE owner=? ORDER BY created_at,id",
                (owner,),
            ).fetchall()
            policy = self.store._reading_policy(c, owner)
            feedback, topics_with_decisions = self._daily_feedback_counts(c, owner)
            # Same read-only snapshot; keys contain every SQL-relevant
            # property. NEVER reuse another topic's explicit decisions.
            raw_cache, current_cache, new_event_cache = {}, {}, {}
            no_decisions_cache, original_cache = {}, {}
            topic_summaries = []
            candidates = []
            for index, row in enumerate(rows):
                topic = _topic(row)
                if index >= self.details["limits"]["max_topics"]:
                    topic_summaries.append({
                        "id": topic["id"], "name": topic["name"],
                        "version": topic["version"], "suspended": True,
                        "last_reviewed_at": topic["last_reviewed_at"],
                        "status": {
                            "code": "suspended",
                            "explanation": "当前计划暂不分析此主题，原配置与个人判断仍保留。",
                        },
                        "since_baseline": None, "raw": None,
                        "unprocessed_samples": [],
                    })
                    continue
                reviewed = topic["last_reviewed_at"]
                if reviewed is None:
                    baseline_kind = "first_review_baseline"
                    start, start_op = earliest, ">="
                    truncated = False
                elif reviewed < earliest:
                    baseline_kind = "history_limited"
                    start, start_op = earliest, ">="
                    truncated = True
                else:
                    baseline_kind = "since_review"
                    start, start_op = reviewed, ">"
                    truncated = False
                semantics = (topic["query"], tuple(topic["platforms"]),
                             topic["min_importance"])
                raw_key = (semantics[:2], start, upper, start_op)
                if raw_key not in raw_cache:
                    raw_cache[raw_key] = (
                        self._daily_raw_counts(c, topic, start, upper, start_op),
                        self._daily_raw_samples(c, topic, start, upper, start_op),
                    )
                raw, raw_samples = raw_cache[raw_key]
                current_key = (semantics, earliest, upper)
                if current_key not in current_cache:
                    current_where, current_args = self._daily_recent_event_match(
                        topic, earliest, upper
                    )
                    current_cache[current_key] = c.execute(
                        "SELECT count(*) FROM events e WHERE " + current_where,
                        current_args,
                    ).fetchone()[0]
                current_events = current_cache[current_key]
                if reviewed is None:
                    newly_ingested_events = None
                else:
                    new_key = (current_key, reviewed)
                    if new_key not in new_event_cache:
                        current_where, current_args = self._daily_recent_event_match(
                            topic, earliest, upper
                        )
                        new_event_cache[new_key] = c.execute(
                            "SELECT count(*) FROM events e WHERE " + current_where
                            + " AND coalesce(e.first_ingested_at,e.created_at)>?",
                            (*current_args, reviewed),
                        ).fetchone()[0]
                    newly_ingested_events = new_event_cache[new_key]
                # Reuse a candidate SQL result across topics only when neither
                # topic has ANY owner decisions and all other parameters match.
                rows_key = (semantics, reviewed, earliest, upper)
                if topic["id"] not in topics_with_decisions and rows_key in no_decisions_cache:
                    event_rows = no_decisions_cache[rows_key]
                else:
                    event_rows = self._daily_event_rows(
                        c, topic, owner, now, earliest, daily_source_only=True
                    )
                    if topic["id"] not in topics_with_decisions:
                        no_decisions_cache[rows_key] = event_rows
                missing_links = 0
                duplicate_only = 0
                uncertain_replays = 0
                valid = 0
                for event in event_rows:
                    # A revived old event must cite an actually *new* original.
                    # A safe historical link cannot substitute for an unsafe
                    # or missing link on the new change that triggered the card.
                    new_after = (
                        reviewed if reviewed is not None
                        and event["first_ingested_at"] <= reviewed else None
                    )
                    if (event["decided_at"] is not None
                            and event["first_ingested_at"] <= event["decided_at"]):
                        new_after = max(new_after or "", event["decided_at"])
                    evidence_key = (semantics[:2], event["id"], reviewed,
                                    upper, new_after)
                    if evidence_key not in original_cache:
                        original_cache[evidence_key] = self._daily_ranked_originals(
                            c, topic, event["id"], reviewed, upper,
                            new_after=new_after,
                        )
                    originals, source_meta = original_cache[evidence_key]
                    if not originals:
                        if source_meta["scan_truncated"] and new_after is not None:
                            uncertain_replays += 1
                        elif source_meta["duplicate_only"]:
                            duplicate_only += 1
                        else:
                            missing_links += 1
                        continue
                    value, components, reason = self._daily_personal_priority(
                        topic, event, source_meta, feedback.get(topic["id"], {}), now,
                    )
                    # Only the new daily preview uses primary-original priority:
                    # saved V132 overview/review heuristics remain unchanged.
                    enriched = dict(event)
                    enriched["personal_relevance"] = value
                    valid += 1
                    candidates.append((
                        topic, enriched, originals, baseline_kind,
                        source_meta, components, reason,
                    ))
                # These are distinct data conditions, not guessed collector/model
                # failures. Global collector/worker telemetry is attached by web.
                if valid:
                    status = ("ready", "发现可打开词项命中原文的待决定或有新证据待重判事件。")
                elif missing_links:
                    status = ("missing_evidence_link", "本次候选变化缺少可打开且通过本地安全校验的对应原文链接；不会用旧证据冒充新增。")
                elif raw["pending_or_processing"]:
                    status = ("processing", "命中原文确实存在待处理/重试/视频等待状态，当前不能当作已整理事件。")
                elif raw["matching_by_state"]["failed"]:
                    status = ("processing_failed", "命中原文有失败记录，请查看处理器状态或稍后重试。")
                elif raw["completed_without_event"]:
                    status = ("not_linked_to_event", "有已完成原文但尚未关联到事件，不能进行事件分诊。")
                elif raw["raw_ingested_on_selected_platforms"] == 0:
                    status = ("no_raw_in_window", "该平台及对照窗口内派生库没有新的原始入库记录；无法据此断言采集器未运行。")
                elif raw["matching_originals"] == 0:
                    status = ("no_keyword_match", "窗口内有原文入库，但没有同一原文满足全部查询词项。")
                elif raw["matching_by_state"]["filtered"]:
                    status = ("filtered", "命中原文存在已过滤记录，未形成符合条件的事件。")
                elif uncertain_replays:
                    status = ("no_actionable_change", "历史原文超过有界去重扫描，无法排除较旧的同文转载；本轮不声称有新证据。")
                elif duplicate_only:
                    status = ("no_actionable_change", "新入库记录仅为已见过的相同链接或足够长的原文复制件，不作为新增行动项。")
                else:
                    status = ("no_actionable_change", "没有可打开原文且符合主题门槛的新增待决定事件；已决定且无新证据的事件不会重复推送。")
                topic_summaries.append({
                    "id": topic["id"], "name": topic["name"],
                    "version": topic["version"], "suspended": False,
                    "last_reviewed_at": reviewed,
                    "since_baseline": {
                        "kind": baseline_kind, "from": start, "from_operator": start_op,
                        "through": upper, "history_truncated": truncated,
                        "description": (
                            "尚未首次复盘：这是计划窗口内已有内容的初始基线，不冒充复盘后新增。"
                            if reviewed is None else
                            "上次复盘早于计划可见窗口，仅显示窗口内变化，不能声称完整覆盖其间。"
                            if truncated else
                            "只对照本主题上次复盘后首次入库的记录（UTC）。"
                        ),
                    },
                    "raw": raw, "current_matched_events": current_events,
                    "newly_ingested_events_since_review": newly_ingested_events,
                    "eligible_action_samples": valid,
                    "candidate_limit_reached": len(event_rows) == 24,
                    "not_navigable_candidate_samples": missing_links,
                    "duplicate_reprint_candidate_samples": duplicate_only,
                    "dedup_scan_uncertain_candidate_samples": uncertain_replays,
                    "unprocessed_samples": raw_samples,
                    "status": {"code": status[0], "explanation": status[1]},
                })

            def sort_timestamp(value):
                try:
                    stamp = datetime.fromisoformat(value)
                    return stamp.timestamp() if stamp.tzinfo is not None else 0
                except (ValueError, TypeError, OverflowError):
                    return 0

            def score(entry):
                topic, event, _, baseline_kind, _, _, _ = entry
                # Rank deterministic, not a model-assigned probability: reviewed
                # changes, undecided, explicit personal heuristic, editorial rank.
                return (
                    baseline_kind == "first_review_baseline",
                    event["decision"] is not None,
                    -int(event["personal_relevance"]),
                    -int(event["importance"]),
                    -sort_timestamp(event["matching_original_latest_at"]),
                    topic["id"], event["id"],
                )

            top = []
            seen_events = set()
            seen_exact_originals = set()
            cross_event_exact_copies = 0
            for (topic, event, originals, baseline_kind, source_meta,
                 components, reason) in sorted(candidates, key=score):
                if event["id"] in seen_events:
                    continue
                # Cross-event clusters with different IDs can still share the
                # EXACT same permalink/long literal original. No semantic
                # inference about merely similar reports.
                signatures = source_meta["copy_keys"]
                if (source_meta["per_original_copy_keys"] and all(
                    keys and not keys.isdisjoint(seen_exact_originals)
                    for keys in source_meta["per_original_copy_keys"]
                )):
                    cross_event_exact_copies += 1
                    continue
                seen_events.add(event["id"])
                seen_exact_originals.update(signatures)
                decorated = self._decorate_event(
                    c, event, topic["platforms"], topic["last_reviewed_at"],
                    policy, topic=topic,
                )
                reviewed = topic["last_reviewed_at"]
                new_event = reviewed is not None and event["first_ingested_at"] > reviewed
                change = (
                    "initial_baseline" if reviewed is None else
                    "new_event" if new_event else "new_original_on_existing_event"
                )
                validated_occurrence = decorated["event_time_precision"] != "unknown"
                publications = [
                    src["source_published_at"] for src in originals
                    if src["source_published_at"] is not None
                ]
                matched_publication = (
                    min(publications, key=self._daily_utc_stamp) if publications else None
                )
                publication_status = (
                    "publisher_reported_unverified" if matched_publication
                    else "unknown"
                )
                old_publication_new_ingestion = (
                    matched_publication is not None and reviewed is not None
                    and self._daily_utc_stamp(matched_publication)
                    <= self._daily_utc_stamp(reviewed)
                    and any(src["new_since_review"] for src in originals)
                )
                occurred = event["event_time_start"] if validated_occurrence else None
                date_explanation = (
                    "发生时间未知，不能用入库或发表时间代替。"
                    if occurred is None else
                    "发生时间来自既有质量字段，仍需亲自核对。"
                )
                if matched_publication is None:
                    date_explanation += " 这批关键词命中原文的发表时间未知。"
                if old_publication_new_ingestion:
                    date_explanation += " 有较早标记发表的原文最近才入库，不能称作新发生。"
                dedup_note = (
                    f"去重排除了{source_meta['duplicate_original_rows']}条重复原文；"
                    if source_meta["duplicate_original_rows"] else ""
                )
                # Owner/topic/event usefulness is a separate explicit action.
                # Read it only for at most three selected cards, from this SAME
                # read-only transaction. Never infer it from triage and never
                # reuse per-topic candidates as though feedback were global.
                usefulness_row = c.execute(
                    "SELECT value FROM radar_usefulness "
                    "WHERE owner=? AND topic_id=? AND event_id=?",
                    (owner, topic["id"], event["id"]),
                ).fetchone()
                usefulness = (
                    usefulness_row["value"] if usefulness_row is not None
                    and usefulness_row["value"] in ("useful", "noise") else None
                )
                top.append({
                    "rank": len(top) + 1,
                    "topic": {
                        "id": topic["id"], "name": topic["name"],
                        "version": topic["version"],
                        "last_reviewed_at": reviewed,
                    },
                    "event": {
                        "id": event["id"], "title": event["title"],
                        "editorial_summary": event["summary"],
                        "summary_is_original_evidence": False,
                        "importance": event["importance"],
                        "importance_is_probability": False,
                        "personal_relevance": event["personal_relevance"],
                        "read": decorated["read"],
                        "decision": event["decision"],
                        "decided_at": event["decided_at"],
                        "usefulness": usefulness,
                        "source_count": decorated["source_count"],
                        "event_occurred_at": (
                            event["event_time_start"] if validated_occurrence else None
                        ),
                        "event_time_status": decorated["event_time_status"],
                        "event_time_precision": decorated["event_time_precision"],
                        "event_civil_start": decorated["event_civil_start"],
                        "event_civil_end": decorated["event_civil_end"],
                        "source_published_at": decorated["source_published_at"],
                        "first_ingested_at": event["first_ingested_at"],
                        "matching_original_published_at": matched_publication,
                        "matching_original_published_status": publication_status,
                    },
                    "ranking": {
                        "personal_priority": int(event["personal_relevance"]),
                        "components": components,
                        "order": [
                            "reviewed_topic_changes_before_initial_baseline",
                            "undecided_before_handled_with_new_original",
                            "original_only_personal_priority_desc",
                            "editorial_importance_tiebreak_desc",
                            "matching_original_latest_ingestion_desc",
                            "stable_topic_event_id",
                        ],
                        "scope": (
                            "同条已完成原文内AND词项及标题命中位置、个人显式"
                            "主题决定、入库新鲜度、已读状态构成行动优先级。"
                            "仅对每主题最多24条样本排序，非真实性/语义/全库概率。"
                        ),
                    },
                    "dates": {
                        "event_occurred_at": occurred,
                        "event_occurred_status": (
                            decorated["event_time_status"] if occurred else "unknown"
                        ),
                        "matching_original_published_at": matched_publication,
                        "matching_original_published_status": publication_status,
                        "event_first_ingested_at": event["first_ingested_at"],
                        "latest_matching_original_ingested_at": event["matching_original_latest_at"],
                        "old_publication_new_ingestion": bool(old_publication_new_ingestion),
                        "event_source_published_scope": (
                            "legacy earliest associated completed original; may not match topic"
                        ),
                        "explanation": date_explanation,
                    },
                    "change": {
                        "kind": change,
                        "description": (
                            "首次复盘前的初始候选，不属于‘上次复盘后新增’。"
                            if reviewed is None else
                            "事件首次入库晚于本主题上次复盘。"
                            if new_event else
                            "事件已存在，但至少一条命中词项的原文首次入库晚于上次复盘。"
                        ),
                        "latest_matching_original_at": event["matching_original_latest_at"],
                        "history_limited": baseline_kind == "history_limited",
                        "ingested_does_not_imply_newly_occurred_or_published": True,
                        "old_publication_new_ingestion": bool(old_publication_new_ingestion),
                    },
                    "evidence": {
                        "originals": originals,
                        "locally_checked": "safe_navigation_url_and_same_original_AND_terms",
                        "claim_verified": False, "independent_confirmation": "unknown",
                        "note": "仅同条已完成原文匹配与离线链接安全校验；可能为转载，不等于独立证实；不联网/不核查事实。",
                        "deduplication": {
                            "method": "identical_safe_url_and_literal_content_or_long_whitespace_exact_title_text",
                            "long_copy_min_characters": DAILY_LONG_COPY_CHARS,
                            "duplicate_original_rows_in_sample": source_meta["duplicate_original_rows"],
                            "matching_original_rows_scanned": source_meta["matching_original_rows_scanned"],
                            "scan_cap": DAILY_REPOST_SCAN_CAP,
                            "scan_truncated": source_meta["scan_truncated"],
                            "semantic_duplicate_detection": False,
                            "independent_authorship_verified": False,
                        },
                    },
                    "why_watch": (
                        reason + " " + date_explanation + dedup_note
                        + "编辑重要度只作资格门槛及同分排序，不是事实概率；"
                          "跨平台转载不等于独立确认。"
                    ),
                    "actions": {
                        "decision": {
                            "method": "POST",
                            "path": f"/api/radar/topics/{topic['id']}/decisions",
                            "event_id": event["id"],
                            "allowed_values": ["watch", "research", "dismiss", None],
                        },
                        "usefulness": {
                            "method": "POST",
                            "path": f"/api/radar/topics/{topic['id']}/usefulness",
                            "event_id": event["id"],
                            "allowed_values": ["useful", "noise", None],
                            "independent_of_decision": True,
                        },
                        "dossier": {
                            "path": f"/api/events/{event['id']}/dossier",
                            "read_method": "GET",
                            "write_method": "PUT" if self.plan in ("pro", "analyst") else None,
                            "review_on_timezone": "Asia/Shanghai",
                        },
                        "topic_review": {
                            "method": "POST",
                            "path": f"/api/radar/topics/{topic['id']}/review",
                            "version": topic["version"],
                        },
                        "review_due_path": "/api/radar/reviews",
                    },
                })
                if len(top) == 3:
                    break
            return {
                "generated_at": upper,
                "day_utc": now.date().isoformat(),
                "today_top3": top,
                "topics": topic_summaries,
                "coverage_today": self._coverage_today(c, now),
                "review_due": self._review_due(c, owner, now),
                "owner_revision": self._owner_revision(c, owner),
                "limits": {
                    "top_events": 3, "candidate_samples_per_topic": 24,
                    "original_links_per_event": 3, "history_days": history_days,
                    "daily_repost_scan_per_event": DAILY_REPOST_SCAN_CAP,
                    "topic_feedback_days": DAILY_FEEDBACK_DAYS,
                },
                "deduplication": {
                    "cross_event_exact_copy_candidates_skipped": cross_event_exact_copies,
                    "event_ids_unique": True,
                    "semantic_story_identity_unverified": True,
                },
                "interpretation": (
                    "只统计本站已收录的 Telegram/X/YouTube 及已完成原文；"
                    "复盘水位按主题保留 UTC 时间，无首次复盘时明确显示初始基线。"
                    "今日 Top 3 是当前主题中优先采取行动的三条候选，不表示全部发生于今日，"
                    "也不保证全网完整或事实真伪。候选每主题最多扫描24条，"
                    "同一事件跨主题去重，另过滤相同原文链接/较长同文复制；"
                    "相似报道不做语义聚类，原文不代表独立核实，来源 URL 不联网核查。"
                    "先读原文再选择关注/研究/忽略，Pro/Analyst 可在独立证据包保存北京时间复查日，"
                    "主题复盘另通过版本化 POST 更新水位；三者不会彼此隐式代办。"
                ),
            }

    @staticmethod
    def _orientation_query_hint(editorial_title: str, original_text: str) -> str | None:
        """One literal substring in the SAME completed original; never AI search.

        Display only as an optional editable starting point. An event's model
        title may be Chinese while its actual original is English; therefore
        NEVER send a translated editorial term as a confirmed topic match.
        """
        import re
        raw = (original_text or "")[:2400]
        # Favor a Chinese subject mentioned repeatedly in the real original,
        # but also appearing in the editorial headline. No semantic inference.
        choices = []
        for phrase in re.findall(r"[一-龥]{3,36}", editorial_title or ""):
            for width in range(3, min(8, len(phrase)) + 1):
                for start in range(len(phrase) - width + 1):
                    part = phrase[start:start + width]
                    count = raw.count(part)
                    if count:
                        choices.append((min(count, 6), width, -start, part))
        if choices:
            return max(choices)[-1]
        # Prefer a literal subject name present in BOTH the displayed headline
        # and the SAME completed original. A longest-word-only hint can select
        # an unrelated tail word (e.g. "vulnerabilities" for Navier-Stokes).
        # The shared term is only a query suggestion, never fact corroboration.
        shared = []
        generic = {"api", "sdk", "app", "web", "ios", "llm", "rce", "cve",
                   "pro", "www", "http", "https", "the", "and", "for",
                   "new", "use", "core", "data", "tech"}
        for index, word in enumerate(re.findall(
            r"[A-Za-z][A-Za-z0-9-]{2,26}", editorial_title or ""
        )):
            if word.lower() in generic or re.fullmatch(r"[IVXLCDM]+", word, re.I):
                continue
            if not re.search(r"(?<![A-Za-z0-9])" + re.escape(word)
                             + r"(?![A-Za-z0-9])", raw, re.I):
                continue
            distinctive = (any(ch.isdigit() for ch in word) or
                           (any(ch.isupper() for ch in word[1:]) and
                            any(ch.islower() for ch in word)))
            specificity = 3 if distinctive else 2 if word.isupper() else 1
            shared.append((specificity, len(word), -index, word))
        if shared:
            return max(shared)[-1]
        # With translated headlines and no shared Latin term, a clearly
        # capitalized compound named in the original's opening is preferable
        # to a longer generic word later in the post. No translation occurs.
        plain = re.sub(r"https?://[^\s]+|@[A-Za-z0-9_]+", " ", raw)
        rejected = {"breaking", "following", "important", "available",
                    "sponsored", "subscribe", "copyright", "newsletter",
                    "probably", "sometimes", "everything", "yesterday",
                    "tomorrow", "announcement", "according", "something"}
        words = re.findall(r"\b[A-Za-z][A-Za-z-]{8,26}\b", plain[:640])
        matches = [(
            1 if word in plain[:240] and re.fullmatch(
                r"[A-Z][a-z]{2,}(?:-[A-Z][a-z]{2,})+", word
            ) else 0,
            len(word), -index, word
        ) for index, word in enumerate(words)
            if word.lower() not in rejected and len(set(word.lower())) >= 4]
        return max(matches)[-1] if matches else None

    def _orientation_samples(self, c, now: datetime) -> list[dict]:
        """Three REAL linked event examples for a 0-topic owner, not their Top 3.

        A derived event title/importance is unverified model output. Search a
        strict 48h UTC ingestion window, only completed linked records. Avoid
        auto-opening third-party URLs, side effects, personalization and AI.
        """
        since = (now - timedelta(hours=48)).isoformat(timespec="milliseconds")
        discovery = "coalesce(e.first_ingested_at,e.created_at)"
        rows = c.execute(
            "SELECT e.id,e.title,e.importance,e.category,"
            + discovery + " AS first_ingested_at FROM events e "
            "WHERE " + discovery + ">=? AND " + discovery + "<=? "
            "AND e.importance>=60 "
            "AND EXISTS(SELECT 1 FROM raw_records r "
            "WHERE r.event_id=e.id AND r.state='completed' "
            "AND r.plugin_id IN ('telegram','x','youtube') "
            "AND r.source_url LIKE 'http%') "
            "ORDER BY e.importance DESC," + discovery + " DESC,e.id LIMIT 32",
            (since, now.isoformat(timespec="milliseconds")),
        ).fetchall()
        eligible = []
        for row in rows:
            originals = c.execute(
                "SELECT source_url,source_name,plugin_id,"
                "source_published_at,first_ingested_at AS original_first_ingested_at,"
                "substr(title,1,360) AS original_title,"
                "substr(text,1,2400) AS original_text FROM raw_records "
                "WHERE event_id=? AND state='completed' "
                "AND plugin_id IN ('telegram','x','youtube') "
                "AND source_url LIKE 'http%' "
                "ORDER BY first_ingested_at,record_id LIMIT 8",
                (row["id"],),
            ).fetchall()
            link = next(
                ((original, url) for original in originals
                 if (url := evidence_url(original["source_url"]))),
                None,
            )
            if link is None:
                continue
            original, url = link
            # Both clocks belong to the SAME clickable original, not to the
            # machine-generated event headline. Newly ingested is not newly
            # published; a missing/malformed publisher timestamp stays unknown.
            published, publication_scope = self._daily_publication(
                original["source_published_at"]
            )
            literal = self._orientation_query_hint(
                row["title"], (original["original_title"] or "")
                + " " + (original["original_text"] or "")
            )
            eligible.append({
                "id": row["id"],
                "title": (row["title"] or "")[:180],
                "category": row["category"] or "未分类",
                "first_ingested_at": row["first_ingested_at"],
                "source_name": (original["source_name"] or original["plugin_id"])[:100],
                "source_url": url,
                "original_source_published_at": published,
                "original_source_published_status": publication_scope,
                "original_first_ingested_at": original["original_first_ingested_at"],
                "source_dates_independently_verified": False,
                "query_hint": literal,
                "query_hint_basis": (
                    "literal_substring_of_the_same_completed_original_not_personal"
                    if literal else "unavailable"
                ),
                "scope": "global_onboarding_example_not_personal",
                "editorial_rank_verified": False,
                "source_authenticity_verified": False,
            })
        # Prefer category diversity but never imply these are globally best.
        chosen, categories = [], set()
        for sample in eligible:
            if sample["category"] not in categories:
                chosen.append(sample)
                categories.add(sample["category"])
                if len(chosen) == 3:
                    return chosen
        for sample in eligible:
            if sample not in chosen:
                chosen.append(sample)
                if len(chosen) == 3:
                    break
        return chosen

    def overview(self, owner: str) -> dict:
        with self.store.connect() as c:
            c.execute("BEGIN")
            rows = c.execute(
                "SELECT * FROM radar_topics WHERE owner=? ORDER BY created_at,id",
                (owner,),
            ).fetchall()
            now = datetime.now(UTC)
            allowed = self.details["limits"]["max_topics"]
            policy = self.store._reading_policy(c, owner)
            coverage = self._coverage_today(c, now)
            global_signals = self._global_signals(c, owner, now, policy)
            orientation_samples = self._orientation_samples(c, now) if not rows else []
            value_feedback = self._value_feedback(c, owner, now)
            topics = []
            for index, row in enumerate(rows):
                topic = _topic(row)
                # When the operator downgrades the single-user plan, existing
                # configuration and judgements remain intact. Historical premium
                # insight is withheld rather than silently granting paid capacity.
                if index >= allowed:
                    topics.append(topic | {"suspended": True, "metrics": None, "highlights": []})
                else:
                    topics.append(
                        self._details_for_topic(c, topic, owner, now, policy) | {"suspended": False}
                        | {"raw_leads": self._raw_leads_for_topic(c, topic, now)}
                        | {"latest_brief": self._latest_brief(c, owner, topic["id"])
                           if self.plan in ("pro", "analyst") else None}
                    )
            owner_revision = self._owner_revision(c, owner)
        return {
            "plan": plan_details(self.plan), "topics": topics, "generated_at": now_iso(),
            "coverage_today": coverage, "global_signals": global_signals,
            "orientation_samples": orientation_samples,
            "value_feedback": value_feedback, "owner_revision": owner_revision,
        }
