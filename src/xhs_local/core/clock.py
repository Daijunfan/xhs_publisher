"""Clock abstraction for deterministic scheduling tests."""

from __future__ import annotations

import time
from datetime import UTC, datetime


def utc_iso(value: datetime | None = None) -> str:
    """Return the legacy-compatible UTC millisecond representation."""

    current = value or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    return current.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class Clock:
    def now(self) -> datetime:
        return datetime.now(UTC)

    def monotonic(self) -> float:
        return time.monotonic()
