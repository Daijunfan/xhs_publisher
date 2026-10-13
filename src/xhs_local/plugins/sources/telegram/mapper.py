"""Pure Telegram message-to-SourceRecord mapping."""

from __future__ import annotations

import mimetypes
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from xhs_local.core.contracts import AttachmentInput, SourceRecord
from xhs_local.core.identifiers import stable_record_id
from xhs_local.plugins.contracts import PluginTarget

SUPPORTED_IMAGE_MIME_TYPES = frozenset({"image/png", "image/jpeg", "image/webp", "image/gif"})


@dataclass(frozen=True, slots=True)
class DownloadedMedia:
    data: bytes | Path
    mime_type: str
    file_name: str
    width: int | None = None
    height: int | None = None


def image_mime_type(message: Any) -> str | None:
    if getattr(message, "photo", None) is not None:
        file = getattr(message, "file", None)
        mime = getattr(file, "mime_type", None) if file is not None else None
        return mime.lower() if isinstance(mime, str) and mime.startswith("image/") else "image/jpeg"
    file = getattr(message, "file", None)
    mime = getattr(file, "mime_type", None) if file is not None else None
    if isinstance(mime, str) and mime.lower() in SUPPORTED_IMAGE_MIME_TYPES:
        return mime.lower()
    return None


def document_message(message: Any) -> bool:
    file = getattr(message, "file", None)
    mime = str(getattr(file, "mime_type", "") or "").lower()
    return getattr(message, "document", None) is not None and not mime.startswith(
        ("image/", "video/", "audio/")
    )


def is_eligible_message(message: Any, *, documents: bool = False) -> bool:
    return (
        bool(str(getattr(message, "message", "") or "").strip())
        or image_mime_type(message) is not None
        or documents
        and document_message(message)
    )


def safe_media_name(value: Any, *, channel_id: int, message_id: int, mime_type: str) -> str:
    configured = Path(str(value).replace("\x00", "")).name.strip() if value else ""
    if configured and configured not in {".", ".."}:
        return configured[:240]
    extension = mimetypes.guess_extension(mime_type) or ".img"
    return f"telegram-{channel_id}-{message_id}{extension}"


def map_message(
    message: Any,
    *,
    source_id: str,
    target: PluginTarget,
    channel_id: int,
    observed_at: datetime,
    media: DownloadedMedia | None = None,
    thumbnail: DownloadedMedia | None = None,
) -> SourceRecord:
    message_id = int(message.id)
    occurred_at = message.date
    if not isinstance(occurred_at, datetime):
        raise ValueError(f"Telegram message {message_id} has no valid date")
    if occurred_at.tzinfo is None:
        occurred_at = occurred_at.replace(tzinfo=UTC)
    grouped_id = getattr(message, "grouped_id", None)
    group_id = str(int(grouped_id)) if grouped_id is not None else None
    attachment = (
        (
            AttachmentInput(
                mime_type=media.mime_type,
                file_name=media.file_name,
                data=media.data,
                width=media.width,
                height=media.height,
            ),
        )
        if media is not None
        else ()
    )
    if thumbnail is not None:
        attachment += (
            AttachmentInput(
                mime_type=thumbnail.mime_type, file_name=thumbnail.file_name, data=thumbnail.data
            ),
        )
    external_id = str(message_id)
    locator = target.locator.removeprefix("@").strip()
    return SourceRecord(
        record_id=stable_record_id(source_id, target.id, external_id),
        source_id=source_id,
        target_id=target.id,
        plugin_id="telegram",
        external_id=external_id,
        content_type="tech_news",
        occurred_at=occurred_at,
        observed_at=observed_at,
        title=media.file_name
        if media is not None and not media.mime_type.startswith("image/")
        else "",
        text=str(getattr(message, "message", "") or ""),
        source_name=target.name,
        source_url=f"https://t.me/{locator}/{message_id}",
        group_id=group_id,
        payload={
            **({"cloud_document_channel": True} if target.options.get("collect_documents") else {}),
            **(
                {
                    "document_thumbnail_index": 1,
                    "document_thumbnail_origin": "telegram"
                    if getattr(getattr(message, "document", None), "thumbs", None)
                    else "generated",
                }
                if thumbnail is not None
                else {}
            ),
            "channel_id": channel_id,
            "message_id": message_id,
            "grouped_id": int(grouped_id) if grouped_id is not None else None,
            "publication_metadata": {"telegram": {
                **({"groupId": group_id} if group_id is not None else {}),
                **(
                    {"views": int(message.views)}
                    if isinstance(getattr(message, "views", None), int)
                    else {}
                ),
                "reactions": [
                    {"emoji": reaction.reaction.emoticon, "count": reaction.count}
                    for reaction in (
                        getattr(getattr(message, "reactions", None), "results", None) or []
                    )
                    if getattr(reaction.reaction, "emoticon", None)
                ],
            }},
        },
        attachments=attachment,
    )
