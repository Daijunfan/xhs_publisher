"""Credential-free reader for X's public profile representation."""

from __future__ import annotations

import asyncio
import json
import mimetypes
import re
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlparse

from .mapper import DownloadedXImage, PublicXPost

PROFILE_API_MAX_BYTES = 1024 * 1024
TIMELINE_API_MAX_BYTES = 4 * 1024 * 1024
SUPPORTED_IMAGE_MIME_TYPES = frozenset({"image/png", "image/jpeg", "image/webp", "image/gif"})
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/140.0 Safari/537.36"
)


class XPublicError(RuntimeError):
    """The public X representation could not satisfy the source contract."""


def parse_profile_avatar(body: bytes, expected_handle: str) -> str | None:
    try:
        payload = json.loads(body.decode("utf-8", "replace"))
    except json.JSONDecodeError as error:
        raise XPublicError("public profile avatar response is invalid JSON") from error
    user = payload.get("user") if isinstance(payload, dict) else None
    if not isinstance(user, dict) or int(payload.get("code") or 0) != 200:
        raise XPublicError("public profile avatar response has no user")
    screen_name = str(user.get("screen_name") or "")
    if screen_name.casefold() != expected_handle.casefold():
        raise XPublicError("public profile avatar handle does not match target")
    avatar_url = str(user.get("avatar_url") or "")
    parsed = urlparse(avatar_url)
    return avatar_url if parsed.scheme == "https" and parsed.netloc else None


class _Article:
    def __init__(self, url: str) -> None:
        self.url = url
        self.post_id = ""
        self.created_at = ""
        self.text = ""
        self.author_name = ""
        self.author_handle = ""
        self.avatar_url = ""
        self.image_urls: list[str] = []


class _ProfileParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[_Article] = []
        self.articles: list[_Article] = []
        self.in_title = False
        self.title_parts: list[str] = []

    @staticmethod
    def _attributes(attrs: list[tuple[str, str | None]]) -> dict[str, str]:
        return {name: value or "" for name, value in attrs}

    def _add_image(self, url: str) -> None:
        if not self.stack or not url:
            return
        parsed = urlparse(url)
        if not parsed.hostname or not parsed.hostname.endswith("twimg.com"):
            return
        if "/profile_images/" in parsed.path:
            if not self.stack[-1].avatar_url:
                self.stack[-1].avatar_url = url
            return
        if "/media/" not in parsed.path and "/amplify_video_thumb/" not in parsed.path:
            return
        article = self.stack[-1]
        key = parsed.path.rsplit(".", 1)[0]
        if any(urlparse(existing).path.rsplit(".", 1)[0] == key for existing in article.image_urls):
            return
        article.image_urls.append(url)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = self._attributes(attrs)
        if tag == "title":
            self.in_title = True
            return
        if tag == "article":
            self.stack.append(_Article(values.get("itemid", "")))
            return
        if not self.stack:
            return
        article = self.stack[-1]
        if tag == "meta":
            prop = values.get("itemprop")
            content = values.get("content", "")
            if prop == "identifier" and not article.post_id:
                article.post_id = content
            elif prop == "datePublished" and not article.created_at:
                article.created_at = content
            elif prop == "text" and not article.text:
                article.text = content
            elif prop == "name" and not article.author_name:
                article.author_name = content
            elif prop == "alternateName" and not article.author_handle:
                article.author_handle = content.removeprefix("@")
            elif prop == "image":
                self._add_image(content)
        elif tag == "img":
            self._add_image(values.get("src", ""))
        elif tag == "video":
            self._add_image(values.get("poster", ""))

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False
            return
        if tag == "article" and self.stack:
            self.articles.append(self.stack.pop())

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data)


def parse_profile_html(value: str, expected_handle: str) -> tuple[PublicXPost, ...]:
    parser = _ProfileParser()
    parser.feed(value)
    expected = expected_handle.removeprefix("@").casefold()
    title = "".join(parser.title_parts)
    match = re.search(r"\(@([A-Za-z0-9_]{1,15})\)\s*/\s*X", title)
    if match is None or match.group(1).casefold() != expected:
        raise XPublicError(f"public X profile does not match @{expected_handle.removeprefix('@')}")
    posts: list[PublicXPost] = []
    seen: set[str] = set()
    for article in parser.articles:
        if article.author_handle.casefold() != expected or article.post_id in seen:
            continue
        try:
            created_at = datetime.fromisoformat(article.created_at.replace("Z", "+00:00"))
        except ValueError:
            continue
        if not article.post_id.isdecimal() or not article.text.strip() or not article.url:
            continue
        seen.add(article.post_id)
        posts.append(
            PublicXPost(
                post_id=article.post_id,
                created_at=created_at,
                text=article.text.strip(),
                url=article.url,
                author_name=article.author_name.strip(),
                author_handle=article.author_handle,
                avatar_url=article.avatar_url or None,
                image_urls=tuple(article.image_urls),
            )
        )
    posts.sort(key=lambda post: (post.created_at, int(post.post_id)))
    return tuple(posts)


def parse_profile_statuses(body: bytes, expected_handle: str) -> tuple[PublicXPost, ...]:
    if not body:
        return ()
    try:
        payload = json.loads(body.decode("utf-8", "replace"))
    except json.JSONDecodeError as error:
        raise XPublicError("public X timeline response is invalid JSON") from error
    if not isinstance(payload, dict) or int(payload.get("code") or 0) != 200:
        raise XPublicError("public X timeline response is unsuccessful")
    results = payload.get("results")
    if not isinstance(results, list):
        raise XPublicError("public X timeline response lacks results")
    expected = expected_handle.removeprefix("@").casefold()
    posts: list[PublicXPost] = []
    seen: set[str] = set()
    for result in results:
        if not isinstance(result, dict):
            continue
        author = result.get("author")
        if not isinstance(author, dict):
            continue
        owner = author
        handle = str(owner.get("screen_name") or "")
        if handle.casefold() != expected:
            reposted_by = result.get("reposted_by")
            if not isinstance(reposted_by, dict):
                continue
            owner = reposted_by
            handle = str(owner.get("screen_name") or "")
        post_id = str(result.get("id") or "")
        text = str(result.get("text") or "").strip()
        timestamp = result.get("created_timestamp")
        if handle.casefold() != expected or not post_id.isdecimal() or not text or post_id in seen:
            continue
        if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)):
            continue
        created_at = datetime.fromtimestamp(float(timestamp), tz=UTC)
        image_urls: list[str] = []
        media = result.get("media")
        if isinstance(media, dict):
            for item in media.get("all") or ():
                if not isinstance(item, dict):
                    continue
                url = str(item.get("thumbnail_url") or item.get("url") or "")
                parsed = urlparse(url)
                if (
                    parsed.scheme == "https"
                    and parsed.hostname
                    and parsed.hostname.endswith("twimg.com")
                    and url not in image_urls
                ):
                    image_urls.append(url)
        seen.add(post_id)
        posts.append(
            PublicXPost(
                post_id=post_id,
                created_at=created_at,
                text=text,
                url=str(result.get("url") or f"https://x.com/{handle}/status/{post_id}"),
                author_name=str(owner.get("name") or handle),
                author_handle=handle,
                avatar_url=str(owner.get("avatar_url") or "") or None,
                image_urls=tuple(image_urls),
            )
        )
    posts.sort(key=lambda post: (post.created_at, int(post.post_id)))
    return tuple(posts)


def _mime_type(content_type: str, url: str, data: bytes) -> str | None:
    declared = content_type.partition(";")[0].strip().lower()
    if declared in SUPPORTED_IMAGE_MIME_TYPES:
        return declared
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    guessed, _encoding = mimetypes.guess_type(urlparse(url).path)
    return guessed if guessed in SUPPORTED_IMAGE_MIME_TYPES else None


class HttpResponse:
    def __init__(self, body: bytes, content_type: str) -> None:
        self.body = body
        self.content_type = content_type


Request = Callable[[str, float, int], HttpResponse]


def public_request(url: str, timeout_seconds: float, maximum_bytes: int) -> HttpResponse:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "no-cache",
        },
    )

    def read(response: Any) -> HttpResponse:
        with response:
            body = response.read(maximum_bytes + 1)
            if len(body) > maximum_bytes:
                raise XPublicError(f"public X response exceeds {maximum_bytes} bytes")
            return HttpResponse(body, str(response.headers.get("Content-Type") or ""))

    try:
        # Re-read current proxy settings instead of reusing urlopen's cached opener.
        return read(urllib.request.build_opener().open(request, timeout=timeout_seconds))
    except urllib.error.HTTPError as error:
        raise XPublicError(f"public X request returned HTTP {error.code}") from error
    except (urllib.error.URLError, ConnectionError, OSError) as routed_error:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            return read(opener.open(request, timeout=timeout_seconds))
        except urllib.error.HTTPError as error:
            raise XPublicError(f"public X request returned HTTP {error.code}") from error
        except (urllib.error.URLError, ConnectionError, OSError) as direct_error:
            raise XPublicError(f"public X request failed: {direct_error}") from routed_error


class XPublicClient:
    def __init__(
        self,
        *,
        request_timeout_seconds: float,
        max_image_bytes: int,
        max_concurrency: int,
        request: Request = public_request,
    ) -> None:
        self.request_timeout_seconds = float(request_timeout_seconds)
        self.max_image_bytes = int(max_image_bytes)
        self.request = request
        self.semaphore = asyncio.Semaphore(int(max_concurrency))

    def _timeout(self, deadline: float | None) -> float:
        if deadline is None:
            return self.request_timeout_seconds
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("X collection deadline passed")
        return min(self.request_timeout_seconds, remaining)

    async def fetch_profile(
        self,
        handle: str,
        *,
        deadline: float | None,
    ) -> tuple[PublicXPost, ...]:
        normalized = handle.removeprefix("@").strip()
        async with self.semaphore:
            response = await asyncio.to_thread(
                self.request,
                f"https://api.fxtwitter.com/2/profile/{normalized}/statuses",
                self._timeout(deadline),
                TIMELINE_API_MAX_BYTES,
            )
        return parse_profile_statuses(response.body, normalized)

    async def fetch_avatar_url(
        self,
        handle: str,
        *,
        deadline: float | None,
    ) -> str | None:
        normalized = handle.removeprefix("@").strip()
        async with self.semaphore:
            response = await asyncio.to_thread(
                self.request,
                f"https://api.fxtwitter.com/2/profile/{normalized}",
                self._timeout(deadline),
                PROFILE_API_MAX_BYTES,
            )
        return parse_profile_avatar(response.body, normalized)

    async def download_image(
        self,
        url: str,
        *,
        post_id: str,
        index: int,
        deadline: float | None,
    ) -> DownloadedXImage:
        async with self.semaphore:
            response = await asyncio.to_thread(
                self.request,
                url,
                self._timeout(deadline),
                self.max_image_bytes,
            )
        mime_type = _mime_type(response.content_type, url, response.body)
        if mime_type is None or not response.body:
            raise XPublicError("public X media is not a supported image")
        extension = mimetypes.guess_extension(mime_type) or ".img"
        return DownloadedXImage(
            data=response.body,
            mime_type=mime_type,
            file_name=f"x-{post_id}-{index}{extension}",
        )
