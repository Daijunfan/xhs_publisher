"""Platform-neutral per-target scheduling in the single asyncio process."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from xhs_local.configuration.loader import ConfigSnapshot
from xhs_local.plugins.contracts import CancellationToken, CollectRequest
from xhs_local.plugins.registry import PreparedSource, SourcePluginRegistry
from xhs_local.storage.checkpoints import CheckpointRepository

from .collector import Collector

BatchCallback = Callable[[str, str, int, bool, bool], Awaitable[None]]
PublishCallback = Callable[[], Awaitable[None]]
WALL_CLOCK_RECHECK_SECONDS = 30.0
SOURCE_CLOCK_RECHECK_SECONDS = 300.0
COLLECTION_TIMEOUT_SECONDS = 180.0


def _failure_delay(interval: float, failures: int) -> float:
    return min(interval * (2 ** min(failures, 4)), 300)


class SourceScheduler:
    def __init__(
        self,
        snapshot: ConfigSnapshot,
        registry: SourcePluginRegistry,
        checkpoints: CheckpointRepository,
        collector: Collector,
        on_batch: BatchCallback,
    ) -> None:
        self.snapshot = snapshot
        self.registry = registry
        self.checkpoints = checkpoints
        self.collector = collector
        self.on_batch = on_batch
        self.tasks: dict[str, asyncio.Task[None]] = {}
        self.plugins: dict[str, Any] = {}
        self.activation: dict[str, dict[str, Any]] = {}
        self.tokens: dict[str, CancellationToken] = {}
        self.log = logging.getLogger(__name__)
        self.stopping = False
        self.status: dict[str, dict[str, Any]] = {}
        self.display_timezone = ZoneInfo(snapshot.app.timezone)

    def _status_now(self) -> datetime:
        return datetime.now(self.display_timezone)

    def _plugin_log(self, event: str, fields: dict[str, Any]) -> None:
        self.log.warning(event, extra={"context": fields})

    async def start(self) -> None:
        await self.update_targets(self.snapshot)

    async def update_targets(self, snapshot: ConfigSnapshot) -> None:
        """Apply changed subscriptions without restarting unrelated target loops."""
        old_sources = {s.id: s for s in self.snapshot.sources.sources}
        sources = {s.id: s for s in snapshot.sources.sources if s.enabled}
        prepared_sources = {
            source.id: self.registry.prepare(
                source,
                config_root=snapshot.config_root,
                runtime_root=snapshot.runtime_root,
                log=self._plugin_log,
            )
            for source in sources.values()
        }
        old_targets = {
            t.id: (s.id, t, t.poll_seconds or s.poll_seconds)
            for s in self.snapshot.sources.sources
            for t in s.targets
            if s.enabled and t.enabled
        }
        targets = {
            t.id: (s.id, t, t.poll_seconds or s.poll_seconds)
            for s in sources.values()
            for t in s.targets
            if t.enabled
        }
        replace_plugins = {
            source_id
            for source_id in self.plugins
            if source_id not in sources
            or old_sources[source_id].options != sources[source_id].options
            or old_sources[source_id].plugin != sources[source_id].plugin
        }
        removed = [
            target_id
            for target_id in self.tasks
            if targets.get(target_id) != old_targets.get(target_id)
            or self.status[target_id]["source_id"] in replace_plugins
        ]
        for target_id in removed:
            self.tokens[target_id].cancel()
            self.tasks[target_id].cancel()
        await asyncio.gather(*(self.tasks[t] for t in removed), return_exceptions=True)
        for target_id in removed:
            self.tasks.pop(target_id)
            self.tokens.pop(target_id)
            self.status.pop(target_id)
        for source_id in replace_plugins:
            await self.plugins.pop(source_id).close()
        self.snapshot = snapshot
        pending = []
        for source in sources.values():
            prepared = prepared_sources[source.id]
            if source.id not in self.plugins:
                self.plugins[source.id] = self.registry.create(prepared)
            plugin = self.plugins[source.id]
            activation_group = prepared.context.options.get("activation_group")
            if activation_group:
                self.activation[source.id] = await asyncio.to_thread(
                    self.checkpoints.initialize,
                    str(activation_group),
                    "__activation__",
                    {"activated_at": datetime.now(UTC).isoformat()},
                )
            for target in prepared.targets:
                configured = next(t for t in source.targets if t.id == target.id)
                interval = float(configured.poll_seconds or source.poll_seconds)
                if target.id in self.tasks:
                    continue
                token = CancellationToken()
                self.tokens[target.id] = token
                self.status[target.id] = {
                    "target_id": target.id,
                    "source_id": source.id,
                    "plugin_id": source.plugin,
                    "enabled": True,
                    "failures": 0,
                }
                pending.append((prepared, plugin, target, interval, token))
        # Register every source before collection can occupy network/thread-pool resources.
        for prepared, plugin, target, interval, token in pending:
            self.tasks[target.id] = asyncio.create_task(
                self._target_loop(prepared, plugin, target, interval, token),
                name=f"source-{target.id}",
            )

    async def _wait_until(self, target_id: str, token: CancellationToken, deadline: datetime):
        self.status[target_id]["next_run_at"] = deadline.isoformat()
        while not self.stopping and not token.cancelled:
            remaining = (deadline - self._status_now()).total_seconds()
            if remaining <= 0:
                break
            with suppress(TimeoutError):
                await asyncio.wait_for(
                    token.wait(), timeout=min(remaining, SOURCE_CLOCK_RECHECK_SECONDS)
                )

    async def _target_loop(
        self,
        prepared: PreparedSource,
        plugin: Any,
        target: Any,
        interval: float,
        token: CancellationToken,
    ) -> None:
        initial = True
        failures = 0
        youtube = self.status[target.id].get("plugin_id") == "youtube"
        if youtube:
            checkpoint = await asyncio.to_thread(
                self.checkpoints.get, prepared.context.source_id, target.id
            )
            if checkpoint and checkpoint.get("last_polled_at"):
                due = datetime.fromisoformat(checkpoint["last_polled_at"]) + timedelta(
                    seconds=interval
                )
                await self._wait_until(target.id, token, due.astimezone(self.display_timezone))
        while not self.stopping and not token.cancelled:
            started = time.monotonic()
            count = 0
            succeeded = False
            try:
                checkpoint = await asyncio.to_thread(
                    self.checkpoints.get,
                    prepared.context.source_id,
                    target.id,
                )
                request = CollectRequest(
                    source_id=prepared.context.source_id,
                    target=target,
                    checkpoint={
                        **self.activation.get(prepared.context.source_id, {}),
                        **(checkpoint or {}),
                    },
                    observed_at=datetime.now(UTC),
                    deadline=time.monotonic()
                    + float(
                        target.options.get(
                            "collect_timeout_seconds",
                            min(max(90, interval), COLLECTION_TIMEOUT_SECONDS),
                        )
                    ),
                    cancellation=token,
                )
                async with asyncio.timeout_at(request.deadline):
                    batch = await plugin.collect(request)
                result = await self.collector.commit(
                    batch,
                    config_revision=self.snapshot.revision,
                )
                inserted = set(result.inserted_record_ids)
                count = len(
                    {
                        record.group_id or record.record_id
                        for record in batch.records
                        if record.record_id in inserted
                    }
                )
                failures = 0
                succeeded = True
                self.status[target.id].update(
                    {
                        "last_success_at": self._status_now().isoformat(),
                        "last_new_items": count,
                        "failures": 1 if batch.errors else 0,
                        "last_error": f"{batch.errors} items failed; see structured log"
                        if batch.errors
                        else None,
                    }
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                failures += 1
                self.status[target.id].update(
                    {
                        "last_failure_at": self._status_now().isoformat(),
                        "failures": failures,
                        "last_error": "collection failed; see structured log",
                    }
                )
                self.log.exception(
                    "source target failed",
                    extra={
                        "context": {
                            "source_id": prepared.context.source_id,
                            "target_id": target.id,
                            "failures": failures,
                        }
                    },
                )
            finally:
                await self.on_batch(
                    prepared.context.source_id,
                    target.id,
                    count,
                    initial,
                    succeeded,
                )
                initial = False
            delay = _failure_delay(interval, failures) if failures else interval
            if youtube:
                delay = max(interval, delay)
            remaining = max(0.0, delay - (time.monotonic() - started))
            deadline = self._status_now() + timedelta(seconds=remaining)
            await self._wait_until(target.id, token, deadline)

    async def stop(self) -> None:
        self.stopping = True
        for token in self.tokens.values():
            token.cancel()
        for task in self.tasks.values():
            task.cancel()
        await asyncio.gather(*self.tasks.values(), return_exceptions=True)
        await asyncio.gather(
            *(plugin.close() for plugin in self.plugins.values()),
            return_exceptions=True,
        )
        self.tasks.clear()
        self.plugins.clear()
        self.tokens.clear()

    def status_snapshot(self) -> dict[str, dict[str, Any]]:
        return {target_id: dict(state) for target_id, state in self.status.items()}


class NewsPublishScheduler:
    """Drain startup backlog, then publish by threshold or elapsed interval."""

    def __init__(
        self,
        *,
        target_ids: set[str],
        settings: Callable[[], Any],
        enqueue: PublishCallback,
        startup_enqueue: PublishCallback | None = None,
        capacity_enqueue: PublishCallback | None = None,
        five_star_enqueue: PublishCallback | None = None,
        pending_count: Callable[[], Awaitable[int]] | None = None,
        local_hour: Callable[[], int] = lambda: datetime.now().astimezone().hour,
        wall_now: Callable[[], datetime] = lambda: datetime.now().astimezone(),
        schedule_key: str | None = None,
    ) -> None:
        self.initial_pending = set(target_ids)
        self.settings = settings
        self.enqueue = enqueue
        self.startup_enqueue = startup_enqueue or enqueue
        self.capacity_enqueue = capacity_enqueue or self.startup_enqueue
        self.five_star_enqueue = five_star_enqueue
        self.pending_count = pending_count
        self.local_hour = local_hour
        self.wall_now = wall_now
        self.schedule_key = schedule_key
        self.trigger = asyncio.Event()
        self.stop_event = asyncio.Event()
        self.five_star_requested = False
        self.accumulated = 0
        self.stopping = False
        self.cooldown_until: str | None = None
        self.next_check_at: str | None = None

    def _night(self) -> bool:
        config = self.settings()
        hour = self.local_hour()
        if config.night_start_hour < config.night_end_hour:
            return config.night_start_hour <= hour < config.night_end_hour
        return hour >= config.night_start_hour or hour < config.night_end_hour

    def interval_seconds(self) -> float:
        config = self.settings()
        minutes = (
            config.night_publish_interval_minutes
            if self._night()
            else config.source_publish_interval_minutes.get(
                self.schedule_key,
                config.publish_interval_minutes,
            )
        )
        return float(minutes) * 60

    def mode(self) -> str:
        return self.settings().source_publish_modes.get(self.schedule_key, "interval")

    def batch_size(self) -> int:
        config = self.settings()
        return int(config.source_batch_sizes.get(self.schedule_key, config.max_news_per_note))

    def immediate_five_star_enabled(self) -> bool:
        return bool(self.settings().source_immediate_five_star.get(self.schedule_key, False))

    async def _refresh_pending(self) -> int:
        if self.pending_count is None:
            return self.accumulated
        count = await self.pending_count()
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError("pending_count must return a non-negative integer")
        self.accumulated = count
        return count

    async def refresh_pending(self) -> int:
        count = await self._refresh_pending()
        self._refresh_trigger()
        return count

    def _refresh_trigger(self) -> None:
        threshold = (
            self.batch_size() if self.mode() == "capacity" else self.settings().new_post_threshold
        )
        if self.five_star_requested or self.accumulated >= threshold:
            self.trigger.set()
        else:
            self.trigger.clear()

    async def _publish_round(
        self,
        *,
        callback: PublishCallback | None = None,
    ) -> tuple[int, int]:
        before = await self._refresh_pending()
        self.trigger.clear()
        await (callback or self.enqueue)()
        if self.pending_count is None:
            capacity = self.settings().max_news_per_note
            self.accumulated = max(0, self.accumulated - capacity)
        else:
            await self._refresh_pending()
        return before, self.accumulated

    async def _cooldown(self) -> None:
        started_at = self.wall_now()
        try:
            await self._wait_for_interval(
                self.stop_event,
                started_at,
                status_field="cooldown_until",
            )
        finally:
            self.cooldown_until = None

    async def _wait_after_no_progress(self) -> None:
        self.trigger.clear()
        started_at = self.wall_now()
        try:
            await self._wait_for_interval(
                self.trigger,
                started_at,
                status_field="next_check_at",
            )
        finally:
            self.next_check_at = None

    async def _wait_for_interval(
        self,
        event: asyncio.Event,
        started_at: datetime,
        *,
        status_field: str,
    ) -> bool:
        """Wait against wall time and recompute the active day/night interval."""

        while not self.stopping:
            if event.is_set():
                return True
            deadline = started_at + timedelta(seconds=self.interval_seconds())
            setattr(self, status_field, deadline.isoformat())
            remaining = (deadline - self.wall_now()).total_seconds()
            if remaining <= 0:
                return False
            try:
                await asyncio.wait_for(
                    event.wait(),
                    timeout=min(remaining, WALL_CLOCK_RECHECK_SECONDS),
                )
            except TimeoutError:
                continue
        return event.is_set()

    async def _drain_initial_backlog(self) -> bool:
        published = False
        pending = await self._refresh_pending()
        while pending > 0 and not self.stopping:
            before, pending = await self._publish_round(callback=self.startup_enqueue)
            published = True
            if pending >= before:
                break
        return published

    async def _publish_immediate_five_stars(self) -> None:
        if self.five_star_enqueue is None:
            self.five_star_requested = False
            return
        while not self.stopping:
            self.five_star_requested = False
            before, after = await self._publish_round(callback=self.five_star_enqueue)
            if after >= before or after == 0:
                return

    async def record_batch(
        self,
        target_id: str,
        new_items: int,
        initial: bool,
        succeeded: bool,
    ) -> None:
        if new_items > 0:
            self.accumulated += new_items
            if self.immediate_five_star_enabled():
                self.five_star_requested = True
        if initial:
            self.initial_pending.discard(target_id)
        if new_items > 0 or (initial and not self.initial_pending):
            await self._refresh_pending()
        self._refresh_trigger()

    async def run(self) -> None:
        if self.stopping:
            return
        await self._refresh_pending()
        if self.mode() == "scheduled_only":
            await self.stop_event.wait()
            return
        if self.accumulated > 0 and self.immediate_five_star_enabled():
            self.five_star_requested = True
        if self.five_star_requested:
            await self._publish_immediate_five_stars()
        initial_published = False
        if self.mode() == "interval":
            initial_published = await self._drain_initial_backlog()
            if initial_published and not self.stopping:
                await self._cooldown()
        periodic_due = initial_published
        while not self.stopping:
            await self._refresh_pending()
            if self.five_star_requested:
                await self._publish_immediate_five_stars()
                continue
            if self.mode() == "capacity":
                if self.accumulated >= self.batch_size():
                    before, after = await self._publish_round(callback=self.capacity_enqueue)
                    if after >= before and not self.stopping:
                        await self._wait_after_no_progress()
                    continue
                if self.stopping:
                    break
                self.trigger.clear()
                self.next_check_at = None
                self._refresh_trigger()
                if not self.trigger.is_set():
                    await self.trigger.wait()
                continue
            threshold = self.settings().new_post_threshold
            should_publish = self.accumulated >= threshold or (
                periodic_due and self.accumulated > 0
            )
            if should_publish:
                await self._publish_round()
                await self._cooldown()
                periodic_due = True
                continue
            if self.stopping:
                break
            periodic_due = False
            self.trigger.clear()
            started_at = self.wall_now()
            try:
                triggered = await self._wait_for_interval(
                    self.trigger,
                    started_at,
                    status_field="next_check_at",
                )
                periodic_due = not triggered
            finally:
                self.next_check_at = None

    def stop(self) -> None:
        self.stopping = True
        self.trigger.set()
        self.stop_event.set()


class PeriodicNewsCadence:
    """Run the global scheduled-news route on the configured day/night cadence."""

    def __init__(
        self,
        *,
        settings: Callable[[], Any],
        enqueue: PublishCallback,
        ready: Callable[[], Awaitable[None]],
        wall_now: Callable[[], datetime] = lambda: datetime.now().astimezone(),
    ) -> None:
        self.settings = settings
        self.enqueue = enqueue
        self.ready = ready
        self.wall_now = wall_now
        self.last_run_at = wall_now()
        self.next_check_at: str | None = None
        self.wake = asyncio.Event()
        self.stopping = False
        self.log = logging.getLogger(__name__)

    def interval_seconds(self) -> float:
        config = self.settings()
        hour = self.wall_now().hour
        if config.night_start_hour < config.night_end_hour:
            night = config.night_start_hour <= hour < config.night_end_hour
        else:
            night = hour >= config.night_start_hour or hour < config.night_end_hour
        minutes = (
            config.night_publish_interval_minutes if night else config.publish_interval_minutes
        )
        return float(minutes) * 60

    async def run(self) -> None:
        await self.ready()
        while not self.stopping:
            self.wake.clear()
            baseline = self.last_run_at
            deadline = baseline + timedelta(seconds=self.interval_seconds())
            self.next_check_at = deadline.isoformat()
            remaining = (deadline - self.wall_now()).total_seconds()
            if remaining > 0:
                with suppress(TimeoutError):
                    await asyncio.wait_for(
                        self.wake.wait(),
                        timeout=min(remaining, WALL_CLOCK_RECHECK_SECONDS),
                    )
                if self.stopping:
                    break
                if self.wall_now() < deadline:
                    continue
            self.next_check_at = None
            try:
                await self.enqueue()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.log.exception("periodic news cadence failed")
            self.last_run_at = self.wall_now()

    def note_published(self) -> None:
        self.last_run_at = self.wall_now()
        self.wake.set()

    def stop(self) -> None:
        self.stopping = True
        self.wake.set()
