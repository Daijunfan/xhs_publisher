"""Rotating structured JSON logging with conservative field redaction."""

from __future__ import annotations

import json
import logging
import logging.handlers
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

SENSITIVE_KEYS = frozenset(
    {"cookie", "token", "access_token", "refresh_token", "session", "password", "code"}
)


def _safe(value: Any, key: str = "") -> Any:
    if key.casefold() in SENSITIVE_KEYS:
        return "[redacted]"
    if isinstance(value, dict):
        return {str(child): _safe(item, str(child)) for child, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(item) for item in value]
    if isinstance(value, bytes):
        return f"[bytes:{len(value)}]"
    return value


class JsonFormatter(logging.Formatter):
    def __init__(self, timezone: str = "Asia/Shanghai") -> None:
        super().__init__()
        self.timezone = ZoneInfo(timezone)

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(self.timezone).isoformat(),
            "level": record.levelname,
            "component": record.name,
            "event": record.getMessage(),
        }
        context = getattr(record, "context", None)
        if isinstance(context, dict):
            payload.update(_safe(context))
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)[:4000]
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_logging(
    log_directory: Path,
    *,
    level: int = logging.INFO,
    timezone: str = "Asia/Shanghai",
    console: bool = True,
) -> None:
    log_directory.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)

    if console:
        stream = logging.StreamHandler()
        stream.setFormatter(JsonFormatter(timezone))
        root.addHandler(stream)

    file_handler = logging.handlers.RotatingFileHandler(
        log_directory / "pipeline.jsonl",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(JsonFormatter(timezone))
    root.addHandler(file_handler)


def log_event(logger: logging.Logger, level: int, event: str, **context: Any) -> None:
    logger.log(level, event, extra={"context": context})
