"""Public HTML-photo renderer and temporary-file lifecycle."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import re
import shutil
import tempfile
import uuid
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from .chromium import capture_screenshot, find_browser, read_dom, screenshot_args
from .layout import DEFAULT_HEIGHT, DEFAULT_WIDTH, assert_dimension, build_html

DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[3] / "runtime/generated"
DEFAULT_BROWSER_PATH = os.environ.get("HTML_PHOTO_BROWSER_PATH")
_PREFIX = re.compile(r"^[A-Za-z0-9._-]{1,80}$")
_DATA_URL = re.compile(r"^data:image/(?:png|jpeg|webp|gif);base64,", re.IGNORECASE)
_IMAGE_MIME = frozenset({"image/png", "image/jpeg", "image/webp", "image/gif"})


def _timestamp() -> str:
    return datetime.now().astimezone().strftime("%Y%m%dT%H%M%SZ")


def _today_label() -> str:
    return datetime.now().astimezone().strftime("%Y/%m/%d")


def _format_date(value: object) -> str:
    if isinstance(value, datetime):
        date = value
    else:
        try:
            date = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return _today_label()
    if date.tzinfo is not None:
        date = date.astimezone()
    return date.strftime("%Y/%m/%d %H:%M")


def _value(value: object, *names: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        for name in names:
            if name in value:
                return value[name]
        return default
    for name in names:
        if hasattr(value, name):
            return getattr(value, name)
    return default


class HtmlPhotoGenerator:
    """Turn editorial items into deterministic-size PNG files via Chromium."""

    def __init__(
        self,
        *,
        output_dir: str | Path = DEFAULT_OUTPUT_DIR,
        browser_path: str | Path | None = DEFAULT_BROWSER_PATH,
        runtime_root: str | Path | None = None,
    ) -> None:
        self.output_dir = Path(output_dir).expanduser().resolve()
        self.browser_path = browser_path
        self.runtime_root = Path(runtime_root).expanduser().resolve() if runtime_root else None

    async def check_configuration(self) -> dict[str, object]:
        return {"ok": True, "browser": str(find_browser(self.browser_path))}

    def _normalize_attachment(self, attachment: object) -> dict[str, str] | None:
        data_url = _value(attachment, "data_url", "dataUrl")
        if isinstance(data_url, str) and _DATA_URL.match(data_url):
            return {"data_url": data_url}

        mime_type = str(_value(attachment, "mime_type", "mimeType", default="")).lower()
        if mime_type not in _IMAGE_MIME:
            return None
        data = _value(attachment, "data")
        if data is None:
            path_value = _value(attachment, "path")
            if path_value is None:
                relative_path = _value(attachment, "relative_path", "relativePath")
                if relative_path is not None and self.runtime_root is not None:
                    candidate = (self.runtime_root / str(relative_path)).resolve()
                    try:
                        candidate.relative_to(self.runtime_root)
                    except ValueError:
                        return None
                    path_value = candidate
            if path_value is not None:
                try:
                    data = Path(path_value).read_bytes()
                except OSError:
                    return None
        if not isinstance(data, (bytes, bytearray, memoryview)) or len(data) == 0:
            return None
        encoded = base64.b64encode(bytes(data)).decode("ascii")
        return {"data_url": f"data:{mime_type};base64,{encoded}"}

    async def paginate_x_story(self, text: str, *, headline: str, attachments=()) -> list[str]:
        media = [
            item
            for attachment in attachments[:3]
            if (item := self._normalize_attachment(attachment)) is not None
        ]
        document = build_html(
            text=text,
            headline=headline,
            media=media,
            date_label="",
            source_platform="x",
            template_name="x_post.html",
            measure_pages=True,
        )
        with tempfile.TemporaryDirectory(prefix="xhs-story-layout-") as temporary:
            root = Path(temporary)
            html_path = root / "story.html"
            html_path.write_text(document, encoding="utf-8")
            dom = await read_dom(
                find_browser(self.browser_path),
                screenshot_args(
                    width=DEFAULT_WIDTH,
                    height=DEFAULT_HEIGHT,
                    profile_dir=root / "profile",
                    screenshot_path=None,
                    page_url=html_path.as_uri(),
                ),
            )
        result = re.search(
            r'<script id="x-pagination" type="application/json">(.*?)</script>', dom, re.S
        )
        pages = json.loads(result[1]) if result else None
        if (
            not isinstance(pages, list)
            or not pages
            or any(not isinstance(page, str) or not page.strip() for page in pages)
            or "".join(pages) != text
        ):
            raise RuntimeError("browser pagination did not preserve the complete story")
        return pages

    async def generate_news_cards(
        self,
        items: Sequence[object],
        *,
        prefix: str | None = None,
        width: int | None = None,
        height: int | None = None,
        on_progress: Callable[[str], None] | None = None,
    ) -> list[Path]:
        if not isinstance(items, Sequence) or isinstance(items, (str, bytes)) or not items:
            raise TypeError("items must be a non-empty sequence")
        report = on_progress if callable(on_progress) else lambda _message: None
        requested_prefix = prefix or f"series-{_timestamp()}"
        if not isinstance(requested_prefix, str) or not _PREFIX.fullmatch(requested_prefix):
            raise TypeError("prefix must contain only letters, numbers, dot, underscore, or hyphen")
        unique_prefix = f"{requested_prefix}-{uuid.uuid4().hex[:8]}"
        paths: list[Path] = []
        report(f"{len(items)} news card(s) -> {self.output_dir}")
        try:
            for zero_index, item in enumerate(items):
                item_id = _value(item, "record_id", "id")
                headline = _value(item, "headline")
                text = _value(item, "text")
                if (
                    not isinstance(item_id, str)
                    or not item_id.strip()
                    or not isinstance(headline, str)
                    or not headline.strip()
                    or not isinstance(text, str)
                    or not text.strip()
                ):
                    raise TypeError(
                        f"Item {zero_index + 1} requires non-empty id, headline, and text"
                    )
                attachments = _value(item, "attachments", default=())
                if not isinstance(attachments, Sequence) or isinstance(attachments, (str, bytes)):
                    attachments = ()
                media = [
                    normalized
                    for attachment in attachments[:3]
                    if (normalized := self._normalize_attachment(attachment)) is not None
                ]
                avatar_value = _value(item, "avatar")
                avatar = (
                    self._normalize_attachment(avatar_value) if avatar_value is not None else None
                )
                filename = f"{unique_prefix}-{zero_index + 1:02d}.png"
                path = await self.generate_single_photo(
                    text,
                    filename=filename,
                    width=width,
                    height=height,
                    headline=headline,
                    source=_value(item, "source", "source_name", default="科技资讯"),
                    posted_at=_value(item, "posted_at", "occurred_at"),
                    media=media,
                    avatar=avatar,
                    index=_value(item, "story_page", default=zero_index + 1),
                    total=_value(item, "story_pages", default=len(items)),
                    template_name=_value(item, "template_name"),
                    source_platform=_value(item, "source_platform"),
                    story_has_media=_value(item, "story_has_media"),
                )
                paths.append(path)
                report(f"rendered {zero_index + 1}/{len(items)}")
            return paths
        except BaseException:
            for path in paths:
                if not path.name.startswith("video-"):
                    path.unlink(missing_ok=True)
            raise

    async def generate_single_photo(
        self,
        text: str,
        *,
        filename: str | None = None,
        width: int | None = None,
        height: int | None = None,
        headline: str | None = None,
        source: object = "科技资讯",
        posted_at: object = None,
        media: Sequence[object] = (),
        avatar: object | None = None,
        index: int = 1,
        total: int = 1,
        variant: int | None = None,
        template_name: str | None = None,
        source_platform: str | None = None,
        story_has_media: bool | None = None,
    ) -> Path:
        if not isinstance(text, str) or not text.strip():
            raise TypeError("text must be a non-empty string")
        normalized_text = text.strip()
        final_width = DEFAULT_WIDTH if width is None else width
        final_height = DEFAULT_HEIGHT if height is None else height
        assert_dimension(final_width, "width")
        assert_dimension(final_height, "height")

        requested_name = (
            Path(filename).name
            if filename
            else f"html-photo-{_timestamp()}-{uuid.uuid4().hex[:8]}.png"
        )
        final_name = (
            requested_name
            if Path(requested_name).suffix.lower() == ".png"
            else (f"{requested_name}.png")
        )
        document = build_html(
            text=normalized_text,
            headline=headline,
            media=media,
            avatar=avatar,
            source=str(source or "科技资讯"),
            date_label=_format_date(posted_at) if posted_at is not None else _today_label(),
            index=index,
            total=total,
            width=final_width,
            height=final_height,
            variant=1 if source_platform == "youtube" else variant,
            template_name=template_name,
            source_platform=source_platform,
            story_has_media=story_has_media,
        )
        if source_platform == "youtube":
            final_name = f"video-{hashlib.sha256(document.encode()).hexdigest()}.png"
        output_path = self.output_dir / final_name
        if source_platform == "youtube" and output_path.is_file():
            return output_path
        run_id = f"{os.getpid()}-{uuid.uuid4()}"
        temporary_html_path = self.output_dir / f".{final_name}.{run_id}.html"
        temporary_png_path = self.output_dir / f".{final_name}.{run_id}.png"
        browser = find_browser(self.browser_path)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        temporary_html_path.write_text(document, encoding="utf-8")
        profile_dir: Path | None = None
        try:
            profile_dir = Path(tempfile.mkdtemp(prefix="xhs-html-photo-"))
            await capture_screenshot(
                browser,
                screenshot_args(
                    width=final_width,
                    height=final_height,
                    profile_dir=profile_dir,
                    screenshot_path=temporary_png_path,
                    page_url=temporary_html_path.as_uri(),
                ),
                temporary_png_path,
            )
            os.replace(temporary_png_path, output_path)
            if not os.access(output_path, os.R_OK):
                raise RuntimeError(f"generated image is not readable: {output_path}")
            return output_path
        except asyncio.CancelledError:
            raise
        except Exception as error:
            raise RuntimeError(f"Failed to generate HTML photo: {error}") from error
        finally:
            temporary_html_path.unlink(missing_ok=True)
            temporary_png_path.unlink(missing_ok=True)
            if profile_dir is not None:
                shutil.rmtree(profile_dir, ignore_errors=True)
