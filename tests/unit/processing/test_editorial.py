from __future__ import annotations

import asyncio
import json

import pytest

from xhs_local.processing import (
    COMPLIANCE_RULES,
    COMPLIANCE_SYSTEM_PROMPT,
    QUALITY_SYSTEM_PROMPT,
    DeepSeekFilter,
    DeepSeekHttpError,
    DeepSeekResponseError,
    TechnologyNewsProcessor,
    parse_compliance_response,
    parse_editorial_response,
    platform_balance_weights,
)
from xhs_local.processing.technology_news import ORIGINAL_TRANSLATION_RULES


def candidate(record_id: str, *, with_image: bool = False) -> dict[str, object]:
    return {
        "record_id": record_id,
        "source_name": "科技频道",
        "text": f"{record_id} sufficiently detailed technology source text",
        "attachments": ({"mime_type": "image/png"},) if with_image else (),
    }


def test_compliance_rules_explicitly_reject_military_and_nuclear_weapons() -> None:
    for term in ("军事", "战争", "武器装备", "导弹", "核武器", "核试验"):
        assert term in COMPLIANCE_RULES


def test_compliance_rules_explicitly_reject_cryptocurrency_and_stablecoins() -> None:
    for term in ("加密货币", "虚拟货币", "数字货币", "稳定币", "代币", "炒币", "挖矿", "ICO"):
        assert term in COMPLIANCE_RULES


def test_compliance_rules_unconditionally_reject_china_linked_cyberattacks() -> None:
    for phrase in (
        "中国技术助长攻击",
        "中国实施、支持或纵容网络攻击",
        "DeepSeek",
        "安全防护宽松",
        "攻击数量增长",
        "整条拒绝",
    ):
        assert phrase in COMPLIANCE_RULES


def test_compliance_parser_deduplicates_and_rejects_invalid_indexes() -> None:
    candidates = [candidate("one"), candidate("two")]
    assert parse_compliance_response('{"approved":[1,"2",1]}', candidates) == candidates
    # JavaScript Number(true) is 1; retain that legacy correlation behavior.
    assert parse_compliance_response('{"approved":[true]}', candidates) == [candidates[0]]
    with pytest.raises(DeepSeekResponseError, match="invalid index"):
        parse_compliance_response('{"approved":[3]}', candidates)
    with pytest.raises(DeepSeekResponseError, match=r"approved\[\]"):
        parse_compliance_response('{"selected":[]}', candidates)


def test_editorial_parser_uses_only_llm_star_ratings_for_ranking_and_truncates() -> None:
    candidates = [
        candidate("plain"),
        candidate("image-low", with_image=True),
        candidate("image-high", with_image=True),
    ]
    result = parse_editorial_response(
        json.dumps(
            {
                "title": "五分钟科技" * 5,
                "body": "本时段值得关注的科技研发与产品动态摘要，内容客观且精炼。" * 10,
                "tags": ["#科技", "研 发", "科技", "#产品", "开发者"],
                "selected": [
                    {
                        "index": 1,
                        "headline": "普通更新",
                        "text": "普通正文",
                        "star_rating": 5,
                    },
                    {
                        "index": 2,
                        "headline": "工具更新",
                        "text": "工具正文",
                        "star_rating": 3,
                    },
                    {
                        "index": 3,
                        "headline": "芯片进展",
                        "text": "芯片正文",
                        "star_rating": 4,
                    },
                ],
            },
            ensure_ascii=False,
        ),
        candidates,
        max_items=2,
    )
    assert len(result.title) == 20
    assert result.body == ""
    assert result.tags == ("科技", "研发", "产品", "开发者")
    assert [item.record_id for item in result.items] == ["plain", "image-high"]
    assert [item.star_rating for item in result.items] == [5, 4]


@pytest.mark.parametrize("model_body", [None, "", "重复图片中的新闻正文。" * 200])
def test_model_batch_body_is_ignored_while_card_text_and_summary_headline_are_preserved(model_body):
    card_text = "图片里的具体技术事实、说明与数字完整保留。"
    payload = {
        "title": "模型性能更新",
        "tags": ["人工智能", "模型"],
        "selected": [{"index": 1, "headline": "模型性能更新", "text": card_text, "star_rating": 4}],
    }
    if model_body is not None:
        payload["body"] = model_body
    result = parse_editorial_response(json.dumps(payload), [candidate("one")])
    assert result.body == ""
    assert result.items[0].text == card_text
    assert result.title == "模型性能更新"
    assert result.tags == ("人工智能", "模型")
    assert "body：固定输出空字符串" in QUALITY_SYSTEM_PROMPT


@pytest.mark.parametrize("headline", ["第一行\n第二行", "第一条事实。第二条事实。"])
def test_invalid_summary_sentences_require_regeneration_instead_of_truncation(headline):
    payload = {
        "title": "技术进展",
        "tags": ["科技"],
        "selected": [
            {"index": 1, "headline": headline, "text": "完整的图片正文。", "star_rating": 4}
        ],
    }
    with pytest.raises(DeepSeekResponseError, match="summary"):
        parse_editorial_response(json.dumps(payload), [candidate("one")])


def test_summary_is_separate_from_image_title_and_is_not_truncated():
    summary = "这个核心总结比图片标题更长，但依然是一句完整的技术事实，不应在正文被截断。"
    payload = {
        "title": "技术进展",
        "tags": ["科技"],
        "selected": [
            {
                "index": 1,
                "headline": "短图片标题",
                "summary": summary,
                "text": "完整的图片正文。",
                "star_rating": 4,
            }
        ],
    }
    result = parse_editorial_response(json.dumps(payload), [candidate("one")])
    assert result.items[0].headline == "短图片标题"
    assert result.items[0].summary == summary
    payload["selected"][0].pop("summary")
    payload["selected"][0]["headline"] = summary
    result = parse_editorial_response(json.dumps(payload), [candidate("one")])
    assert len(result.items[0].headline) == 28  # Existing image-title policy.
    assert result.items[0].summary == summary  # Never truncate the caption.


def test_one_note_rejects_more_than_one_five_star_item() -> None:
    payload = {
        "title": "两项人工智能进展",
        "body": "两项人工智能研究均公布了具体结果与公开数据。",
        "tags": ["人工智能", "研究", "科技", "模型"],
        "selected": [
            {"index": 1, "headline": "第一项进展", "text": "第一项具体进展。", "star_rating": 5},
            {"index": 2, "headline": "第二项进展", "text": "第二项具体进展。", "star_rating": 5},
        ],
    }

    with pytest.raises(DeepSeekResponseError, match="at most one"):
        parse_editorial_response(
            json.dumps(payload, ensure_ascii=False),
            [candidate("one"), candidate("two")],
        )


def test_platform_balance_mildly_downweights_recently_overexposed_source() -> None:
    weights = platform_balance_weights({"telegram": 20, "x": 2})

    assert 0.65 <= weights["telegram"] < 1
    assert 1 < weights["x"] <= 1.35


def test_empty_selection_does_not_require_note_envelope() -> None:
    result = parse_editorial_response(
        'prefix ```json\n{"title":"","selected":[]}\n``` suffix',
        [candidate("one")],
    )
    assert result.title == ""
    assert result.body == ""
    assert result.tags == ()
    assert result.items == ()


def test_editorial_parser_requires_llm_to_supply_valid_star_rating() -> None:
    payload = {
        "title": "开发工具发布新版本",
        "body": "开发工具公布了明确功能变化和正式上线时间。",
        "tags": ["开发者", "工具", "科技", "软件"],
        "selected": [
            {
                "index": 1,
                "headline": "开发工具更新",
                "text": "开发工具公布了明确功能变化和正式上线时间。",
            }
        ],
    }
    with pytest.raises(DeepSeekResponseError, match="star_rating"):
        parse_editorial_response(
            json.dumps(payload, ensure_ascii=False),
            [candidate("one")],
            max_items=1,
        )


@pytest.mark.parametrize("rating", [0, 6, 4.5, True])
def test_editorial_parser_rejects_invalid_star_rating(rating: object) -> None:
    payload = {
        "title": "开发工具发布新版本",
        "body": "开发工具公布了明确功能变化和正式上线时间。",
        "tags": ["开发者", "工具", "科技", "软件"],
        "selected": [
            {
                "index": 1,
                "headline": "开发工具更新",
                "text": "开发工具公布了明确功能变化和正式上线时间。",
                "star_rating": rating,
            }
        ],
    }
    with pytest.raises(DeepSeekResponseError, match="star_rating"):
        parse_editorial_response(
            json.dumps(payload, ensure_ascii=False),
            [candidate("one")],
            max_items=1,
        )


def test_editorial_parser_excludes_llm_rated_low_value_items() -> None:
    payload = {
        "title": "推理框架发布优化",
        "body": "推理框架公布了明确的性能优化方案和适用场景。",
        "tags": ["人工智能", "推理", "开发者", "软件"],
        "selected": [
            {
                "index": 1,
                "headline": "推理性能优化",
                "text": "项目公布了具体优化路径、适用场景与性能变化。",
                "star_rating": 4,
            },
            {
                "index": 2,
                "headline": "仅有跳转链接",
                "text": "候选没有事实或上下文，无法判断价值。",
                "star_rating": 1,
            },
        ],
    }

    result = parse_editorial_response(
        json.dumps(payload, ensure_ascii=False),
        [candidate("valuable"), candidate("link-only")],
        max_items=2,
    )

    assert [item.record_id for item in result.items] == ["valuable"]


def test_quality_prompt_forbids_link_only_and_self_declared_low_value_items() -> None:
    assert "原文只有链接" in QUALITY_SYSTEM_PROMPT
    assert "selected 只能包含达到正常发布价值的 3-5 星内容" in QUALITY_SYSTEM_PROMPT
    assert "无法判断价值" in ORIGINAL_TRANSLATION_RULES


@pytest.mark.parametrize("title", ["今日科技快讯", "AI精选内容"])
def test_editorial_parser_rejects_generic_or_forbidden_note_titles(title: str) -> None:
    with pytest.raises(DeepSeekResponseError, match="forbidden phrase"):
        parse_editorial_response(
            json.dumps(
                {
                    "title": title,
                    "body": "一条包含明确主体和具体变化的科技新闻导语。",
                    "tags": ["科技", "产品"],
                    "selected": [
                        {
                            "index": 1,
                            "headline": "产品发布具体功能",
                            "text": "产品团队公布了具体功能变化与上线时间。",
                            "star_rating": 4,
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            [candidate("one")],
            max_items=1,
        )


class RecordingProvider:
    def __init__(self, responses: list[str | BaseException]) -> None:
        self.responses = responses
        self.calls: list[tuple[list[dict[str, str]], str]] = []

    async def check_configuration(self) -> bool:
        return True

    async def complete(self, messages: list[dict[str, str]], *, model: str) -> str:
        self.calls.append((messages, model))
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


def test_catchup_keeps_multiple_five_stars_then_four_stars_using_shared_reviews():
    source = [candidate(str(index)) for index in range(3)]
    payload = json.dumps(
        {
            "title": "模型与开发工具更新",
            "body": "模型和开发工具发布明确的新能力。",
            "tags": ["模型", "科技"],
            "selected": [
                {
                    "index": index + 1,
                    "headline": "技术更新",
                    "text": "具体的技术进展与测试结果。",
                    "star_rating": score,
                }
                for index, score in enumerate([4, 5, 5])
            ],
        }
    )
    provider = RecordingProvider(['{"approved":[1,2,3]}', '{"approved":[1,2,3]}', payload])
    result = asyncio.run(
        TechnologyNewsProcessor(DeepSeekFilter(provider=provider)).compose(
            source,
            max_items=18,
            fill_capacity=True,
            catch_up=True,
        )
    )
    assert [item.star_rating for item in result.items] == [5, 5, 4]
    assert [item.record_id for item in result.items] == ["1", "2", "0"]
    assert provider.calls[0][0][0]["content"] == COMPLIANCE_SYSTEM_PROMPT
    assert provider.calls[1][0][0]["content"] == COMPLIANCE_SYSTEM_PROMPT
    assert "每个平台最多补发一篇" in provider.calls[2][0][0]["content"]
    with pytest.raises(DeepSeekResponseError, match="at most one"):
        parse_editorial_response(payload, source)


def test_two_stage_filter_preserves_prompts_models_capacity_and_order() -> None:
    provider = RecordingProvider(
        [
            '{"approved":[1,2]}',
            '{"approved":[1,2]}',
            json.dumps(
                {
                    "title": "开发工具迎来更新",
                    "body": "本时段值得关注的科技研发与产品动态摘要，信息客观且精炼。",
                    "tags": ["科技", "研发", "产品", "开发者"],
                    "selected": [
                        {
                            "index": 2,
                            "headline": "产品进展",
                            "text": "经过编辑的科技新闻正文。",
                            "star_rating": 5,
                        }
                    ],
                },
                ensure_ascii=False,
            ),
        ]
    )
    editorial_filter = DeepSeekFilter(
        provider=provider,  # type: ignore[arg-type]
        first_review_model="deepseek-v4-pro",
        second_review_model="deepseek-v4-flash",
    )
    result = asyncio.run(
        editorial_filter.compose([candidate("one"), candidate("two", with_image=True)], max_items=2)
    )
    assert [item.record_id for item in result.items] == ["two"]
    assert [model for _messages, model in provider.calls] == [
        "deepseek-v4-pro",
        "deepseek-v4-flash",
        "deepseek-v4-flash",
    ]
    assert provider.calls[0][0][0]["content"] == COMPLIANCE_SYSTEM_PROMPT
    assert provider.calls[1][0] == provider.calls[0][0]
    assert provider.calls[2][0][0]["content"] == QUALITY_SYSTEM_PROMPT
    assert "本次最多选择 2 条" in provider.calls[2][0][-1]["content"]
    assert "attachedImages: 1" in provider.calls[2][0][-1]["content"]


def test_unavailable_review_model_falls_back_to_other_configured_model() -> None:
    editorial = json.dumps(
        {
            "title": "开发工具更新",
            "body": "开发工具公布了具体功能变化和正式上线时间。",
            "tags": ["开发者", "软件", "工具", "科技"],
            "selected": [
                {
                    "index": 1,
                    "headline": "开发工具更新",
                    "text": "开发工具公布了具体功能变化和正式上线时间。",
                    "star_rating": 4,
                }
            ],
        },
        ensure_ascii=False,
    )
    provider = RecordingProvider(
        [
            DeepSeekHttpError(
                "DeepSeek HTTP 404: model not found",
                status=404,
                retryable=False,
            ),
            '{"approved":[1]}',
            '{"approved":[1]}',
            editorial,
        ]
    )
    result = asyncio.run(
        DeepSeekFilter(
            provider=provider,  # type: ignore[arg-type]
            first_review_model="deepseek-v4-pro",
            second_review_model="deepseek-v4-flash",
        ).compose([candidate("one")], max_items=1)
    )

    assert [item.record_id for item in result.items] == ["one"]
    assert [model for _messages, model in provider.calls] == [
        "deepseek-v4-pro",
        "deepseek-v4-flash",
        "deepseek-v4-flash",
        "deepseek-v4-flash",
    ]


def test_second_review_model_unavailable_falls_back_to_first_model() -> None:
    editorial = json.dumps(
        {
            "title": "芯片工具更新",
            "body": "芯片开发工具公布了明确的功能更新和上线时间。",
            "tags": ["芯片", "开发者", "工具", "科技"],
            "selected": [
                {
                    "index": 1,
                    "headline": "芯片工具更新",
                    "text": "芯片开发工具公布了明确的功能更新和上线时间。",
                    "star_rating": 4,
                }
            ],
        },
        ensure_ascii=False,
    )
    provider = RecordingProvider(
        [
            '{"approved":[1]}',
            DeepSeekHttpError(
                "DeepSeek HTTP 404: model unavailable",
                status=404,
                retryable=False,
            ),
            '{"approved":[1]}',
            editorial,
        ]
    )

    result = asyncio.run(
        DeepSeekFilter(
            provider=provider,  # type: ignore[arg-type]
            first_review_model="deepseek-v4-pro",
            second_review_model="deepseek-v4-flash",
        ).compose([candidate("one")], max_items=1)
    )

    assert [item.record_id for item in result.items] == ["one"]
    assert [model for _messages, model in provider.calls] == [
        "deepseek-v4-pro",
        "deepseek-v4-flash",
        "deepseek-v4-pro",
        "deepseek-v4-flash",
    ]


def test_transient_provider_failure_does_not_switch_models() -> None:
    provider = RecordingProvider(
        [
            DeepSeekHttpError(
                "DeepSeek HTTP 503: service unavailable",
                status=503,
                retryable=True,
            )
        ]
    )

    with pytest.raises(DeepSeekHttpError, match="503"):
        asyncio.run(
            DeepSeekFilter(
                provider=provider,  # type: ignore[arg-type]
                first_review_model="deepseek-v4-pro",
                second_review_model="deepseek-v4-flash",
            ).compose([candidate("one")], max_items=1)
        )

    assert [model for _messages, model in provider.calls] == ["deepseek-v4-pro"]


def test_compliance_empty_never_calls_quality() -> None:
    provider = RecordingProvider(['{"approved":[]}'])
    result = asyncio.run(
        DeepSeekFilter(provider=provider).compose([candidate("one")])  # type: ignore[arg-type]
    )
    assert result.items == ()
    assert len(provider.calls) == 1


def test_quality_stage_retries_empty_selection_with_llm_instead_of_keyword_filtering() -> None:
    provider = RecordingProvider(
        [
            '{"approved":[1,2]}',
            '{"approved":[1,2]}',
            '{"title":"","body":"","tags":[],"selected":[]}',
            json.dumps(
                {
                    "title": "系统更新",
                    "body": "一项面向桌面软件用户的权限管理更新已经正式公布。",
                    "tags": ["科技", "软件", "Windows", "隐私"],
                    "selected": [
                        {
                            "index": 2,
                            "headline": "Windows权限更新",
                            "text": "Windows 为桌面软件增加了更细粒度的隐私权限控制。",
                            "star_rating": 4,
                        }
                    ],
                },
                ensure_ascii=False,
            ),
        ]
    )
    gossip = {
        "record_id": "gossip",
        "source_name": "娱乐频道",
        "text": "一部动画电影的观众评分发生变化，讨论主要集中于剧情表现。",
        "attachments": (),
    }
    technology = {
        "record_id": "windows",
        "source_name": "科技频道",
        "text": "Windows 为 Win32 软件提供单独的麦克风、摄像头和位置权限管理。",
        "attachments": (),
    }

    result = asyncio.run(
        DeepSeekFilter(provider=provider).compose(  # type: ignore[arg-type]
            [gossip, technology], max_items=1
        )
    )

    assert [item.record_id for item in result.items] == ["windows"]
    assert provider.calls[0][0] == provider.calls[1][0]
    quality_input = provider.calls[2][0][-1]["content"]
    assert "Windows 为 Win32" in quality_input
    assert "动画电影" in quality_input
    retry_input = provider.calls[3][0][-1]["content"]
    assert "不得依靠固定关键词" in retry_input
    assert "Windows 为 Win32" in retry_input
    assert "动画电影" in retry_input


def test_original_translation_presentation_preserves_x_text_and_adds_chinese() -> None:
    original = (
        "We released a new open-source inference engine today with lower memory use "
        "and faster decoding on consumer GPUs."
    )
    provider = RecordingProvider(
        [
            '{"approved":[1]}',
            '{"approved":[1]}',
            json.dumps(
                {
                    "title": "推理引擎降低显存占用",
                    "body": "一款开源推理引擎公布了面向消费级显卡的性能与显存改进。",
                    "tags": ["人工智能", "开源", "推理", "显卡"],
                    "selected": [
                        {
                            "index": 1,
                            "headline": "开源推理引擎提速",
                            "translation_required": True,
                            "text": (
                                "中文翻译：团队今天发布了新的开源推理引擎，可降低显存占用，"
                                "并在消费级显卡上加快解码。\n\n"
                                "背景概述：推理引擎负责让训练好的人工智能模型生成结果。"
                                "显存占用降低后，普通消费级显卡也更容易运行这类模型。"
                            ),
                            "star_rating": 5,
                        }
                    ],
                },
                ensure_ascii=False,
            ),
        ]
    )
    x_candidate = {
        "record_id": "x-one",
        "source_name": "Andrej Karpathy @karpathy",
        "text": original,
        "attachments": ({"mime_type": "image/webp"},),
    }

    result = asyncio.run(
        DeepSeekFilter(provider=provider).compose(  # type: ignore[arg-type]
            [x_candidate],
            max_items=1,
            preserve_original=True,
        )
    )

    assert result.items[0].text == (
        f"原文：\n{original}\n\n中文翻译：\n"
        "团队今天发布了新的开源推理引擎，可降低显存占用，并在消费级显卡上加快解码。"
        "\n\n背景概述：\n推理引擎负责让训练好的人工智能模型生成结果。"
        "显存占用降低后，普通消费级显卡也更容易运行这类模型。"
    )
    quality_prompt = provider.calls[2][0][-1]["content"]
    assert "逐字保留候选原文" in quality_prompt
    assert "中文翻译" in quality_prompt
    assert "背景概述" in quality_prompt


def test_scheduled_route_ranks_both_platforms_and_preserves_only_selected_x() -> None:
    original = "We released a concrete open-source developer tool with faster local inference."
    provider = RecordingProvider(
        [
            '{"approved":[1,2]}',
            '{"approved":[1,2]}',
            json.dumps(
                {
                    "title": "本地推理工具发布",
                    "body": "一款新的开源开发工具公布了本地推理性能改进。",
                    "tags": ["人工智能", "开源", "开发者", "推理"],
                    "selected": [
                        {
                            "index": 2,
                            "headline": "开源工具加速本地推理",
                            "translation_required": True,
                            "text": (
                                "中文翻译：团队发布了新的开源工具，可加速本地推理。\n\n"
                                "背景概述：本地推理是在用户自己的设备上运行人工智能模型，"
                                "通常有助于保护数据并减少网络等待。"
                            ),
                            "star_rating": 4,
                        }
                    ],
                },
                ensure_ascii=False,
            ),
        ]
    )
    telegram = {
        **candidate("telegram-one"),
        "plugin_id": "telegram",
        "text": "一项包含明确功能变化的正常科技产品更新。",
    }
    x_post = {
        **candidate("x-one"),
        "plugin_id": "x",
        "source_name": "X Author @author",
        "text": original,
    }

    result = asyncio.run(
        DeepSeekFilter(provider=provider).compose(  # type: ignore[arg-type]
            [telegram, x_post],
            max_items=1,
            preserve_original_ids=frozenset({"x-one"}),
            scheduled_best_only=True,
            platform_publish_counts={"telegram": 12, "x": 3},
        )
    )

    assert [item.record_id for item in result.items] == ["x-one"]
    assert result.items[0].star_rating == 4
    assert result.items[0].text == (
        f"原文：\n{original}\n\n中文翻译：\n团队发布了新的开源工具，可加速本地推理。"
        "\n\n背景概述：\n本地推理是在用户自己的设备上运行人工智能模型，"
        "通常有助于保护数据并减少网络等待。"
    )
    quality_prompt = provider.calls[2][0][-1]["content"]
    assert "固定周期强制发布" in provider.calls[2][0][0]["content"]
    assert "平台：telegram" in quality_prompt
    assert "平台：x" in quality_prompt
    assert "候选编号 2" in quality_prompt
    assert "必须严格使用以下三段标签与顺序" in quality_prompt
    assert "所有非中文原文绝对不能省略“中文翻译：”标签" in quality_prompt
    assert "背景概述" in quality_prompt
    assert "过滤广告、带货、引流" in quality_prompt
    assert "其他编号仍按普通中文科技新闻编辑" in quality_prompt
    system_prompt = provider.calls[2][0][0]["content"]
    assert "telegram: 最近24小时已发布 12 条" in system_prompt
    assert "x: 最近24小时已发布 3 条" in system_prompt


def test_scheduled_note_keeps_only_the_cover_platform_when_model_mixes_sources() -> None:
    provider = RecordingProvider(
        [
            '{"approved":[1,2]}',
            '{"approved":[1,2]}',
            json.dumps(
                {
                    "title": "两项科技产品更新",
                    "body": "两项产品均公布了具体功能变化和正式上线信息。",
                    "tags": ["科技", "产品", "软件", "开发者"],
                    "selected": [
                        {
                            "index": 1,
                            "headline": "第一项产品更新",
                            "text": "第一项产品公布了具体功能变化。",
                            "star_rating": 5,
                        },
                        {
                            "index": 2,
                            "headline": "第二项产品更新",
                            "text": "第二项产品公布了具体功能变化。",
                            "star_rating": 4,
                        },
                    ],
                },
                ensure_ascii=False,
            ),
        ]
    )
    telegram = {**candidate("telegram-one"), "plugin_id": "telegram"}
    x_post = {**candidate("x-one"), "plugin_id": "x"}

    result = asyncio.run(
        DeepSeekFilter(provider=provider).compose(  # type: ignore[arg-type]
            [telegram, x_post],
            max_items=2,
            scheduled_best_only=True,
        )
    )

    assert [item.record_id for item in result.items] == ["telegram-one"]
    assert result.title == "第一项产品更新"
    assert result.body == ""


def test_chinese_x_post_preserves_original_and_still_adds_background_overview() -> None:
    original = "团队发布了支持本地推理的新开源运行时，并公布了完整基准测试。"
    provider = RecordingProvider(
        [
            '{"approved":[1]}',
            '{"approved":[1]}',
            json.dumps(
                {
                    "title": "开源本地推理运行时发布",
                    "body": "一款面向本地设备的开源推理运行时公布了性能数据。",
                    "tags": ["人工智能", "开源", "推理", "开发者"],
                    "selected": [
                        {
                            "index": 1,
                            "headline": "本地推理运行时发布",
                            "translation_required": False,
                            "text": (
                                "原文：团队发布了支持本地推理的新开源运行时。\n\n"
                                "背景概述：本地推理指模型直接在用户设备上运行，"
                                "可减少云端依赖，并让开发者更容易控制数据。"
                            ),
                            "star_rating": 5,
                        }
                    ],
                },
                ensure_ascii=False,
            ),
        ]
    )

    result = asyncio.run(
        DeepSeekFilter(provider=provider).compose(  # type: ignore[arg-type]
            [{**candidate("x-cn"), "text": original}],
            max_items=1,
            preserve_original=True,
        )
    )

    assert result.items[0].text == (
        f"原文：\n{original}\n\n背景概述：\n本地推理指模型直接在用户设备上运行，"
        "可减少云端依赖，并让开发者更容易控制数据。"
    )


@pytest.mark.parametrize(
    "original",
    [
        "新しい推論エンジンを公開しました。メモリ使用量を減らせます。",
        "深層学習研究会公開資料",  # Japanese with kanji alone: no letter-count heuristic.
        "새로운 추론 엔진을 공개했습니다.",
        "Опубликован новый движок машинного обучения.",
        "أصدر الفريق محرك استدلال جديدًا.",
        "Nueva herramienta de aprendizaje automático disponible.",
        "New API!",  # Short English failed the previous 12-letter threshold.
    ],
)
@pytest.mark.parametrize("mode", ["normal", "scheduled", "catchup"])
def test_all_non_chinese_x_languages_keep_the_llm_translation(original, mode):
    translation = "团队发布了新的推理工具。"
    provider = RecordingProvider(
        [
            '{"approved":[1]}',
            '{"approved":[1]}',
            json.dumps(
                {
                    "title": "推理工具更新",
                    "tags": ["人工智能"],
                    "selected": [
                        {
                            "index": 1,
                            "headline": "推理工具更新",
                            "star_rating": 4,
                            "translation_required": True,
                            "text": (
                                f"原文：\n{original}\n\n中文翻译：\n{translation}\n\n"
                                "背景概述：\n推理是使用训练好的模型生成结果。"
                            ),
                        }
                    ],
                }
            ),
        ]
    )
    options = {"preserve_original": True}
    if mode == "scheduled":
        options = {"scheduled_best_only": True, "preserve_original_ids": frozenset({"foreign"})}
    elif mode == "catchup":
        options["catch_up"] = True
    result = asyncio.run(
        DeepSeekFilter(provider=provider).compose(
            [{**candidate("foreign"), "plugin_id": "x", "text": original}],
            max_items=1,
            **options,
        )
    )
    assert result.items[0].text == (
        f"原文：\n{original}\n\n中文翻译：\n{translation}\n\n背景概述：\n推理是使用训练好的模型生成结果。"
    )
    assert result.items[0].translation_required is True
    assert "translation_required" in provider.calls[2][0][-1]["content"]


@pytest.mark.parametrize(
    "decision,error",
    [(True, "Chinese translation"), (None, "language decision"), ("false", "language decision")],
)
def test_x_missing_translation_or_language_decision_cannot_pass(decision, error):
    provider = RecordingProvider(
        [
            '{"approved":[1]}',
            '{"approved":[1]}',
            json.dumps(
                {
                    "title": "推理工具更新",
                    "tags": ["人工智能"],
                    "selected": [
                        {
                            "index": 1,
                            "headline": "推理工具更新",
                            "star_rating": 4,
                            "translation_required": decision,
                            "text": "背景概述：推理是让模型生成结果。",
                        }
                    ],
                }
            ),
        ]
    )
    with pytest.raises(DeepSeekResponseError, match=error):
        asyncio.run(
            DeepSeekFilter(provider=provider).compose(
                [{**candidate("jp"), "text": "新しい推論エンジンを公開しました。"}],
                max_items=1,
                preserve_original=True,
            )
        )


def test_x_presentation_rejects_missing_background_overview() -> None:
    provider = RecordingProvider(
        [
            '{"approved":[1]}',
            '{"approved":[1]}',
            json.dumps(
                {
                    "title": "开源工具发布",
                    "body": "一款开源工具公布了明确的功能与性能变化。",
                    "tags": ["开源", "工具", "开发者", "科技"],
                    "selected": [
                        {
                            "index": 1,
                            "headline": "开源工具发布",
                            "text": "中文翻译：团队发布了一款新的开源工具。",
                            "star_rating": 5,
                        }
                    ],
                },
                ensure_ascii=False,
            ),
        ]
    )

    with pytest.raises(DeepSeekResponseError, match="background overview"):
        asyncio.run(
            DeepSeekFilter(provider=provider).compose(  # type: ignore[arg-type]
                [
                    {
                        **candidate("x-missing-background"),
                        "text": "We released a new open-source developer tool today.",
                    }
                ],
                max_items=1,
                preserve_original=True,
            )
        )


def test_x_long_original_keeps_translation_and_background_after_eight_hundred_chars():
    original = "The team released an open source inference runtime with streaming support. " * 14
    translation = "团队发布了支持流式推理的开源运行时。"
    background = "流式推理会逐步返回模型输出。"
    provider = RecordingProvider(
        [
            '{"approved":[1]}',
            '{"approved":[1]}',
            json.dumps(
                {
                    "title": "开源运行时支持流式推理",
                    "body": translation,
                    "tags": ["开源", "推理"],
                    "selected": [
                        {
                            "index": 1,
                            "headline": "流式推理更新",
                            "translation_required": True,
                            "star_rating": 4,
                            "text": (
                                f"原文：\n{original}\n\n中文翻译：\n{translation}"
                                f"\n\n背景概述：\n{background}"
                            ),
                        }
                    ],
                },
                ensure_ascii=False,
            ),
        ]
    )
    result = asyncio.run(
        DeepSeekFilter(provider=provider).compose(
            [{**candidate("long-x"), "text": original}],
            max_items=1,
            preserve_original=True,
        )
    )
    assert original.strip() in result.items[0].text
    assert result.items[0].text.endswith(background)
    assert translation in result.items[0].text


def test_immediate_five_star_rejects_a_non_five_star_selection() -> None:
    provider = RecordingProvider(
        [
            '{"approved":[1]}',
            '{"approved":[1]}',
            json.dumps(
                {
                    "title": "开发工具功能更新",
                    "body": "开发工具公布了明确的功能变化和正式上线时间。",
                    "tags": ["开发者", "工具", "科技", "软件"],
                    "selected": [
                        {
                            "index": 1,
                            "headline": "开发工具更新",
                            "text": "开发工具公布了明确功能变化和上线时间。",
                            "star_rating": 4,
                        }
                    ],
                },
                ensure_ascii=False,
            ),
        ]
    )

    with pytest.raises(DeepSeekResponseError, match="must start with star_rating 5"):
        asyncio.run(
            DeepSeekFilter(provider=provider).compose(  # type: ignore[arg-type]
                [candidate("one")],
                max_items=1,
                five_star_only=True,
            )
        )


def test_immediate_five_star_allows_empty_selection_without_forcing_normal_news() -> None:
    provider = RecordingProvider(
        [
            '{"approved":[1]}',
            '{"approved":[1]}',
            '{"title":"","body":"","tags":[],"selected":[]}',
        ]
    )

    result = asyncio.run(
        DeepSeekFilter(provider=provider).compose(  # type: ignore[arg-type]
            [candidate("ordinary-update")],
            max_items=1,
            five_star_only=True,
        )
    )

    assert result.items == ()
    assert len(provider.calls) == 3
    system_prompt = provider.calls[2][0][0]["content"]
    assert "五星即时单发" in system_prompt
    assert "绝对 1-5 星" in system_prompt
    assert "相对第一" in system_prompt
    assert "selected 为空" in system_prompt


def test_startup_fill_capacity_retries_an_underfilled_quality_selection() -> None:
    first = {
        "title": "人工智能产品更新",
        "body": "多项人工智能产品与开发工具更新已经公布，包含具体功能变化。",
        "tags": ["人工智能", "产品", "开发者", "科技"],
        "selected": [
            {
                "index": 1,
                "headline": "第一项产品更新",
                "text": "第一项人工智能产品公布了明确的功能更新。",
                "star_rating": 4,
            }
        ],
    }
    filled = {
        **first,
        "selected": [
            *first["selected"],
            {
                "index": 2,
                "headline": "第二项工具更新",
                "text": "第二项开发工具也公布了面向用户的具体改进。",
                "star_rating": 4,
            },
        ],
    }
    provider = RecordingProvider(
        [
            '{"approved":[1,2]}',
            '{"approved":[1,2]}',
            json.dumps(first, ensure_ascii=False),
            json.dumps(filled, ensure_ascii=False),
        ]
    )

    result = asyncio.run(
        DeepSeekFilter(provider=provider).compose(  # type: ignore[arg-type]
            [candidate("one"), candidate("two")],
            max_items=2,
            fill_capacity=True,
        )
    )

    assert [item.record_id for item in result.items] == ["one", "two"]
    assert "启动积压合并模式" in provider.calls[3][0][-1]["content"]
    assert "不要留给后续帖子" in provider.calls[3][0][-1]["content"]


def test_outer_processor_retries_schema_failures_but_not_type_errors() -> None:
    class FlakyFilter:
        def __init__(self) -> None:
            self.calls = 0

        async def compose(self, _candidates: object, *, max_items: int) -> object:
            self.calls += 1
            if self.calls < 3:
                raise DeepSeekResponseError("response lacks selected[]")
            return parse_editorial_response(
                json.dumps(
                    {
                        "title": "科技测试",
                        "body": "一条用于验证发布链路的科技信息摘要。",
                        "tags": ["科技"],
                        "selected": [
                            {
                                "index": 1,
                                "headline": "测试",
                                "text": "测试正文",
                                "star_rating": 4,
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                [candidate("one")],
            )

    async def no_sleep(_seconds: float) -> None:
        return None

    flaky = FlakyFilter()
    processor = TechnologyNewsProcessor(flaky, sleep=no_sleep)  # type: ignore[arg-type]
    result = asyncio.run(processor.compose([candidate("one")], max_items=1))
    assert result.title == "科技测试"
    assert flaky.calls == 3

    class InvalidFilter:
        calls = 0

        async def compose(self, _candidates: object, *, max_items: int) -> object:
            self.calls += 1
            raise TypeError("bad contract")

    invalid = InvalidFilter()
    with pytest.raises(TypeError, match="bad contract"):
        asyncio.run(
            TechnologyNewsProcessor(invalid, sleep=no_sleep).compose(  # type: ignore[arg-type]
                [candidate("one")], max_items=1
            )
        )
    assert invalid.calls == 1
