"""Server-native collector entrypoint; no external agent host and no publication sinks."""

from __future__ import annotations

import asyncio
import fcntl
import logging
import os
import signal
from contextlib import suppress
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

from xhs_local.configuration.loader import load_snapshot
from xhs_local.core.contracts import CollectBatch
from xhs_local.pipeline.collector import Collector
from xhs_local.observability.logging import configure_logging
from xhs_local.observability.status import StatusStore
from xhs_local.pipeline.source_scheduler import SourceScheduler
from xhs_local.plugins.registry import SourcePluginRegistry
from xhs_local.storage.checkpoints import CheckpointRepository
from xhs_local.storage.records import RecordsRepository, CommitResult
from xhs_local.storage.schema import open_database
from xhs_local.website import WebsiteVideos

from .models import now_iso
from .store import Store
from .subscriptions import Subscriptions, PLATFORMS
from .web import Settings


class FrontierScheduler(SourceScheduler):
    """Spread the cold-start sweep so waiting for a network slot cannot exhaust every deadline."""

    def __init__(self, snapshot, *args, **kwargs):
        super().__init__(snapshot, *args, **kwargs)
        self.next_starts: dict[str, float] = {}

    async def _target_loop(self, prepared, plugin, target, interval, token):
        platform = self.status[target.id]["plugin_id"]
        spacing = 8.0 if platform == "youtube" else (0.25 if platform == "x" else 0.1)
        now = asyncio.get_running_loop().time()
        slot = max(now, self.next_starts.get(platform, now))
        self.next_starts[platform] = slot + spacing
        if slot > now:
            await self._wait_until(target.id, token, self._status_now() + timedelta(seconds=slot - now))
        if not self.stopping and not token.cancelled:
            await super()._target_loop(prepared, plugin, target, interval, token)


class FrontierCollector(Collector):
    """Persist subscribed originals; reading-window settings never delete source records."""

    def __init__(self, records):
        super().__init__(records)
        self.targets: set[tuple[str, str]] = set()

    def set_sources(self, snapshot):
        self.targets = {(s.id, t.id) for s in snapshot.sources.sources for t in s.targets
                        if s.plugin in PLATFORMS and s.enabled and t.enabled}

    async def commit(self, batch: CollectBatch, *, config_revision: str) -> CommitResult:
        prepared = []
        for record in batch.records:
            if record.plugin_id not in PLATFORMS:
                continue
            metadata = record.payload.get("video_metadata", {})
            timestamp = metadata.get("release_timestamp") or metadata.get("timestamp")
            if isinstance(timestamp, (int, float)):
                record = replace(record, occurred_at=datetime.fromtimestamp(timestamp, UTC))
            prepared.append(record)

        def commit():
            with self.records.database.locked():
                if (batch.source_id, batch.target_id) not in self.targets:
                    return CommitResult((), (), ())
                deleted = self.records.deleted_news_ids(tuple(r.record_id for r in prepared))
                return self.records.commit_batch(
                    replace(batch, records=tuple(r for r in prepared if r.record_id not in deleted)),
                    create_work=False, config_revision=config_revision,
                )
        task = asyncio.create_task(asyncio.to_thread(commit))
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            # A source is not acknowledged as disabled until its in-flight durable write finishes.
            await task
            raise


def platform_targets(snapshot):
    return {platform: [t.id for s in snapshot.sources.sources if s.plugin == platform and s.enabled
                       for t in s.targets if t.enabled] for platform in PLATFORMS}


async def apply_subscription_revision(manager, scheduler, collector, base_snapshot):
    """Persist applied_revision only after the actual target scheduler accepts the overlay."""
    candidate, revision = await asyncio.to_thread(manager.overlay, base_snapshot)
    # Validate before touching any running tasks. Registry.prepare performs no network requests.
    for source in candidate.sources.sources:
        if source.enabled:
            scheduler.registry.prepare(source, config_root=candidate.config_root,
                                       runtime_root=candidate.runtime_root, log=scheduler._plugin_log)
    previous = scheduler.snapshot
    collector.set_sources(candidate)
    try:
        await scheduler.update_targets(candidate)
    except Exception:
        collector.set_sources(previous)
        await scheduler.update_targets(previous)
        raise
    await asyncio.to_thread(manager.mark_applied, revision)
    return revision


async def run(root: Path):
    root = Path(root).resolve()
    snapshot = load_snapshot(root / "config")
    # The original files are retained. The new service owns its runtime snapshot.
    app = snapshot.app.model_copy(
        update={
            "agents": snapshot.app.agents.model_copy(update={"enabled": False}),
        }
    )
    snapshot = replace(snapshot, app=app)
    base_snapshot = snapshot
    derived = Store(root / "runtime/frontier/events.sqlite3")
    subscriptions = Subscriptions(derived, root)
    snapshot, subscription_revision = subscriptions.overlay(base_snapshot)
    runtime = snapshot.runtime_root
    work = runtime / "frontier"
    work.mkdir(parents=True, exist_ok=True)
    lock = (work / "collector.lock").open("w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise RuntimeError("A Frontier collector is already running") from None
    configure_logging(work / "logs", timezone=snapshot.app.timezone, console=False)
    database = open_database(
        snapshot.database_path,
        busy_timeout_seconds=snapshot.app.sqlite.busy_timeout_seconds,
        apply_migrations=True,
    )
    records = RecordsRepository(database, runtime)
    checkpoints = CheckpointRepository(database)
    status = StatusStore(work / "collector-status.json", snapshot.app.timezone)
    status.update(
        started_at=now_iso(),
        ready=False,
        mode="frontier",
        external_publication=False,
        agents_enabled=False,
    )
    stop = asyncio.Event()
    videos = None

    async def on_batch(source_id, *_args):
        if videos is not None and any(
            s.id == source_id and s.plugin == "youtube" for s in scheduler.snapshot.sources.sources
        ):
            await videos.enqueue()

    collector = FrontierCollector(records)
    collector.set_sources(snapshot)
    scheduler = FrontierScheduler(
        snapshot, SourcePluginRegistry(), checkpoints, collector, on_batch
    )
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    try:
        await scheduler.start()
        subscriptions.mark_applied(subscription_revision)
        if os.getenv("FRONTIER_PROCESS_VIDEO", "1") == "1":
            # WebsiteVideos uses the HTTP DeepSeek provider and local Whisper only.
            # No Codex CLI provider or external publisher is instantiated.
            os.environ["DEEPSEEK_VIDEO_KEY_FILE"] = str(runtime / "secrets/frontier-deepseek.key")
            os.environ["DEEPSEEK_VIDEO_ENDPOINT"] = "https://api.deepseek.com/chat/completions"
            os.environ["DEEPSEEK_VIDEO_MODEL"] = os.getenv("FRONTIER_MODEL", "deepseek-flash")
            videos = WebsiteVideos(scheduler, records, status)
            # Bound the RAM peak of Whisper and audio preparation independently of subscriptions.
            count = max(1, min(2, int(os.getenv("FRONTIER_VIDEO_WORKERS", "1"))))
            videos.workers = videos.workers[:count]
            await videos.start()
        status.update(ready=True, platform_targets=platform_targets(scheduler.snapshot),
                      subscription_revision=subscription_revision)
        logging.getLogger(__name__).info(
            "Frontier collection started; external publication is disabled"
        )
        while not stop.is_set():
            if subscriptions.revision() != subscription_revision:
                try:
                    subscription_revision = await apply_subscription_revision(
                        subscriptions, scheduler, collector, base_snapshot)
                    if videos is not None:
                        await videos.enqueue()
                except Exception as error:
                    subscriptions.mark_error()
                    logging.getLogger(__name__).error("Subscription sync failed: %s", type(error).__name__)
            status.update(source_targets=scheduler.status_snapshot(), ready=True,
                          platform_targets=platform_targets(scheduler.snapshot),
                          subscription_revision=subscription_revision)
            with suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=5)
    finally:
        await scheduler.stop()
        if videos is not None:
            await videos.close()
        status.update(ready=False, stopped_at=now_iso())
        database.close()
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.remove_signal_handler(sig)


def main():
    asyncio.run(run(Settings.from_env().root))


if __name__ == "__main__":
    main()
