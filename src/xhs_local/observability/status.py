"""Atomic local status snapshot used by `xhs status`."""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


class StatusStore:
    def __init__(self, path: Path, timezone: str = "Asia/Shanghai") -> None:
        self.path = path
        self.timezone = ZoneInfo(timezone)
        self._lock = threading.Lock()
        self._state: dict[str, Any] = {
            "pid": os.getpid(),
            "started_at": datetime.now(self.timezone).isoformat(),
            "timezone": timezone,
            "ready": False,
        }

    def update(self, **values: Any) -> None:
        with self._lock:
            self._state.update(values)
            self._state["updated_at"] = datetime.now(self.timezone).isoformat()
            payload = json.dumps(self._state, ensure_ascii=False, indent=2, sort_keys=True)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_name(f".{self.path.name}.{os.getpid()}.tmp")
            temporary.write_text(payload, encoding="utf-8")
            temporary.replace(self.path)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._state)


def read_status(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None
