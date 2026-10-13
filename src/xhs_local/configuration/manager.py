"""Validate complete candidates and atomically swap one in-process snapshot."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path

from .diff import snapshot_diff
from .history import ConfigHistory
from .loader import ConfigSnapshot, ConfigurationError, load_snapshot

Preflight = Callable[[ConfigSnapshot], Awaitable[dict[str, object]]]
Apply = Callable[[ConfigSnapshot, ConfigSnapshot], Awaitable[None]]


class ConfigManager:
    def __init__(
        self,
        config_root: Path,
        history: ConfigHistory,
        preflight: Preflight,
        *,
        debounce_seconds: float = 0.25,
    ) -> None:
        if debounce_seconds < 0:
            raise ValueError("debounce_seconds must not be negative")
        self.config_root = config_root.resolve()
        self.history = history
        self.preflight = preflight
        self.debounce_seconds = debounce_seconds
        self.current: ConfigSnapshot | None = None
        self._lock = asyncio.Lock()
        self._last_mtimes: tuple[int, ...] | None = None

    async def load_initial(self) -> tuple[ConfigSnapshot, bool]:
        try:
            candidate = load_snapshot(self.config_root)
            degraded = False
        except ConfigurationError:
            candidate = await asyncio.to_thread(self.history.last_active)
            if candidate is None:
                raise
            degraded = True
        report = await self.preflight(candidate)
        await asyncio.to_thread(
            self.history.save_candidate,
            candidate,
            source="startup",
            diff=None,
            preflight=report,
        )
        await asyncio.to_thread(self.history.activate, candidate.revision)
        self.current = candidate
        self._last_mtimes = self._mtimes()
        return candidate, degraded

    async def refresh(self, apply: Apply) -> ConfigSnapshot | None:
        if self.current is None:
            raise RuntimeError("configuration manager has not been initialized")
        mtimes = self._mtimes()
        if mtimes == self._last_mtimes:
            return None
        if self.debounce_seconds:
            await asyncio.sleep(self.debounce_seconds)
        self._last_mtimes = self._mtimes()
        candidate = load_snapshot(self.config_root)
        if candidate.revision == self.current.revision:
            return None
        report = await self.preflight(candidate)
        previous = self.current
        diff = snapshot_diff(previous, candidate)
        await asyncio.to_thread(
            self.history.save_candidate,
            candidate,
            source="watcher",
            diff=diff,
            preflight=report,
        )
        async with self._lock:
            await apply(previous, candidate)
            await asyncio.to_thread(self.history.activate, candidate.revision)
            self.current = candidate
            self._last_mtimes = self._mtimes()
        return candidate

    def _mtimes(self) -> tuple[int, ...]:
        return tuple(
            (self.config_root / name).stat().st_mtime_ns
            for name in ("app.yaml", "sources.yaml", "publishing.yaml")
        )
