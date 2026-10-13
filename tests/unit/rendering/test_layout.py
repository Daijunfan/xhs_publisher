from __future__ import annotations

import pytest

from xhs_local.rendering import build_html


def test_media_card_preserves_original_structure_and_embeds_media() -> None:
    html = build_html(
        text="科技正文包含 Anthropic 和 50% 的具体进展。",
        headline="科技标题",
        media=({"data_url": "data:image/png;base64,iVBORw0KGgo="},),
        source="来源",
        date_label="2026/08/16",
        width=1080,
        height=1440,
    )
    assert "科技资讯简报" in html
    assert "data:image/png;base64" in html
    assert 'class="copy-frame"' in html
    assert "dataset.layoutValid" in html
    assert "dataset.bottomWhitespace" in html
    assert "desiredStoryHeight" in html
    assert "storyRect.top >= heroRect.bottom + 12" in html
    assert 'class="canvas  has-media"' in html
    assert '<div class="hero"><section class="media-grid media-1">' in html
    assert "<strong>Anthropic</strong>" in html
    assert "<strong>50%</strong>" in html


def test_no_media_card_exposes_all_six_unchanged_editorial_variants() -> None:
    variants: list[str] = []
    for variant in range(1, 7):
        html = build_html(
            text="无图科技新闻使用网格纸张、醒目大字和克制的技术编辑装饰。",
            headline="高雅随机视觉",
            source="测试来源",
            date_label="2026/08/19",
            width=1080,
            height=1440,
            variant=variant,
        )
        marker = f"text-poster text-variant-{variant}"
        assert marker in html
        variants.append(marker)
        assert '<main class="poster-copy">' in html
        assert 'class="poster-title"' in html
        assert 'class="poster-body"' in html
        assert "text-wrap:balance" in html
        assert 'class="poster-decor decor-three"' in html
        assert "#f0edf7" not in html
        assert "#8f78d8" not in html
        assert 'class="canvas' not in html
        assert "dataset.layoutValid" in html
    assert len(set(variants)) == 6


def test_x_card_has_distinct_style_avatar_author_translation_and_media() -> None:
    html = build_html(
        text=(
            "原文：\nWe released 3 models with 50% lower latency.\n\n"
            "中文翻译：\n我们发布了速度更快的推理引擎。#开源\n\n"
            "背景概述：\n推理引擎负责让训练好的人工智能模型生成结果，"
            "延迟降低意味着用户可以更快获得回答。"
        ),
        headline="推理引擎性能更新",
        source="Andrej Karpathy @karpathy",
        avatar={"data_url": "data:image/webp;base64,UklGRg=="},
        media=({"data_url": "data:image/jpeg;base64,/9j/"},),
        date_label="2026/08/27",
        variant=1,
        template_name="x_post.html",
    )

    assert 'class="canvas x-variant-1 has-media' in html
    assert 'class="brand-mark"' not in html
    assert "PUBLIC TECH POST" not in html
    assert '<header class="topbar"><div class="profile"><div class="avatar">' in html
    assert '<div class="profile-name">Andrej Karpathy @karpathy</div>' in html
    assert '<time class="profile-time">2026/08/27 · 01 / 01</time>' in html
    assert '<div class="x-mark"><svg viewBox="0 0 24 24" aria-label="X">' in html
    assert 'class="hero"><section class="media-grid media-1">' in html
    assert '<main class="story">' in html
    assert 'class="copy-frame"' in html
    assert 'alt="作者头像"' in html
    assert "Andrej Karpathy @karpathy" in html
    assert "<strong>released</strong>" not in html
    assert "<strong>inference</strong>" not in html
    assert "<strong>50%</strong>" in html
    assert "<strong>3</strong> models" in html
    assert "<strong>#开源</strong>" in html
    assert "中文翻译" in html
    assert "背景概述" in html
    assert "data:image/jpeg;base64" in html
    assert 'class="media-backdrop"' in html
    assert 'class="media-main"' in html
    assert "object-fit:contain" in html
    assert "科技资讯简报" not in html


@pytest.mark.parametrize("variant", [1, 2, 3])
def test_x_card_supports_three_light_visual_variants(variant: int) -> None:
    html = build_html(
        text=(
            "原文：\nA public technology update.\n\n中文翻译：\n一项公开科技更新。\n\n"
            "背景概述：\n这段文字用于向普通读者补充相关背景。"
        ),
        headline="公开科技更新",
        source="Author @author",
        date_label="2026/08/27",
        variant=variant,
        template_name="x_post.html",
    )

    assert f"x-variant-{variant}" in html
    assert 'class="canvas x-variant-' in html
    assert "no-media .topbar" not in html
    assert 'class="profile-name">Author @author</div>' in html
    assert 'class="profile-time">2026/08/27 · 01 / 01</time>' in html
    assert 'class="x-mark"><svg' in html
    assert "#e8eefb" in html
    assert "#ff765f" in html


def test_x_media_and_text_cards_use_the_identical_topbar() -> None:
    common = {
        "text": "原文：\nA useful update.\n\n中文翻译：\n一项更新。\n\n背景概述：\n背景说明。",
        "headline": "更新",
        "source": "Author @author",
        "avatar": {"data_url": "data:image/png;base64,iVBORw0KGgo="},
        "date_label": "2026/08/28 12:05",
        "variant": 1,
        "template_name": "x_post.html",
    }
    text_html = build_html(**common)
    media_html = build_html(
        **common,
        media=({"data_url": "data:image/jpeg;base64,/9j/"},),
    )

    def header(value: str) -> str:
        return value.split('<header class="topbar">', 1)[1].split("</header>", 1)[0]

    assert header(text_html) == header(media_html)


@pytest.mark.parametrize("platform", ["x", "youtube"])
@pytest.mark.parametrize("with_cover", [False, True])
def test_x_pages_share_the_cover_typography_without_affecting_youtube(platform, with_cover):
    canvases = []
    for page in (1, 2, 3):
        html = build_html(
            text="完整保留长文内容，使用舒适的正文字号。" * 35,
            headline="技术长文",
            source="作者",
            date_label="2026/09/13",
            template_name="x_post.html",
            source_platform=platform,
            story_has_media=with_cover,
            index=page,
            total=3,
            variant=1,
        )
        canvases.append(html.split('<div class="canvas ', 1)[1].split('"', 1)[0])
    assert len(set(canvases)) == 1
    assert ("x-story" in canvases[0]) is (platform == "x")
    assert ("x-photo-story" in canvases[0]) is (platform == "x" and with_cover)
    assert "x-continuation" not in html
    if platform == "x":
        assert "dense" not in canvases[0]


def test_pagination_input_cannot_inject_script_markup():
    html = build_html(
        text='</script><img src=x onerror="alert(1)">',
        headline="示例",
        date_label="",
        template_name="x_post.html",
        source_platform="x",
        measure_pages=True,
    )
    assert "</script><img" not in html
    assert "\\u003c/script>" in html


@pytest.mark.parametrize("variant", [0, 4])
def test_x_card_rejects_unknown_visual_variant(variant: int) -> None:
    with pytest.raises(ValueError, match="X variant"):
        build_html(
            text="公开科技更新。",
            headline="公开科技更新",
            source="Author @author",
            date_label="2026/08/27",
            variant=variant,
            template_name="x_post.html",
        )


def test_template_escapes_untrusted_copy_without_corrupting_highlights() -> None:
    html = build_html(
        text="<script>alert('x')</script> 42%",
        headline='A&B "headline"',
        date_label="2026/08/19",
        variant=1,
    )
    assert "<script>alert" not in html
    assert "&lt;<strong>script</strong>&gt;" in html
    assert "A&amp;B &quot;headline&quot;" in html
    assert "<strong>42%</strong>" in html


def test_layout_validates_dimensions_and_variants() -> None:
    with pytest.raises(ValueError, match="width"):
        build_html(text="x", date_label="today", width=599)
    with pytest.raises(ValueError, match="variant"):
        build_html(text="x", date_label="today", variant=7)
    with pytest.raises(ValueError, match="headline"):
        build_html(text="", date_label="today")
