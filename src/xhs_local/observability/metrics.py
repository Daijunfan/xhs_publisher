"""Small in-process counters and gauges for local status reporting."""

from __future__ import annotations

import threading
from collections import Counter
from typing import Any


class LocalMetrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: Counter[str] = Counter()
        self._gauges: dict[str, int | float | str | bool | None] = {}

    def increment(self, name: str, value: int = 1) -> None:
        with self._lock:
            self._counters[name] += value

    def gauge(self, name: str, value: int | float | str | bool | None) -> None:
        with self._lock:
            self._gauges[name] = value

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {"counters": dict(self._counters), "gauges": dict(self._gauges)}
