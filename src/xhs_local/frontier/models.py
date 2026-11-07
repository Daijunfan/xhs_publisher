"""Validate model output before it can become an event. Unknown facts stay unknown."""

from __future__ import annotations

import hashlib
import math
import re
from datetime import UTC, date, datetime
from typing import Any
from urllib.parse import urlsplit

from .time_quality import MONTH_DAY_CUE, withdraw_week_point

CATEGORIES = (
    "ai",
    "chips",
    "robotics",
    "space",
    "science",
    "energy",
    "security",
    "technology",
    "business",
)
SCORE_WEIGHTS = {"impact": 0.35, "scope": 0.25, "novelty": 0.25, "urgency": 0.15}
SCORE_VERSION = "editorial-v1"
PROMPT_VERSION = "frontier-evidence-v1"
RELATIVE_TIME = re.compile(
    r"\b(?:today|yesterday|tomorrow|tonight|now)\b|"
    r"\b(?:last|this|next|previous)\s+(?:week|month|year|night|morning|evening|"
    r"Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b|"
    r"\b(?:\d+|a|an|one|two|three|few|several)\s+"
    r"(?:minutes?|hours?|days?|weeks?|months?|years?)\s+ago\b|"
    r"今[天日晨晚早]|昨[天日夜晚]|明[天日早晚]|前天|后天|刚刚|现在|"
    r"(?:上|本|这|下)(?:周|星期|月|年)|[一二三四五六七八九十\d]+(?:小时|分钟|天|周|月|年)前",
    re.I,
)


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def iso_time(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str) or len(value) > 40:
        raise ValueError("invalid_timestamp")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    if dt.year < 1900 or dt.year > 2200:
        raise ValueError("timestamp_out_of_range")
    return dt.astimezone(UTC).isoformat(timespec="milliseconds")


def safe_url(value: Any) -> str | None:
    if not isinstance(value, str) or len(value) > 4096:
        return None
    try:
        p = urlsplit(value)
        if p.scheme not in {"http", "https"} or not p.hostname or p.username or p.password:
            return None
        return value
    except ValueError:
        return None


def _text(value: Any, maximum: int, *, required: bool = False) -> str:
    if not isinstance(value, str):
        if required:
            raise ValueError("missing_text")
        return ""
    result = value.strip()[:maximum]
    if required and not result:
        raise ValueError("empty_text")
    return result


def _compact(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def has_evidence(value: str, original: str) -> bool:
    return len(value.strip()) >= 2 and _compact(value) in _compact(original)


def raw_fingerprint(raw: dict) -> str:
    text = _compact(str(raw.get("title", "")) + "\n" + str(raw.get("text", "")))
    # Identical relative-date wording on different days can describe different events.
    # The source timestamp is context, never a fallback event occurrence timestamp.
    if RELATIVE_TIME.search(text):
        published = raw.get("source_published_at") or raw.get("occurred_at")
        anchor = iso_time(published) if published else None
        context = anchor or "unknown:" + str(raw.get("record_id", ""))
        text += "\nrelative-time-context:" + context
    return hashlib.sha256(text.encode()).hexdigest()


def validate_analysis(data: Any, raw: dict) -> dict:
    if not isinstance(data, dict) or not isinstance(data.get("is_event"), bool):
        raise ValueError("invalid_model_schema")
    if not data["is_event"]:
        return {"is_event": False, "reason": _text(data.get("reason"), 300)}
    original = str(raw.get("title", "")) + "\n" + str(raw.get("text", ""))
    result = {
        "is_event": True,
        "title": _text(data.get("title"), 160, required=True),
        "summary": _text(data.get("summary"), 2500, required=True),
        "category": data.get("category") if data.get("category") in CATEGORIES else "technology",
        "tags": [_text(t, 40) for t in data.get("tags", [])[:8] if isinstance(t, str)]
        if isinstance(data.get("tags", []), list)
        else [],
        "event_time_start": None,
        "event_time_end": None,
        # Non-instant calendar evidence MUST keep the source's civil date:
        # iso_time() normalizes to UTC and can cross a day/month boundary.
        # These are DERIVED by validator, not trusted verbatim model fields.
        "event_civil_start": None,
        "event_civil_end": None,
        "event_time_precision": "unknown",
        "event_time_status": "unknown",
        "event_time_evidence": "",
        "event_timezone": None,
        "locations": [],
        "location_status": "unknown",
        "confidence": "single_source",
        "score_version": SCORE_VERSION,
        "prompt_version": PROMPT_VERSION,
    }
    scores = data.get("score_components")
    if not isinstance(scores, dict) or set(scores) != set(SCORE_WEIGHTS):
        raise ValueError("invalid_score_components")
    for value in scores.values():
        if isinstance(value, bool) or not isinstance(value, (float, int)):
            raise ValueError("invalid_score")
        if not math.isfinite(value) or not 0 <= value <= 100:
            raise ValueError("score_out_of_range")
    result["score_components"] = scores
    result["importance"] = round(sum(scores[k] * w for k, w in SCORE_WEIGHTS.items()))
    result["score_reason"] = _text(data.get("score_reason"), 700, required=True)
    evidence = _text(data.get("event_time_evidence"), 450)
    precision = data.get("event_time_precision", "unknown")
    status = data.get("event_time_status", "unknown")
    # A timestamp supplied by the model is never itself evidence.
    temporal_cue = re.search(
        r"20\d{2}|\d{1,2}月|\d{1,2}[/.-]\d{1,2}|today|yesterday|tomorrow|"
        r"last (?:week|month|night)|this (?:week|morning)|今[天日晨晚]|昨日|昨天|明天|上周|"
        r"January|February|March|April|May|June|July|August|September|October|November|December|"
        r"Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday",
        evidence,
        re.I,
    )
    if (
        precision in {"exact", "day", "month", "range"}
        and status in {"explicit", "inferred", "scheduled"}
        and has_evidence(evidence, original)
        and (temporal_cue or MONTH_DAY_CUE.search(evidence))
    ):
        raw_start = data.get("event_time_start")
        if precision == "exact" and isinstance(raw_start, str):
            parsed = datetime.fromisoformat(raw_start.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                raise ValueError("exact_event_time_requires_timezone")
        start = iso_time(raw_start)
        end = iso_time(data.get("event_time_end"))
        if start and (not end or end >= start):
            raw_end = data.get("event_time_end")
            def civil_day(raw_time):
                if not isinstance(raw_time,str) or len(raw_time)<10:
                    return None
                candidate=raw_time[:10]
                try:
                    valid=date.fromisoformat(candidate)
                except ValueError:
                    return None
                return candidate if valid.isoformat()==candidate else None
            # A model-validated noninstant date is a calendar fact, not a
            # local-time-independent moment. Save BEFORE losing its UTC offset.
            civil_start=civil_day(raw_start) if precision!="exact" else None
            civil_end=civil_day(raw_end) if precision!="exact" and end else None
            result.update(
                event_time_start=start,
                event_time_end=end,
                event_civil_start=civil_start,
                event_civil_end=civil_end,
                event_time_precision=precision,
                event_time_status=status,
                event_time_evidence=evidence,
                event_timezone=_text(data.get("event_timezone"), 80) or None,
            )
            if datetime.fromisoformat(start) > datetime.now(UTC):
                result["event_time_status"] = "scheduled"
            if (
                re.search(
                    r"today|yesterday|tomorrow|今[天日]|昨天|昨日|明天|last |this ", evidence, re.I
                )
                and result["event_time_status"] != "scheduled"
            ):
                result["event_time_status"] = "inferred"
    result = withdraw_week_point(result)
    locations = data.get("locations", [])
    if not isinstance(locations, list):
        raise ValueError("invalid_locations")
    for location in locations[:6]:
        if not isinstance(location, dict):
            raise ValueError("invalid_location")
        lat, lon = location.get("latitude"), location.get("longitude")
        if (
            isinstance(lat, bool)
            or isinstance(lon, bool)
            or not isinstance(lat, (float, int))
            or not isinstance(lon, (float, int))
            or not math.isfinite(lat)
            or not math.isfinite(lon)
            or not -90 <= lat <= 90
            or not -180 <= lon <= 180
        ):
            raise ValueError("coordinates_out_of_range")
        ev = _text(location.get("evidence"), 450)
        if (
            not has_evidence(ev, original)
            or location.get("role") not in {"occurrence", "affected"}
            or location.get("precision") not in {"point", "city", "region", "country"}
        ):
            continue
        result["locations"].append(
            {
                "name": _text(location.get("name"), 100, required=True),
                "country_code": _text(location.get("country_code"), 3).upper(),
                "latitude": lat,
                "longitude": lon,
                "precision": location["precision"],
                "role": location["role"],
                "status": "explicit" if location.get("status") == "explicit" else "inferred",
                "evidence": ev,
            }
        )
    if result["locations"]:
        result["location_status"] = "located"
    elif data.get("location_status") == "global":
        result["location_status"] = "global"
    return result


def event_key(analysis: dict, fingerprint: str) -> str:
    """Only exact normalized title/date/category matches merge; no fuzzy identity guesses."""
    if analysis.get("event_time_start"):
        start = analysis["event_time_start"]
        precision = analysis.get("event_time_precision")
        # Preserve existing day identities while keeping distinct exact times and ranges.
        when = start[:10]
        if precision in {"exact", "range"}:
            when = precision + ":" + start + "/" + (analysis.get("event_time_end") or "")
        elif precision == "month":
            when = "month:" + start[:7]
        identity = "\n".join(
            (
                _compact(analysis["title"]),
                when,
                analysis["category"],
                ",".join(sorted(x["name"] for x in analysis["locations"])),
            )
        )
    else:
        identity = fingerprint
    return hashlib.sha256(identity.encode()).hexdigest()[:32]
