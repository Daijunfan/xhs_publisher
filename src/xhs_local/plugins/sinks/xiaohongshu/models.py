"""Internal request and result values for the Safari backend."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from .errors import PublishPreflightError


class BackendPublishStatus(StrEnum):
    PUBLISHED = "published"


@dataclass(frozen=True, slots=True)
class BackendPublishRequest:
    title: str
    body: str
    image_paths: tuple[Path, ...]
    topics: tuple[str, ...] = ()
    allow_empty_text: bool = False
    require_new_title_occurrence: bool = False
    max_images: int = 18
    timeout_seconds: float = 90.0

    @property
    def effective_body(self) -> str:
        return self.body

    def validate(self) -> None:
        if len(self.title) > 20 or (not self.allow_empty_text and not self.title):
            raise PublishPreflightError("title must contain 1-20 characters")
        if len(self.effective_body) > 1000:
            raise PublishPreflightError("body must contain at most 1000 characters")
        if not self.allow_empty_text and not self.body:
            raise PublishPreflightError("body must not be empty")
        if not 1 <= len(self.image_paths) <= self.max_images:
            raise PublishPreflightError(f"a note requires between 1 and {self.max_images} images")
        if self.timeout_seconds <= 0:
            raise PublishPreflightError("timeout_seconds must be positive")
        if len(self.topics) > 8 or any(
            not topic or topic.startswith("#") or any(char.isspace() for char in topic)
            for topic in self.topics
        ):
            raise PublishPreflightError("topics must be non-empty names without # or whitespace")
        supported = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
        for image_path in self.image_paths:
            if not image_path.is_file():
                raise PublishPreflightError(f"image does not exist: {image_path}")
            if image_path.suffix.lower() not in supported:
                raise PublishPreflightError(f"unsupported image type: {image_path.suffix}")


@dataclass(frozen=True, slots=True)
class BackendPublishResult:
    status: BackendPublishStatus
    page_url: str
    message: str
    excerpt: str
