"""Disabled-by-default local retention loop."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable


class RetentionWorker:
    def __init__(
        self,
        enabled: bool | Callable[[], bool],
        run_once: Callable[[], object],
        *,
        interval_seconds: float = 24 * 60 * 60,
    ) -> None:
        self.enabled = enabled
        self.run_once = run_once
        self.interval_seconds = interval_seconds
        self.log = logging.getLogger(__name__)

    async def run(self) -> None:
        while True:
            enabled = self.enabled() if callable(self.enabled) else self.enabled
            if enabled:
                try:
                    await asyncio.to_thread(self.run_once)
                except Exception:
                    self.log.exception("local maintenance failed")
            await asyncio.sleep(self.interval_seconds)
