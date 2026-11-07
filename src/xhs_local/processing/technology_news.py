"""Two-stage DeepSeek editorial workflow for technology news."""

# Prompt wording is an external behavior contract and must not be line-wrapped.
# ruff: noqa: E501

from __future__ import annotations

import asyncio
import math
import os
import re
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import replace
from typing import Any

from xhs_local.core.contracts import Editorial, EditorialItem
from xhs_local.core.errors import ErrorClass, PipelineError

from .compliance import (
    COMPLIANCE_SYSTEM_PROMPT,
    extract_json,
    js_number,
    parse_compliance_response,
)
from .provider import (
    ChatCompletionProvider,
    DeepSeekHttpError,
    DeepSeekProvider,
    DeepSeekResponseError,
)

DEFAULT_FIRST_REVIEW_MODEL = os.environ.get(
    "DEEPSEEK_FIRST_REVIEW_MODEL", os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-pro")
)
DEFAULT_SECOND_REVIEW_MODEL = os.environ.get(
    "DEEPSEEK_SECOND_REVIEW_MODEL", os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash")
)

QUALITY_SYSTEM_PROMPT = """你是小红书科技新闻的资深主编。你只会收到已经通过两轮相同合规审核的候选；此阶段只做内容质量筛选、排序和编辑，不改变合规结论。

内容质量筛选规则：
- 优先科技产业、产品发布、软件与硬件、人工智能、网络安全、科研、开发者生态和数字商业
- 优先有明确来源、具体事实、数字、时间、产品变化、实际影响和读者价值的内容
- 有具体原理、方法或实例的科技、数学和自然科学教学内容也应参与正常评分，不得仅因不是时事快讯而排除
- 优先新颖、可验证、有信息增量的消息；有原图的高质量消息优先
- 主动降低明星与娱乐八卦、猎奇话题、泛泛观点、营销软文、重复消息、标题党和低信息量内容的优先级
- 排除传言、来源不明、纯情绪表达，以及与科技关联薄弱的内容
- 原文只有链接、表情或跳转提示，且自身没有可核验事实或上下文时必须排除；不得根据链接目标、作者身份或常识替它补写价值
- 合规优先于质量和数量；输出前再次逐条复核，任何疑似违反合规规则的候选必须删除

把所有入选新闻组织成一篇小红书图文笔记：
- title：整篇笔记标题，中文，不超过 20 个字符；必须直接概括本批最重要新闻的具体主体与核心变化，禁止使用“科技快讯”“精选”等空泛或违禁表述
- body：固定输出空字符串；系统会把实际入选新闻的 summary 各作为一句简短总结汇入笔记正文，禁止在此重复 selected.text 的详细内容
- tags：4-8 个搜索标签，不带 #，不要空格
- selected：每条入选新闻一项；index 是候选编号；headline 为图片标题，不超过 28 个字符；summary 用一句简短中文概括该新闻的核心事实，建议不超过 50 字，不换行、不罗列细节，用于笔记正文；text 为 100-260 个中文字符，准确、精炼、避免夸张；star_rating 是 1-5 的整数星级

每条 selected 对应一条内容，视频摘要可能完整分页成多张图片。候选带有 attachedImages 数量时，可在文字中结合图片提供的上下文，但不得猜测图片内容。
title、body、headline、text 和背景概述都必须尊重原文、直接给事实；禁止“本期聚焦”“本期AI聚焦”“本期重点”“本期关注”“本次整理”“以下为精选”“值得关注”“让我们看看”等编辑套话，不得声明由AI生成或辅助整理。英文忠实翻译，中文保留原意，背景只解释必要名词和已知事实，不评价新闻价值；不把原文没有的事实、结论或意义补写进去。
你必须先在内部逐条评估所有合规候选，再为入选项给出 star_rating：5 星代表价值、信息量或真实用户兴趣显著突出，必须作为整篇笔记的第一张封面；4 星代表明显优质；3 星代表合格；2 星代表价值偏低；1 星代表最差。评分必须由你独立判断真实小红书用户的点击与阅读兴趣，综合新颖性、知名主体、实际影响、具体数字、实用价值、话题性和图片吸引力，不得用固定关键词或来源替代评分。星级是绝对质量判断，不得仅因为某条是当前候选中的相对第一名就把它抬高到 5 星。
selected 按 star_rating 从高到低排列；系统只验证并执行你返回的星级，不会用图片、关键词或来源另行加权。
selected 只能包含达到正常发布价值的 3-5 星内容；自评为 1-2 星的候选必须排除，绝不能为了接近数量上限而入选。数量上限不是配额，质量不足时应少选。
同一篇笔记若选择 5 星，selected 必须只有这一条内容，单独成帖，不得搭配任何其他星级；有合规五星时优先安排，其他内容留待后续周期。
本次可选数量上限会随候选一起给出。符合标准的新闻超过一条时，应尽量选到该上限，不要习惯性只选一条。只要合规候选中存在一条与科技产业、产品、软件、硬件、人工智能、网络安全、科研或开发者生态直接相关且包含明确事实的内容，就必须至少选择一条；只有全部候选都与科技关联薄弱、缺少事实或属于明确低价值内容时才可以不选。

只输出 JSON，不要 markdown 或解释：
{{"title":"标题","body":"","tags":["标签"],"selected":[{{"index":1,"headline":"卡片标题","summary":"该新闻的一句话核心总结。","text":"卡片正文","star_rating":5}}]}}

若没有符合条件的新闻，输出：
{{"title":"","body":"","tags":[],"selected":[]}}"""

X_LANGUAGE_RULES = """由你根据原文主体语言判断是否需要翻译，每条入选 X 新闻必须额外输出 JSON 布尔字段 translation_required：
- 中文为主体时为 false；中文中出现产品名、英文术语或代码不等于外语帖，不要重复翻译中文
- 英语、日语、韩语、俄语、阿拉伯语等任意非中文为主体时为 true，必须完整生成“中文翻译：”一节，不能用背景概述代替翻译
- 日文包含汉字也不等于中文，不能按汉字或英文字母数量猜测语言；短外语原文同样需要翻译"""

ORIGINAL_TRANSLATION_RULES = (
    """这些候选来自公开作者账号。每条 selected.text 必须严格采用以下格式：
原文：
<逐字保留候选原文，不得改写、摘要或删减>

中文翻译：
<忠实、完整、自然的中文翻译>

背景概述：
<用通俗中文简要解释理解原文必需的新名词、项目或技术背景；直接写事实，不写“值得关注”等价值评价，不臆测原文没有的信息，不凑句数>

如果候选原文主要是中文，省略“中文翻译”一节，但仍必须逐字保留原文并生成“背景概述”。headline、整篇 title 和 tags 仍使用中文，body 留空。

X 内容质量附加规则：必须过滤广告、带货、引流、活动推销、无意义链接或表情、纯粹个人情绪和没有具体科技或科学事实的随手感想；不得因为作者知名就放宽标准。如果你生成的背景概述认为候选缺少事实、上下文、信息量或无法判断价值，该候选与 selected 逻辑冲突，必须从 selected 删除，不能把这段负面判断当作可发布的背景概述。"""
    + "\n\n"
    + X_LANGUAGE_RULES
)

FIVE_STAR_IMMEDIATE_RULES = """当前是“五星即时单发”模式，本规则覆盖普通质量模式中“至少选择一条”和“尽量选满”的要求：
- 逐条使用绝对 1-5 星标准判断；selected 第一条必须是真正 5 星，不得把相对第一但仅有 1-4 星的内容拔高为 5 星
- 5 星可以来自显著行业影响，也可以来自你预测普通用户会高度感兴趣、容易讨论或转发、具有明显爆发流量潜力且事实充分的内容
- 只选择最高价值的一条 5 星候选，必须单独成帖，不搭配其他新闻
- 没有真正 5 星候选时必须输出 selected 为空，普通内容继续积累，不标记、不丢弃
- 星级必须完全由你依据既定质量规则判断，程序不会用关键词、来源、图片或数值阈值做额外评分"""

SCHEDULED_BEST_RULES = """当前是“固定周期强制发布”模式，具体周期由运行时配置决定：
- 首先比较本批来自所有平台的全部合规候选，选出全局优先级最高的一条作为封面，不得先按平台分组再各选一条
- 封面确定后，本篇后续内容只能来自封面所属平台，Telegram、X、YouTube绝对不能混入同一篇笔记
- 在图片总容量允许的范围内尽可能选满；同平台仍有正常发布价值的候选时，不得习惯性只选一条
- 若存在真实 5 星，优先选最高价值的 5 星，整篇只选这一条；没有五星时才打包其他同平台内容
- 只要存在达到正常发布质量的候选就必须选择；不得为了本路线伪造 5 星
- 如果全部候选均未达到正常发布质量，可以输出 selected 为空
- 内容星级和事实价值是主要排序依据；平台曝光均衡权重只用于降低近期发布过多的平台优先级，不能把低质量内容抬成高质量"""

CATCH_UP_RULES = """当前是停机超过20分钟后的单平台补发，每个平台最多补发一篇：
- 本规则覆盖普通模式的五星单独成帖限制；允许多条五星同帖，五星在最前面，其次四星，再次合格三星，按你评定的真实价值降序排列
- 在最多18张图片的限制内尽可能装满最重要的内容，长文分页也计入图片数量；不要仅因有五星就只选一条
- 不混入其他平台；其余合规、内容质量和原文保留规则与正常发布完全相同"""


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


def _translation_rules(
    candidates: Sequence[object],
    record_ids: frozenset[str] | None,
) -> str:
    if record_ids is None:
        return ORIGINAL_TRANSLATION_RULES
    indexes = [
        str(index)
        for index, candidate in enumerate(candidates, start=1)
        if candidate_id(candidate) in record_ids
    ]
    if not indexes:
        return ""
    return (
        f"候选编号 {', '.join(indexes)} 来自需要保留原文的公开作者账号。仅当 selected 选择这些编号时，"
        "selected.text 必须严格使用以下三段标签与顺序：\n原文：\n<逐字保留原文>\n\n中文翻译：\n"
        "<忠实、完整、自然的中文翻译>\n\n背景概述：\n<2-4 句通俗中文背景>。"
        "所有非中文原文绝对不能省略“中文翻译：”标签；中文原文才可省略整个中文翻译段。"
        f"\n{X_LANGUAGE_RULES}\n"
        "背景概述只解释理解原文必需的陌生名词和已知背景，不写开场、价值评价或凑字套话。"
        "这些 X 候选还必须过滤广告、带货、引流、活动推销、无意义链接或表情、纯粹个人情绪，以及"
        "没有具体科技或科学事实的随手感想；不得因为作者知名就放宽标准。"
        "其他编号仍按普通中文科技新闻编辑，不要套用原文翻译格式。"
    )


class DeepSeekFilter:
    """Behavior-compatible two-stage editorial facade."""

    def __init__(
        self,
        *,
        provider: ChatCompletionProvider | None = None,
        first_review_model: str = DEFAULT_FIRST_REVIEW_MODEL,
        second_review_model: str = DEFAULT_SECOND_REVIEW_MODEL,
    ) -> None:
        if not isinstance(first_review_model, str) or not first_review_model.strip():
            raise TypeError("first_review_model must be non-empty")
        if not isinstance(second_review_model, str) or not second_review_model.strip():
            raise TypeError("second_review_model must be non-empty")
        if first_review_model == second_review_model:
            raise ValueError("review models must differ so each can be the other's fallback")
        self.provider = provider or DeepSeekProvider()
        self.first_review_model = first_review_model
        self.second_review_model = second_review_model

    async def check_configuration(self) -> bool:
        return await self.provider.check_configuration()

    @staticmethod
    def _review_messages(
        candidates: Sequence[object], *, text_limit: int | None = 1_200
    ) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": COMPLIANCE_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"本次共 {len(candidates)} 条候选，approved 只能使用行首编号 1 到 {len(candidates)}，"
                    "不得使用 id 字段或正文内部的序号；只有一条候选时，通过为 [1]，拒绝为 []。\n"
                    f"逐条执行合规审查。候选新闻：\n\n{_candidate_list(candidates, text_limit=text_limit)}"
                ),
            },
        ]

    @staticmethod
    def _model_unavailable(error: DeepSeekHttpError) -> bool:
        if error.status == 404:
            return True
        detail = str(error).casefold()
        return error.status in {400, 422} and any(
            marker in detail
            for marker in (
                "model not found",
                "model does not exist",
                "model unavailable",
                "invalid model",
                "模型不存在",
                "模型不可用",
            )
        )

    async def _complete_with_fallback(
        self,
        messages: Sequence[Mapping[str, str]],
        *,
        primary_model: str,
        fallback_model: str,
    ) -> str:
        try:
            return await self.provider.complete(messages, model=primary_model)
        except DeepSeekHttpError as error:
            if not self._model_unavailable(error) or fallback_model == primary_model:
                raise
            return await self.provider.complete(messages, model=fallback_model)

    async def compose(
        self,
        candidates: Sequence[object],
        *,
        max_items: int | None = None,
        fill_capacity: bool = False,
        preserve_original: bool = False,
        preserve_original_ids: frozenset[str] = frozenset(),
        five_star_only: bool = False,
        scheduled_best_only: bool = False,
        catch_up: bool = False,
        platform_publish_counts: Mapping[str, int] | None = None,
    ) -> Editorial:
        if not isinstance(candidates, Sequence) or isinstance(candidates, (str, bytes)):
            raise TypeError("candidates must be a sequence")
        if not candidates:
            return Editorial(title="", body="", tags=(), items=())
        if max_items is None:
            max_items = len(candidates)
        if not isinstance(max_items, int) or isinstance(max_items, bool) or max_items < 1:
            raise ValueError("max_items must be a positive integer")
        if not isinstance(fill_capacity, bool):
            raise TypeError("fill_capacity must be a boolean")
        if not isinstance(preserve_original, bool):
            raise TypeError("preserve_original must be a boolean")
        if not isinstance(preserve_original_ids, frozenset) or any(
            not isinstance(record_id, str) or not record_id for record_id in preserve_original_ids
        ):
            raise TypeError("preserve_original_ids must be a frozenset of non-empty strings")
        if not isinstance(five_star_only, bool):
            raise TypeError("five_star_only must be a boolean")
        if not isinstance(scheduled_best_only, bool):
            raise TypeError("scheduled_best_only must be a boolean")
        if five_star_only and scheduled_best_only:
            raise ValueError("five_star_only and scheduled_best_only are mutually exclusive")
        platform_publish_counts = dict(platform_publish_counts or {})
        platform_rules = _platform_balance_rules(platform_publish_counts)
        if platform_rules and not scheduled_best_only:
            raise ValueError("platform exposure balancing is only valid for scheduled publishing")
        for candidate in candidates:
            if not candidate_id(candidate).strip() or not _candidate_text(candidate).strip():
                raise TypeError("every candidate requires string id and text")

        compliant = await self.review(candidates)
        if not compliant:
            return Editorial(title="", body="", tags=(), items=())

        return await self._compose_compliant(
            compliant,
            max_items=max_items,
            fill_capacity=fill_capacity,
            preserve_original=preserve_original,
            preserve_original_ids=preserve_original_ids,
            five_star_only=five_star_only,
            scheduled_best_only=scheduled_best_only,
            catch_up=catch_up,
            platform_rules=platform_rules,
        )

    async def review(
        self, candidates: Sequence[object], *, text_limit: int | None = 1_200
    ) -> list[object]:
        """The same two independent text admission passes, reusable before video summarization."""
        first_messages = self._review_messages(candidates, text_limit=text_limit)
        first_content = await self._complete_with_fallback(
            first_messages,
            primary_model=self.first_review_model,
            fallback_model=self.second_review_model,
        )
        first_approved = parse_compliance_response(first_content, candidates)
        if not first_approved:
            return []

        second_messages = self._review_messages(first_approved, text_limit=text_limit)
        second_content = await self._complete_with_fallback(
            second_messages,
            primary_model=self.second_review_model,
            fallback_model=self.first_review_model,
        )
        return parse_compliance_response(second_content, first_approved)

    async def _compose_compliant(
        self,
        compliant,
        *,
        max_items,
        fill_capacity,
        preserve_original,
        preserve_original_ids,
        five_star_only,
        scheduled_best_only,
        catch_up,
        platform_rules,
    ) -> Editorial:

        preserved_ids = None if preserve_original else preserve_original_ids
        presentation = _translation_rules(compliant, preserved_ids)
        presentation_rules = f"\n\n{presentation}" if presentation else ""
        mode_rules = (
            CATCH_UP_RULES
            if catch_up
            else FIVE_STAR_IMMEDIATE_RULES
            if five_star_only
            else SCHEDULED_BEST_RULES
            if scheduled_best_only
            else ""
        )
        quality_system = "\n\n".join(
            rule for rule in (QUALITY_SYSTEM_PROMPT, mode_rules, platform_rules) if rule
        )
        if five_star_only:
            selection_request = "执行五星检查：只选择最高价值的一条真正 5 星，单独成帖。"
        elif scheduled_best_only:
            selection_request = (
                "执行固定周期发布：先比较所有平台候选选出全局最优封面，再仅从封面所属平台继续选择，"
                f"本次最多选择 {min(max_items, len(compliant))} 条并尽可能填满。"
            )
        else:
            selection_request = (
                f"本次最多选择 {min(max_items, len(compliant))} 条；"
                "在严格合规和保证质量的前提下尽量选满。"
            )
        quality_messages = [
            {"role": "system", "content": quality_system},
            {
                "role": "user",
                "content": (
                    f"{selection_request}\n\n候选新闻：\n\n"
                    f"{_candidate_list(compliant)}{presentation_rules}"
                ),
            },
        ]
        quality_content = await self._complete_with_fallback(
            quality_messages,
            primary_model=self.second_review_model,
            fallback_model=self.first_review_model,
        )
        editorial = parse_editorial_response(
            quality_content,
            compliant,
            max_items=max_items,
            text_limit=None if presentation else 320,
            catch_up=catch_up,
        )
        by_id = {candidate_id(candidate): candidate for candidate in compliant}

        def validate_bundle(value: Editorial) -> Editorial:
            if not value.items:
                return value
            if not catch_up and value.items[0].star_rating == 5 and len(value.items) > 1:
                cover = value.items[0]
                value = replace(value, items=value.items[:1], title=cover.headline[:20], body="")
            if scheduled_best_only:
                selected_plugin = str(
                    _value(by_id[value.items[0].record_id], "plugin_id", default="") or ""
                )
                if not selected_plugin:
                    raise DeepSeekResponseError("scheduled cover lacks a source platform")
                platform_items = tuple(
                    item
                    for item in value.items
                    if str(_value(by_id[item.record_id], "plugin_id", default="") or "")
                    == selected_plugin
                )
                if len(platform_items) != len(value.items):
                    cover = platform_items[0]
                    return replace(
                        value,
                        title=_unicode_slice(cover.headline, 20),
                        body="",
                        items=platform_items,
                    )
            return value

        editorial = validate_bundle(editorial)
        target_count = min(max_items, len(compliant))
        if scheduled_best_only and editorial.items:
            selected_plugin = str(
                _value(by_id[editorial.items[0].record_id], "plugin_id", default="") or ""
            )
            target_count = min(
                max_items,
                sum(
                    str(_value(candidate, "plugin_id", default="") or "") == selected_plugin
                    for candidate in compliant
                ),
            )
        if five_star_only and editorial.items and editorial.items[0].star_rating != 5:
            raise DeepSeekResponseError("immediate selection must start with star_rating 5")
        if not catch_up and editorial.items and editorial.items[0].star_rating == 5:
            target_count = 1

        def apply_presentation(value: Editorial) -> Editorial:
            value = (
                _preserve_original_text(value, compliant, preserved_ids) if presentation else value
            )
            return replace(
                value,
                items=tuple(
                    replace(item, text=_candidate_text(by_id[item.record_id]))
                    if _value(by_id[item.record_id], "plugin_id") == "youtube"
                    else item
                    for item in value.items
                ),
            )

        if five_star_only and not editorial.items:
            return apply_presentation(validate_bundle(editorial))
        if editorial.items and (not fill_capacity or len(editorial.items) >= target_count):
            return apply_presentation(editorial)
        if editorial.items:
            retry_messages = [
                {"role": "system", "content": quality_system},
                {
                    "role": "user",
                    "content": (
                        f"启动积压合并模式：上一轮只选择了 {len(editorial.items)} 条，本次容量为 {target_count} 条。"
                        "目标是在维持相同合规与质量标准的前提下，用最少帖子清理积压。逐条排除广告、无用杂乱信息、"
                        "低价值或非科技内容；其余符合规则的正常科技新闻必须全部放入 selected，不要留给后续帖子，"
                        f"并尽量达到 {target_count} 条。\n\n候选新闻：\n\n{_candidate_list(compliant)}{presentation_rules}"
                    ),
                },
            ]
            retry_content = await self._complete_with_fallback(
                retry_messages,
                primary_model=self.second_review_model,
                fallback_model=self.first_review_model,
            )
            retry_editorial = parse_editorial_response(
                retry_content,
                compliant,
                max_items=max_items,
                text_limit=None if presentation else 320,
                catch_up=catch_up,
            )
            retry_editorial = validate_bundle(retry_editorial)
            if (
                five_star_only
                and retry_editorial.items
                and retry_editorial.items[0].star_rating != 5
            ):
                raise DeepSeekResponseError("immediate selection must start with star_rating 5")
            selected_editorial = (
                retry_editorial if len(retry_editorial.items) > len(editorial.items) else editorial
            )
            return apply_presentation(validate_bundle(selected_editorial))
        retry_messages = [
            {"role": "system", "content": quality_system},
            {
                "role": "user",
                "content": (
                    "上一轮对这些已通过合规的候选全部空选，可能过度保守。请重新逐条判断科技相关性和事实价值，"
                    "不得依靠固定关键词，也不得因为候选混有低价值内容就忽略其中正常的科技新闻。"
                    "只要存在一条符合系统质量规则的科技内容，就必须至少选择一条；"
                    f"本次最多选择 {min(max_items, len(compliant))} 条。\n\n候选新闻：\n\n"
                    f"{_candidate_list(compliant)}{presentation_rules}"
                ),
            },
        ]
        retry_content = await self._complete_with_fallback(
            retry_messages,
            primary_model=self.second_review_model,
            fallback_model=self.first_review_model,
        )
        retry_editorial = parse_editorial_response(
            retry_content,
            compliant,
            max_items=max_items,
            text_limit=None if presentation else 320,
            catch_up=catch_up,
        )
        return apply_presentation(validate_bundle(retry_editorial))


class TechnologyNewsProcessor:
    """Retry schema-invalid editorial runs before any rendering or publication."""

    def __init__(
        self,
        editorial_filter: DeepSeekFilter,
        *,
        attempts: int = 3,
        retry_base_delay_seconds: float = 2.0,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if not isinstance(attempts, int) or isinstance(attempts, bool) or attempts < 1:
            raise ValueError("attempts must be >= 1")
        if retry_base_delay_seconds <= 0:
            raise ValueError("retry_base_delay_seconds must be positive")
        self.editorial_filter = editorial_filter
        self.attempts = attempts
        self.retry_base_delay_seconds = float(retry_base_delay_seconds)
        self.sleep = sleep

    async def compose(
        self,
        candidates: Sequence[object],
        *,
        max_items: int,
        fill_capacity: bool = False,
        preserve_original: bool = False,
        preserve_original_ids: frozenset[str] = frozenset(),
        five_star_only: bool = False,
        scheduled_best_only: bool = False,
        catch_up: bool = False,
        platform_publish_counts: Mapping[str, int] | None = None,
    ) -> Editorial:
        last_error: BaseException | None = None
        for attempt in range(1, self.attempts + 1):
            try:
                if (
                    fill_capacity
                    or preserve_original
                    or preserve_original_ids
                    or five_star_only
                    or scheduled_best_only
                    or catch_up
                    or platform_publish_counts
                ):
                    return await self.editorial_filter.compose(
                        candidates,
                        max_items=max_items,
                        fill_capacity=fill_capacity,
                        preserve_original=preserve_original,
                        preserve_original_ids=preserve_original_ids,
                        five_star_only=five_star_only,
                        scheduled_best_only=scheduled_best_only,
                        **({"catch_up": True} if catch_up else {}),
                        platform_publish_counts=platform_publish_counts,
                    )
                return await self.editorial_filter.compose(candidates, max_items=max_items)
            except BaseException as error:
                if isinstance(error, (KeyboardInterrupt, SystemExit, asyncio.CancelledError)):
                    raise
                if (
                    isinstance(error, PipelineError)
                    and error.error_class is ErrorClass.TRANSIENT_NETWORK
                ):
                    raise
                last_error = error
                deterministic = isinstance(error, (TypeError, ValueError)) or (
                    isinstance(error, DeepSeekHttpError) and not error.retryable
                )
                if deterministic or attempt >= self.attempts:
                    raise
                await self.sleep(self.retry_base_delay_seconds * attempt)
        assert last_error is not None
        raise last_error
