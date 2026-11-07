"""One frozen personal judgment versus the CURRENT local completed originals.

Not revision-vs-revision diff (dossier.compare already owns that workflow).
This read-only, bounded view does not read collector DB, fetch remote URLs,
classify truth/independence, auto-edit a human judgment or infer occurrence time.
"""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from .dossier import evidence_url
from .models import now_iso
from .preferences import ProductError

MAX_SCAN = 500
MAX_DISPLAY = 6
# Only whitespace-identical substantial texts count as cross-URL copy.
# Short announcements at different URLs remain unresolved candidates.
LONG_LITERAL_MIN = 180


def _aware(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(UTC) if parsed.tzinfo else None
    except (OverflowError, TypeError, ValueError):
        return None


def _published(value):
    return (value, "publisher_reported_unverified") if _aware(value) else (None, "unknown")


def _compact(value):
    if not isinstance(value, str):
        raise ValueError("raw text is not a string")
    return " ".join(value.split())


def _signature(record):
    """Exact title+body (whitespace folded), not model semantic similarity."""
    return _compact(record["title"]) + "\n" + _compact(record["text"])


def _long_key(record):
    body = _compact(record["text"])
    return hashlib.sha256(body.encode()).hexdigest() if len(body) >= LONG_LITERAL_MIN else None


def _sample(record, saved_at):
    url = evidence_url(record["url"])
    published, publication_status = _published(record["published_at"])
    ingested = _aware(record["first_ingested_at"])
    baseline = _aware(saved_at)
    return {
        "record_id": record["record_id"],
        "platform": record["platform"],
        "source_name": record["name"],
        "url": url,
        "link_status": "not_checked" if url else "unavailable",
        "published_at": published,
        "publication_status": publication_status,
        "first_ingested_at": record["first_ingested_at"] if ingested else None,
        "ingested_after_save": ingested > baseline if ingested and baseline else None,
        "sha256": hashlib.sha256(record["text"].encode("utf-8")).hexdigest(),
    }


def _frozen_record(item):
    required = ("record_id", "title", "text")
    if not isinstance(item, dict) or any(
        not isinstance(item.get(key), str) or not item[key]
        for key in required[:1]
    ) or any(not isinstance(item.get(key), str) for key in required[1:]):
        raise ProductError("changes_baseline_invalid", "冻结出处结构不完整；不能比较。", 422)
    return {
        "record_id": item["record_id"], "title": item["title"],
        "text": item["text"], "url": item.get("url"),
        "platform": item.get("platform"), "name": item.get("name"),
        "published_at": item.get("published_at"),
        "first_ingested_at": item.get("first_ingested_at"),
    }


def evidence_changes(store, owner: str, event_id: str, version: int) -> dict:
    """Fresh record membership vs latest owner's immutable snapshot, no writes.

    New-to-snapshot != newly published, independent, verified, or occurred today.
    Same URL with differing text is a local CONTENT VARIANT, not proof that
    the publisher edited its live page. Exact repeats never count as new links.
    """
    if type(version) is not int or not 1 <= version <= 2**63 - 1:
        raise ProductError("invalid_changes_version", "请输入已保存的正整数研判版本。", 400)
    with store.connect() as c:
        c.execute("BEGIN")
        latest = c.execute(
            "SELECT version,created_at,data FROM dossier_revisions "
            "WHERE owner=? AND event_id=? ORDER BY version DESC LIMIT 1",
            (owner, event_id),
        ).fetchone()
        if latest is None:
            raise ProductError("revision_missing", "没有当前账户保存的此事件研判。", 404)
        if latest["version"] != version:
            raise ProductError(
                "changes_version_conflict",
                "最新研判已改变；刷新保存版本后重新核对，不能展示过期基线。",
                409,
            )
        try:
            frozen = json.loads(latest["data"])
            fields = frozen["fields"]
            original = frozen["evidence"]["records"]
            if not isinstance(original, list) or not isinstance(fields, dict):
                raise ValueError("invalid saved types")
            if not all(isinstance(fields.get(k), str) for k in (
                "judgment", "falsification", "support", "review_on"
            )):
                raise ValueError("invalid saved fields")
            before = [_frozen_record(item) for item in original]
            baseline = {item["record_id"]: item for item in before}
            if len(baseline) != len(before):
                raise ValueError("duplicate IDs in snapshot")
        except (KeyError, TypeError, ValueError) as exc:
            raise ProductError(
                "changes_baseline_invalid",
                "原有冻结证据无法安全解析；不推测新增原文。",
                422,
            ) from exc

        # A hard cap protects a single-user DB from huge synchronous reads.
        # If incomplete, do NOT report either zero changes or definite novelty.
        rows = c.execute(
            "SELECT record_id,plugin_id,source_name,source_url,title,text,"
            "source_published_at,first_ingested_at "
            "FROM raw_records WHERE event_id=? AND state='completed' "
            "ORDER BY first_ingested_at,record_id LIMIT ?",
            (event_id, MAX_SCAN + 1),
        ).fetchall()

        personal = {key: fields[key] for key in (
            "judgment", "falsification", "support", "review_on"
        )}
        result = {
            "event_id": event_id,
            "base_version": version,
            "base_saved_at": latest["created_at"],
            "computed_at": now_iso(),
            "basis": "owner_frozen_evidence_vs_current_linked_completed_records",
            "personal": personal,
            "truth": {
                "event_occurred_at": None,
                "event_time_status": "not_determined_in_this_view",
                "independent_confirmation": "unknown",
                "claim_verified": False,
                "falsification_detected": False,
                "human_judgment_changed": False,
            },
            "changes": {
                "status": "scan_limited" if (
                    len(rows) > MAX_SCAN or len(before) > MAX_SCAN
                ) else "complete",
                "baseline_count": len(before),
                "scanned_count": min(len(rows), MAX_SCAN),
                "new_link_count": None,
                "same_url_variant_count": None,
                "edited_record_count": None,
                "exact_repeat_count": None,
                "unverifiable_count": None,
                "frozen_missing_count": None,
                "new_links": [],
                "same_url_variants": [],
                "edited_records": [],
                "frozen_missing": [],
            },
            "notice": (
                "仅对比本人保存时的原始记录集合与本地当前已完成且关联到同一事件的记录；"
                "原文首次收录并非原文发表，原文发表并非事件发生。"
                "同 URL 内容差异不证明网页已编辑；异 URL 未见精确复制也不证明独立首发。"
                "相同 URL+文字或足够长的完全相同正文归为精确重复候选，"
                "不做语义转载推断。冻结原文不再位于已完成关联集合不等于线上撤稿。"
                "安全链接未联网验证，外部未采到的证据未知；"
                "本人保存的反证条件只供对照，系统未检测反证满足与否，绝不自动改判。"
            ),
        }
        delta = result["changes"]
        if delta["status"] == "scan_limited":
            return result

        url_signatures: dict[str, set[str]] = {}
        long_text_keys: set[str] = set()

        def index(record):
            url = evidence_url(record.get("url"))
            signature = _signature(record)
            if url:
                url_signatures.setdefault(url, set()).add(signature)
            if key := _long_key(record):
                long_text_keys.add(key)

        for item in before:
            index(item)

        counts = {
            "new_link_count": 0,
            "same_url_variant_count": 0,
            "edited_record_count": 0,
            "exact_repeat_count": 0,
            "unverifiable_count": 0,
        }
        current_ids = {row["record_id"] for row in rows}
        lost = [baseline[key] for key in sorted(set(baseline) - current_ids)]
        counts["frozen_missing_count"] = len(lost)
        for item in lost:
            # Link to FROZEN URL, not a claim that the live page was removed.
            if evidence_url(item["url"]) and len(delta["frozen_missing"]) < MAX_DISPLAY:
                sample = _sample(item, latest["created_at"])
                sample["kind"] = "frozen_record_no_longer_completed"
                delta["frozen_missing"].append(sample)
        for row in rows:
            item = {
                "record_id": row["record_id"],
                "platform": row["plugin_id"],
                "name": row["source_name"],
                "url": row["source_url"],
                "title": row["title"],
                "text": row["text"],
                "published_at": row["source_published_at"],
                "first_ingested_at": row["first_ingested_at"],
            }
            if not all(isinstance(item[k], str) for k in (
                "record_id", "platform", "name", "title", "text"
            )):
                counts["unverifiable_count"] += 1
                continue

            previous = baseline.get(item["record_id"])
            if previous is not None:
                # Original same-ID evidence may have been rewritten in the DB.
                # This is not a newly reported URL or a second witness.
                # Compare exact stored fields, not inferred online edits.
                changed_fields = [
                    key for key in (
                        "title", "text", "platform", "name",
                        "published_at", "first_ingested_at",
                    ) if previous.get(key) != item.get(key)
                ]
                if evidence_url(previous["url"]) != evidence_url(item["url"]):
                    changed_fields.append("url")
                if changed_fields:
                    if evidence_url(item["url"]):
                        counts["edited_record_count"] += 1
                        sample = _sample(item, latest["created_at"])
                        sample["kind"] = "existing_record_local_fields_changed"
                        sample["changed_properties"] = changed_fields
                        sample["previous_sha256"] = hashlib.sha256(
                            previous["text"].encode("utf-8")
                        ).hexdigest()
                        if len(delta["edited_records"]) < MAX_DISPLAY:
                            delta["edited_records"].append(sample)
                    else:
                        counts["unverifiable_count"] += 1
                index(item)
                continue

            url = evidence_url(item["url"])
            if not url:
                counts["unverifiable_count"] += 1
                index(item)
                continue
            sig = _signature(item)
            long_key = _long_key(item)
            if sig in url_signatures.get(url, set()) or (
                long_key is not None and long_key in long_text_keys
            ):
                counts["exact_repeat_count"] += 1
            elif url in url_signatures:
                counts["same_url_variant_count"] += 1
                if len(delta["same_url_variants"]) < MAX_DISPLAY:
                    sample = _sample(item, latest["created_at"])
                    sample["kind"] = "same_url_different_local_text"
                    delta["same_url_variants"].append(sample)
            else:
                counts["new_link_count"] += 1
                if len(delta["new_links"]) < MAX_DISPLAY:
                    sample = _sample(item, latest["created_at"])
                    sample["kind"] = "new_to_frozen_link_candidate"
                    delta["new_links"].append(sample)
            index(item)

        delta.update(counts)
        return result
