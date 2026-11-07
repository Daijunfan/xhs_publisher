"""Durable subscription overlay; credentials remain in the existing private config."""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit
from uuid import uuid4

from xhs_local.configuration.loader import load_snapshot
from xhs_local.configuration.models import SourcesConfig, TargetConfig
from xhs_local.configuration.subscriptions import parse_creator_link

from .models import now_iso
from .preferences import ProductError, validate_version

PLATFORMS = ("telegram", "x", "youtube")
MIN_POLL = {"telegram": 60, "x": 300, "youtube": 1800}
DEFAULT_POLL = {"telegram": 300, "x": 3600, "youtube": 7200}
PUBLIC_FIELDS = {"platform", "locator", "name", "enabled", "poll_seconds"}
HEALTH_STATES = ("healthy", "error", "rate_limited", "auth_required", "checking", "offline", "pending")
ERROR_CODES = {"404", "timeout", "rate-limit", "login", "TLS", "command-exit", "partial", "unknown"}


def _stamp(value):
    try:
        return datetime.fromisoformat(value).isoformat()
    except (TypeError, ValueError):
        return None


def source_health(target, *, enabled, deleted, online, pending):
    """Only target observations establish success; heartbeat establishes freshness."""
    success, failure = _stamp(target.get("last_success_at")), _stamp(target.get("last_failure_at"))
    has_error = bool(target.get("last_error") or target.get("error_class"))
    code = target.get("error_class") if target.get("error_class") in ERROR_CODES else "unknown"
    failures = target.get("consecutive_failures", target.get("failures"))
    # Older schedulers used failures=1 for a partially completed batch too.
    if "consecutive_failures" not in target and "items failed; see structured log" in str(target.get("last_error", "")):
        failures = None
    failures = failures if type(failures) is int and failures >= 0 else None
    state = ("deleted" if deleted else "disabled" if not enabled else "offline" if not online
             else "pending" if pending else "rate_limited" if has_error and code == "rate-limit"
             else "auth_required" if has_error and code == "login" else "error" if has_error
             else "healthy" if success else "checking")
    new_items = target.get("last_new_items")
    new_items = new_items if success and type(new_items) is int and new_items >= 0 else None
    suggestion = None
    if enabled and not deleted and online and not pending:
        if has_error and code == "login":
            suggestion = "需要人工检查登录；可先暂停来源，修复后再启用。"
        elif has_error and code == "404":
            suggestion = "来源返回 404；请核对账号地址，确认失效后可暂停。"
        elif has_error and failures is not None and failures >= 3:
            suggestion = f"连续 {failures} 次采集失败；可暂停并核查，历史资讯会保留。"
    return {"state": state, "last_success_at": success, "last_failure_at": failure,
            "next_run_at": _stamp(target.get("next_run_at")), "failures": failures,
            "consecutive_failures": failures, "error_class": code if has_error else None,
            "last_error": "部分内容获取失败" if has_error and code == "partial" else "采集失败，请按错误类别核查" if has_error else None,
            "last_new_items": new_items, "pause_suggestion": suggestion,
            "last_success_partial": target.get("last_success_partial") if type(target.get("last_success_partial")) is bool else None,
            "observation_fresh": online}


def _parse_url(value):
    try:
        parsed = urlsplit(value if "://" in value else "https://" + value)
        _ = parsed.port
        return parsed
    except ValueError:
        raise ProductError("invalid_locator", "来源地址格式无效") from None


def normalize_locator(platform: str, value: Any) -> tuple[str, str]:
    if platform not in PLATFORMS:
        raise ProductError("unsupported_platform", "来源仅支持 Telegram、X 和 YouTube")
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 500:
        raise ProductError("invalid_locator", "请输入有效的频道或账号地址")
    value = value.strip()
    if any(ord(ch) < 32 for ch in value):
        raise ProductError("invalid_locator", "来源地址包含无效字符")
    if platform in {"x", "youtube"}:
        if platform == "x" and re.fullmatch(r"@?[A-Za-z0-9_]{1,15}", value):
            value = "https://x.com/" + value.removeprefix("@")
        elif platform == "youtube" and value.startswith("@"):
            value = "https://www.youtube.com/" + value
        elif platform == "youtube" and re.fullmatch(r"UC[\w-]{22}", value):
            value = "https://www.youtube.com/channel/" + value
        parsed = _parse_url(value)
        if parsed.username or parsed.password or parsed.port not in (None, 443, 80):
            raise ProductError("invalid_locator", "来源地址不能包含登录信息或自定义端口")
        try:
            found, target = parse_creator_link(value)
        except ValueError as error:
            raise ProductError("invalid_locator", str(error)) from None
        if found != platform:
            raise ProductError("platform_mismatch", "链接与选择的平台不一致")
        locator = target.locator
        homepage = "https://x.com/" + locator if platform == "x" else locator
        return locator, homepage
    if value.startswith(("https://", "http://", "t.me/", "telegram.me/")):
        parsed = _parse_url(value)
        if (
            parsed.hostname not in {"t.me", "www.t.me", "telegram.me", "www.telegram.me"}
            or parsed.username or parsed.password or parsed.port not in (None, 443, 80)
        ):
            raise ProductError("invalid_locator", "请输入 Telegram 公开频道主页或已加入频道的 ID")
        path = unquote(parsed.path).strip("/")
        if path.startswith("s/"):
            path = path[2:]
        value = path
    value = value.removeprefix("@")
    # Numeric IDs are useful for private channels already joined by the stored session.
    if re.fullmatch(r"-100[0-9]{5,16}", value):
        return value, "https://t.me/c/" + value[4:]
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{3,31}", value):
        raise ProductError(
            "invalid_locator", "请输入 Telegram 频道用户名或主页，不能使用单条消息或邀请链接"
        )
    return value, "https://t.me/" + value


def canonical_key(platform: str, locator: str) -> str:
    try:
        normalized, _ = normalize_locator(platform, locator)
    except (ProductError, ValueError):
        normalized = locator.strip()
    return normalized.casefold()


def safe_homepage(platform: str, locator: str) -> str | None:
    try:
        return normalize_locator(platform, locator)[1]
    except (ProductError, ValueError):
        return None


def validate_fields(data: Any, *, creating: bool = False) -> dict:
    if not isinstance(data, dict) or not data:
        raise ProductError("invalid_source", "请提供来源信息")
    if set(data) - PUBLIC_FIELDS:
        raise ProductError("unknown_source_field", "来源请求包含不支持的字段")
    if creating and not {"platform", "locator"} <= set(data):
        raise ProductError("missing_source_fields", "请选择平台并填写频道或账号")
    result = dict(data)
    if "platform" in result and result["platform"] not in PLATFORMS:
        raise ProductError("unsupported_platform", "来源仅支持 Telegram、X 和 YouTube")
    if "name" in result:
        name = result["name"]
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 100:
            raise ProductError("invalid_source_name", "来源名称应为 1–100 个字符")
        if any(ord(ch) < 32 for ch in name):
            raise ProductError("invalid_source_name", "来源名称包含无效字符")
        result["name"] = name.strip()
    if "enabled" in result and type(result["enabled"]) is not bool:
        raise ProductError("invalid_source_enabled", "启用状态必须为 true 或 false")
    if "poll_seconds" in result and type(result["poll_seconds"]) is not int:
        raise ProductError("invalid_poll_seconds", "采集间隔必须为整数秒")
    return result


def _source_output_by_target(c, now_utc: datetime) -> dict[str, dict]:
    """One SQLite aggregation for every source; polling health is NOT evidence of output.

    `first_ingested_at` is the UTC-normalized, immutable first collector arrival
    (not a later update or a model run). A video_pending row is just video
    metadata, counted separately so it cannot be mistaken for a transcript.
    Events are counted by first *creation* of an organised event, not by number
    of records attached to it. Explicit user decisions are distinct linked
    event IDs, across topics, and never represent independent corroboration.
    """
    if now_utc.tzinfo is None:
        raise ValueError("source output clock must be timezone-aware")
    now_utc = now_utc.astimezone(UTC)
    start = (now_utc - timedelta(days=7)).isoformat(timespec="milliseconds")
    end = now_utc.isoformat(timespec="milliseconds")
    sql = """
        WITH decision_events AS (
          SELECT event_id,
                 max(CASE WHEN decision='watch' THEN 1 ELSE 0 END) AS watched,
                 max(CASE WHEN decision='research' THEN 1 ELSE 0 END) AS researched
          FROM radar_decisions WHERE decision IN ('watch','research')
          GROUP BY event_id
        )
        SELECT r.target_id,
               count(DISTINCT r.event_id) AS events,
               sum(CASE WHEN r.content_type IN ('tech_news','video_pending')
                         AND r.first_ingested_at>=? AND r.first_ingested_at<=?
                        THEN 1 ELSE 0 END) AS raw_7d,
               sum(CASE WHEN r.content_type='video_pending'
                         AND r.first_ingested_at>=? AND r.first_ingested_at<=?
                        THEN 1 ELSE 0 END) AS video_pending_7d,
               max(CASE WHEN r.content_type IN ('tech_news','video_pending')
                         AND coalesce(r.first_ingested_at,r.ingested_at)<=?
                        THEN coalesce(r.first_ingested_at,r.ingested_at) END) AS last_raw_at,
               count(DISTINCT CASE WHEN r.state='completed'
                        AND e.created_at>=? AND e.created_at<=?
                        THEN r.event_id END) AS events_7d,
               count(DISTINCT CASE WHEN r.state='completed' AND d.watched=1
                        THEN r.event_id END) AS watch_events,
               count(DISTINCT CASE WHEN r.state='completed' AND d.researched=1
                        THEN r.event_id END) AS research_events
        FROM raw_records r
        LEFT JOIN events e ON e.id=r.event_id
        LEFT JOIN decision_events d ON d.event_id=r.event_id
        WHERE r.target_id<>''
        GROUP BY r.target_id
    """
    return {row["target_id"]: dict(row) for row in c.execute(sql, (start, end, start, end, end, start, end))}


class Subscriptions:
    def __init__(self, store, root: Path):
        self.store, self.root = store, Path(root)

    def load_base(self):
        try:
            return load_snapshot(self.root / "config")
        except Exception as error:
            raise ProductError(
                "source_configuration_unavailable", "采集配置暂时无法读取，现有订阅不会被覆盖", 503
            ) from error

    def ensure_seeded(self, snapshot=None) -> None:
        """Import every configured target without deduplicating or reviving deleted rows."""
        snapshot = snapshot or self.load_base()
        stamp = now_iso()
        with self.store.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            changed = False
            for source in snapshot.sources.sources:
                if source.plugin not in PLATFORMS:
                    continue
                for target in source.targets:
                    exists = c.execute("SELECT 1 FROM subscriptions WHERE id=?", (target.id,)).fetchone()
                    if exists:
                        continue
                    c.execute(
                        "INSERT INTO subscriptions(id,parent_id,platform,locator,canonical_key,name,"
                        "poll_seconds,enabled,restore_enabled,target_options,created_at,updated_at) "
                        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                        (target.id, source.id, source.plugin, target.locator,
                         canonical_key(source.plugin, target.locator), target.name,
                         int(target.poll_seconds or source.poll_seconds),
                         int(source.enabled and target.enabled), int(source.enabled and target.enabled),
                         json.dumps(target.options, ensure_ascii=False), stamp, stamp),
                    )
                    changed = True
            if changed:
                c.execute("UPDATE subscription_state SET revision=revision+1,updated_at=? WHERE id=1", (stamp,))

    def revision(self) -> int:
        with self.store.connect() as c:
            return c.execute("SELECT revision FROM subscription_state WHERE id=1").fetchone()[0]

    def overlay(self, snapshot=None):
        snapshot = snapshot or self.load_base()
        self.ensure_seeded(snapshot)
        with self.store.connect() as c:
            rows = c.execute("SELECT * FROM subscriptions ORDER BY created_at,id").fetchall()
            revision = c.execute("SELECT revision FROM subscription_state WHERE id=1").fetchone()[0]
        grouped: dict[str, list] = {}
        for row in rows:
            if row["deleted_at"]:
                continue
            grouped.setdefault(row["parent_id"], []).append(TargetConfig(
                id=row["id"], locator=row["locator"], name=row["name"],
                poll_seconds=row["poll_seconds"], enabled=bool(row["enabled"]),
                options=json.loads(row["target_options"]),
            ))
        sources = tuple(
            source.model_copy(update={
                "enabled": any(t.enabled for t in grouped.get(source.id, [])),
                "targets": tuple(grouped.get(source.id, [])),
            })
            for source in snapshot.sources.sources if source.plugin in PLATFORMS
        )
        # The unique original IDs and private source options are retained verbatim.
        settings = SourcesConfig(version=1, sources=sources)
        return replace(snapshot, sources=settings, revision=f"{snapshot.revision}:frontier:{revision}"), revision

    def mark_applied(self, revision: int) -> None:
        with self.store.connect() as c:
            c.execute(
                "UPDATE subscription_state SET applied_revision=?,applied_at=?,error=NULL WHERE id=1",
                (revision, now_iso()),
            )

    def mark_error(self) -> None:
        with self.store.connect() as c:
            c.execute("UPDATE subscription_state SET error=? WHERE id=1", ("采集器同步失败，现有任务继续运行；正在重试",))

    def _collector_status(self) -> dict:
        try:
            value = json.loads((self.root / "runtime/frontier/collector-status.json").read_text())
            if not isinstance(value, dict):
                return {}
            return value
        except (OSError, ValueError):
            return {}

    def list(self, *, include_deleted=False, initialize=True) -> dict:
        if initialize:
            self.ensure_seeded()
        collector = self._collector_status()
        try:
            recent = 0 <= datetime.now().timestamp() - datetime.fromisoformat(collector["updated_at"]).timestamp() < 120
        except (TypeError, ValueError, KeyError):
            recent = False
        online = recent and collector.get("ready") is True
        targets = collector.get("source_targets", {})
        if not isinstance(targets, dict):
            targets = {}
        with self.store.connect() as c:
            state = dict(c.execute("SELECT * FROM subscription_state WHERE id=1").fetchone())
            rows = c.execute(
                "SELECT * FROM subscriptions " + ("" if include_deleted else "WHERE deleted_at IS NULL ")
                + "ORDER BY platform,name COLLATE NOCASE,id"
            ).fetchall()
            now_utc = datetime.now(UTC)
            output = _source_output_by_target(c, now_utc)
        counts: dict[str, int] = {}
        source_path = self.root / "runtime/app.sqlite3"
        if source_path.is_file():
            try:
                with sqlite3.connect(source_path.resolve().as_uri() + "?mode=ro", uri=True, timeout=3) as c:
                    counts = dict(c.execute("SELECT target_id,count(*) FROM records GROUP BY target_id"))
            except sqlite3.Error:
                pass
        pending = state["revision"] != state["applied_revision"]
        items = []
        for row in rows:
            target = targets.get(row["id"], {})
            if not isinstance(target, dict):
                target = {}
            enabled = bool(row["enabled"])
            health = source_health(target, enabled=enabled, deleted=row["deleted_at"], online=online, pending=pending)
            homepage = safe_homepage(row["platform"], row["locator"])
            produced = output.get(row["id"], {})
            items.append({
                "id": row["id"], "platform": row["platform"], "name": row["name"],
                "locator": normalize_locator(row["platform"], row["locator"])[0] if homepage else "", "url": homepage,
                "enabled": enabled, "deleted_at": row["deleted_at"], "version": row["version"],
                "poll_seconds": row["poll_seconds"], "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "counts": {"records": counts.get(row["id"], 0), "events": produced.get("events", 0),
                           "raw_7d": produced.get("raw_7d", 0),
                           "video_pending_7d": produced.get("video_pending_7d", 0),
                           "last_raw_at": produced.get("last_raw_at"),
                           "events_7d": produced.get("events_7d", 0),
                           "watch_events": produced.get("watch_events", 0),
                           "research_events": produced.get("research_events", 0)},
                "status": health,
            })
        platforms = {}
        for platform in PLATFORMS:
            live = [i for i in items if i["platform"] == platform and not i["deleted_at"]]
            active = [i for i in live if i["enabled"]]
            platforms[platform] = {"total": len(live), "enabled": len(active),
                "states": {s: sum(i["status"]["state"] == s for i in active) for s in HEALTH_STATES}}
        return {
            "health": {"platforms": platforms, "observed_at": _stamp(collector.get("updated_at")),
                       "fresh": online, "denominator": "enabled_non_deleted_sources"},
            "output": {"window_start_utc": (now_utc - timedelta(days=7)).isoformat(timespec="milliseconds"),
                       "window_end_utc": now_utc.isoformat(timespec="milliseconds"),
                       "raw_basis": "raw_records.first_ingested_at",
                       "event_basis": "events.created_at",
                       "decision_basis": "current_explicit_distinct_linked_events"},
            "items": items, "revision": state["revision"], "applied_revision": state["applied_revision"],
            "sync": {"state": "offline" if not online else ("error" if state["error"] else "pending" if pending else "applied"),
                     "error": state["error"], "updated_at": state["applied_at"]},
            "limits": {"platforms": list(PLATFORMS), "minimum_poll_seconds": MIN_POLL,
                       "maximum_poll_seconds": 86400, "max_active_sources": 1000},
        }

    def _validate_complete(self, data: dict, current=None, snapshot=None) -> dict:
        platform = data.get("platform", current["platform"] if current else None)
        if current is not None and platform != current["platform"]:
            raise ProductError("source_platform_immutable", "来源平台不能修改，请新增另一平台的来源")
        locator, _ = normalize_locator(platform, data.get("locator", current["locator"] if current else ""))
        interval = data.get("poll_seconds", current["poll_seconds"] if current else DEFAULT_POLL[platform])
        if (current is None or "poll_seconds" in data) and not MIN_POLL[platform] <= interval <= 86400:
            raise ProductError("invalid_poll_seconds", f"此平台采集间隔须在 {MIN_POLL[platform]}–86400 秒之间")
        name = data.get("name", current["name"] if current else locator.rsplit("/", 1)[-1].removeprefix("@"))
        if len(name) > 100:
            name = name[:100]
        enabled = data.get("enabled", bool(current["enabled"]) if current else True)
        if current is not None:
            parent_id = current["parent_id"]
        else:
            candidates = [s for s in snapshot.sources.sources if s.plugin == platform]
            if not candidates:
                raise ProductError("platform_not_configured", "该平台尚未配置采集登录信息", 409)
            parent_id = next((s.id for s in candidates if s.enabled), candidates[0].id)
        return {"platform": platform, "locator": locator, "canonical_key": canonical_key(platform, locator),
                "name": name, "enabled": int(enabled), "poll_seconds": interval, "parent_id": parent_id}

    @staticmethod
    def _changed(c, owner: str, action: str, identity: str) -> int:
        stamp = now_iso()
        c.execute("UPDATE subscription_state SET revision=revision+1,updated_at=?,error=NULL WHERE id=1", (stamp,))
        c.execute("INSERT INTO audit(at,owner,action,target) VALUES(?,?,?,?)", (stamp, owner, action, identity))
        return c.execute("SELECT revision FROM subscription_state WHERE id=1").fetchone()[0]

    def create(self, owner: str, data: Any) -> dict:
        checked = validate_fields(data, creating=True)
        snapshot = self.load_base()
        self.ensure_seeded(snapshot)
        final = self._validate_complete(checked, snapshot=snapshot)
        stamp = now_iso()
        with self.store.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            duplicate = c.execute("SELECT deleted_at FROM subscriptions WHERE platform=? AND canonical_key=? LIMIT 1",
                                  (final["platform"], final["canonical_key"])).fetchone()
            if duplicate:
                raise ProductError("source_deleted" if duplicate[0] else "source_exists",
                                   "该来源已删除，请从已删除列表恢复" if duplicate[0] else "该来源已存在", 409)
            if c.execute("SELECT count(*) FROM subscriptions WHERE deleted_at IS NULL").fetchone()[0] >= 1000:
                raise ProductError("source_limit", "最多同时保留 1000 个订阅，请先移除不需要的来源", 409)
            # Locator is editable. The subscription's stable identity must not occupy
            # the old locator's identity after the user changes its destination.
            identity = final["platform"] + "-" + uuid4().hex
            c.execute(
                "INSERT INTO subscriptions(id,parent_id,platform,locator,canonical_key,name,poll_seconds,"
                "enabled,restore_enabled,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (identity, final["parent_id"], final["platform"], final["locator"], final["canonical_key"],
                 final["name"], final["poll_seconds"], final["enabled"], final["enabled"], stamp, stamp),
            )
            revision = self._changed(c, owner, "source.created", identity)
        return {"id": identity, "version": 1, "revision": revision, "sync_state": "pending"}

    def update(self, identity: str, owner: str, data: Any, version: Any) -> dict:
        checked, version = validate_fields(data), validate_version(version)
        with self.store.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            current = c.execute("SELECT * FROM subscriptions WHERE id=?", (identity,)).fetchone()
            if not current:
                raise ProductError("source_missing", "来源不存在", 404)
            if current["deleted_at"]:
                raise ProductError("source_deleted", "请先恢复来源再编辑", 409)
            if current["version"] != version:
                raise ProductError("source_conflict", "来源已在其他窗口更新，请刷新后重试", 409)
            final = self._validate_complete(checked, current)
            duplicate = c.execute("SELECT 1 FROM subscriptions WHERE platform=? AND canonical_key=? AND id!=? LIMIT 1",
                                  (final["platform"], final["canonical_key"], identity)).fetchone()
            if duplicate and final["canonical_key"] != current["canonical_key"]:
                raise ProductError("source_exists", "该账号或频道已存在", 409)
            if all(current[k] == v for k, v in final.items()):
                return {"id": identity, "version": version, "revision": c.execute("SELECT revision FROM subscription_state WHERE id=1").fetchone()[0]}
            c.execute(
                "UPDATE subscriptions SET locator=?,canonical_key=?,name=?,enabled=?,poll_seconds=?,"
                "version=version+1,updated_at=? WHERE id=?",
                (final["locator"], final["canonical_key"], final["name"], final["enabled"],
                 final["poll_seconds"], now_iso(), identity),
            )
            revision = self._changed(c, owner, "source.updated", identity)
        return {"id": identity, "version": version + 1, "revision": revision, "sync_state": "pending"}

    def delete_or_restore(self, identity: str, owner: str, version: Any, *, restore=False) -> dict:
        version = validate_version(version)
        with self.store.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            current = c.execute("SELECT * FROM subscriptions WHERE id=?", (identity,)).fetchone()
            if not current:
                raise ProductError("source_missing", "来源不存在", 404)
            if current["version"] != version:
                raise ProductError("source_conflict", "来源已在其他窗口更新，请刷新后重试", 409)
            already = current["deleted_at"] is None if restore else current["deleted_at"] is not None
            if already:
                return {"id": identity, "version": version, "revision": c.execute("SELECT revision FROM subscription_state WHERE id=1").fetchone()[0]}
            if restore:
                if c.execute("SELECT count(*) FROM subscriptions WHERE deleted_at IS NULL").fetchone()[0] >= 1000:
                    raise ProductError("source_limit", "最多同时保留 1000 个订阅，请先移除不需要的来源", 409)
                c.execute("UPDATE subscriptions SET deleted_at=NULL,enabled=restore_enabled,version=version+1,updated_at=? WHERE id=?", (now_iso(), identity))
            else:
                c.execute("UPDATE subscriptions SET deleted_at=?,restore_enabled=enabled,enabled=0,version=version+1,updated_at=? WHERE id=?", (now_iso(), now_iso(), identity))
            revision = self._changed(c, owner, "source.restored" if restore else "source.deleted", identity)
        return {"id": identity, "version": version + 1, "revision": revision, "sync_state": "pending"}
