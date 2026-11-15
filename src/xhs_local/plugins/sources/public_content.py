"""Bounded public-content transport and mapping shared by knowledge sources."""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlsplit

from xhs_local.core.contracts import AttachmentInput, CollectBatch, SourceRecord
from xhs_local.core.errors import (
    AuthenticationRequired,
    ErrorClass,
    TransientError,
    ValidationFailure,
)
from xhs_local.core.identifiers import stable_record_id
from xhs_local.plugins.contracts import CollectRequest, PluginContractError, SourcePluginContext

USER_AGENT = "AexusBot/0.58 (+https://github.com/Daijunfan/Aexus-Bot)"
IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}


@dataclass(frozen=True)
class PublicResponse:
    body: bytes
    content_type: str = "application/json"
    url: str = ""


@dataclass(frozen=True)
class PublicPost:
    id: str
    time: datetime
    text: str
    title: str
    url: str
    author: str
    author_url: str | None = None
    images: tuple[str, ...] = ()
    avatar: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


Request = Callable[[str, float, int], PublicResponse]


class PublicRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        parsed = urlsplit(new_url)
        hosts = ("linkedin.com", "licdn.com", "zhihu.com", "zhimg.com")
        if (
            parsed.scheme != "https"
            or parsed.username
            or parsed.password
            or parsed.port not in (None, 443)
            or not any(
                parsed.hostname == host or (parsed.hostname or "").endswith("." + host)
                for host in hosts
            )
        ):
            raise ValidationFailure("Public source redirect is outside supported platforms")
        return super().redirect_request(request, fp, code, message, headers, new_url)


def public_request(url: str, timeout: float, maximum: int) -> PublicResponse:
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept-Language": "en,zh-CN;q=0.8"}
    )
    try:
        with urllib.request.build_opener(PublicRedirect()).open(
            request, timeout=timeout
        ) as response:
            body = response.read(maximum + 1)
            if len(body) > maximum:
                raise ValidationFailure("Public source response exceeds its size limit")
            return PublicResponse(body, str(response.headers.get("Content-Type", "")), response.url)
    except urllib.error.HTTPError as error:
        if error.code in {401, 403, 999}:
            raise AuthenticationRequired(
                f"Public source requires authorized access (HTTP {error.code})"
            ) from error
        if error.code == 429:
            limited = TransientError("Public source returned HTTP 429; collection must back off")
            limited.error_class = ErrorClass.RATE_LIMITED
            raise limited from error
        raise TransientError(f"Public source returned HTTP {error.code}") from error
    except (urllib.error.URLError, OSError) as error:
        raise TransientError("Public source network request failed") from error


class PublicClient:
    def __init__(
        self,
        hosts: tuple[str, ...],
        *,
        request: Request = public_request,
        timeout: float = 20,
        concurrency: int = 2,
    ):
        self.hosts, self.request, self.timeout = hosts, request, timeout
        self.semaphore = asyncio.Semaphore(concurrency)
        self.images: dict[str, AttachmentInput] = {}
        self.image_bytes = 0

    def allowed(self, url: str) -> bool:
        parsed = urlsplit(url)
        return (
            parsed.scheme == "https"
            and not parsed.username
            and not parsed.password
            and parsed.port in (None, 443)
            and any(
                parsed.hostname == host or (parsed.hostname or "").endswith("." + host)
                for host in self.hosts
            )
        )

    async def get(
        self, url: str, deadline: float | None = None, maximum: int = 3_000_000
    ) -> PublicResponse:
        if not self.allowed(url):
            raise ValidationFailure("Public source URL is outside its platform")
        async with self.semaphore:
            remaining = (
                self.timeout if deadline is None else min(self.timeout, deadline - time.monotonic())
            )
            if remaining <= 0:
                raise TimeoutError("Public source collection deadline passed")
            response = await asyncio.to_thread(self.request, url, remaining, maximum)
        if response.url and not self.allowed(response.url):
            raise AuthenticationRequired(
                "Public source redirected away from its authorized platform"
            )
        return response

    async def json(self, url: str, deadline: float | None = None) -> dict:
        response = await self.get(url, deadline)
        try:
            value = json.loads(response.body)
            if not isinstance(value, dict):
                raise ValueError("Expected an object")
            return value
        except (ValueError, UnicodeDecodeError) as error:
            raise ValidationFailure("Public source returned invalid JSON") from error

    async def image(self, url: str, deadline: float | None = None) -> AttachmentInput:
        if url in self.images:
            return self.images[url]
        response = await self.get(url, deadline, 8 * 1024 * 1024)
        mime = response.content_type.split(";", 1)[0].lower()
        if mime not in IMAGE_TYPES:
            raise ValidationFailure("Public source media is not a supported image")
        extension = {
            "image/jpeg": "jpg",
            "image/png": "png",
            "image/webp": "webp",
            "image/gif": "gif",
        }[mime]
        image = AttachmentInput(
            mime_type=mime,
            file_name=hashlib.sha256(response.body).hexdigest()[:24] + "." + extension,
            data=response.body,
        )
        if self.image_bytes + len(response.body) > 16 * 1024 * 1024:
            self.images.clear()
            self.image_bytes = 0
        self.images[url] = image
        self.image_bytes += len(response.body)
        return image


async def collect_public(
    context: SourcePluginContext,
    client: PublicClient,
    request: CollectRequest,
    posts: list[PublicPost],
    plugin: str,
) -> CollectBatch:
    if request.source_id != context.source_id or request.observed_at.tzinfo is None:
        raise PluginContractError(
            "Public collection requires its own source and an aware observation time"
        )
    request.ensure_active()
    now = request.observed_at.astimezone(UTC)
    cutoff = now - timedelta(hours=float(context.options.get("lookback_hours", 168)))
    fingerprints = dict(request.checkpoint.get("fingerprints", {}))
    records, errors = [], 0
    for post in sorted(posts, key=lambda entry: (entry.time, entry.id)):
        request.ensure_active()
        if not cutoff <= post.time <= now:
            continue
        digest = hashlib.sha256(
            json.dumps(
                [
                    post.text,
                    post.title,
                    post.time.isoformat(),
                    [urlsplit(url).path for url in post.images],
                ],
                ensure_ascii=False,
            ).encode()
        ).hexdigest()
        if fingerprints.get(post.id) == digest:
            continue
        attachments, downloaded, avatar_index, media_failed = [], [], None, False
        media = [
            (False, url)
            for url in post.images[: int(context.options.get("max_images_per_post", 4))]
        ]
        if post.avatar:
            media.insert(0, (True, post.avatar))
        for is_avatar, url in media:
            try:
                image = await client.image(url, request.deadline)
                if is_avatar:
                    avatar_index = len(attachments)
                else:
                    downloaded.append(url)
                attachments.append(image)
            except asyncio.CancelledError:
                raise
            except (
                AuthenticationRequired,
                TransientError,
                ValidationFailure,
                TimeoutError,
            ) as error:
                errors += 1
                media_failed |= not isinstance(error, ValidationFailure)
                context.log(
                    "public_source_media_unavailable",
                    {
                        "platform": plugin,
                        "target_id": request.target.id,
                        "external_id": post.id,
                        "error_class": str(getattr(error, "error_class", "TIMEOUT")),
                    },
                )
        records.append(
            SourceRecord(
                record_id=stable_record_id(request.source_id, request.target.id, post.id),
                source_id=request.source_id,
                target_id=request.target.id,
                plugin_id=plugin,
                external_id=post.id,
                content_type="tech_news",
                occurred_at=post.time,
                observed_at=now,
                text=post.text,
                title=post.title,
                source_name=request.target.name,
                source_url=post.url,
                payload={
                    **post.metadata,
                    "author_name": post.author,
                    "author_url": post.author_url,
                    "image_urls": list(post.images),
                    "downloaded_image_urls": downloaded,
                    **(
                        {"avatar_attachment_index": avatar_index}
                        if avatar_index is not None
                        else {}
                    ),
                },
                attachments=tuple(attachments),
            )
        )
        # Retry unavailable media; a rejected size/type cannot pass the publication contract.
        if not media_failed:
            fingerprints[post.id] = digest
    return CollectBatch(
        source_id=request.source_id,
        target_id=request.target.id,
        records=tuple(records),
        checkpoint={"fingerprints": dict(list(fingerprints.items())[-500:])},
        messages_seen=len(posts),
        errors=errors,
    )
