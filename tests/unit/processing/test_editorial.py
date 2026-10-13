from __future__ import annotations

import json

import pytest

from xhs_local.processing import (
    DeepSeekResponseError,
    parse_editorial_response,
    platform_balance_weights,
)


def candidate(record_id: str, *, with_image: bool = False) -> dict[str, object]:
    return {
        "record_id": record_id,
        "source_name": "科技频道",
        "text": f"{record_id} sufficiently detailed technology source text",
        "attachments": ({"mime_type": "image/png"},) if with_image else (),
    }


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
