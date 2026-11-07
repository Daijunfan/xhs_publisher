"""Personal research revisions and frozen citations, independent of reading state."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import re
import socket
import sqlite3
import unicodedata
from datetime import date
from urllib.parse import parse_qsl, unquote, urlsplit

import idna

from .models import now_iso, safe_url
from .preferences import ProductError

FIELDS = {
    "judgment": "我的判断",
    "support": "支持或疑问",
    "falsification": "反证条件",
    "next_step": "下一步",
    "review_on": "复查日",
}
# Server-owned entitlement only. Billing is not active; never trust a request plan.
DOSSIER_WRITE_PLANS = frozenset({"pro", "analyst"})
# Mirrored from the frontend Radar outbound-link policy; never resolve DNS here.
_PRIVATE_DNS_ALIASES = ("nip.io", "sslip.io", "lvh.me", "localtest.me")
# A share is a human-reviewed draft, not an automatic rights or fact check.
_SHARE_EMPTY_JUDGMENTS = frozenset({
    "无", "暂无", "无判断", "暂无判断", "尚无判断", "未判断", "待判断",
    "无结论", "暂无结论", "尚无结论", "没有结论", "未填写", "待填写",
    "待定", "待核实", "待验证", "不知道", "我不知道", "尚不知道",
    "我尚不知道", "我尚不知道需要验证", "尚不知道需要验证",
    "需要验证", "需要核实", "待补充", "测试", "测试判断", "占位",
    "todo", "tbd", "na", "unknown", "nojudgment", "nojudgmentyet",
    "notsure", "placeholder", "test",
})
# Relevant share-time signals, not unqualified mentions of "private", "localhost"
# or "127.0.0.1". Those terms occur in legitimate public technical tutorials.
# This is static best-effort copy protection, not rights or destination validation.
_SHARE_PRIVATE_TEXT = re.compile(
    r"(?i)(?:(?:bearer\s+|(?:access[_-]?(?:token|key)|api[_-]?key|password|secret|"
    r"signature|authorization|session[_-]?id|token|account[_-]?id)\s*[:=]\s*)\S+"
    r"|sk-[A-Za-z0-9_-]{8,}|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}"
    r"|(?<![\w])@[A-Za-z0-9_]{2,})"
)
# A whole personal/OS path is different from the isolated grammar token "/Users/".
# The URL-path check anchors at its root, so /papers/private/methodology stays public.
_SHARE_TEXT_LOCAL_PATH = re.compile(
    r"(?i)(?<![\w/])/(?:Users|home|private)/[^/\s?#&]+"
    r"|(?<![\w/])/(?:etc|var)/[^/\s?#&]+"
)
_SHARE_URL_LOCAL_PATH = re.compile(
    r"(?i)^/+(?:Users|home|private|etc|var)/[^/\s?#&]+"
)
_SHARE_WINDOWS_LOCAL_PATH = re.compile(
    r"(?i)[A-Za-z]:[\\/](?:Users|Documents)[\\/]"
)
_SHARE_EMBEDDED_HTTP = re.compile(
    r"(?i)(?:https?|file|ftp)://[^\s<>\"'，。；;（）)]+"
    r"|(?<!:)//[^\s<>\"'，。；;（）)]+"
)
# Unlike a lone term "localhost", host:port can denote a runnable private
# endpoint. Validate its *host* locally; public host:port remains permissible.
_SHARE_PORTED_HOST = re.compile(
    r"(?i)(?<![\w./])(?:localhost|(?:[a-z0-9-]+\.)+[a-z0-9-]+"
    r"|\[[0-9a-f:.]+\]):[0-9]{1,5}\b"
)
# Maximum four unquote passes (in addition to parse_qsl's one decode). Residual
# encoded schemes are ambiguous, so they are not released to explicit share.
_SHARE_ENCODED_SCHEME = re.compile(r"(?i)(?:https?|file|ftp)%[0-9a-f]{2}")
_SHARE_ENCODED_OS_PATH = re.compile(
    r"(?i)%(?:25)*(?:2f|5c)(?:Users|home|private|etc|var)"
    r"%(?:25)*(?:2f|5c)[^%/\s?#&]"
)
_SHARE_SECRET_QUERY_KEYS = frozenset({
    "key", "auth", "code", "session", "credential", "sig", "jwt", "pwd",
    "accesskey", "accesskeyid", "keypairid", "apikey", "signature",
    "password", "authorization", "sessionid", "secret", "ticket",
})
SCHEMA_DOSSIER = """
CREATE TABLE IF NOT EXISTS dossier_revisions(
 owner TEXT NOT NULL,event_id TEXT NOT NULL REFERENCES events(id),
 version INTEGER NOT NULL CHECK(version>0),created_at TEXT NOT NULL,
 data TEXT NOT NULL,PRIMARY KEY(owner,event_id,version));
CREATE TRIGGER IF NOT EXISTS dossier_no_update BEFORE UPDATE ON dossier_revisions
 BEGIN SELECT RAISE(ABORT,'research revisions are append-only'); END;
CREATE TRIGGER IF NOT EXISTS dossier_no_delete BEFORE DELETE ON dossier_revisions
 BEGIN SELECT RAISE(ABORT,'research revisions are append-only'); END;
"""


def evidence_url(value):
    """Navigation only; never fetch a submitted URL or claim its availability."""
    value = safe_url(value)
    if not value or any(ord(ch) < 33 for ch in value) or "\\" in value:
        return None
    # WHATWG/browser navigation applies IDNA mapping (Unicode dot variants and
    # fullwidth labels included). Screen that canonical *host*, not raw Unicode
    # labels; preserve the caller's original URL for ordinary public/IDN links.
    # Encoding is local string work only: no DNS lookup or HTTP request.
    try:
        parsed = urlsplit(value)
        # A blank user:password pair is still userinfo, even when .username
        # and .password are both empty; never link an ambiguous authority.
        if "@" in parsed.netloc:
            return None
        # urlsplit().hostname alone does not validate the port.
        parsed.port
        raw_host = parsed.hostname
        if ":" in raw_host:
            # Bracketed IPv6 is already validated by urlsplit; zone identifiers
            # and percent escapes have no reliable browser-safe policy mapping.
            if "%" in raw_host:
                return None
            host = raw_host.lower()
        else:
            if re.search(r"%(?![0-9a-fA-F]{2})", raw_host):
                return None
            decoded_host = unquote(raw_host, encoding="utf-8", errors="strict")
            # Decode percent-encoded public hosts BEFORE alias/IP screening,
            # but reject encoded delimiters and further escape ambiguity.
            if re.search(r"[%/?#@:\\\x00-\x20\x7f]", decoded_host):
                return None
            # UTS #46 non-transitional IDNA (e.g. ßlip.io -> xn--lip-4ka.io)
            # matches WHATWG; builtin IDNA2003 would falsely map to sslip.io.
            host = idna.encode(
                unicodedata.normalize("NFKC", decoded_host),
                uts46=True, transitional=False
            ).decode("ascii").rstrip(".").lower()
    except (UnicodeError, ValueError, idna.IDNAError, TypeError):
        return None
    if "." not in host and ":" not in host:
        return None
    if (host == "home.arpa" or host.endswith(".home.arpa")
            or host.endswith((".localhost", ".local", ".internal", ".home", ".lan"))):
        return None
    if any(host == alias or host.endswith("." + alias) for alias in _PRIVATE_DNS_ALIASES):
        return None
    try:
        # inet_aton also recognizes browser-compatible shorthand/decimal IPv4.
        try:
            address = ipaddress.ip_address(socket.inet_aton(host))
        except OSError:
            address = ipaddress.ip_address(host)
    except ValueError:
        return value
    return value if address.is_global else None


def _share_compact(value):
    """Best-effort placeholder check; never claim semantic or factual verification."""
    if not isinstance(value, str):
        return ""
    return "".join(
        char for char in unicodedata.normalize("NFKC", value).casefold()
        if char.isalnum()
    )


def _share_encoded_views(value):
    """Bounded offline percent decoding for static share checks, never a fetch."""
    current = unicodedata.normalize("NFKC", value)
    yield current
    for _ in range(4):
        try:
            decoded = unicodedata.normalize(
                "NFKC", unquote(current, encoding="utf-8", errors="strict")
            )
        except UnicodeError:
            # No safe Unicode interpretation: force the caller's conservative
            # ambiguous-scheme signal without exposing undecodable bytes.
            yield "http%3A"
            return
        if decoded == current:
            return
        current = decoded
        yield current


def _share_url_has_local_path(path):
    """Only root-anchored absolute OS paths; not /papers/private/methodology."""
    views = list(_share_encoded_views(path))
    if any(_SHARE_URL_LOCAL_PATH.search(v) or _SHARE_WINDOWS_LOCAL_PATH.search(v)
           for v in views):
        return True
    # Even beyond the four-pass budget, an encoded leading slash plus a named
    # personal/OS root and a further path component is not a public citation.
    return any(
        v.startswith("/") and _SHARE_ENCODED_OS_PATH.search(v.lstrip("/")) is not None
        and re.match(r"(?i)^%(?:25)*(?:2f|5c)", v.lstrip("/")) is not None
        for v in views
    )


def _share_secret_key(key):
    canonical = re.sub(
        r"[^a-z0-9]", "", unicodedata.normalize("NFKC", key).casefold()
    )
    return (
        canonical in _SHARE_SECRET_QUERY_KEYS
        or canonical.endswith((
            "token", "secret", "password", "apikey", "accesskey", "accesskeyid",
            "signature", "sessionid", "credential", "authorization", "keypairid"
        ))
        or canonical.startswith(("xamz", "xgoog"))
    )


def _share_sensitive_static_text(value, depth=0):
    """Recognize explicit private references, not harmless discussion of terms.

    A public first hop can contain a private nested URL as *text*. Only this
    hand-reviewed share gate examines it; evidence_url remains navigation-only.
    Four decode passes bound work and reject still-encoded scheme ambiguity.
    No DNS, network, redirect following, raw notes edit or automatic sharing.
    """
    if len(value) > 8192 or depth > 3:
        return True
    for view in _share_encoded_views(value):
        if _SHARE_PRIVATE_TEXT.search(view) or _SHARE_WINDOWS_LOCAL_PATH.search(view):
            return True
        # A URL may contain a nested query value. Evaluate each visible embedded
        # HTTP URL's static host/path and sensitive nested query without fetching.
        for match in _SHARE_EMBEDDED_HTTP.finditer(view):
            url = match.group(0).rstrip(".,")
            if evidence_url(url) is None:
                return True
            try:
                parts = urlsplit(url)
                if _share_url_has_local_path(parts.path):
                    return True
                for key, inner in parse_qsl(parts.query, keep_blank_values=True):
                    if _share_secret_key(key) or _share_sensitive_static_text(inner, depth + 1):
                        return True
            except ValueError:
                return True
        # Exclude public URL path segments before considering absolute *manual*
        # paths. A tutorial URL mentioning /private/ is not a local file path.
        remainder = _SHARE_EMBEDDED_HTTP.sub(" ", view)
        if _SHARE_TEXT_LOCAL_PATH.search(remainder) or _SHARE_ENCODED_OS_PATH.search(remainder):
            return True
        for endpoint in _SHARE_PORTED_HOST.finditer(remainder):
            if evidence_url("http://" + endpoint.group(0)) is None:
                return True
    # Ambiguous deeply escaped scheme or complete OS-path syntax fails closed.
    return (_SHARE_ENCODED_SCHEME.search(view) is not None
            or _SHARE_ENCODED_OS_PATH.search(view) is not None)


def _share_safe_url(value):
    """Frozen explicitly shared public URL: conservative static privacy screen."""
    url = evidence_url(value)
    if not url:
        return None
    parsed = urlsplit(url)
    # A top-level fragment may carry session state and is not required for a
    # source index. A public URL *inside* a query may cite a #page fragment.
    if parsed.fragment or _share_url_has_local_path(parsed.path):
        return None
    if _SHARE_PRIVATE_TEXT.search(url):
        return None
    for key, item in parse_qsl(parsed.query, keep_blank_values=True):
        if _share_secret_key(key) or _share_sensitive_static_text(item):
            return None
    return url



# Private Markdown is a provenance index, not the existing external-share draft.
# No source body, collected title, model summary or automatic time prose is copied.
_MD_TIME_RE = re.compile(
    r"\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?)?"
)
_MD_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\u202a-\u202e\u2066-\u2069]")


def _md_literal(value):
    """Use an inert fence longer than any untrusted ~ run, preventing Markdown injection."""
    if not isinstance(value, str):
        value = "未知"
    if _MD_CONTROL_RE.search(value):
        raise ProductError("markdown_sensitive_content", "冻结数据含不可安全导出的控制字符。", 422)
    fence = "~" * max(3, max((len(s) for s in re.findall(r"~+", value)), default=0) + 1)
    return fence + "text\n" + value + "\n" + fence


def _md_timestamp(value):
    """Absent/malformed frozen times remain unknown; never substitute ingestion."""
    return value if isinstance(value, str) and _MD_TIME_RE.fullmatch(value) else "未知"


def _md_safe_text(value):
    return (
        isinstance(value, str)
        and not _MD_CONTROL_RE.search(value)
        and not _share_sensitive_static_text(value)
    )


def _md_label(value):
    # The frozen automatic status/precision may contain untrusted free text.
    return value if _md_safe_text(value) and len(value) <= 80 else "未知"


def _md_private_export(event_id, revision):
    """All content from one frozen owner revision; no current/live-event reads."""
    evidence = revision["evidence"]
    fields = revision["fields"]
    if (not isinstance(evidence, dict) or not isinstance(fields, dict)
            or not isinstance(evidence.get("event"), dict)
            or not isinstance(evidence.get("records"), list)):
        raise ProductError("markdown_evidence_invalid", "冻结证据结构无法导出。", 422)
    if not _md_safe_text(event_id):
        raise ProductError("markdown_sensitive_content", "事件标识含可能私密信息。", 422)
    for key in FIELDS:
        if not _md_safe_text(fields.get(key)):
            raise ProductError(
                "markdown_sensitive_content",
                "冻结笔记含可能的私密信息、凭据或本机路径；请另存脱敏版本后再导出。", 422,
            )

    # Canonical JSON from the authenticated GET revision API reproduces this
    # checksum, including hidden raw/model fields; NOT a server signature.
    encoded = json.dumps(
        revision, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    snapshot_sha256 = hashlib.sha256(encoded).hexdigest()
    event = evidence["event"]
    frozen_count = evidence.get("raw_record_count")
    publisher_count = evidence.get("publisher_count")
    count = str(frozen_count) if type(frozen_count) is int and frozen_count >= 0 else "未知"
    sources = (
        str(publisher_count)
        if type(publisher_count) is int and publisher_count >= 0 else "未知"
    )
    lines = [
        "# Frontier · 个人证据 Dossier（冻结只读 Markdown）", "",
        "> **仅限本人私有离线归档，不是可直接对外分发的摘要。**",
        "> 未核验事实、独立来源、URL 可达性、首发/转载关系或版权许可。",
        "> 不导出原始采集正文/标题、模型摘要、自动时空依据全文或内部密钥。",
        "> 本文件不访问网络、不新增来源、不调用模型、不修改任何冻结版本。", "",
        "## 版本出处", "",
        "事件 ID：", _md_literal(event_id), "",
        "冻结研判版本：v" + str(revision["version"]), "",
        "版本保存时间：", _md_literal(_md_timestamp(revision.get("created_at"))), "",
        "完整私有修订 JSON 的 SHA-256：", _md_literal(snapshot_sha256), "",
        "校验办法：授权登录后读取 GET /api/events/{id}/dossier/revisions/{version}；",
        "对返回的 JSON 对象按键排序、无额外空白、UTF-8、非 ASCII 不转义重新序列化并取 SHA-256。",
        "此值是完整冻结快照的一致性指纹，不是服务端数字签名，不能单独证明来源真实性。",
        "完整私有 JSON 含不对外释放的采集/模型材料，请勿将其交给第三方。", "",
        "## 本人笔记（保存时原样）", "",
    ]
    for key, label in FIELDS.items():
        lines.extend(["### " + label, "", _md_literal(fields[key] or "（未填写）"), ""])
    lines += [
        "## 事件发生时间（冻结字段，非新推断）", "",
        "发生状态：", _md_literal(_md_label(event.get("event_time_status"))), "",
        "开始：", _md_literal(_md_timestamp(event.get("event_time_start"))), "",
        "结束：", _md_literal(_md_timestamp(event.get("event_time_end"))), "",
        "精度：", _md_literal(_md_label(event.get("event_time_precision"))), "",
        "原帖发布、首次收录、事件发生是不同时间概念；缺失必须保留为“未知”，不得互相替代。",
        "自动生成的时间依据全文仅留在私有版本 JSON，不作为独立原始证实。", "",
        "## 冻结出处索引（不是独立信源清单）", "",
        "冻结记录数：" + count, "",
        "冻结出处标识数：" + sources, "",
        "**独立证实：未知；首发/转载关系：未知；链接可达性：未检查。**", "",
    ]
    for idx, record in enumerate(evidence["records"], 1):
        if not isinstance(record, dict):
            raise ProductError("markdown_evidence_invalid", "冻结来源结构损坏。", 422)
        record_id, digest = record.get("record_id"), record.get("sha256")
        if (not isinstance(record_id, str)
                or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,256}", record_id)
                or not _md_safe_text(record_id)):
            raise ProductError("markdown_evidence_invalid", "冻结记录标识无法安全导出。", 422)
        if not isinstance(digest, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", digest):
            raise ProductError("markdown_evidence_invalid", "冻结证据缺少完整 SHA-256。", 422)
        platform = record.get("platform")
        if platform not in ("telegram", "x", "youtube"):
            platform = "未知"
        name = record.get("name")
        if not _md_safe_text(name) or len(name) > 200:
            name = "（敏感或无效名称已略）"
        # Same conservative URL filter as the existing strict share path.
        url = _share_safe_url(record.get("url"))
        lines += [
            "### 来源 " + str(idx), "",
            "冻结记录标识：", _md_literal(record_id), "",
            "平台：", _md_literal(platform), "",
            "出处名称：", _md_literal(name), "",
            "原始出处 URL（静态筛选但不联网）：",
            _md_literal(url or "不可用或可能泄露私密数据，已略"), "",
            "原帖发布时间：", _md_literal(_md_timestamp(record.get("published_at"))), "",
            "首次收录时间：", _md_literal(_md_timestamp(record.get("first_ingested_at"))), "",
            "冻结原文 SHA-256：", _md_literal(digest.lower()), "",
        ]
    lines += [
        "## 复核与外发边界", "",
        "SHA-256 只能用于核对当时收录的文字字节，并不证明内容真实或信源独立。",
        "请本人访问安全原始链接复核时间、内容、首发和转载；链接可达性未由程序检查。",
        "自动敏感信息筛选不能替代人工逐字审核，也不代表版权授权。",
        "外发请使用原有严格筛选的 format=share 人工审核摘要，不要外发此私人 Markdown。",
        "",
    ]
    return "\n".join(lines), snapshot_sha256


class Dossier:
    def __init__(self, store, plan: str = "free"):
        self.store = store
        self.plan = plan
        # Separate processes serialize additive DDL without changing V2's schema number.
        with store.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            # complete_statement keeps the trigger bodies together.
            statement = ""
            for line in SCHEMA_DOSSIER.splitlines():
                statement += line + "\n"
                if sqlite3.complete_statement(statement):
                    c.execute(statement)
                    statement = ""

    def _require_pro(self):
        if self.plan not in DOSSIER_WRITE_PLANS:
            raise ProductError(
                "dossier_plan_required",
                "新增个人研判版本与版本导出仅对 Pro/Analyst 内测开放。"
                "当前 Free 仍可阅读原始证据和已有研判；内测尚未开放购买或付费升级。",
                403,
            )

    @staticmethod
    def _evidence(c, event_id):
        row = c.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
        if row is None:
            raise ProductError("event_missing", "这条事件不存在", 404)
        analysis = json.loads(row["data"])
        event = {key: row[key] for key in ("id", "title", "summary", "updated_at")}
        event.update(
            {
                key: analysis.get(key)
                for key in (
                    "event_time_start",
                    "event_time_end",
                    "event_time_precision",
                    "event_time_evidence",
                    "event_time_note",
                    "locations",
                    "analysed_at",
                )
            }
        )
        event["event_time_status"] = analysis.get("event_time_status", "unknown")
        event["location_status"] = row["location_status"]
        event["first_ingested_at"] = row["first_ingested_at"] or row["created_at"]
        records = []
        publishers = set()
        for raw in c.execute(
            "SELECT * FROM raw_records WHERE event_id=? AND state='completed' "
            "ORDER BY source_published_at,record_id",
            (event_id,),
        ):
            publishers.add((raw["plugin_id"], raw["target_id"] or raw["source_name"]))
            url = evidence_url(raw["source_url"])
            records.append(
                {
                    "record_id": raw["record_id"],
                    "platform": raw["plugin_id"],
                    "source_id": raw["target_id"],
                    "name": raw["source_name"],
                    "url": url,
                    "title": raw["title"],
                    "text": raw["text"],
                    "published_at": raw["source_published_at"],
                    "first_ingested_at": raw["first_ingested_at"] or raw["ingested_at"],
                    "sha256": hashlib.sha256(raw["text"].encode()).hexdigest(),
                    "link_status": "not_checked" if url else "unavailable",
                }
            )
        return {
            "event": event,
            "records": records,
            "raw_record_count": len(records),
            "publisher_count": len(publishers),
            "independence_status": "unknown",
            "notice": "出处标识按平台与订阅/名称计数，未核实首发或转载关系；"
            "多条原文≠多个独立证实。链接可达性未检查。",
        }

    @staticmethod
    def _latest(c, owner, event_id):
        return c.execute(
            "SELECT * FROM dossier_revisions WHERE owner=? AND event_id=? "
            "ORDER BY version DESC LIMIT 1",
            (owner, event_id),
        ).fetchone()

    @staticmethod
    def _revision(row):
        return {
            "version": row["version"],
            "created_at": row["created_at"],
            **json.loads(row["data"]),
        }

    def get(self, owner, event_id):
        with self.store.connect() as c:
            c.execute("BEGIN")
            evidence = self._evidence(c, event_id)
            latest = self._latest(c, owner, event_id)
            history = [
                dict(row)
                for row in c.execute(
                    "SELECT version,created_at FROM dossier_revisions WHERE owner=? AND event_id=? "
                    "ORDER BY version DESC",
                    (owner, event_id),
                )
            ]
            return {
                "event_id": event_id,
                "version": latest["version"] if latest else 0,
                "fields": json.loads(latest["data"])["fields"]
                if latest
                else dict.fromkeys(FIELDS, ""),
                "evidence": evidence,
                "history": history,
            }

    def save(self, owner, event_id, payload):
        self._require_pro()
        if not isinstance(payload, dict) or set(payload) != {"version", "fields"}:
            raise ProductError("invalid_dossier", "请提交研判字段和当前版本")
        version, fields = payload["version"], payload["fields"]
        if type(version) is not int or version < 0:
            raise ProductError("version_required", "请先加载当前研判版本")
        if not isinstance(fields, dict) or set(fields) != set(FIELDS):
            raise ProductError("invalid_dossier_fields", "研判字段不完整")
        if any(not isinstance(v, str) or len(v) > 20000 for v in fields.values()):
            raise ProductError("invalid_dossier_text", "每项请使用不超过 20000 字的文本")
        review_on = fields["review_on"]
        if review_on:
            try:
                if date.fromisoformat(review_on).isoformat() != review_on:
                    raise ValueError
            except ValueError:
                raise ProductError("invalid_review_date", "复查日请使用 YYYY-MM-DD") from None
        with self.store.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            evidence = self._evidence(c, event_id)
            latest = self._latest(c, owner, event_id)
            current = latest["version"] if latest else 0
            if current != version:
                raise ProductError(
                    "dossier_conflict",
                    "研判已在其他会话更新；草稿仍保留，请查看最新修订后合并",
                    409,
                )
            stamp = now_iso()
            snapshot = {"fields": fields, "evidence": evidence}
            c.execute(
                "INSERT INTO dossier_revisions(owner,event_id,version,created_at,data) "
                "VALUES(?,?,?,?,?)",
                (owner, event_id, current + 1, stamp, json.dumps(snapshot, ensure_ascii=False)),
            )
            c.execute(
                "INSERT INTO audit(at,owner,action,target,details) VALUES(?,?,?,?,?)",
                (stamp, owner, "dossier.saved", event_id, json.dumps({"version": current + 1})),
            )
            return {"event_id": event_id, "version": current + 1, "created_at": stamp, **snapshot}

    def evidence_changes(self, owner, event_id, version):
        """Latest saved judgment → current linked originals, not frozen-vs-frozen diff."""
        self._require_pro()
        # Local import avoids circular import with this module's URL gate.
        from .evidence_change import evidence_changes
        return evidence_changes(self.store, owner, event_id, version)

    def revision(self, owner, event_id, version):
        if type(version) is not int or version < 1:
            raise ProductError("invalid_revision", "修订版本无效")
        with self.store.connect() as c:
            row = c.execute(
                "SELECT * FROM dossier_revisions WHERE owner=? AND event_id=? AND version=?",
                (owner, event_id, version),
            ).fetchone()
            if row is None:
                raise ProductError("revision_missing", "这次研判修订不存在", 404)
            return {"event_id": event_id, **self._revision(row)}

    @staticmethod
    def _comparison_source(record):
        """Frozen source index only, never raw body/title or an inferred witness."""
        keys = (
            "record_id", "platform", "source_id", "name", "sha256",
            "published_at", "first_ingested_at",
        )
        url = evidence_url(record.get("url"))
        return {
            **{key: record.get(key) for key in keys},
            "url": url,
            "link_status": "not_checked" if url else "unavailable",
        }

    def compare(self, owner, event_id, from_version, to_version):
        """Read-only, owner-scoped comparison of two *frozen* judgments.

        No live-event query and no model-created explanation. Different record
        identifiers or hashes do not imply independent corroboration.
        """
        if (
            type(from_version) is not int or type(to_version) is not int
            or not 1 <= from_version < to_version <= 2**63 - 1
        ):
            raise ProductError(
                "invalid_comparison",
                "请指定从较早版本到较新版本的有效正整数版本号",
                400,
            )
        with self.store.connect() as c:
            c.execute("BEGIN")
            rows = c.execute(
                "SELECT version,created_at,data FROM dossier_revisions "
                "WHERE owner=? AND event_id=? AND version IN (?,?)",
                (owner, event_id, from_version, to_version),
            ).fetchall()
        if len(rows) != 2:
            raise ProductError("revision_missing", "研判版本不存在或不属于当前用户", 404)

        versions = {row["version"]: self._revision(row) for row in rows}
        before, after = versions[from_version], versions[to_version]
        field_changes = [
            {
                "key": key,
                "label": label,
                "before": before["fields"].get(key, ""),
                "after": after["fields"].get(key, ""),
                "changed": before["fields"].get(key, "") != after["fields"].get(key, ""),
            }
            for key, label in FIELDS.items()
        ]

        frozen_before = before["evidence"]
        frozen_after = after["evidence"]
        old_records = {
            record["record_id"]: record for record in frozen_before["records"]
        }
        new_records = {
            record["record_id"]: record for record in frozen_after["records"]
        }
        old_keys, new_keys = set(old_records), set(new_records)
        added = [
            self._comparison_source(new_records[key]) for key in sorted(new_keys - old_keys)
        ]
        removed = [
            self._comparison_source(old_records[key]) for key in sorted(old_keys - new_keys)
        ]
        tracked = (
            "sha256", "platform", "source_id", "name", "url", "title",
            "published_at", "first_ingested_at",
        )
        updated = []
        for key in sorted(old_keys & new_keys):
            previous, current = old_records[key], new_records[key]
            changed = [
                item for item in tracked if previous.get(item) != current.get(item)
            ]
            if changed:
                updated.append({
                    "record_id": key,
                    "changed_properties": changed,
                    "before": self._comparison_source(previous),
                    "after": self._comparison_source(current),
                })

        occurrence_keys = (
            "event_time_start", "event_time_end", "event_time_status",
            "event_time_precision", "event_time_evidence", "event_time_note",
        )
        old_occurrence = {
            key: frozen_before["event"].get(key) for key in occurrence_keys
        }
        new_occurrence = {
            key: frozen_after["event"].get(key) for key in occurrence_keys
        }
        return {
            "event_id": event_id,
            "from_version": from_version,
            "to_version": to_version,
            "from_saved_at": before["created_at"],
            "to_saved_at": after["created_at"],
            "field_changes": field_changes,
            "changed_field_keys": [
                item["key"] for item in field_changes if item["changed"]
            ],
            "source_changes": {
                "from_count": len(old_records),
                "to_count": len(new_records),
                "added": added,
                "removed": removed,
                "updated": updated,
                "unchanged_count": len(old_keys & new_keys) - len(updated),
                "independence_status": "unknown",
            },
            "event_occurrence": {
                "before": old_occurrence,
                "after": new_occurrence,
                "changed": old_occurrence != new_occurrence,
            },
            "notice": (
                "只比较保存时的冻结证据与本人文字，不推断判断为何变化；"
                "出处发布时间、首次收录时间与事件发生时间不能混用；"
                "同源转载或记录数变化不代表独立证实，链接可达性未检查。"
            ),
        }

    @staticmethod
    def _share_export(event_id, revision):
        """Allowlisted frozen references plus human-authored fields only.

        No current event/raw query or model output is used; a link, SHA or count
        does not establish factual truth, rights clearance or independence.
        """
        fields = revision["fields"]
        evidence = revision["evidence"]
        judgment = fields.get("judgment")
        compact = _share_compact(judgment)
        if (
            len(compact) < 8
            or len(set(compact)) < 3
            or compact in _SHARE_EMPTY_JUDGMENTS
            or ("不知道" in compact and "需要验证" in compact and len(compact) < 20)
            or re.match(r"^\s*已撤回\s*v\d+\s*判断", judgment) is not None
        ):
            raise ProductError(
                "share_judgment_required",
                "请先在冻结版本写下本人原创且有实质内容的判断；空白、占位或仅称待核实不能对外生成摘要。",
                422,
            )
        # The internal revision may contain raw text, raw titles and AI summary.
        # Never transfer those keys. Reject accidental copy/paste of such source
        # material into human fields instead of silently redacting frozen notes.
        event = evidence.get("event", {})
        records = evidence.get("records", [])
        originals = [event.get("title"), event.get("summary")]
        originals.extend(record.get(key) for record in records for key in ("title", "text"))
        for key in FIELDS:
            value = fields.get(key)
            if not isinstance(value, str) or _share_sensitive_static_text(value):
                raise ProductError(
                    "share_sensitive_content",
                    "人工研判中包含可能的账号、凭据或本机路径；请保存脱敏后的新修订再申请摘要。",
                    422,
                )
            normalized = _share_compact(value)
            for original in originals:
                if not isinstance(original, str) or not original:
                    continue
                source = _share_compact(original)
                if (source and normalized == source) or (
                    len(source) >= 10 and original in value
                ):
                    raise ProductError(
                        "share_source_copy_forbidden",
                        "人工字段中复制了采集原文、标题或自动摘要；请用本人原创判断重写并保存新版本。",
                        422,
                    )

        version = revision["version"]
        lines = [
            "FRONTIER · 本人原创研判摘要（待本人核验）",
            f"冻结研判版本：v{version}",
            "仅供本人完成逐项审核后，自愿手工提供给外部潜在买方核对；生成不等于授权外发。",
            "警示：必须本人逐条核实出处、确认分发授权和适用法律；平台未核实事实、来源独立性或版权。",
            "不得未经许可转发版权内容。",
            "本人自行粘贴到人工字段的版权原文、机密或账号可能无法被程序识别或清除；本人须逐字检查后才可决定外发。",
            "默认完整私人原版仍保留，仅供本人留档，不可外发；本摘要不是来源转载许可。",
            "",
        ]
        for key, label in FIELDS.items():
            lines.extend([label + "（本人填写）：", fields[key] or "未填写", ""])
        # These counts were frozen when this revision was saved. The distinct
        # subscription/source count is NOT a count of corroborating witnesses.
        raw_count = evidence.get("raw_record_count")
        publisher_count = evidence.get("publisher_count")
        raw_label = raw_count if type(raw_count) is int and raw_count >= 0 else "未知"
        publisher_label = (
            publisher_count if type(publisher_count) is int and publisher_count >= 0 else "未知"
        )
        lines.extend([
            f"冻结原始记录数：{raw_label}；冻结出处标识数：{publisher_label}；独立性：未知",
            "出处标识按平台及订阅归类，未核首发、转载、来源独立性；链接可达性亦未核验。",
            "保存时冻结的出处索引（不含采集原文、标题或自动摘要）：",
        ])
        for index, record in enumerate(records, 1):
            record_id = record.get("record_id")
            sha256 = record.get("sha256")
            published = record.get("published_at")
            if not isinstance(record_id, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,256}", record_id):
                raise ProductError("share_evidence_invalid", "冻结证据记录标识不适合公开；请勿外发。", 422)
            if not isinstance(sha256, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", sha256):
                raise ProductError("share_evidence_invalid", "冻结证据 SHA-256 不完整；请勿外发。", 422)
            if not isinstance(published, str) or not re.fullmatch(
                r"\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?)?",
                published,
            ):
                published = "未知"
            url = _share_safe_url(record.get("url"))
            lines.extend([
                f"[{index}] 原始记录 ID：{record_id}",
                "SHA-256：" + sha256,
                "出处发布时间：" + published,
                "保存时的安全出处 URL：" + (url or "不可用（不披露危险或可能含凭据的链接）"),
                "",
            ])
        lines.extend([
            "人工发出前再次核对：必须本人核出处、确认授权和法律，平台未核实；不得未经许可转发版权内容。",
        ])
        # The event identifier is an internal record correlation ID, never an
        # account, path or auth token. The current client fails closed unless it
        # matches the explicitly requested event and frozen version.
        return {"event_id": event_id, "version": version, "format": "share", "text": "\n".join(lines)}

    def markdown(self, owner, event_id, version):
        """Pro/Analyst private Markdown; legacy full/share JSON is unchanged."""
        self._require_pro()
        return _md_private_export(event_id, self.revision(owner, event_id, version))

    def export(self, owner, event_id, version, *, format="full"):
        self._require_pro()
        if format not in ("full", "share"):
            raise ProductError("invalid_export_format", "仅支持 format=full 或 format=share", 400)
        revision = self.revision(owner, event_id, version)
        if format == "share":
            return self._share_export(event_id, revision)
        evidence = revision["evidence"]
        event = evidence["event"]
        lines = [
            "FRONTIER 个人研究卡",
            event["title"],
            f"事件 ID：{event_id}",
            f"研判版本：{version} · 保存于 {revision['created_at']}",
            f"站内详情：/?event={event_id}",
            "",
            "自动整理摘要（未经人工事实核验）：",
            event["summary"],
            f"发生时间：{event.get('event_time_start') or '未知'}（{event['event_time_status']}）",
            f"地点状态：{event['location_status']}（详见保存的时空依据）",
            "时空依据快照："
            + json.dumps(
                {
                    k: event[k]
                    for k in (
                        "event_time_end",
                        "event_time_precision",
                        "event_time_evidence",
                        "event_time_note",
                        "locations",
                        "analysed_at",
                    )
                },
                ensure_ascii=False,
            ),
            "",
        ]
        for key, label in FIELDS.items():
            lines.extend([label + "：", revision["fields"][key] or "未填写", ""])
        lines.extend(
            [
                f"原始记录数：{evidence['raw_record_count']}；出处标识数：{evidence['publisher_count']}；独立性：未知",
                evidence["notice"],
                "",
                "保存时的引用与原文（不是已验证的独立证据）：",
            ]
        )
        for index, record in enumerate(evidence["records"], 1):
            lines.extend(
                [
                    f"[{index}] {record['name']} · {record['platform']}",
                    f"原始记录：{record['record_id']}",
                    record["url"] or "安全原文链接不可用",
                    f"原帖发布：{record['published_at'] or '未知'}；"
                    f"首次收录：{record['first_ingested_at']}",
                    "SHA-256：" + record["sha256"],
                    record["text"] or "原文正文缺失",
                    "",
                ]
            )
        return {"event_id": event_id, "version": version, "text": "\n".join(lines)}
