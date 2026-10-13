"""Pure data contracts shared by plugins, pipeline stages, and sinks."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .states import WorkTopic


@dataclass(frozen=True, slots=True)
class AttachmentInput:
    mime_type: str
    file_name: str
    data: bytes | Path
    width: int | None = None
    height: int | None = None


@dataclass(frozen=True, slots=True)
class StoredAttachment:
    attachment_id: str
    record_id: str
    index: int
    mime_type: str
    file_name: str
    relative_path: str
    byte_size: int
    sha256: str
    width: int | None = None
    height: int | None = None

    def absolute_path(self, runtime_root: Path) -> Path:
        return (runtime_root / self.relative_path).resolve()


@dataclass(frozen=True, slots=True)
class SourceRecord:
    record_id: str
    source_id: str
    target_id: str
    plugin_id: str
    external_id: str
    content_type: str
    occurred_at: datetime
    observed_at: datetime
    text: str
    source_name: str
    title: str = ""
    source_url: str | None = None
    group_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    attachments: tuple[AttachmentInput, ...] = ()


@dataclass(frozen=True, slots=True)
class CollectBatch:
    source_id: str
    target_id: str
    records: tuple[SourceRecord, ...]
    checkpoint: dict[str, Any]
    messages_seen: int = 0
    errors: int = 0
    work_topic: WorkTopic = WorkTopic.RECORD_COLLECTED
    preserve_existing: bool = False


@dataclass(frozen=True, slots=True)
class NewsCandidate:
    record_id: str
    source_name: str
    occurred_at: datetime
    text: str
    group_record_ids: tuple[str, ...]
    attachments: tuple[StoredAttachment, ...]
    avatar: StoredAttachment | None = None
    plugin_id: str = ""
    title: str = ""


@dataclass(frozen=True, slots=True)
class EditorialItem:
    record_id: str
    headline: str
    text: str
    star_rating: int
    summary: str = ""
    translation_required: bool | None = None


@dataclass(frozen=True, slots=True)
class Editorial:
    title: str
    body: str
    tags: tuple[str, ...]
    items: tuple[EditorialItem, ...]


@dataclass(frozen=True, slots=True)
class PublishNote:
    title: str
    body: str
    images: tuple[Path, ...]
    allow_empty_text: bool = False
    topics: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PublishResult:
    ok: bool
    confirmed_in_note_manager: bool = False
    submission_started: bool = False
    detail: dict[str, Any] = field(default_factory=dict)
