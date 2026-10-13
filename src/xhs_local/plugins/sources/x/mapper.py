"""Pure mapping from public X posts to the shared source contract."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from xhs_local.core.contracts import AttachmentInput, SourceRecord
from xhs_local.core.identifiers import stable_record_id
from xhs_local.plugins.contracts import PluginTarget


@dataclass(frozen=True, slots=True)
class PublicXPost:
    post_id: str
    created_at: datetime
    text: str
    url: str
    author_name: str
    author_handle: str
    avatar_url: str | None = None
    image_urls: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DownloadedXImage:
    data: bytes
    mime_type: str
    file_name: str


def map_post(
    post: PublicXPost,
    *,
    source_id: str,
    target: PluginTarget,
    observed_at: datetime,
    avatar: DownloadedXImage | None = None,
    images: tuple[DownloadedXImage, ...] = (),
) -> SourceRecord:
    downloaded = (*((avatar,) if avatar is not None else ()), *images)
    attachments = tuple(
        AttachmentInput(
            mime_type=image.mime_type,
            file_name=image.file_name,
            data=image.data,
        )
        for image in downloaded
    )
    handle = target.locator.removeprefix("@").strip()
    return SourceRecord(
        record_id=stable_record_id(source_id, target.id, post.post_id),
        source_id=source_id,
        target_id=target.id,
        plugin_id="x",
        external_id=post.post_id,
        content_type="tech_news",
        occurred_at=post.created_at,
        observed_at=observed_at,
        text=post.text,
        source_name=target.name,
        source_url=f"https://x.com/{handle}/status/{post.post_id}",
        payload={
            "post_id": post.post_id,
            "author_name": post.author_name,
            "author_handle": handle,
            **({"avatar_attachment_index": 0} if avatar is not None else {}),
        },
        attachments=attachments,
    )
