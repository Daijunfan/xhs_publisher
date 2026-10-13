"""Opt-in local browser verification; never opens a GUI or publishes a post."""

from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path

import pytest

from xhs_local.rendering import renderer
from xhs_local.rendering.chromium import assert_png, read_dom

pytestmark = pytest.mark.skipif(
    not os.environ.get("XHS_LAYOUT_BROWSER"), reason="set XHS_LAYOUT_BROWSER to a headless browser"
)


@pytest.mark.parametrize("with_media", [False, True])
@pytest.mark.parametrize("language", ["chinese", "english"])
def test_measured_pages_keep_font_size_and_fill_nonfinal_pages(
    tmp_path, monkeypatch, with_media, language
):
    text = (
        ("具体方法包括分析模型的输入、评估推理的开销，并记录 50% 的性能变化。" * 9 + "\n\n") * 7
        if language == "chinese"
        else ("The model improves inference speed by 50% with useful benchmarks. " * 22 + "\n\n")
        * 5
    ).strip()
    metrics = []
    build = renderer.build_html

    def instrument(**kwargs):
        return build(**kwargs).replace(
            "</body>",
            """<script>
          document.body.dataset.metrics=JSON.stringify({
            font:getComputedStyle(document.querySelector('article')).fontSize,
            title:getComputedStyle(document.querySelector('h1')).fontSize,
            transform:getComputedStyle(document.querySelector('.copy-content')).transform,
            fill:document.querySelector('.copy-content').getBoundingClientRect().height /
                 document.querySelector('.copy-frame').getBoundingClientRect().height,
            valid:document.body.dataset.layoutValid
          });
        </script></body>""",
        )

    async def capture(browser, args, output):
        import html

        dom = await read_dom(browser, (*args, "--dump-dom"))
        assert_png(output, 1080, 1440)
        value = re.search(r'data-metrics="([^"]+)"', dom)
        metrics.append(json.loads(html.unescape(value[1])))

    monkeypatch.setattr(renderer, "build_html", instrument)
    monkeypatch.setattr(renderer, "capture_screenshot", capture)

    async def run():
        generator = renderer.HtmlPhotoGenerator(
            output_dir=tmp_path, browser_path=Path(os.environ["XHS_LAYOUT_BROWSER"])
        )
        media = (
            (
                {
                    "data_url": "data:image/png;base64,"
                    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/"
                    "x8AAwMCAO+jRZkAAAAASUVORK5CYII="
                },
            )
            if with_media
            else ()
        )
        pages = await generator.paginate_x_story(text, headline="长文技术解析", attachments=media)
        assert len(pages) > 2
        assert "".join(pages) == text
        await generator.generate_news_cards(
            [
                {
                    "record_id": "one-story",
                    "headline": "长文技术解析",
                    "text": page,
                    "source_platform": "x",
                    "template_name": "x_post.html",
                    "story_page": index + 1,
                    "story_pages": len(pages),
                    "story_has_media": with_media,
                    "attachments": media if index == 0 else (),
                }
                for index, page in enumerate(pages)
            ]
        )
        assert all(item["font"] == ("28px" if with_media else "38px") for item in metrics)
        assert all(item["title"] == ("50px" if with_media else "70px") for item in metrics)
        assert all(item["valid"] == "true" and item["transform"] == "none" for item in metrics)
        assert all(item["fill"] >= 0.85 for item in metrics[:-1]), metrics

    asyncio.run(run())
