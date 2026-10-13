"""Narrow contracts shared by source plugins and the source scheduler.

Plugins receive every durable input in :class:`CollectRequest` and return every
durable output in ``CollectBatch``.  They never receive a database, queue, or
publisher reference.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from xhs_local.core.contracts import CollectBatch, PublishNote, PublishResult


class PluginContractError(ValueError):
    """A manifest, target, or plugin class violates the public contract."""


@dataclass(frozen=True, slots=True)
class PluginTarget:
    """Platform-neutral target passed to every source plugin."""

    id: str
    locator: str
    name: str
    options: Mapping[str, Any] = field(default_factory=dict)


class CancellationToken:
    """Cooperative cancellation shared without exposing scheduler internals."""

    __slots__ = ("_event",)

    def __init__(self) -> None:
        self._event = asyncio.Event()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def cancel(self) -> None:
        self._event.set()

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise asyncio.CancelledError

    async def wait(self) -> None:
        await self._event.wait()


@dataclass(frozen=True, slots=True)
class CollectRequest:
    """Complete input for one bounded target collection call."""

    source_id: str
    target: PluginTarget
    checkpoint: Mapping[str, Any]
    observed_at: datetime
    deadline: float | None = None
    cancellation: CancellationToken = field(default_factory=CancellationToken)

    def remaining_seconds(self, *, now: Callable[[], float] = time.monotonic) -> float | None:
        if self.deadline is None:
            return None
        return max(0.0, self.deadline - now())

    def ensure_active(self) -> None:
        self.cancellation.raise_if_cancelled()
        if self.deadline is not None and self.deadline <= time.monotonic():
            raise TimeoutError(f"collection deadline passed for target {self.target.id}")


@dataclass(frozen=True, slots=True)
class HealthReport:
    """Read-only plugin health result suitable for status output."""

    ok: bool
    message: str = "ok"
    detail: Mapping[str, Any] = field(default_factory=dict)


LogEvent = Callable[[str, Mapping[str, Any]], None]


def _discard_log(_event: str, _fields: Mapping[str, Any]) -> None:
    return None


@dataclass(frozen=True, slots=True)
class SourcePluginContext:
    """Capabilities allowed inside a SourcePlugin.

    ``options`` contains only that plugin's validated options.  Paths are
    already resolved by the composition root, so a plugin never reads the full
    application configuration.
    """

    source_id: str
    runtime_root: Path
    options: Mapping[str, Any]
    log: LogEvent = _discard_log


@runtime_checkable
class SourcePlugin(Protocol):
    """The only interface the collector may use for any source platform."""

    @classmethod
    def validate_target(cls, target: PluginTarget) -> None:
        """Validate without network, file writes, or global state changes."""

    async def healthcheck(
        self, target: PluginTarget, deadline: float | None = None
    ) -> HealthReport:
        """Check minimal read-only access without producing records."""

    async def collect(self, request: CollectRequest) -> CollectBatch:
        """Collect one target from its supplied checkpoint."""

    async def close(self) -> None:
        """Release temporary resources; repeated calls must be safe."""


@runtime_checkable
class SinkPlugin(Protocol):
    """Lifecycle shared by every capability-specific remote Sink."""

    async def preflight(self) -> HealthReport:
        """Perform a read-only machine/session check."""

    async def close(self) -> None:
        """Release temporary resources; repeated calls must be safe."""


@runtime_checkable
class NoteSinkPlugin(SinkPlugin, Protocol):
    """Fenced image-note publication capability."""

    async def publish(
        self,
        note: PublishNote,
        *,
        require_new_title_occurrence: bool = False,
    ) -> PublishResult:
        """Perform one fenced remote publication."""

    async def reconcile(self, operation: Mapping[str, Any]) -> PublishResult | None:
        """Check an ambiguous operation without submitting it again."""


@runtime_checkable
class UploadShareSinkPlugin(SinkPlugin, Protocol):
    """Upload-and-share capability used by local document delivery."""

    async def async_upload_and_share(
        self,
        paths: list[Path],
        folder_key: str,
    ) -> Mapping[str, Any]:
        """Upload exact local files and return one confirmed share."""
