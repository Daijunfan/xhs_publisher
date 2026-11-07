"""Private, authenticated HTTP API and bundled application. No secrets enter the browser bundle."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import math
import os
import re
import uuid
import secrets
import sqlite3
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from aiohttp import web

from . import __version__
from .dossier import Dossier
from .media import IMAGE_MIMES, MediaCache
from .models import now_iso
from .preferences import Preferences, ProductError
from .radar import Radar, plan_comparison
from .store import Store
from .subscriptions import Subscriptions
from .worker import EnrichmentWorker

# V145 integrated owner-only manual ledger; 9-source official allowlist
PILOT_SCHEMA = "frontier.owner-pilot.manual-v1"
PILOT_PROVENANCE = "manual_self_report_not_independently_verified"
MAX_SESSIONS = 90
BEIJING = ZoneInfo("Asia/Shanghai")

COUNT_FIELDS = ("old_seconds", "frontier_seconds", "reviewed_items",
                "noise_items", "explicit_page_actions")
FLAG_FIELDS = (
    "owner_confirmed_original_opened",
    "owner_confirmed_decision_saved",
    "owner_confirmed_no_prompt",
    "owner_confirmed_comparable_task",
    "key_miss",
    "claimed_independence_without_check",
    "fabricated_occurrence_time",
)
SESSION_FIELDS = ("session_ref", "day", *COUNT_FIELDS, *FLAG_FIELDS)
COLUMN_NAMES = ", ".join(("owner", *SESSION_FIELDS))
QMARKS = ", ".join("?" for _ in ("owner", *SESSION_FIELDS))
UUID_PATTERN = re.compile(
    r"manual-([0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12})\Z"
)


def _reject(code: str, message: str, status: int = 422):
    raise ProductError(code, message, status)


def _owner(owner: object) -> str:
    # HTTP obtains this ONLY from the authenticated cookie session, never JSON.
    if not isinstance(owner, str) or not owner or len(owner) > 128:
        _reject("owner_pilot_unauthenticated", "需要有效的个人登录身份", 401)
    return owner


def _ref(value: object) -> str:
    if not isinstance(value, str):
        _reject("invalid_owner_pilot_ref", "请使用浏览器生成的匿名记录编号")
    match = UUID_PATTERN.fullmatch(value)
    if not match or str(uuid.UUID(match.group(1))) != match.group(1):
        _reject("invalid_owner_pilot_ref", "仅接受无身份信息的随机 UUIDv4 编号")
    return value


def _calendar_day(value: object, *, today: date) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        _reject("invalid_owner_pilot_day", "日期必须是北京时间 YYYY-MM-DD")
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        _reject("invalid_owner_pilot_day", "不是有效的日历日期")
    if parsed.isoformat() != value:
        _reject("invalid_owner_pilot_day", "日期格式不正确")
    # Same policy as V143's appendOwnerPilotSession: actual entry on Beijing TODAY.
    # No future/backfilled human observations masquerading as a live trial.
    if parsed != today:
        _reject("owner_pilot_today_only", "只能主动提交北京时间今天的本人手填记录", 422)
    return value


def validate_session_payload(payload: object, *, today: date | None = None) -> dict:
    """Validate *exact* v143-gate-compatible manual fields, never free text."""
    if type(payload) is not dict or set(payload) != {
        "session", "owner_consent", "manual_confirmation"
    }:
        _reject("invalid_owner_pilot_payload", "只能提交一条本人自报记录及两项明确确认")
    if payload["owner_consent"] is not True or payload["manual_confirmation"] is not True:
        _reject("owner_pilot_consent_required", "须明确同意服务端保存，并确认真人手填", 403)
    session = payload["session"]
    if type(session) is not dict or set(session) != set(SESSION_FIELDS):
        _reject("invalid_owner_pilot_fields", "不接收主题、原文、URL、账号或多余字段")
    today = today or datetime.now(BEIJING).date()
    result = {"session_ref": _ref(session["session_ref"])}
    result["day"] = _calendar_day(session["day"], today=today)
    for field in COUNT_FIELDS:
        value = session[field]
        max_value = 86400 if field.endswith("_seconds") else 20000
        minimum = 1 if field.endswith("_seconds") else 0
        if type(value) is not int or not minimum <= value <= max_value:
            _reject("invalid_owner_pilot_number", "实用秒数和数量须是真人填写的范围内整数")
        result[field] = value
    if result["noise_items"] > result["reviewed_items"]:
        _reject("invalid_owner_pilot_noise", "没帮助条数不能超过已评条数")
    for field in FLAG_FIELDS:
        if type(session[field]) is not bool:
            _reject("invalid_owner_pilot_flag", "本人确认项必须是明确 true/false")
        result[field] = session[field]
    return result


def _validate_delete_body(data: object, *, all_rows: bool) -> str | None:
    expected = {"confirm_delete"} if all_rows else {"confirm_delete", "session_ref"}
    if type(data) is not dict or set(data) != expected or data["confirm_delete"] is not True:
        _reject("owner_pilot_delete_confirmation", "必须本人明确确认删除", 403)
    return None if all_rows else _ref(data["session_ref"])


class OwnerLedger:
    """Sidecar-only access via Store.connect(). No audit/collector mutations."""

    def __init__(self, store):
        self.store = store

    def save(self, owner: str, payload: object, *, today: date | None = None) -> dict:
        owner = _owner(owner)
        item = validate_session_payload(payload, today=today)
        fields = [owner, *[int(item[name]) if name in FLAG_FIELDS else item[name]
                            for name in SESSION_FIELDS]]
        with self.store.connect() as conn:
            # Serializes per-owner limit across different processes, not only RLock.
            conn.execute("BEGIN IMMEDIATE")
            count = conn.execute(
                "SELECT COUNT(*) FROM owner_pilot_sessions WHERE owner=?", (owner,)
            ).fetchone()[0]
            if count >= MAX_SESSIONS:
                _reject("owner_pilot_limit", "最多保存90条本人自报记录，请先导出或删除", 409)
            try:
                conn.execute(
                    f"INSERT INTO owner_pilot_sessions ({COLUMN_NAMES}) VALUES ({QMARKS})",
                    fields,
                )
            except sqlite3.IntegrityError:
                _reject("owner_pilot_duplicate", "该本人匿名会话已提交，不接受重复重放", 409)
        return {
            "saved": True,
            "session_ref": item["session_ref"],
            "day": item["day"],
            "total_sessions": count + 1,
            "provenance": PILOT_PROVENANCE,
            "independently_verified": False,
        }

    def read(self, owner: str) -> dict:
        owner = _owner(owner)
        with self.store.connect() as conn:
            rows = conn.execute(
                f"SELECT {', '.join(SESSION_FIELDS)} FROM owner_pilot_sessions "
                "WHERE owner=? ORDER BY day ASC,session_ref ASC", (owner,)
            ).fetchall()
        sessions = []
        for row in rows:
            item = dict(row)
            for key in FLAG_FIELDS:
                item[key] = bool(item[key])
            sessions.append(item)
        # Exact V143 owner_pilot_gate.py JSON contract. Revenue is NEVER verified.
        return {
            "schema": PILOT_SCHEMA,
            "provenance": PILOT_PROVENANCE,
            "sessions": sessions,
            "reviews": [],
            "willingness": [],
            "external_receipt_verified": False,
        }

    def summary(self, owner: str) -> dict:
        data = self.read(owner)
        sessions = data["sessions"]
        eligible = [s for s in sessions if (
            s["owner_confirmed_original_opened"]
            and s["owner_confirmed_decision_saved"]
            and s["owner_confirmed_no_prompt"]
            and s["owner_confirmed_comparable_task"]
        )]
        risky = [s for s in sessions if (
            s["key_miss"] or s["claimed_independence_without_check"]
            or s["fabricated_occurrence_time"]
        )]
        return {
            "source": "MANUAL_OWNER_REPORT_NOT_INDEPENDENTLY_AUDITED",
            "recorded_sessions": len(sessions),
            "paired_sessions": len(eligible),
            "paired_beijing_days": len({s["day"] for s in eligible}),
            "risk_records": len(risky),
            "savings_verified": False,
            "legal_revenue_verified": False,
        }

    def delete_session(self, owner: str, data: object) -> dict:
        owner = _owner(owner)
        reference = _validate_delete_body(data, all_rows=False)
        with self.store.connect() as conn:
            result = conn.execute(
                "DELETE FROM owner_pilot_sessions WHERE owner=? AND session_ref=?",
                (owner, reference),
            )
            if result.rowcount == 0:
                # Identical result for missing and another owner's ref.
                _reject("owner_pilot_missing", "本人记录不存在", 404)
        return {"deleted": True, "deleted_sessions": 1}

    def delete_all(self, owner: str, data: object) -> dict:
        owner = _owner(owner)
        _validate_delete_body(data, all_rows=True)
        with self.store.connect() as conn:
            count = conn.execute(
                "DELETE FROM owner_pilot_sessions WHERE owner=?", (owner,)
            ).rowcount
        return {"deleted": True, "deleted_sessions": count}

def official_delivery_snapshot(root: Path, *, day: str | None = None, audit_root: Path | None = None) -> dict:
    """Authenticated, read-only view of REAL publisher + independent 20:40 audit.

    No user-supplied paths, no fake COMMITTED from a frontend build ID, no
    writing production evidence, no inferred source event times or revenue.
    QA roots read only their own disposable local audit fixtures.
    """
    from datetime import timedelta
    root = Path(root).resolve()
    date_today = datetime.now(ZoneInfo("Asia/Shanghai")).date() if day is None else date.fromisoformat(day)
    day_today = date_today.isoformat()
    dispatch = root / "runtime/frontier/daily-dispatch"
    if audit_root is None:
        audit_root = root / "runtime/delivery-audits"

    def receipt(folder, name):
        target = folder / name
        try:
            if target.is_symlink() or not target.is_file() or not 0 < target.stat().st_size < 150_000:
                return None
            value = json.loads(target.read_bytes())
            return value if isinstance(value, dict) else None
        except (OSError, ValueError, UnicodeError):
            return None

    def confirmed(label):
        ledger = receipt(dispatch, label + ".json")
        audit = receipt(audit_root, label + ".json")
        if not ledger or not audit:
            return None
        product = ledger.get("product_release")
        post = audit.get("postverify")
        recorded = audit.get("ledger")
        evidence = audit.get("handoff")
        expected_sources = "8/8" if label < "2026-10-25" else "9/9"
        if not (
            ledger.get("beijing_date") == label
            and ledger.get("status") == "COMMITTED"
            and ledger.get("cloud_deploy_executed") is True
            and isinstance(product, str)
            and re.fullmatch(r"Frontier-[A-Za-z0-9-]{10,180}", product)
            and audit.get("beijing_date") == label
            and audit.get("status") == "VERIFIED_REAL_COMMITTED"
            and audit.get("cloud_deploy_confirmed") is True
            and audit.get("audit_verifier_exit_code") == 0
            and isinstance(recorded, dict)
            and recorded.get("product_release") == product
            and recorded.get("checkpoint") == ledger.get("checkpoint")
            and isinstance(evidence, dict) and evidence.get("pin_matches") is True
            and isinstance(post, dict)
            and post.get("production_source_sha") == expected_sources
            and post.get("production_static_sha") == "7/7"
            and post.get("http_static_sha") == "7/7"
        ):
            return None
        # Only independently audited owner-delivery text may become the
        # authenticated user's release note. Product ID must be EXACTLY
        # the committed+audited ID; neither private build meta nor a HOLD
        # can promote draft feature claims to deployed customer updates.
        owner_receipt = audit.get("owner_delivery")
        updates = []
        if (isinstance(owner_receipt, dict)
            and owner_receipt.get("status") == "DELIVERED_AND_INDEPENDENTLY_VERIFIED"
            and owner_receipt.get("product_release") == product
            and isinstance(owner_receipt.get("actual_updates"), list)):
            for value in owner_receipt["actual_updates"][:12]:
                if isinstance(value, str) and 1 <= len(value) <= 180:
                    updates.append(value)
        return {"beijing_date": label, "product_release": product,
                "backend": expected_sources, "static": "7/7", "http": "7/7",
                "actual_updates": updates,
                "update_source": "independent_2040_audit_owner_delivery"
                if updates else "not_available"}

    # The previously verified release stays visible during today's rollout.
    latest = None
    for offset in range(31):
        label = (date_today - timedelta(days=offset)).isoformat()
        latest = confirmed(label)
        if latest:
            break
    todays = receipt(dispatch, day_today + ".json")
    if latest and latest["beijing_date"] == day_today:
        today_status = "VERIFIED_REAL_COMMITTED"
    elif todays and todays.get("status") == "COMMITTED":
        today_status = "COMMITTED_AWAITING_INDEPENDENT_AUDIT"
    elif todays and todays.get("status") in {"HOLD", "HOLD_AFTER_ATTEMPT", "DEPLOYING"}:
        today_status = "NOT_VERIFIED_OR_HELD"
    else:
        today_status = "NO_VERIFIED_TODAY_RELEASE"
    pending = todays.get("product_release") if isinstance(todays, dict) else None
    pending = pending if (isinstance(pending, str)
                          and re.fullmatch(r"Frontier-[A-Za-z0-9-]{10,180}", pending)) else None
    return {
        "schema": "frontier.owner.real-delivery-status.v1",
        "beijing_date": day_today,
        "today_status": today_status,
        "today_committed_release": pending if today_status == "COMMITTED_AWAITING_INDEPENDENT_AUDIT" else None,
        "last_independently_verified": latest,
        "billing_enabled": False,
        "human_saved_time_verified": False,
        "real_paid_revenue_verified": False,
        "basis": "real_cloud_ledger_plus_independent_2040_audit_not_frontend_build_label",
    }


LOG = logging.getLogger(__name__)
APP_KEY = web.AppKey("store", Store)
SETTINGS_KEY = web.AppKey("settings", object)
# A gallery must not spend the budget needed to change settings or reading state.
# All three buckets are authenticated; write requests also pass the CSRF gate.
RATE_LIMITS = {"media": (2400, 60), "read": (600, 60), "write": (180, 60)}


@dataclass
class Settings:
    root: Path = field(default_factory=lambda: Path(__file__).resolve().parents[3])
    host: str = "127.0.0.1"
    port: int = 8088
    model: str = "deepseek-flash"
    daily_limit: int = 2000
    enrich: bool = True
    secure_cookie: bool = False
    # Single-user internal preview entitlement, never supplied by the browser.
    plan: str = field(default_factory=lambda: os.getenv("FRONTIER_PLAN", "analyst").strip().lower())
    database: Path | None = None
    source_database: Path | None = None
    access_token_file: Path | None = None
    deepseek_key_file: Path | None = None
    static_dir: Path | None = None

    def __post_init__(self):
        self.root = Path(self.root).resolve()
        runtime = self.root / "runtime"
        self.database = Path(self.database or runtime / "frontier/events.sqlite3")
        self.source_database = Path(self.source_database or runtime / "app.sqlite3")
        self.access_token_file = Path(
            self.access_token_file or runtime / "secrets/frontier-access.token"
        )
        self.deepseek_key_file = Path(
            self.deepseek_key_file or runtime / "secrets/frontier-deepseek.key"
        )
        self.static_dir = Path(self.static_dir or Path(__file__).parent / "static")

    @classmethod
    def from_env(cls):
        values = {
            "host": os.getenv("FRONTIER_HOST", "127.0.0.1"),
            "port": int(os.getenv("FRONTIER_PORT", "8088")),
            "model": os.getenv("FRONTIER_MODEL", "deepseek-flash"),
            "daily_limit": int(os.getenv("FRONTIER_DAILY_LIMIT", "2000")),
            "enrich": os.getenv("FRONTIER_ENRICH", "1") == "1",
            "secure_cookie": os.getenv("FRONTIER_SECURE_COOKIE", "0") == "1",
        }
        if os.getenv("FRONTIER_ROOT"):
            values["root"] = Path(os.environ["FRONTIER_ROOT"])
        return cls(**values)


def error_response(status: int, code: str, message: str):
    return web.json_response({"error": {"code": code, "message": message}}, status=status)


def _first_run_source_coverage(settings: Settings) -> dict:
    """Small aggregate of collector target coverage; never reveal target IDs.

    A fresh collector heartbeat is required before presenting target errors as
    current. One previous success does NOT prove current source availability.
    These counts also cannot establish the completeness of the world's news.
    """
    file = settings.root / "runtime/frontier/collector-status.json"
    try:
        state = json.loads(file.read_text())
        stamp = datetime.fromisoformat(state["updated_at"])
        fresh = abs(time.time() - stamp.timestamp()) < 150
        if not fresh or not state.get("ready"):
            return {"status": "unavailable_or_stale"}
        targets = state["source_targets"]
        by_platform = state["platform_targets"]
        if not isinstance(targets, dict) or not isinstance(by_platform, dict):
            return {"status": "unavailable_or_stale"}
        totals = {"configured": 0, "ever_succeeded": 0,
                  "reported_errors": 0, "never_succeeded": 0}
        platform_errors = {}
        for platform in ("telegram", "x", "youtube"):
            keys = by_platform.get(platform, [])
            if not isinstance(keys, list):
                return {"status": "unavailable_or_stale"}
            errors = 0
            for key in keys:
                record = targets.get(key)
                if not isinstance(record, dict) or record.get("enabled") is False:
                    continue
                totals["configured"] += 1
                if record.get("last_success_at"):
                    totals["ever_succeeded"] += 1
                else:
                    totals["never_succeeded"] += 1
                if record.get("last_error"):
                    errors += 1
            totals["reported_errors"] += errors
            platform_errors[platform] = errors
        if not totals["configured"]:
            return {"status": "unavailable_or_stale"}
        return {"status": "observed_recent_heartbeat", **totals,
                "reported_errors_by_platform": platform_errors,
                "success_observation_scope": "current_collector_process_only_not_lifetime",
                "process_started_at": state.get("started_at")
                if isinstance(state.get("started_at"), str) else None,
                "semantics": "last_recorded_target_error_not_confirmed_ongoing_outage",
                "worldwide_completeness_verified": False}
    except (OSError, KeyError, ValueError, TypeError):
        return {"status": "unavailable_or_stale"}


def _collector_state(settings: Settings, stats: dict) -> tuple[dict, list]:
    file = settings.root / "runtime/frontier/collector-status.json"
    try:
        status = json.loads(file.read_text())
    except (OSError, ValueError):
        status = {}
    updated = status.get("updated_at")
    try:
        recent = time.time() - datetime.fromisoformat(updated).timestamp() < 120
    except (TypeError, ValueError):
        recent = False
    collector = {
        "state": "running" if recent and status.get("ready") else "offline",
        "updated_at": updated,
        "started_at": status.get("started_at"),
    }
    target_states = status.get("source_targets", {})
    rows = []
    counts = {s["platform"]: s for s in stats["sources"]}
    platform_targets = status.get("platform_targets", {})
    for platform in ("telegram", "x", "youtube"):
        targets = [
            target_states[k] for k in platform_targets.get(platform, []) if k in target_states
        ]
        successes = [s.get("last_success_at") for s in targets if s.get("last_success_at")]
        failed = [s for s in targets if s.get("last_error") or s.get("error")]
        if collector["state"] == "offline":
            state = "offline"
        elif failed and not successes:
            state = "degraded"
        elif failed:
            state = "partial"
        elif successes:
            state = "healthy"
        else:
            state = "checking"
        count = counts.get(platform, {})
        rows.append(
            {
                "platform": platform,
                "state": state,
                "records": count.get("records", 0),
                "last_success_at": max(successes) if successes else None,
                "latest_ingested_at": count.get("latest_ingested_at"),
                "latest_published_at": count.get("latest_published_at"),
                "configured_targets": len(platform_targets.get(platform, [])),
                "checked_targets": len(successes),
                "failed_targets": len(failed),
                "error": "部分订阅需要重试或更新登录状态"
                if failed
                else ("采集进程未在线" if state == "offline" else None),
            }
        )
    return collector, rows


def create_app(
    settings: Settings, store: Store | None = None, *, background: bool = False
) -> web.Application:
    store = store or Store(settings.database)
    if not settings.access_token_file.is_file():
        raise RuntimeError("A private access token file is required; provision it before starting.")
    access_token = settings.access_token_file.read_text().strip()
    if len(access_token) < 24:
        raise RuntimeError("Access token must contain at least 24 characters.")
    login_attempts = defaultdict(deque)
    request_counts = defaultdict(deque)
    preferences = Preferences(store)
    radar = Radar(store, settings.plan)
    owner_ledger = OwnerLedger(store)
    dossier = Dossier(store, settings.plan)
    subscriptions = Subscriptions(store, settings.root)
    import_lock = asyncio.Lock()

    @web.middleware
    async def middleware(request: web.Request, handler):
        try:
            # Only same-origin browser mutations. Mac URLSession may omit Origin.
            if request.method not in {"GET", "HEAD", "OPTIONS"}:
                origin = request.headers.get("Origin")
                if origin:
                    expected = request.scheme + "://" + request.host
                    if origin != expected:
                        return error_response(403, "origin_rejected", "请求来源不匹配")
                if request.headers.get("Sec-Fetch-Site") == "cross-site":
                    return error_response(403, "cross_site_rejected", "请从本站操作")
            public = request.path in {
                "/api/auth/session",
                "/health/live",
                "/health/ready",
                "/api/version",
            } or not request.path.startswith("/api/")
            if not public:
                session = await asyncio.to_thread(
                    store.session, request.cookies.get("frontier_session", "")
                )
                if not session:
                    return error_response(401, "unauthenticated", "请输入访问码登录")
                request["owner"] = session["owner"]
                request["csrf"] = session["csrf"]
                if request.method not in {"GET", "HEAD", "OPTIONS"} and not hmac.compare_digest(
                    request.headers.get("X-CSRF-Token", ""), session["csrf"]
                ):
                    return error_response(403, "csrf_rejected", "登录状态已变更，请刷新页面")
                stamp = time.monotonic()
                is_read = request.method in {"GET", "HEAD", "OPTIONS"}
                bucket = (
                    "media"
                    if is_read and request.path.startswith("/api/media/")
                    else "read"
                    if is_read
                    else "write"
                )
                maximum, window = RATE_LIMITS[bucket]
                key = (request.cookies.get("frontier_session", ""), bucket)
                recent = request_counts[key]
                while recent and recent[0] <= stamp - window:
                    recent.popleft()
                if len(recent) >= maximum:
                    retry_after = max(1, math.ceil(recent[0] + window - stamp))
                    response = error_response(
                        429, "rate_limited", f"请求较频繁，请在 {retry_after} 秒后重试"
                    )
                    response.headers["Retry-After"] = str(retry_after)
                    return response
                recent.append(stamp)
                if len(request_counts) > 4096:
                    for identity, timestamps in list(request_counts.items()):
                        if not timestamps or timestamps[-1] <= stamp - 300:
                            request_counts.pop(identity, None)
            response = await handler(request)
        except web.HTTPException as error:
            response = error_response(
                error.status,
                "http_" + str(error.status),
                "请求不存在" if error.status == 404 else "请求无法处理",
            )
        except ProductError as error:
            response = error_response(error.status, error.code, error.message)
        except (ValueError, TypeError):
            response = error_response(400, "invalid_request", "请检查筛选条件或请求格式")
        except Exception as error:
            LOG.error("HTTP failure type=%s path=%s", type(error).__name__, request.path[:100])
            response = error_response(500, "internal_error", "服务暂时不可用，请稍后重试")
        return response

    @web.middleware
    async def security_headers(request, handler):
        response = await handler(request)
        response.headers.update(
            {
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer",
                "X-Frame-Options": "DENY",
                "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
                "Content-Security-Policy": "default-src 'self'; script-src 'self'; "
                "style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
                "connect-src 'self'; worker-src 'self' blob:; font-src 'self'; "
                "object-src 'none'; base-uri 'self'; frame-ancestors 'none'",
            }
        )
        if request.path.startswith("/api/"):
            if (
                request.method in {"GET", "HEAD"}
                and request.path.startswith("/api/media/")
                and response.status in {200, 206, 304}
            ):
                # FileResponse supplies ETag/Last-Modified and honors conditional
                # requests. Cookie variation prevents a logged-out browser from
                # matching a response cached for the former authenticated session.
                response.headers["Cache-Control"] = "private, max-age=300, must-revalidate"
                vary = [
                    value.strip()
                    for value in response.headers.get("Vary", "").split(",")
                    if value.strip()
                ]
                if "cookie" not in {value.lower() for value in vary}:
                    vary.append("Cookie")
                response.headers["Vary"] = ", ".join(vary)
            else:
                response.headers["Cache-Control"] = "no-store"
        return response

    app = web.Application(middlewares=[security_headers, middleware], client_max_size=16 * 1024)
    app[APP_KEY], app[SETTINGS_KEY] = store, settings

    async def body(request):
        if request.content_type != "application/json":
            raise web.HTTPUnsupportedMediaType()
        value = await request.json()
        if not isinstance(value, dict):
            raise ValueError
        return value

    async def radar_body(request):
        # Radar gives clear 4xx JSON errors; legacy V2 handlers keep their
        # previous error codes and request parsing behavior unchanged.
        if request.content_type != "application/json":
            raise ProductError("invalid_content_type", "请使用 application/json 提交 JSON", 415)
        try:
            value = await request.json()
        except (ValueError, UnicodeError):
            raise ProductError("invalid_json", "请求正文不是有效 JSON", 400) from None
        if not isinstance(value, dict):
            raise ProductError("invalid_json_object", "请提交 JSON 对象", 400)
        return value

    # V144 candidate ONLY. Same authenticated session/Origin/CSRF/rate limit
    # middleware as all other /api/ mutations. No URL/topic/token/body logging.
    async def owner_pilot_read(request):
        result = await asyncio.to_thread(owner_ledger.read, request["owner"])
        return web.json_response(result)

    async def owner_pilot_summary(request):
        result = await asyncio.to_thread(owner_ledger.summary, request["owner"])
        return web.json_response(result)

    async def owner_pilot_export(request):
        result = await asyncio.to_thread(owner_ledger.read, request["owner"])
        return web.json_response(
            result,
            headers={"Content-Disposition": 'attachment; filename="frontier-owner-pilot-manual.json"'},
        )

    async def owner_pilot_save(request):
        result = await asyncio.to_thread(
            owner_ledger.save, request["owner"], await radar_body(request)
        )
        return web.json_response(result, status=201)

    async def owner_pilot_delete_session(request):
        result = await asyncio.to_thread(
            owner_ledger.delete_session, request["owner"], await radar_body(request)
        )
        return web.json_response(result)

    async def owner_pilot_delete_all(request):
        result = await asyncio.to_thread(
            owner_ledger.delete_all, request["owner"], await radar_body(request)
        )
        return web.json_response(result)

    async def login(request):
        stamp = time.monotonic()
        key = request.remote or "local"
        recent = login_attempts[key]
        while recent and recent[0] < stamp - 300:
            recent.popleft()
        if len(recent) >= 10:
            return error_response(429, "login_rate_limited", "尝试过多，请 5 分钟后重试")
        data = await body(request)
        token = data.get("token", "")
        if (
            not isinstance(token, str)
            or len(token) > 256
            or not hmac.compare_digest(token, access_token)
        ):
            recent.append(stamp)
            return error_response(401, "invalid_token", "访问码不正确")
        recent.clear()
        session_token, csrf = secrets.token_urlsafe(36), secrets.token_urlsafe(32)
        await asyncio.to_thread(store.create_session, session_token, csrf, time.time() + 30 * 86400)
        response = web.json_response({"authenticated": True, "csrf_token": csrf, "role": "owner"})
        response.set_cookie(
            "frontier_session",
            session_token,
            httponly=True,
            secure=settings.secure_cookie,
            samesite="Strict",
            path="/",
            max_age=30 * 86400,
        )
        return response

    async def me(request):
        return web.json_response(
            {
                "authenticated": True,
                "csrf_token": request["csrf"],
                "role": "owner",
                "name": "观测者",
            }
        )

    async def logout(request):
        await asyncio.to_thread(store.revoke_session, request.cookies.get("frontier_session", ""))
        response = web.json_response({"authenticated": False})
        response.del_cookie("frontier_session", path="/")
        return response

    async def events(request):
        result = await asyncio.to_thread(store.list_events, dict(request.query), request["owner"])
        return web.json_response(result)

    async def event(request):
        value = await asyncio.to_thread(store.get_event, request.match_info["id"], request["owner"])
        return (
            web.json_response(value)
            if value
            else error_response(404, "event_missing", "这条事件不存在")
        )

    async def event_dossier(request):
        if request.method in {"GET", "HEAD"}:
            result = await asyncio.to_thread(dossier.get, request["owner"], request.match_info["id"])
        else:
            if request.content_type != "application/json":
                raise web.HTTPUnsupportedMediaType()
            # Only research notes accept long text; keep all V2 body limits intact.
            payload = await request.clone(client_max_size=512 * 1024).json()
            result = await asyncio.to_thread(
                dossier.save, request["owner"], request.match_info["id"], payload
            )
        return web.json_response(result)

    async def dossier_revision(request):
        result = await asyncio.to_thread(
            dossier.revision, request["owner"], request.match_info["id"],
            int(request.match_info["version"])
        )
        return web.json_response(result)

    async def dossier_evidence_changes(request):
        # GET-only, exact latest owner version: reject extra/duplicate overrides.
        params = list(request.query.items())
        if len(params) != 1 or params[0][0] != "version" or (
            not params[0][1].isascii() or not params[0][1].isdigit()
            or len(params[0][1]) > 19 or int(params[0][1]) < 1
        ):
            raise ProductError(
                "invalid_changes_version",
                "请仅提交 version=最新已保存的正整数研判版本。",
                400,
            )
        result = await asyncio.to_thread(
            dossier.evidence_changes, request["owner"],
            request.match_info["id"], int(params[0][1]),
        )
        return web.json_response(result)

    async def dossier_compare(request):
        # Exactly two ASCII decimal version parameters; reject duplicates and
        # all extra switches. Owner is taken only from the authenticated session.
        params = list(request.query.items())
        if len(params) != 2 or {key for key, _ in params} != {"from", "to"}:
            raise ProductError(
                "invalid_comparison",
                "请仅提交 from 与 to 两个研判版本参数",
                400,
            )
        values = dict(params)
        if any(
            not value.isascii() or not value.isdigit() or len(value) > 19
            for value in values.values()
        ):
            raise ProductError("invalid_comparison", "研判版本必须是正整数", 400)
        result = await asyncio.to_thread(
            dossier.compare, request["owner"], request.match_info["id"],
            int(values["from"]), int(values["to"]),
        )
        return web.json_response(result)

    async def dossier_export(request):
        # No query remains the legacy private/full JSON contract.
        # Only one exact format switch; no plan or paid overrides.
        params = list(request.query.items())
        if not params:
            export_format = "full"
        elif len(params) == 1 and params[0][0] == "format" and params[0][1] in {
            "full", "share", "markdown",
        }:
            export_format = params[0][1]
        else:
            raise ProductError(
                "invalid_export_format",
                "仅允许单个 format=full、share 或 markdown 查询参数；不得附加其他参数。",
                400,
            )
        event_id = request.match_info["id"]
        version = int(request.match_info["version"])
        if export_format == "markdown":
            text, snapshot_sha = await asyncio.to_thread(
                dossier.markdown, request["owner"], event_id, version,
            )
            content = text.encode("utf-8")
            digest = hashlib.sha256(event_id.encode("utf-8")).hexdigest()[:12]
            return web.Response(
                body=content,
                content_type="text/markdown",
                charset="utf-8",
                headers={
                    "Content-Disposition": (
                        f'attachment; filename="frontier-dossier-v{version}-{digest}.md"'
                    ),
                    "X-Frontier-Snapshot-SHA256": snapshot_sha,
                    "X-Frontier-Export-SHA256": hashlib.sha256(content).hexdigest(),
                },
            )
        result = await asyncio.to_thread(
            dossier.export, request["owner"], event_id, version, format=export_format,
        )
        return web.json_response(result)

    async def bookmark(request):
        value = (await body(request)).get("bookmarked")
        if not isinstance(value, bool):
            raise ValueError
        found = await asyncio.to_thread(
            store.bookmark, request.match_info["id"], request["owner"], value
        )
        if not found:
            raise web.HTTPNotFound()
        return web.json_response({"bookmarked": value})

    async def reading_settings(request):
        if request.method == "GET":
            return web.json_response(await asyncio.to_thread(preferences.get, request["owner"]))
        value = await body(request)
        if set(value) != {"settings", "version"}:
            raise ProductError("invalid_settings_request", "请提交设置内容和当前版本")
        return web.json_response(
            await asyncio.to_thread(
                preferences.update, request["owner"], value["settings"], value["version"]
            )
        )

    async def read_event(request):
        value = await body(request)
        ids = value.get("ids") if "id" not in request.match_info else [request.match_info["id"]]
        return web.json_response(
            await asyncio.to_thread(store.mark_read, ids, request["owner"], value.get("read"))
        )

    async def sync_originals():
        async with import_lock:
            last = await asyncio.to_thread(store.get_meta, "last_import_at")
            try:
                elapsed = time.time() - datetime.fromisoformat(last).timestamp()
            except (TypeError, ValueError):
                elapsed = 999
            if elapsed >= 3:
                await asyncio.to_thread(store.import_records, settings.source_database)

    async def inbox(request):
        await sync_originals()
        return web.json_response(
            await asyncio.to_thread(store.list_inbox, dict(request.query), request["owner"])
        )

    async def raw_detail(request):
        await sync_originals()
        value = await asyncio.to_thread(store.get_raw, request.match_info["id"], request["owner"])
        if value is None:
            raise ProductError("source_record_missing", "这条原始消息不存在", 404)
        return web.json_response(value)

    async def read_raw(request):
        value = await body(request)
        ids = value.get("ids") if "id" not in request.match_info else [request.match_info["id"]]
        return web.json_response(
            await asyncio.to_thread(
                store.mark_read, ids, request["owner"], value.get("read"), raw=True
            )
        )

    async def radar_overview(request):
        result = await asyncio.to_thread(radar.overview, request["owner"])
        if not result.get("topics"):
            # Only on the true first run; the server returns aggregate counts,
            # never account/source IDs or private collector failure text.
            result["source_target_coverage"] = await asyncio.to_thread(
                _first_run_source_coverage, settings)
        return web.json_response(result)

    async def radar_daily(request):
        # Read-only daily Radar and *observed* collector/worker telemetry.
        # Telemetry is a separate, later read, not falsely represented as the
        # same atomic SQLite snapshot as Radar's event/source evidence.
        result = await asyncio.to_thread(radar.daily, request["owner"])
        stats = await asyncio.to_thread(store.stats)
        collector, sources = await asyncio.to_thread(_collector_state, settings, stats)
        worker = await asyncio.to_thread(store.get_meta, "worker", {})
        if not isinstance(worker, dict):
            worker = {}
        result["pipeline"] = {
            "observed_at": now_iso(),
            "collector_heartbeat": collector,
            "sources": [
                {
                    key: row[key] for key in (
                        "platform", "state", "configured_targets",
                        "checked_targets", "failed_targets",
                        "last_success_at", "latest_ingested_at", "error"
                    )
                }
                for row in sources
            ],
            "enrichment": {
                "state": worker.get("state", "unknown"),
                "updated_at": worker.get("updated_at"),
                "error": worker.get("error"),
                "last_success_at": worker.get("last_success_at"),
                "daily_limit": worker.get("daily_limit"),
                "used_items_utc_today": stats["usage"].get("items", 0),
                "pending": stats["enrichment"]["pending"],
                "processing": stats["enrichment"]["processing"],
                "failed": stats["enrichment"]["failed"],
                "awaiting_video": stats["enrichment"]["awaiting_video"],
            },
            "scope": (
                "采集来源状态取自现有心跳文件、处理状态取自最近持久化 worker "
                "状态及派生库当前计数，与主题快照非同一原子时刻。"
                "心跳缺失或过期标为 offline 仅表示未见近期健康证明，"
                "不等于已经证实采集永久停止；仅当 worker 实报 "
                "daily_limit/budget_pacing/blocked 时才称为额度/节奏/阻断。"
            ),
        }
        return web.json_response(result)

    async def radar_reviews(request):
        return web.json_response(await asyncio.to_thread(radar.review_due, request["owner"]))

    async def radar_plans(request):
        return web.json_response(plan_comparison(settings.plan))

    async def radar_preview(request):
        # A POST for an explicit user trial, not a mutation: the shared gate
        # enforces login, same-origin/CSRF, rate limiting and 16 KiB body size.
        result = await asyncio.to_thread(radar.preview, request["owner"], await radar_body(request))
        return web.json_response(result)

    async def radar_topic_create(request):
        result = await asyncio.to_thread(radar.create, request["owner"], await radar_body(request))
        return web.json_response(result, status=201)

    async def radar_topic_update(request):
        result = await asyncio.to_thread(
            radar.update, request["owner"], request.match_info["id"], await radar_body(request)
        )
        return web.json_response(result)

    async def radar_topic_delete(request):
        return web.json_response(
            await asyncio.to_thread(
                radar.delete, request["owner"], request.match_info["id"], await radar_body(request)
            )
        )

    async def radar_topic_review(request):
        return web.json_response(
            await asyncio.to_thread(
                radar.review, request["owner"], request.match_info["id"], await radar_body(request)
            )
        )

    async def radar_topic_decision(request):
        result = await asyncio.to_thread(
            radar.decide, request["owner"], request.match_info["id"], await radar_body(request)
        )
        return web.json_response(result)

    async def radar_topic_usefulness(request):
        result = await asyncio.to_thread(
            radar.usefulness, request["owner"], request.match_info["id"], await radar_body(request)
        )
        return web.json_response(result)

    async def source_list(request):
        include_deleted = request.query.get("include_deleted", "0")
        if include_deleted not in {"0", "1", "false", "true"}:
            raise ProductError("invalid_deleted_filter", "已删除来源筛选值无效")
        return web.json_response(
            await asyncio.to_thread(
                subscriptions.list, include_deleted=include_deleted in {"1", "true"}
            )
        )

    async def source_create(request):
        result = await asyncio.to_thread(
            subscriptions.create, request["owner"], await body(request)
        )
        return web.json_response(result, status=201)

    async def source_update(request):
        value = await body(request)
        version = value.pop("version", None)
        return web.json_response(
            await asyncio.to_thread(
                subscriptions.update, request.match_info["id"], request["owner"], value, version
            )
        )

    async def source_remove_restore(request):
        value = await body(request)
        if set(value) != {"version"}:
            raise ProductError("invalid_source_request", "请提交当前来源版本")
        return web.json_response(
            await asyncio.to_thread(
                subscriptions.delete_or_restore,
                request.match_info["id"],
                request["owner"],
                value["version"],
                restore=request.method == "POST",
            )
        )

    async def status(request):
        stats = await asyncio.to_thread(store.stats)
        collector, sources = await asyncio.to_thread(_collector_state, settings, stats)
        worker = await asyncio.to_thread(store.get_meta, "worker", {"state": "starting"})
        return web.json_response(
            {
                "service": {"state": "healthy", "started_at": app["started_at"]},
                "collector": collector,
                "sources": sources,
                "version": __version__,
                "enrichment": {**stats["enrichment"], **worker, "usage": stats["usage"]},
                "stats": {
                    k: v for k, v in stats.items() if k not in {"sources", "enrichment", "usage"}
                },
                "last_backup": await asyncio.to_thread(store.get_meta, "last_backup"),
                "generated_at": now_iso(),
            }
        )

    async def media(request):
        attachment_id = request.match_info["id"]
        if len(attachment_id) > 128 or not attachment_id.replace("-", "").isalnum():
            raise web.HTTPNotFound()

        def resolve():
            with store.connect() as c:
                asset = c.execute(
                    "SELECT relative_path,mime_type,state FROM media_assets WHERE id=?",
                    (attachment_id,),
                ).fetchone()
                if asset is not None:
                    row = (
                        (asset["relative_path"], asset["mime_type"])
                        if asset["state"] == "ready"
                        else None
                    )
                else:
                    if not settings.source_database.is_file():
                        return None
                    original = sqlite3.connect(
                        settings.source_database.resolve().as_uri() + "?mode=ro",
                        uri=True,
                        timeout=3,
                    )
                    try:
                        row = original.execute(
                            "SELECT relative_path,mime_type FROM attachments WHERE attachment_id=?",
                            (attachment_id,),
                        ).fetchone()
                    finally:
                        original.close()
            if row is None or not row[0] or row[1] not in IMAGE_MIMES:
                return None
            root = (settings.root / "runtime").resolve()
            path = (root / row[0]).resolve()
            if not path.is_relative_to(root) or not path.is_file():
                return None
            return path, row[1]

        resolved = await asyncio.to_thread(resolve)
        if resolved is None:
            raise web.HTTPNotFound()
        return web.FileResponse(resolved[0], headers={"Content-Type": resolved[1]})

    async def export(request):
        filters = dict(request.query)
        filters.update(limit=200, offset=0)
        values = await asyncio.to_thread(store.list_events, filters, request["owner"])
        values["export"] = {
            "version": __version__,
            "at": now_iso(),
            "limit": 200,
            "time_semantics": "event_occurrence",
        }
        return web.json_response(
            values, headers={"Content-Disposition": 'attachment; filename="frontier-events.json"'}
        )

    async def health(request):
        await asyncio.to_thread(store.stats)
        return web.json_response({"ready": True, "service": "frontier", "version": __version__})

    async def version(request):
        return web.json_response({"product": "Frontier", "version": __version__})

    async def official_release(request):
        # Owner-authenticated read only; isolate missing/stale audit as UNVERIFIED.
        result = await asyncio.to_thread(official_delivery_snapshot, settings.root)
        return web.json_response(result)

    async def index(request):
        file = settings.static_dir / "index.html"
        if not file.is_file():
            return web.Response(text="Frontier assets are being deployed.", status=503)
        return web.FileResponse(file, headers={"Cache-Control": "no-cache"})

    async def asset(request):
        base = settings.static_dir.resolve()
        relative = request.match_info["path"]
        path = (base / relative).resolve()
        if not path.is_relative_to(base) or not path.is_file() or path.name.startswith("."):
            raise web.HTTPNotFound()
        return web.FileResponse(path, headers={"Cache-Control": "public, max-age=3600"})

    app["started_at"] = now_iso()
    app.add_routes(
        [
            web.post("/api/auth/session", login),
            web.get("/api/auth/me", me),
            web.post("/api/auth/logout", logout),
            web.get("/api/version", version),
            web.get("/api/release", official_release),
            web.get("/api/owner/pilot", owner_pilot_read),
            web.get("/api/owner/pilot/summary", owner_pilot_summary),
            web.get("/api/owner/pilot/export", owner_pilot_export),
            web.post("/api/owner/pilot/sessions", owner_pilot_save),
            web.delete("/api/owner/pilot/sessions", owner_pilot_delete_session),
            web.delete("/api/owner/pilot", owner_pilot_delete_all),
            web.get("/api/events", events),
            web.get("/api/radar", radar_overview),
            web.get("/api/radar/daily", radar_daily),
            web.get("/api/radar/reviews", radar_reviews),
            web.get("/api/plans", radar_plans),
            web.post("/api/radar/preview", radar_preview),
            web.post("/api/radar/topics", radar_topic_create),
            web.patch("/api/radar/topics/{id}", radar_topic_update),
            web.delete("/api/radar/topics/{id}", radar_topic_delete),
            web.post("/api/radar/topics/{id}/review", radar_topic_review),
            web.post("/api/radar/topics/{id}/decisions", radar_topic_decision),
            web.post("/api/radar/topics/{id}/usefulness", radar_topic_usefulness),
            web.post("/api/events/read", read_event),
            web.get("/api/events/{id}", event),
            web.get("/api/events/{id}/dossier", event_dossier),
            web.put("/api/events/{id}/dossier", event_dossier),
            web.get("/api/events/{id}/dossier/compare", dossier_compare),
            web.get("/api/events/{id}/dossier/changes", dossier_evidence_changes),
            web.get("/api/events/{id}/dossier/revisions/{version}", dossier_revision),
            web.get("/api/events/{id}/dossier/revisions/{version}/export", dossier_export),
            web.put("/api/events/{id}/read", read_event),
            web.get("/api/settings", reading_settings),
            web.put("/api/settings", reading_settings),
            web.get("/api/inbox", inbox),
            web.post("/api/inbox/read", read_raw),
            web.get("/api/inbox/{id}", raw_detail),
            web.put("/api/inbox/{id}/read", read_raw),
            web.get("/api/sources", source_list),
            web.post("/api/sources", source_create),
            web.patch("/api/sources/{id}", source_update),
            web.delete("/api/sources/{id}", source_remove_restore),
            web.post("/api/sources/{id}/restore", source_remove_restore),
            web.put("/api/events/{id}/bookmark", bookmark),
            web.get("/api/status", status),
            web.get("/api/media/{id}", media),
            web.get("/api/export", export),
            web.get("/health/live", version),
            web.get("/health/ready", health),
            web.get("/", index),
            web.get("/{path:assets/.*}", asset),
            web.get("/{path:favicon.*}", asset),
            web.get("/{path:ASSET-LICENSES.txt}", asset),
        ]
    )

    if background:

        async def worker_context(application):
            worker = EnrichmentWorker(
                store,
                settings.source_database,
                settings.deepseek_key_file,
                model=settings.model,
                daily_limit=settings.daily_limit,
                enabled=settings.enrich,
            )
            task = asyncio.create_task(worker.run(), name="frontier-enrichment")
            media_cache = MediaCache(store, settings.root / "runtime")
            media_task = asyncio.create_task(media_cache.run(), name="frontier-media-cache")
            yield
            worker.stop.set()
            task.cancel()
            media_cache.stop.set()
            media_task.cancel()
            await asyncio.gather(task, media_task, return_exceptions=True)

        app.cleanup_ctx.append(worker_context)
    return app


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = Settings.from_env()
    web.run_app(
        create_app(settings, background=True),
        host=settings.host,
        port=settings.port,
        access_log=None,
        print=lambda _: LOG.info("Frontier listening on %s:%s", settings.host, settings.port),
    )
