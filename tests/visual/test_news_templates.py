from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from xhs_local.rendering.chromium import assert_png, find_browser
from xhs_local.rendering.renderer import HtmlPhotoGenerator


def test_real_chromium_renders_text_and_media_cards(tmp_path: Path) -> None:
    try:
        browser = find_browser()
    except RuntimeError as error:
        pytest.skip(str(error))

    generator = HtmlPhotoGenerator(output_dir=tmp_path, browser_path=browser)
    text_card = asyncio.run(
        generator.generate_single_photo(
            "Anthropic 宣布一项重要的开发者工具更新，覆盖 50% 的现有用户。",
            filename="text.png",
            headline="开发者工具迎来重要更新",
            source="科技资讯",
            posted_at="2026-08-19T12:05:00+08:00",
            variant=1,
        )
    )
    media_card = asyncio.run(
        generator.generate_single_photo(
            (
                "原文：\nWe released a new open-source inference engine with lower memory use "
                "and faster decoding on consumer GPUs.\n\n"
                "中文翻译：\n我们发布了一款新的开源推理引擎，可降低显存占用，"
                "并在消费级显卡上加快解码。\n\n"
                "背景概述：\n推理引擎负责让训练好的模型生成回答。显存占用降低后，"
                "普通消费级显卡也更容易运行这类人工智能模型。"
            ),
            filename="media.png",
            headline="开源推理引擎降低显存",
            source="Andrej Karpathy @karpathy",
            posted_at="2026-08-19T12:05:00+08:00",
            avatar={
                "data_url": (
                    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAAB"
                    "CAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9Zl1sAAAAASUVORK5CYII="
                )
            },
            media=(
                {
                    "data_url": (
                        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAAB"
                        "CAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9Zl1sAAAAASUVORK5CYII="
                    )
                },
            ),
            template_name="x_post.html",
        )
    )
    x_text_card = asyncio.run(
        generator.generate_single_photo(
            (
                "原文：\nA public AI research update.\n\n"
                "中文翻译：\n一项公开人工智能研究更新。\n\n"
                "背景概述：\n这项研究关注模型在现实工具环境中的稳定表现。"
            ),
            filename="x-text.png",
            headline="智能体工具适应能力更新",
            source="Researcher @researcher",
            posted_at="2026-08-19T12:05:00+08:00",
            avatar={
                "data_url": (
                    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAAB"
                    "CAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9Zl1sAAAAASUVORK5CYII="
                )
            },
            variant=1,
            template_name="x_post.html",
        )
    )
    assert_png(text_card, 1080, 1440)
    assert_png(media_card, 1080, 1440)
    assert_png(x_text_card, 1080, 1440)
    assert text_card.stat().st_size > 20_000
    assert media_card.stat().st_size > 20_000
    assert x_text_card.stat().st_size > 20_000
