"""Editorial JSON parsing retained for existing data interfaces."""

# ruff: noqa: E501

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import Any

from xhs_local.core.contracts import Editorial, EditorialItem

from .compliance import (
    extract_json,
    js_number,
)
from .provider import (
    DeepSeekResponseError,
)


def _value(candidate: object, *names: str, default: Any = None) -> Any:
    if isinstance(candidate, Mapping):
        for name in names:
            if name in candidate:
                return candidate[name]
        return default
    for name in names:
        if hasattr(candidate, name):
            return getattr(candidate, name)
    return default


def candidate_id(candidate: object) -> str:
    return str(_value(candidate, "record_id", "id", default=""))


def _source_name(candidate: object) -> str:
    return str(_value(candidate, "source_name", "channel_name", "channelName", default="") or "")


def _candidate_text(candidate: object) -> str:
    return str(_value(candidate, "text", default="") or "")


def _attachments(candidate: object) -> Sequence[object]:
    value = _value(candidate, "attachments", default=())
    return value if isinstance(value, Sequence) and not isinstance(value, (str, bytes)) else ()


def _unicode_slice(value: object, limit: int | None) -> str:
    return str(value)[:limit]


def _normalize_tags(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    tags: list[str] = []
    seen: set[str] = set()
    for raw in value:
        if raw is None:
            text = "null"
        elif isinstance(raw, bool):
            text = str(raw).lower()
        else:
            text = str(raw)
        tag = re.sub(r"\s+", "", text.removeprefix("#")).strip()
        if tag and tag not in seen:
            seen.add(tag)
            tags.append(tag)
        if len(tags) == 8:
            break
    return tuple(tags)


def _star_rating(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1 or value > 5:
        raise DeepSeekResponseError("DeepSeek star_rating must be an integer from 1 to 5")
    return value


def platform_balance_weights(published_counts: Mapping[str, int]) -> dict[str, float]:
    """Return a mild inverse-exposure weight normalized around 1.0."""

    if any(
        not isinstance(plugin_id, str)
        or not plugin_id
        or isinstance(count, bool)
        or not isinstance(count, int)
        or count < 0
        for plugin_id, count in published_counts.items()
    ):
        raise TypeError("platform publish counts must map plugin IDs to non-negative integers")
    if not published_counts:
        return {}
    raw = {plugin_id: 1 / math.sqrt(count + 4) for plugin_id, count in published_counts.items()}
    mean = sum(raw.values()) / len(raw)
    return {
        plugin_id: round(max(0.65, min(1.35, value / mean)), 2) for plugin_id, value in raw.items()
    }


def _platform_balance_rules(published_counts: Mapping[str, int]) -> str:
    weights = platform_balance_weights(published_counts)
    if not weights:
        return ""
    rows = "\n".join(
        f"- {plugin_id}: 最近24小时已发布 {published_counts[plugin_id]} 条，均衡权重 {weight:.2f}"
        for plugin_id, weight in sorted(weights.items())
    )
    return f"""平台曝光均衡信息：
{rows}
规则：近期发布越多的平台权重越低。先比较内容的真实星级和事实价值；当质量相近时优先较高权重的平台。真正 5 星不得被非 5 星仅凭平台权重压过。最终仍只能选择一个平台成帖。"""


def parse_editorial_response(
    content: str,
    candidates: Sequence[object],
    *,
    max_items: int | None = None,
    text_limit: int | None = 320,
    catch_up: bool = False,
) -> Editorial:
    if max_items is None:
        max_items = len(candidates)
    if not isinstance(max_items, int) or isinstance(max_items, bool) or max_items < 1:
        raise ValueError("max_items must be a positive integer")
    payload = extract_json(content)
    selected = payload.get("selected")
    if not isinstance(selected, list):
        raise DeepSeekResponseError("DeepSeek response lacks selected[]")
    if not selected:
        return Editorial(title="", body="", tags=(), items=())

    title = _unicode_slice(str(payload.get("title") or "").strip(), 20)
    tags = _normalize_tags(payload.get("tags"))
    if not title or not tags:
        raise DeepSeekResponseError("Selected response requires title and tags")
    if "科技快讯" in title or "精选" in title:
        raise DeepSeekResponseError("DeepSeek title is generic or contains a forbidden phrase")

    ranked: list[tuple[int, int, EditorialItem]] = []
    used_ids: set[str] = set()
    for selection_order, selection in enumerate(selected):
        if not isinstance(selection, Mapping):
            continue
        raw_index = selection.get("index")
        source_number = js_number(raw_index)
        if not math.isfinite(source_number) or not source_number.is_integer():
            continue
        source_index = int(source_number)
        source = candidates[source_index - 1] if 1 <= source_index <= len(candidates) else None
        raw_headline = str(selection.get("headline") or "").strip()
        headline = _unicode_slice(raw_headline, 28)
        text = _unicode_slice(str(selection.get("text") or "").strip(), text_limit)
        source_id = candidate_id(source) if source is not None else ""
        if source is None or not source_id or not headline or not text or source_id in used_ids:
            continue
        score = _star_rating(selection.get("star_rating"))
        if score < 3:
            continue
        summary = str(selection.get("summary") or raw_headline).strip()
        if "\n" in summary or "\r" in summary or re.search(r"[。！？!?].*\S", summary):
            raise DeepSeekResponseError("summary must be one sentence on one line")
        used_ids.add(source_id)
        item = EditorialItem(
            record_id=source_id,
            headline=headline,
            text=text,
            star_rating=score,
            summary=summary,
            translation_required=selection.get("translation_required"),
        )
        ranked.append((score, selection_order, item))
    if not ranked:
        raise DeepSeekResponseError("DeepSeek selected[] contains no usable items")
    if not catch_up and sum(score == 5 for score, _order, _item in ranked) > 1:
        raise DeepSeekResponseError("one note may contain at most one star_rating 5 item")
    ranked.sort(key=lambda entry: (-entry[0], entry[1]))
    return Editorial(
        title=title,
        body="",
        tags=tags,
        items=tuple(entry[2] for entry in ranked[:max_items]),
    )


def _candidate_list(candidates: Sequence[object], *, text_limit: int | None = 1_200) -> str:
    rows: list[str] = []
    for index, candidate in enumerate(candidates, start=1):
        source_name = _source_name(candidate)
        source = f"来源：{source_name}\n" if source_name else ""
        plugin_id = str(_value(candidate, "plugin_id", default="") or "")
        platform = f"平台：{plugin_id}\n" if plugin_id else ""
        title = _value(candidate, "title", default="")
        title_line = f"标题：{title}\n" if title else ""
        rows.append(
            f"[{index}] {platform}{source}{title_line}attachedImages: {len(_attachments(candidate))}\n"
            f"{_unicode_slice(_candidate_text(candidate), text_limit)}"
        )
    return "\n\n".join(rows)


def _preserve_original_text(
    editorial: Editorial,
    candidates: Sequence[object],
    record_ids: frozenset[str] | None = None,
) -> Editorial:
    by_id = {candidate_id(candidate): candidate for candidate in candidates}
    items = []
    for item in editorial.items:
        if record_ids is not None and item.record_id not in record_ids:
            items.append(item)
            continue
        original = _candidate_text(by_id[item.record_id]).strip()
        generated = item.text.strip()
        if "背景概述：" not in generated:
            raise DeepSeekResponseError("X presentation lacks a background overview")
        background = generated.split("背景概述：", 1)[1].strip()
        if not re.search(r"[\u3400-\u9fff]", background):
            raise DeepSeekResponseError("X background overview must contain Chinese")
        if not isinstance(item.translation_required, bool):
            raise DeepSeekResponseError("X presentation requires an LLM language decision")
        if not item.translation_required:
            text = f"原文：\n{original}\n\n背景概述：\n{background}"
        else:
            if "中文翻译：" not in generated:
                raise DeepSeekResponseError("X presentation lacks a Chinese translation")
            translation = generated.split("中文翻译：", 1)[1].split("背景概述：", 1)[0].strip()
            if not re.search(r"[\u3400-\u9fff]", translation):
                raise DeepSeekResponseError("X presentation lacks a Chinese translation")
            text = f"原文：\n{original}\n\n中文翻译：\n{translation}\n\n背景概述：\n{background}"
        items.append(replace(item, text=text))
    return replace(editorial, items=tuple(items))
