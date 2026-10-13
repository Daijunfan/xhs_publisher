"""Pure news-card HTML construction over repository-owned templates."""

from __future__ import annotations

import json
import random
import re
from collections.abc import Mapping, Sequence
from functools import lru_cache
from pathlib import Path
from string import Template

DEFAULT_WIDTH = 1080
DEFAULT_HEIGHT = 1440
MIN_DIMENSION = 600
MAX_DIMENSION = 4096
TEMPLATE_DIR = Path(__file__).with_name("templates")


def paginate_text(text: str, limit: int = 320, *, first_page_limit: int | None = None) -> list[str]:
    """Split without dropping text, reserving extra room for an optional cover image."""
    pages = []
    page_limit = first_page_limit or limit
    while len(text) > page_limit:
        boundary = max(text.rfind(separator, 0, page_limit) for separator in ("\n", "。", ". ")) + 1
        boundary = boundary if boundary >= page_limit // 2 else page_limit
        pages.append(text[:boundary])
        text = text[boundary:]
        page_limit = limit
    if text:
        pages.append(text)
    return pages


_IMPORTANT = re.compile(
    r"(\d+(?:\.\d+)?(?:\s*亿|\s*万|\s*%|\s*倍|\s*项|\s*款)?|"
    r"[A-Za-z][A-Za-z0-9.+-]{2,})"
)
_X_ACCENT = re.compile(
    r"(\d+(?:[.,]\d+)?(?:\s*(?:亿|万|千|%|％|倍|项|款|GB|TB|MB|B|M|K|x|X))?|"
    r"#[A-Za-z0-9_\-\u4e00-\u9fff]+)"
)


def escape_html(value: object) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#039;")
    )


def render_paragraph(text: object) -> str:
    source = str(text)
    output: list[str] = []
    cursor = 0
    for match in _IMPORTANT.finditer(source):
        output.append(escape_html(source[cursor : match.start()]))
        output.append(f"<strong>{escape_html(match.group(0))}</strong>")
        cursor = match.end()
    output.append(escape_html(source[cursor:]))
    return "".join(output)


def render_text(text: object) -> str:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", str(text))]
    return "\n".join(
        f"<p>{render_paragraph(paragraph)}</p>" for paragraph in paragraphs if paragraph
    )


def render_x_text(text: object) -> str:
    """Keep English copy calm while accenting only explicit quantitative tokens."""

    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", str(text))]
    output: list[str] = []
    for paragraph in paragraphs:
        if not paragraph:
            continue
        rendered: list[str] = []
        cursor = 0
        for match in _X_ACCENT.finditer(paragraph):
            rendered.append(escape_html(paragraph[cursor : match.start()]))
            rendered.append(f"<strong>{escape_html(match.group(0))}</strong>")
            cursor = match.end()
        rendered.append(escape_html(paragraph[cursor:]))
        output.append(f"<p>{''.join(rendered)}</p>")
    return "\n".join(output)


def derive_headline(text: object) -> str:
    first = re.split(r"[。！？\n]", str(text), maxsplit=1)[0].strip()
    if not first:
        raise ValueError("headline cannot be derived from empty text")
    return first[:25] + ("…" if len(first) > 25 else "")


def assert_dimension(value: int, name: str) -> None:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value < MIN_DIMENSION
        or value > MAX_DIMENSION
    ):
        raise ValueError(f"{name} must be an integer between {MIN_DIMENSION} and {MAX_DIMENSION}")


def _media_data_url(media: object) -> str | None:
    if isinstance(media, Mapping):
        value = media.get("data_url", media.get("dataUrl"))
    else:
        value = getattr(media, "data_url", getattr(media, "dataUrl", None))
    return value if isinstance(value, str) and value.startswith("data:image/") else None


def render_media(media: Sequence[object], *, layered: bool = False) -> str:
    images = [value for item in media if (value := _media_data_url(item))][:3]
    figures = []
    for index, data_url in enumerate(images, start=1):
        source = escape_html(data_url)
        if layered:
            image = (
                f'<img class="media-backdrop" src="{source}" alt="">'
                f'<img class="media-main" src="{source}" alt="新闻配图 {index}">'
            )
        else:
            image = f'<img src="{source}" alt="新闻配图 {index}">'
        figures.append(f'<figure class="media-item media-item-{index}">{image}</figure>')
    figures_html = "\n".join(figures)
    return (
        f'<section class="media-grid media-{len(images)}">\n'
        f"    {figures_html}\n"
        '    <div class="media-shade"></div>\n'
        "  </section>"
    )


def render_avatar(avatar: object | None) -> str:
    data_url = _media_data_url(avatar) if avatar is not None else None
    if data_url is None:
        return '<span class="avatar-fallback">X</span>'
    return f'<img src="{escape_html(data_url)}" alt="作者头像">'


@lru_cache(maxsize=4)
def _template(name: str) -> Template:
    path = TEMPLATE_DIR / name
    try:
        return Template(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError(f"unknown rendering template: {name}") from error


def build_html(
    *,
    text: str,
    headline: str | None = None,
    media: Sequence[object] = (),
    avatar: object | None = None,
    source: str = "科技资讯",
    date_label: str,
    index: int = 1,
    total: int = 1,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    variant: int | None = None,
    template_name: str | None = None,
    source_platform: str | None = None,
    story_has_media: bool | None = None,
    measure_pages: bool = False,
) -> str:
    """Build one complete HTML document without I/O beyond cached template reads."""

    assert_dimension(width, "width")
    assert_dimension(height, "height")
    normalized_text = str(text).strip()
    normalized_headline = str(headline or derive_headline(normalized_text)).strip()
    sequence = f"{index:02d} / {total:02d}"
    has_media = any(_media_data_url(item) for item in media)
    common = {
        "WIDTH": str(width),
        "HEIGHT": str(height),
        "SOURCE": escape_html(source),
        "DATE_LABEL": escape_html(date_label),
        "SEQUENCE": sequence,
        "HEADLINE": escape_html(normalized_headline),
        "TEXT": render_text(normalized_text),
    }
    if template_name == "x_post.html":
        selected_x_variant = random.randint(1, 3) if variant is None else variant
        if not isinstance(selected_x_variant, int) or isinstance(selected_x_variant, bool):
            raise TypeError("X variant must be an integer from 1 to 3")
        if selected_x_variant < 1 or selected_x_variant > 3:
            raise ValueError("X variant must be an integer from 1 to 3")
        common.update(
            {
                "AVATAR": render_avatar(avatar),
                "HAS_MEDIA": "has-media" if has_media else "no-media",
                "DENSE": "dense" if len(normalized_text) > 520 and source_platform != "x" else "",
                "MEDIA": render_media(media, layered=True) if has_media else "",
                "TEXT": render_x_text(normalized_text),
                "VARIANT": str(selected_x_variant),
                "PLATFORM_CLASS": "video-platform"
                if source_platform == "youtube"
                else (
                    "x-story x-photo-story"
                    if (has_media if story_has_media is None else story_has_media)
                    else "x-story"
                )
                if source_platform == "x"
                else "",
                "PAGINATION_TEXT": json.dumps(text).replace("<", "\\u003c")
                if measure_pages
                else "null",
                "ACCENT_PATTERN": json.dumps(_X_ACCENT.pattern),
                "PLATFORM_LABEL": {"youtube": "YouTube"}.get(source_platform, ""),
                "FOOTER_LABEL": "视频核心内容"
                if source_platform == "youtube"
                else "ORIGINAL POST · 中文翻译",
            }
        )
        return _template("x_post.html").substitute(common)
    if has_media:
        common.update(
            {
                "DENSE": "dense" if len(normalized_text) > 220 else "",
                "MEDIA": render_media(media),
            }
        )
        return _template("news_with_media.html").substitute(common)

    selected_variant = random.randint(1, 6) if variant is None else variant
    if not isinstance(selected_variant, int) or isinstance(selected_variant, bool):
        raise TypeError("variant must be an integer from 1 to 6")
    if selected_variant < 1 or selected_variant > 6:
        raise ValueError("variant must be an integer from 1 to 6")
    common["VARIANT"] = str(selected_variant)
    name = template_name or "news_text_editorial.html"
    if name != "news_text_editorial.html":
        raise ValueError(f"unsupported no-media template: {name}")
    return _template(name).substitute(common)
