"""Content-type registry; only existing production behavior is active."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


class ContentRouter:
    def __init__(self, handlers: dict[str, Callable[[Any], Any]] | None = None) -> None:
        self._handlers = dict(handlers or {})

    def register(self, content_type: str, handler: Callable[[Any], Any]) -> None:
        if not content_type or content_type in self._handlers:
            raise ValueError(f"content type is empty or already registered: {content_type}")
        self._handlers[content_type] = handler

    def resolve(self, content_type: str) -> Callable[[Any], Any]:
        try:
            return self._handlers[content_type]
        except KeyError as error:
            raise ValueError(f"unsupported content type: {content_type}") from error
