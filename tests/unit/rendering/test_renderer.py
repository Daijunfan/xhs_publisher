from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from xhs_local.rendering.layout import build_html, paginate_text
from xhs_local.rendering.renderer import HtmlPhotoGenerator


@pytest.mark.parametrize("pages", [["原文", "与翻译"], ["仅一半"], [], None])
def test_measured_x_pagination_validates_content_and_cleans_temporary_files(
    tmp_path, monkeypatch, pages
):
    measured_files = []

    async def measure(_browser, args):
        from urllib.parse import unquote, urlsplit

        path = Path(unquote(urlsplit(args[-1]).path))
        measured_files.append(path)
        assert "const paginationText=" in path.read_text()
        assert "--dump-dom" in args
        return (
            '<script id="x-pagination" type="application/json">' + json.dumps(pages) + "</script>"
        )

    monkeypatch.setattr(
        "xhs_local.rendering.renderer.find_browser", lambda _: Path("/fake/browser")
    )
    monkeypatch.setattr("xhs_local.rendering.renderer.read_dom", measure)
    task = HtmlPhotoGenerator(output_dir=tmp_path).paginate_x_story("原文与翻译", headline="标题")
    if pages == ["原文", "与翻译"]:
        assert asyncio.run(task) == pages
    else:
        with pytest.raises(RuntimeError, match="preserve the complete story"):
            asyncio.run(task)
    assert all(not path.parent.exists() for path in measured_files)


def test_x_pagination_reserves_cover_space_without_losing_original_or_translation():
    text = "原文：\n" + "A useful technical explanation. " * 20
    text += "\n\n中文翻译：\n" + "完整保留技术细节和原文观点。" * 35
    text += "\n\n背景概述：\n必要背景。"
    pages = paginate_text(text, first_page_limit=180)
    assert "".join(pages) == text
    assert len(pages[0]) <= 180
    assert all(0 < len(page) <= 320 for page in pages[1:])
    assert len(pages) > 1


def test_video_pagination_preserves_all_text_and_source_branding():
    text = "完整的中文内容，包含关键事实和限制条件。\n\n" * 60
    pages = paginate_text(text)
    assert "".join(pages) == text
    assert all(0 < len(page) <= 320 for page in pages)
    for platform, name in (("youtube", "YouTube"),):
        html = build_html(
            text=pages[0],
            headline="完整视频标题",
            source="作者名称",
            date_label="2026/09/12 20:00",
            template_name="x_post.html",
            source_platform=platform,
        )
        assert "video-platform" in html
        assert f'class="platform-label">{name}' in html
        assert "视频核心内容" in html
        assert "ORIGINAL POST · 中文翻译" not in html


def test_video_poster_cache_survives_renderer_restart(tmp_path, monkeypatch):
    captures = []

    async def capture(_browser, _args, path):
        captures.append(path)
        path.write_bytes(b"synthetic-png")

    monkeypatch.setattr(
        "xhs_local.rendering.renderer.find_browser", lambda _: Path("/fake/browser")
    )
    monkeypatch.setattr("xhs_local.rendering.renderer.capture_screenshot", capture)
    options = {
        "headline": "视频标题",
        "source": "作者",
        "posted_at": "2026-09-12T12:00:00+08:00",
        "template_name": "x_post.html",
        "source_platform": "youtube",
    }
    first = asyncio.run(
        HtmlPhotoGenerator(output_dir=tmp_path).generate_single_photo("完整摘要", **options)
    )
    second = asyncio.run(
        HtmlPhotoGenerator(output_dir=tmp_path).generate_single_photo("完整摘要", **options)
    )
    assert first == second
    assert len(captures) == 1


def test_renderer_removes_completed_cards_when_a_later_card_fails(tmp_path: Path) -> None:
    class FailingGenerator(HtmlPhotoGenerator):
        calls = 0

        async def generate_single_photo(self, _text: str, **options: object) -> Path:
            self.calls += 1
            if self.calls == 2:
                raise RuntimeError("synthetic second-card failure")
            path = self.output_dir / str(options["filename"])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("temporary-card", encoding="utf-8")
            return path

    generator = FailingGenerator(output_dir=tmp_path)
    cards = [
        {
            "record_id": f"card-{number}",
            "headline": f"Card {number}",
            "text": f"Detailed card text {number}",
            "attachments": (),
        }
        for number in (1, 2)
    ]
    with pytest.raises(RuntimeError, match="synthetic second-card failure"):
        asyncio.run(generator.generate_news_cards(cards, prefix="cleanup-test"))
    assert list(tmp_path.iterdir()) == []


def test_attachment_normalization_accepts_existing_four_media_types(tmp_path: Path) -> None:
    generator = HtmlPhotoGenerator(output_dir=tmp_path)
    for mime_type in ("image/png", "image/jpeg", "image/webp", "image/gif"):
        normalized = generator._normalize_attachment(  # noqa: SLF001
            {"mime_type": mime_type, "data": b"non-empty"}
        )
        assert normalized is not None
        assert normalized["data_url"].startswith(f"data:{mime_type};base64,")
    assert (
        generator._normalize_attachment(  # noqa: SLF001
            {"mime_type": "image/svg+xml", "data": b"svg"}
        )
        is None
    )
