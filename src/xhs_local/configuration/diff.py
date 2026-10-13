"""Readable immutable configuration differences."""

from __future__ import annotations

from typing import Any

from .loader import ConfigSnapshot


def snapshot_diff(previous: ConfigSnapshot, current: ConfigSnapshot) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name in ("app", "sources", "publishing"):
        before = getattr(previous, name).model_dump(mode="json")
        after = getattr(current, name).model_dump(mode="json")
        if before != after:
            result[name] = {"before": before, "after": after}
    return result
