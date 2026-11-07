"""The sole composition root for the local single-process pipeline."""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import subprocess
from collections.abc import Awaitable, Callable
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from xhs_local.configuration.history import ConfigHistory
from xhs_local.configuration.loader import ConfigSnapshot, ConfigurationError, load_snapshot
from xhs_local.configuration.manager import ConfigManager
from xhs_local.core.errors import ErrorClass, PipelineError, PolicyRejected
from xhs_local.core.states import WorkState, WorkTopic
from xhs_local.observability.health import HealthServer
from xhs_local.observability.logging import configure_logging
from xhs_local.observability.metrics import LocalMetrics
from xhs_local.observability.status import StatusStore, read_status
from xhs_local.pipeline.collector import Collector
from xhs_local.pipeline.dispatcher import OutboxDispatcher
from xhs_local.pipeline.processor import ProcessorWorker
from xhs_local.pipeline.publisher import (
    AccountLocks,
    NewsPublicationService,
    PublisherWorker,
)
from xhs_local.pipeline.recovery import StartupRecovery
from xhs_local.pipeline.retention_worker import RetentionWorker
from xhs_local.pipeline.retry_scheduler import RetryScheduler
from xhs_local.pipeline.source_scheduler import (
    NewsPublishScheduler,
    PeriodicNewsCadence,
    SourceScheduler,
)
from xhs_local.pipeline.video import VideoPreparationService
from xhs_local.plugins.registry import SinkPluginRegistry, SourcePluginRegistry
from xhs_local.plugins.sinks.xiaohongshu.browser import SafariPublisher, SafariSession
from xhs_local.plugins.sources.youtube.client import YouTubeClient
from xhs_local.processing.image_review import ImageReviewer
from xhs_local.processing.provider import CodexCliProvider, DeepSeekProvider, FailoverProvider
from xhs_local.processing.router import ContentRouter
from xhs_local.processing.technology_news import (
    DeepSeekFilter,
    TechnologyNewsProcessor,
)
from xhs_local.processing.transcription import LocalWhisperClient
from xhs_local.processing.video_summary import VideoSummarizer
from xhs_local.rendering.renderer import HtmlPhotoGenerator
from xhs_local.storage.backups import BackupService
from xhs_local.storage.checkpoints import CheckpointRepository
from xhs_local.storage.database import Database
from xhs_local.storage.dead_letters import DeadLetterRepository
from xhs_local.storage.outbox import OutboxRepository
from xhs_local.storage.records import RecordsRepository
from xhs_local.storage.remote_operations import RemoteOperationRepository
from xhs_local.storage.retention import RetentionService
from xhs_local.storage.schema import open_database
from xhs_local.storage.work_items import (
    PublicationLedger,
    WorkItemRepository,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_ROOT = PROJECT_ROOT / "config"
CONFIG_WATCH_SECONDS = 5.0
STATUS_REFRESH_SECONDS = 30.0


class LocalApplication:
    @staticmethod
    def _route_for(snapshot: ConfigSnapshot, content_type: str) -> Any | None:
        content_filter = snapshot.publishing.filters.get(content_type)
        if content_filter is None or not content_filter.enabled:
            return None
        return next(
            (
                route
                for route in snapshot.publishing.routes
                if route.enabled and route.content_type == content_type
            ),
            None,
        )

    @staticmethod
    def _route_sinks_enabled(snapshot: ConfigSnapshot, route: Any | None) -> bool:
        return route is not None and all(
            getattr(snapshot.publishing.sinks, sink_id).enabled for sink_id in route.sinks
        )

    def __init__(
        self,
        snapshot: ConfigSnapshot,
        database: Database,
        config_manager: ConfigManager,
    ) -> None:
        self.snapshot = snapshot
        self.database = database
        self.config_manager = config_manager
        self.log = logging.getLogger(__name__)
        self.stop_event = asyncio.Event()
        self.startup_at = datetime.now(UTC)
        self.startup_news_ready = asyncio.Event()
        self.startup_news_complete = asyncio.Event()
        self.daily_news_cleanup_date: str | None = None
        self.caffeinate: subprocess.Popen[bytes] | None = None
        self.tasks: list[asyncio.Task[Any]] = []
        self.source_scheduler: SourceScheduler | None = None
        self.safari_session: SafariSession | None = None

        runtime = snapshot.runtime_root
        previous_status = read_status(runtime / "status.json") or {}
        previous_stop = previous_status.get("stopped_at") or previous_status.get("updated_at")
        self.previous_stopped_at = datetime.fromisoformat(previous_stop) if previous_stop else None
        self.resume_after_restart = self.previous_stopped_at is not None and timedelta(
            0
        ) <= self.startup_at - self.previous_stopped_at <= timedelta(
            minutes=snapshot.publishing.news.restart_resume_minutes
        )
        if self.resume_after_restart:
            self.daily_news_cleanup_date = (previous_status.get("news_daily_cleanup") or {}).get(
                "date"
            )
        self.status = StatusStore(runtime / "status.json", snapshot.app.timezone)
        self.status.update(
            news_initialization={
                "state": "waiting_for_sources",
                "mode": "resume" if self.resume_after_restart else "catchup",
                "window_end": self.startup_at.isoformat(),
            }
        )
        self.metrics = LocalMetrics()
        self.health = HealthServer(
            snapshot.app.status.host,
            snapshot.app.status.port,
            self._status_snapshot,
        )

        self.checkpoints = CheckpointRepository(database)
        recovery = self.checkpoints.get("news_recovery", "state") or {}
        self.news_outage_since = (
            datetime.fromisoformat(recovery["since"]) if recovery.get("since") else None
        )
        self.news_recovery_cutoff = (
            datetime.fromisoformat(recovery["cutoff"]) if recovery.get("cutoff") else None
        )
        self.work_items = WorkItemRepository(database)
        self.dead_letters = DeadLetterRepository(database)
        self.outbox = OutboxRepository(database)
        self.records = RecordsRepository(database, runtime)
        self.ledger = PublicationLedger(database)
        self.remote_operations = RemoteOperationRepository(database)
        self.registry = SourcePluginRegistry()
        self.sink_registry = SinkPluginRegistry()
        self.account_locks = AccountLocks()

        ingest_queue: asyncio.Queue[Any] = asyncio.Queue(maxsize=snapshot.app.queues.ingest_maxsize)
        publish_queue: asyncio.Queue[Any] = asyncio.PriorityQueue(
            maxsize=snapshot.app.queues.publish_maxsize
        )
        self.queues = {
            WorkTopic.RECORD_COLLECTED: ingest_queue,
            WorkTopic.VIDEO_PREPARE: asyncio.Queue(maxsize=snapshot.app.queues.ingest_maxsize),
            WorkTopic.NEWS_PUBLISH: publish_queue,
        }
        self.dispatcher = OutboxDispatcher(self.outbox, self.queues)
        self.collector = Collector(self.records, self.dispatcher)
        self.retry_scheduler = RetryScheduler(self.work_items, self.outbox, self.dispatcher)
        self.recovery = StartupRecovery(self.work_items, self.outbox, self.dispatcher)
        self.retention = RetentionService(database, runtime)
        self.backups = BackupService(database)
        self.news_round_waiters: dict[str, asyncio.Future[str]] = {}

        news_route = self._route_for(snapshot, "tech_news")
        news_targets: dict[str, set[str]] = {}
        for source in snapshot.sources.sources:
            if news_route is not None and source.plugin in news_route.source_plugins:
                news_targets.setdefault(source.plugin, set()).update(
                    target.id for target in source.targets if source.enabled and target.enabled
                )

        def news_enqueue(plugin_id: str, reason: str) -> Callable[[], Awaitable[None]]:
            async def enqueue() -> None:
                news = self.snapshot.publishing.news
                await self._enqueue_news(
                    reason=reason,
                    source_plugin=plugin_id,
                    presentation=news.source_presentations.get(plugin_id),
                    card_template=news.source_card_templates.get(plugin_id),
                )

            return enqueue

        self.news_schedulers = {
            plugin_id: NewsPublishScheduler(
                target_ids=target_ids,
                settings=lambda: self.snapshot.publishing.news,
                enqueue=news_enqueue(plugin_id, "threshold"),
                startup_enqueue=news_enqueue(plugin_id, "startup"),
                capacity_enqueue=news_enqueue(plugin_id, "capacity"),
                five_star_enqueue=news_enqueue(plugin_id, "five_star"),
                pending_count=lambda plugin_id=plugin_id: self._pending_news_count(plugin_id),
                schedule_key=plugin_id,
            )
            for plugin_id, target_ids in news_targets.items()
        }
        if all(not scheduler.initial_pending for scheduler in self.news_schedulers.values()):
            self.startup_news_ready.set()
        self.scheduled_news_cadence = PeriodicNewsCadence(
            settings=lambda: self.snapshot.publishing.news,
            enqueue=self._enqueue_scheduled_news,
            ready=self.startup_news_complete.wait,
        )
        previous_run = previous_status.get("last_scheduled_run_at")
        last_published = self.ledger.latest_published_at(
            sink="xiaohongshu",
            account_id=snapshot.publishing.sinks.xiaohongshu.account_id,
        )
        if self.resume_after_restart:
            baselines = [
                value
                for value in (
                    datetime.fromisoformat(previous_run) if previous_run else None,
                    last_published,
                )
                if value is not None
            ]
            if baselines:
                self.scheduled_news_cadence.last_run_at = max(baselines)
        self.content_router = ContentRouter(
            {
                "tech_news": self._process_news_record,
            }
        )
        self._build_publication_services(snapshot)

    @classmethod
    async def create(cls, config_root: Path = CONFIG_ROOT) -> LocalApplication:
        config_root = config_root.expanduser().resolve()
        try:
            initial = load_snapshot(config_root)
        except ConfigurationError:
            initial = None
        if initial is not None and initial.app.agents.enabled:
            raise PolicyRejected("Avalon collector mode cannot start the Xiaohongshu pipeline")
        runtime = initial.runtime_root if initial is not None else config_root.parent / "runtime"
        runtime.mkdir(parents=True, exist_ok=True)
        for relative in (
            "sessions",
            "secrets",
            "media/sha256",
            "generated",
            "diagnostics",
            "logs",
            "backups",
            "config-history",
            "tmp",
        ):
            (runtime / relative).mkdir(parents=True, exist_ok=True)
        configure_logging(
            runtime / "logs",
            timezone=initial.app.timezone if initial is not None else "Asia/Shanghai",
        )
        database = open_database(
            initial.database_path if initial is not None else runtime / "app.sqlite3",
            busy_timeout_seconds=(
                initial.app.sqlite.busy_timeout_seconds if initial is not None else 30
            ),
            apply_migrations=False,
        )
        history = ConfigHistory(database, runtime / "config-history", config_root)
        registry = SourcePluginRegistry()
        sink_registry = SinkPluginRegistry()

        async def preflight(snapshot: ConfigSnapshot) -> dict[str, object]:
            deepseek_key = snapshot.resolve(snapshot.publishing.news.deepseek_key_path)
            if not deepseek_key.is_file():
                raise FileNotFoundError(f"DeepSeek key file is unavailable: {deepseek_key}")
            reports = []
            for source in snapshot.sources.sources:
                prepared = registry.prepare(
                    source,
                    config_root=snapshot.config_root,
                    runtime_root=snapshot.runtime_root,
                )
                report = await registry.preflight(prepared, healthcheck=False)
                reports.append({"plugin_id": report.plugin_id, "checks": list(report.checks)})
            for route in snapshot.publishing.routes:
                for plugin_id in route.source_plugins:
                    manifest = registry.manifest(plugin_id)
                    if route.content_type not in manifest.content_types:
                        raise ValueError(
                            f"route {route.id} content type is unsupported by {plugin_id}"
                        )
                if route.processor != "technology_news":
                    raise ValueError(f"route {route.id} references an unknown processor")
            sink_reports = []
            configured_sink_ids = {
                sink_id for route in snapshot.publishing.routes for sink_id in route.sinks
            }
            for plugin_id in sorted(configured_sink_ids):
                sink_config = getattr(snapshot.publishing.sinks, plugin_id)
                if not sink_config.enabled:
                    continue
                report = await sink_registry.preflight(sink_registry.prepare(plugin_id))
                sink_reports.append({"plugin_id": report.plugin_id, "checks": list(report.checks)})
            return {"ok": True, "sources": reports, "sinks": sink_reports}

        manager = ConfigManager(config_root, history, preflight)
        snapshot, degraded = await manager.load_initial()
        if snapshot.database_path != database.path:
            database.close()
            raise RuntimeError(
                "fallback configuration points to a different database; restore app.yaml first"
            )
        application = cls(snapshot, database, manager)
        application.status.update(
            ready=False,
            degraded=degraded,
            config_revision=snapshot.revision,
        )
        return application

    def _build_publication_services(self, snapshot: ConfigSnapshot) -> None:
        news = snapshot.publishing.news
        news_route = self._route_for(snapshot, "tech_news")
        retry = snapshot.publishing.retry
        deepseek = DeepSeekProvider(
            api_key_path=snapshot.resolve(news.deepseek_key_path),
            attempts=retry.transient_attempts,
            retry_base_delay_seconds=retry.transient_base_delay_seconds,
        )
        codex = (
            CodexCliProvider(
                executable=news.codex_fallback_executable,
                model=news.codex_fallback_model,
                timeout_seconds=news.codex_fallback_timeout_seconds,
            )
            if news.codex_fallback_enabled
            else None
        )
        provider = FailoverProvider(deepseek, codex)
        editorial_filter = DeepSeekFilter(
            provider=provider,
            first_review_model=news.first_review_model,
            second_review_model=news.second_review_model,
        )
        processor = TechnologyNewsProcessor(
            editorial_filter,
            attempts=retry.editorial_attempts,
            retry_base_delay_seconds=retry.editorial_base_delay_seconds,
        )
        video_clients = {
            source.id: YouTubeClient(
                cookie_file=(
                    snapshot.resolve(str(source.options["cookie_file"]))
                    if source.options.get("cookie_file")
                    else None
                ),
                chrome_profile=source.options.get("chrome_profile"),
                runtime_root=snapshot.runtime_root,
                node_path=snapshot.resolve(str(source.options["node_path"]))
                if source.options.get("node_path")
                else None,
            )
            for source in snapshot.sources.sources
            if source.enabled and source.plugin == "youtube"
        }
        self.video_service = VideoPreparationService(
            records=self.records,
            work_items=self.work_items,
            runtime_root=snapshot.runtime_root,
            client_for=video_clients.get,
            transcription=LocalWhisperClient(
                snapshot.runtime_root / "models" / "whisper-turbo",
            ),
            summarizer=VideoSummarizer(deepseek, editorial_filter, model=news.second_review_model),
            image_review=ImageReviewer(deepseek, model=news.image_review_model),
            retry_attempts=retry.editorial_attempts,
        )
        renderer = HtmlPhotoGenerator(
            output_dir=snapshot.runtime_root / "generated",
            runtime_root=snapshot.runtime_root,
        )
        xhs_settings = snapshot.publishing.sinks.xiaohongshu
        if self.safari_session is None:
            self.safari_session = SafariSession(
                background=xhs_settings.background,
                persistent=True,
                state_path=snapshot.runtime_root / "sessions" / "safari-publisher-window.json",
            )
        elif self.safari_session.background != xhs_settings.background:
            raise RuntimeError("Safari background mode change requires a controlled restart")
        xhs_plugin = self.sink_registry.prepare("xiaohongshu")
        news_sink = self.sink_registry.create(
            xhs_plugin,
            publisher=SafariPublisher(
                max_images=news.max_news_per_note,
                background=xhs_settings.background,
                keep_window_open=xhs_settings.keep_window_open,
                session=self.safari_session,
            ),
        )
        xhs_lock = self.account_locks.get("xiaohongshu", xhs_settings.account_id)

        async def review_final_text(text: str) -> bool:
            chunks = [
                {"id": f"final-text-{index + 1}", "text": text[index : index + 16_000]}
                for index in range(0, len(text), 16_000)
            ]
            approved = await editorial_filter.review(chunks, text_limit=None)
            return len(approved) == len(chunks)

        self.news_service = NewsPublicationService(
            records=self.records,
            ledger=self.ledger,
            remote_operations=self.remote_operations,
            processor=processor,
            image_review=ImageReviewer(deepseek, model=news.image_review_model),
            final_text_review=review_final_text,
            renderer=renderer,
            sink=news_sink,
            sink_lock=xhs_lock,
            runtime_root=snapshot.runtime_root,
            interval_minutes=news.publish_interval_minutes,
            retry_delay_seconds=retry.transient_base_delay_seconds,
            capacity=news.max_news_per_note,
            sink_id="xiaohongshu",
            account_id=xhs_settings.account_id,
            minimum_text_characters=snapshot.publishing.filters[
                "tech_news"
            ].minimum_text_characters,
            source_plugins=() if news_route is None else news_route.source_plugins,
            source_presentations=news.source_presentations,
            source_card_templates=news.source_card_templates,
            avatar_required_plugins=frozenset(news.source_card_templates),
        )

    async def _create_work(
        self,
        topic: WorkTopic,
        *,
        record_id: str | None = None,
        payload: dict[str, Any] | None = None,
        wake: bool = True,
    ) -> str | None:
        def create() -> str | None:
            with self.database.transaction() as connection:
                existing = connection.execute(
                    """
                    SELECT 1 FROM work_items WHERE topic=? AND coalesce(record_id,'')=coalesce(?,'')
                     AND state IN ('READY','RUNNING','SUBMITTING','RETRY_WAIT')
                    """,
                    (topic.value, record_id),
                ).fetchone()
                if existing:
                    return None
                work_id = WorkItemRepository.create_in(
                    connection,
                    topic,
                    record_id=record_id,
                    payload=payload,
                    config_revision=self.snapshot.revision,
                )
                OutboxRepository.add_in(
                    connection,
                    topic,
                    work_id,
                    payload=payload,
                )
                return work_id

        work_id = await asyncio.to_thread(create)
        if work_id and wake:
            self.dispatcher.wake(topic)
        return work_id

    async def _pending_news_count(
        self,
        source_plugin: str | None = None,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int | None = None,
    ) -> int:
        route = self._route_for(self.snapshot, "tech_news")
        if not self._route_sinks_enabled(self.snapshot, route):
            return 0
        current = datetime.now(UTC)
        candidates = await asyncio.to_thread(
            self.records.news_candidates,
            start or current - timedelta(hours=24),
            end or current,
            limit=limit or self.snapshot.publishing.news.new_post_threshold,
            sink="xiaohongshu",
            account_id=self.snapshot.publishing.sinks.xiaohongshu.account_id,
            minimum_text_characters=self.snapshot.publishing.filters[
                "tech_news"
            ].minimum_text_characters,
            plugin_ids=(source_plugin,) if source_plugin else None,
        )
        return len(candidates)

    async def _initialize_recent_news(self) -> None:
        news = self.snapshot.publishing.news
        if self.resume_after_restart and self.news_recovery_cutoff is None:
            self.status.update(
                news_initialization={
                    "state": "complete",
                    "mode": "resume",
                    "discarded_records": 0,
                    "previous_stopped_at": self.previous_stopped_at.isoformat(),
                    "completed_at": datetime.now(UTC).isoformat(),
                }
            )
            self.startup_news_complete.set()
            await self.stop_event.wait()
            return
        if self.news_recovery_cutoff is None:
            self.news_recovery_cutoff = self.startup_at
            await self._save_news_recovery()
        deadline = self.startup_at + timedelta(seconds=news.startup_collection_timeout_seconds)
        source_sweep_timed_out = False
        while not self.startup_news_ready.is_set():
            remaining = (deadline - datetime.now(UTC)).total_seconds()
            if remaining <= 0:
                source_sweep_timed_out = True
                break
            with suppress(TimeoutError):
                await asyncio.wait_for(self.startup_news_ready.wait(), timeout=min(remaining, 30))

        await self._catch_up_news(
            self.news_recovery_cutoff or self.startup_at, source_sweep_timed_out
        )
        if not self.stop_event.is_set():
            await self._clear_news_recovery()
        self.startup_news_complete.set()
        await self.stop_event.wait()

    async def _catch_up_news(self, cutoff: datetime, source_sweep_timed_out: bool = False) -> None:
        news = self.snapshot.publishing.news
        window_start = datetime(1970, 1, 1, tzinfo=UTC)
        outcomes = {}
        discarded = 0
        self.status.update(
            news_initialization={
                "state": "running",
                "mode": "catchup",
                "platform_outcomes": outcomes,
                "source_sweep_timed_out": source_sweep_timed_out,
                "discarded_records": 0,
            }
        )
        active_plugins = {
            source.plugin
            for source in self.snapshot.sources.sources
            if source.enabled and any(target.enabled for target in source.targets)
        }
        for plugin_id in self.news_schedulers:
            if plugin_id not in active_plugins or self.stop_event.is_set():
                continue
            count = await self._pending_news_count(
                plugin_id,
                start=window_start,
                end=cutoff,
                limit=1,
            )
            if not count:
                outcomes[plugin_id] = "empty"
                continue
            # Keep the ordinary global cooldown and publish mutex; only packing differs.
            await self._wait_for_news_publish_cooldown()
            if self.stop_event.is_set():
                break
            outcome = None
            while outcome is None and not self.stop_event.is_set():
                outcome = await self._enqueue_news(
                    reason="catchup",
                    source_plugin=plugin_id,
                    presentation=news.source_presentations.get(plugin_id),
                    card_template=news.source_card_templates.get(plugin_id),
                    candidate_window_start=window_start,
                    candidate_window_end=cutoff,
                    wait_for_terminal=True,
                )
                if outcome is None:
                    with suppress(TimeoutError):
                        await asyncio.wait_for(self.stop_event.wait(), timeout=60)
            outcomes[plugin_id] = outcome
            if outcome == "published":
                # Only retire this platform's old remainder after its own confirmed post.
                discarded += await asyncio.to_thread(
                    self.ledger.discard_unpublished_news_before,
                    cutoff,
                    sink="xiaohongshu",
                    account_id=self.snapshot.publishing.sinks.xiaohongshu.account_id,
                    plugin_id=plugin_id,
                )
            self.status.update(
                news_initialization={
                    "state": "running",
                    "mode": "catchup",
                    "platform_outcomes": dict(outcomes),
                    "source_sweep_timed_out": source_sweep_timed_out,
                    "discarded_records": discarded,
                }
            )
        await asyncio.gather(
            *(scheduler.refresh_pending() for scheduler in self.news_schedulers.values())
        )
        self.status.update(
            news_initialization={
                "state": "complete",
                "mode": "catchup",
                "platform_outcomes": dict(outcomes),
                "source_sweep_timed_out": source_sweep_timed_out,
                "discarded_records": discarded,
                "completed_at": datetime.now(UTC).isoformat(),
            }
        )

    async def _wait_for_news_publish_cooldown(
        self,
        interval_minutes: float | None = None,
    ) -> None:
        account_id = self.snapshot.publishing.sinks.xiaohongshu.account_id
        timezone = ZoneInfo(self.snapshot.app.timezone)
        while not self.stop_event.is_set():
            published_at = await asyncio.to_thread(
                self.ledger.latest_published_at,
                sink="xiaohongshu",
                account_id=account_id,
            )
            if published_at is None:
                self.status.update(news_initialization_cooldown_until=None)
                return
            interval = (
                timedelta(minutes=interval_minutes)
                if interval_minutes is not None
                else timedelta(seconds=self.scheduled_news_cadence.interval_seconds())
            )
            cooldown_until = published_at + interval
            remaining = (cooldown_until - datetime.now(UTC)).total_seconds()
            if remaining <= 0:
                self.status.update(news_initialization_cooldown_until=None)
                return
            self.status.update(
                news_initialization_cooldown_until=cooldown_until.astimezone(timezone).isoformat()
            )
            with suppress(TimeoutError):
                await asyncio.wait_for(self.stop_event.wait(), timeout=min(remaining, 30))

    @staticmethod
    def _daily_news_cutoff(now_local: datetime, keep_minutes: int) -> datetime:
        if now_local.tzinfo is None:
            raise ValueError("daily news cleanup requires an aware local time")
        midnight = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        return (midnight - timedelta(minutes=keep_minutes)).astimezone(UTC)

    async def _apply_daily_news_cleanup(self, now_local: datetime) -> int:
        news = self.snapshot.publishing.news
        cutoff = self._daily_news_cutoff(now_local, news.previous_day_keep_minutes)
        account_id = self.snapshot.publishing.sinks.xiaohongshu.account_id
        discarded = await asyncio.to_thread(
            self.ledger.discard_unpublished_news_before,
            cutoff,
            sink="xiaohongshu",
            account_id=account_id,
        )
        self.daily_news_cleanup_date = now_local.date().isoformat()
        await asyncio.gather(
            *(scheduler.refresh_pending() for scheduler in self.news_schedulers.values())
        )
        self.status.update(
            news_daily_cleanup={
                "date": self.daily_news_cleanup_date,
                "cutoff": cutoff.isoformat(),
                "keep_minutes": news.previous_day_keep_minutes,
                "discarded_records": discarded,
                "completed_at": now_local.isoformat(),
            }
        )
        return discarded

    async def _daily_news_cleanup_loop(self) -> None:
        await self.startup_news_complete.wait()
        timezone = ZoneInfo(self.snapshot.app.timezone)
        while not self.stop_event.is_set():
            if self.news_outage_since is not None or self.news_recovery_cutoff is not None:
                with suppress(TimeoutError):
                    await asyncio.wait_for(self.stop_event.wait(), timeout=60)
                continue
            now_local = datetime.now(timezone)
            date_key = now_local.date().isoformat()
            if self.daily_news_cleanup_date != date_key:
                await self._apply_daily_news_cleanup(now_local)
            next_midnight = (now_local + timedelta(days=1)).replace(
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )
            while not self.stop_event.is_set():
                remaining = (next_midnight - datetime.now(timezone)).total_seconds()
                if remaining <= 0:
                    break
                with suppress(TimeoutError):
                    await asyncio.wait_for(
                        self.stop_event.wait(),
                        timeout=min(remaining, 30),
                    )

    async def _enqueue_scheduled_news(self) -> None:
        if self.news_recovery_cutoff is not None:
            return
        if not await self._pending_news_count():
            return
        await self._enqueue_news(reason="scheduled")

    async def _enqueue_news(
        self,
        *,
        reason: str = "threshold",
        source_plugin: str | None = None,
        presentation: str | None = None,
        card_template: str | None = None,
        candidate_window_start: datetime | None = None,
        candidate_window_end: datetime | None = None,
        wait_for_terminal: bool = False,
    ) -> str | None:
        route = self._route_for(self.snapshot, "tech_news")
        if not self._route_sinks_enabled(self.snapshot, route):
            return None
        released_limits = await asyncio.to_thread(
            self.remote_operations.release_expired_rate_limits
        )
        if released_limits:
            resumed = await asyncio.to_thread(
                self.work_items.resume_waiting,
                error_class="REMOTE_CIRCUIT_OPEN",
                topics=(WorkTopic.NEWS_PUBLISH,),
            )
            await asyncio.to_thread(self.outbox.restore_for_works, resumed)
            if resumed:
                self.dispatcher.wake(WorkTopic.NEWS_PUBLISH)
        unresolved = await asyncio.to_thread(self.remote_operations.unresolved, limit=1)
        if unresolved:
            await self._reconcile_news()
            if await asyncio.to_thread(self.remote_operations.unresolved, limit=1):
                self.metrics.increment("news_publish_circuit_open")
                return None
        work_id = await self._create_work(
            WorkTopic.NEWS_PUBLISH,
            payload={
                "reason": reason,
                "source_plugin": source_plugin,
                "presentation": presentation,
                "card_template": card_template,
                "candidate_window_start": (
                    candidate_window_start.isoformat() if candidate_window_start else None
                ),
                "candidate_window_end": (
                    candidate_window_end.isoformat() if candidate_window_end else None
                ),
            },
            wake=False,
        )
        if work_id is None:
            return None
        self.metrics.increment("news_work_created")
        completion = asyncio.get_running_loop().create_future()
        self.news_round_waiters[work_id] = completion
        self.dispatcher.wake(WorkTopic.NEWS_PUBLISH)
        try:
            first_outcome = await completion
            while True:
                current = await asyncio.to_thread(self.work_items.get, work_id)
                if current is None or current.state is not WorkState.RUNNING:
                    break
                await asyncio.sleep(0)
            if not wait_for_terminal:
                return first_outcome
            while current is not None and current.state in {
                WorkState.READY,
                WorkState.RUNNING,
                WorkState.SUBMITTING,
                WorkState.RETRY_WAIT,
                WorkState.RECONCILE_ONLY,
            }:
                if current.state is WorkState.RECONCILE_ONLY:
                    await self._reconcile_news()
                with suppress(TimeoutError):
                    await asyncio.wait_for(
                        self.stop_event.wait(),
                        timeout=60 if current.state is WorkState.RECONCILE_ONLY else 5,
                    )
                if self.stop_event.is_set():
                    return None
                current = await asyncio.to_thread(self.work_items.get, work_id)
            if current is None or current.state is not WorkState.SUCCEEDED:
                return "failed"
            return (
                "published"
                if await asyncio.to_thread(self.remote_operations.work_succeeded, work_id)
                else "not_published"
            )
        finally:
            self.news_round_waiters.pop(work_id, None)

    async def _on_source_batch(
        self,
        source_id: str,
        target_id: str,
        new_items: int,
        initial: bool,
        succeeded: bool,
    ) -> None:
        source = next(
            (item for item in self.snapshot.sources.sources if item.id == source_id),
            None,
        )
        self.metrics.increment("collection_cycles")
        self.metrics.increment("records_collected", new_items)
        if not succeeded:
            self.metrics.increment("collection_failures")
        route = self._route_for(self.snapshot, "tech_news")
        if source is not None and route is not None and source.plugin in route.source_plugins:
            scheduler = self.news_schedulers.get(source.plugin)
            if scheduler is not None:
                await scheduler.record_batch(
                    target_id,
                    new_items,
                    initial,
                    succeeded,
                )
            if all(not item.initial_pending for item in self.news_schedulers.values()):
                self.startup_news_ready.set()

    async def _on_record(self, work: Any) -> None:
        if not work.record_id:
            return
        stored = await asyncio.to_thread(self.records.get, work.record_id)
        if stored is None:
            return
        handler = self.content_router.resolve(stored.record.content_type)
        await handler((work, stored))

    async def _process_news_record(self, _context: Any) -> None:
        """News publication remains batch/slot based; collection is already durable."""

    async def _prepare_video_work(self, work: Any) -> None:
        await self.video_service(work)

    async def _publish_news_work(self, work: Any) -> None:
        outcome = "error"
        try:
            if (
                work.payload.get("reason") == "scheduled"
                and self.news_outage_since is not None
                and datetime.now(UTC) - self.news_outage_since
                >= timedelta(minutes=self.snapshot.publishing.news.restart_resume_minutes)
            ):
                self.news_recovery_cutoff = datetime.now(UTC)
                await self._save_news_recovery()
                await asyncio.to_thread(self.work_items.succeed, work.work_id)
                outcome = "recovery_deferred"
                return
            route = self._route_for(self.snapshot, "tech_news")
            if not self._route_sinks_enabled(self.snapshot, route):
                await asyncio.to_thread(
                    self.work_items.wait_for_operator,
                    work.work_id,
                    error_class="SINK_DISABLED",
                    error_summary="publication route is disabled by active configuration",
                )
                outcome = "paused"
                return
            unresolved = await asyncio.to_thread(self.remote_operations.unresolved, limit=1)
            if unresolved:
                await asyncio.to_thread(
                    self.work_items.wait_for_operator,
                    work.work_id,
                    error_class="REMOTE_CIRCUIT_OPEN",
                    error_summary="a previous Xiaohongshu submission needs reconciliation",
                )
                outcome = "paused"
                return
            outcome = await self.news_service(work)
            self.metrics.increment(f"news_round_{outcome}")
            if outcome == "published":
                self.metrics.increment("news_notes_published")
                self.scheduled_news_cadence.note_published()
                if self.news_recovery_cutoff is None:
                    await self._clear_news_recovery()
            elif outcome in {"not_submitted", "ambiguous"}:
                await self._note_news_outage()
        except PipelineError as error:
            if error.error_class is ErrorClass.TRANSIENT_NETWORK:
                await self._note_news_outage()
            raise
        finally:
            self.status.update(
                last_news_round_at=datetime.now(ZoneInfo(self.snapshot.app.timezone)).isoformat(),
                last_news_round_outcome=outcome,
            )
            completion = self.news_round_waiters.get(work.work_id)
            if completion is not None and not completion.done():
                completion.set_result(outcome)

    async def _resume_config_paused_work(self) -> None:
        await asyncio.to_thread(self.remote_operations.release_expired_rate_limits)
        topics = []
        if self._route_sinks_enabled(self.snapshot, self._route_for(self.snapshot, "tech_news")):
            topics.append(WorkTopic.NEWS_PUBLISH)
        if not topics:
            return
        work_ids = await asyncio.to_thread(
            self.work_items.resume_waiting,
            error_class="SINK_DISABLED",
            topics=tuple(topics),
        )
        if WorkTopic.NEWS_PUBLISH in topics and not await asyncio.to_thread(
            self.remote_operations.unresolved, limit=1
        ):
            work_ids.extend(
                await asyncio.to_thread(
                    self.work_items.resume_waiting,
                    error_class="REMOTE_CIRCUIT_OPEN",
                    topics=(WorkTopic.NEWS_PUBLISH,),
                )
            )
        await asyncio.to_thread(self.outbox.restore_for_works, work_ids)
        for topic in topics:
            self.dispatcher.wake(topic)

    async def _config_watch(self) -> None:
        while not self.stop_event.is_set():
            try:
                refreshed = await self.config_manager.refresh(self._apply_config)
                if refreshed is not None:
                    self.status.update(degraded=False)
            except Exception:
                self.log.exception("configuration reload rejected")
            with suppress(TimeoutError):
                await asyncio.wait_for(self.stop_event.wait(), timeout=CONFIG_WATCH_SECONDS)

    async def _apply_config(
        self,
        previous: ConfigSnapshot,
        current: ConfigSnapshot,
    ) -> None:
        immutable_app_fields = (
            "runtime_root",
            "database_path",
            "queues",
            "status",
            "sqlite",
        )
        changed_immutable = [
            field
            for field in immutable_app_fields
            if getattr(previous.app, field) != getattr(current.app, field)
        ]
        if changed_immutable:
            raise RuntimeError(
                "configuration change requires a controlled restart: "
                + ", ".join(changed_immutable)
            )
        if previous.publishing.videos.workers != current.publishing.videos.workers:
            raise RuntimeError("video worker count change requires a controlled restart")
        sources_changed = previous.sources != current.sources
        previous_news_service = self.news_service
        previous_video_service = self.video_service
        next_scheduler = (
            SourceScheduler(
                current,
                self.registry,
                self.checkpoints,
                self.collector,
                self._on_source_batch,
            )
            if sources_changed
            else self.source_scheduler
        )
        try:
            self._build_publication_services(current)
            if sources_changed and self.source_scheduler is not None:
                await self.source_scheduler.stop()
            self.snapshot = current
            if sources_changed and next_scheduler is not None:
                await next_scheduler.start()
                self.source_scheduler = next_scheduler
        except BaseException:
            self.snapshot = previous
            self.news_service = previous_news_service
            self.video_service = previous_video_service
            if sources_changed:
                if next_scheduler is not None:
                    await next_scheduler.stop()
                rollback = SourceScheduler(
                    previous,
                    self.registry,
                    self.checkpoints,
                    self.collector,
                    self._on_source_batch,
                )
                await rollback.start()
                self.source_scheduler = rollback
            raise
        await self._resume_config_paused_work()
        self.status.update(config_revision=current.revision)

    def _status_snapshot(self) -> dict[str, Any]:
        snapshot = self.status.snapshot()
        configured_intervals = self.snapshot.publishing.news.source_publish_interval_minutes
        source_scheduling = {
            plugin_id: {
                "pending_candidates": scheduler.accumulated,
                "cooldown_until": scheduler.cooldown_until,
                "next_check_at": scheduler.next_check_at,
                "publish_interval_minutes": configured_intervals.get(
                    plugin_id,
                    self.snapshot.publishing.news.publish_interval_minutes,
                ),
                "mode": scheduler.mode(),
                "batch_size": scheduler.batch_size(),
                "immediate_five_star": scheduler.immediate_five_star_enabled(),
            }
            for plugin_id, scheduler in self.news_schedulers.items()
        }
        cooldowns = [
            value["cooldown_until"]
            for value in source_scheduling.values()
            if value["cooldown_until"]
        ]
        next_checks = [
            value["next_check_at"] for value in source_scheduling.values() if value["next_check_at"]
        ]
        snapshot.update(
            {
                "config_revision": self.snapshot.revision,
                "last_scheduled_run_at": self.scheduled_news_cadence.last_run_at.isoformat(),
                "news_network_recovery": {
                    "since": self.news_outage_since.isoformat() if self.news_outage_since else None,
                    "catchup_pending": self.news_recovery_cutoff is not None,
                },
                "queues": {
                    topic.value: {"size": queue.qsize(), "maxsize": queue.maxsize}
                    for topic, queue in self.queues.items()
                },
                "work_states": self.work_items.counts_by_state(),
                "news_scheduling": {
                    "pending_candidates": sum(
                        scheduler.accumulated for scheduler in self.news_schedulers.values()
                    ),
                    "threshold": self.snapshot.publishing.news.new_post_threshold,
                    "cooldown_until": min(cooldowns) if cooldowns else None,
                    "next_check_at": min(next_checks) if next_checks else None,
                    "scheduled_publish_interval_minutes": (
                        self.scheduled_news_cadence.interval_seconds() / 60
                    ),
                    "scheduled_publish_next_at": self.scheduled_news_cadence.next_check_at,
                },
                "source_news_scheduling": source_scheduling,
                "source_targets": (
                    {} if self.source_scheduler is None else self.source_scheduler.status_snapshot()
                ),
                "dead_letters": len(self.dead_letters.list_open()),
                "remote_ambiguous": len(self.remote_operations.unresolved()),
                "metrics": self.metrics.snapshot(),
                "database_bytes": self.database.path.stat().st_size
                if self.database.path.exists()
                else 0,
                "database_max_bytes": self.snapshot.app.sqlite.max_database_bytes,
            }
        )
        return snapshot

    async def _save_news_recovery(self) -> None:
        await asyncio.to_thread(
            self.checkpoints.put,
            "news_recovery",
            "state",
            {
                "since": self.news_outage_since.isoformat() if self.news_outage_since else None,
                "cutoff": self.news_recovery_cutoff.isoformat()
                if self.news_recovery_cutoff
                else None,
            },
        )

    async def _note_news_outage(self) -> None:
        if self.news_outage_since is None:
            self.news_outage_since = datetime.now(UTC)
            await self._save_news_recovery()

    async def _clear_news_recovery(self) -> None:
        self.news_outage_since = self.news_recovery_cutoff = None
        await asyncio.to_thread(self.checkpoints.delete, "news_recovery", "state")

    async def _reconcile_news(self) -> bool:
        try:
            return await self.news_service.reconcile_pending()
        except Exception:
            self.log.exception("news reconciliation waiting for connection")
            return False

    async def _news_recovery_loop(self) -> None:
        while not self.stop_event.is_set():
            try:
                if await self._reconcile_news():
                    published_at = await asyncio.to_thread(
                        self.ledger.latest_published_at,
                        sink="xiaohongshu",
                        account_id=self.snapshot.publishing.sinks.xiaohongshu.account_id,
                    )
                    self.scheduled_news_cadence.last_run_at = published_at or (
                        datetime.now(UTC) - timedelta(days=1)
                    )
                    self.scheduled_news_cadence.wake.set()
                if self.startup_news_complete.is_set() and self.news_recovery_cutoff is not None:
                    await self._catch_up_news(self.news_recovery_cutoff)
                    if not self.stop_event.is_set():
                        await self._clear_news_recovery()
                        self.scheduled_news_cadence.wake.set()
            except Exception:
                self.log.exception("news recovery waiting for connection")
            with suppress(TimeoutError):
                await asyncio.wait_for(self.stop_event.wait(), timeout=60)

    async def _status_loop(self) -> None:
        while not self.stop_event.is_set():
            self.status.update(**self._status_snapshot())
            with suppress(TimeoutError):
                await asyncio.wait_for(self.stop_event.wait(), timeout=STATUS_REFRESH_SECONDS)

    def _maintenance_enabled(self) -> bool:
        return self.snapshot.app.retention.enabled or self.snapshot.app.backup.automatic

    def _run_maintenance(self) -> None:
        now = datetime.now(UTC)
        report: dict[str, Any] = {}
        if self.snapshot.app.backup.automatic:
            result = self.backups.create(
                self.snapshot.runtime_root / "backups",
                config_paths=tuple(
                    self.snapshot.config_root / name
                    for name in ("app.yaml", "sources.yaml", "publishing.yaml")
                ),
            )
            removed = self.backups.prune(
                self.snapshot.runtime_root / "backups",
                keep=self.snapshot.app.backup.keep,
            )
            report["backup"] = str(result.database_path)
            report["backups_pruned"] = len(removed)
        if self.snapshot.app.retention.enabled:
            policy = self.snapshot.app.retention
            report.update(
                {
                    "outbox": self.retention.purge_dispatched_outbox(
                        now - timedelta(days=policy.logs_days),
                        batch_size=policy.batch_size,
                    ),
                    "work_items": self.retention.purge_terminal_work(
                        now - timedelta(days=policy.media_days),
                        batch_size=policy.batch_size,
                    ),
                    "media": self.retention.purge_orphan_media(
                        now - timedelta(days=policy.media_days),
                        batch_size=policy.batch_size,
                    ),
                    "generated": self.retention.purge_directory(
                        "generated",
                        now - timedelta(days=policy.generated_days),
                        batch_size=policy.batch_size,
                    ),
                    "diagnostics": self.retention.purge_directory(
                        "diagnostics",
                        now - timedelta(days=policy.diagnostics_days),
                        batch_size=policy.batch_size,
                    ),
                    "logs": self.retention.purge_directory(
                        "logs",
                        now - timedelta(days=policy.logs_days),
                        batch_size=policy.batch_size,
                    ),
                }
            )
        self.status.update(
            last_maintenance_at=datetime.now(ZoneInfo(self.snapshot.app.timezone)).isoformat(),
            maintenance=report,
        )

    def _start_caffeinate(self) -> None:
        if Path("/usr/bin/caffeinate").is_file():
            self.caffeinate = subprocess.Popen(
                ["/usr/bin/caffeinate", "-i", "-w", str(os.getpid())],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )

    def request_stop(self) -> None:
        self.stop_event.set()

    def _task_finished(self, task: asyncio.Task[Any]) -> None:
        if self.stop_event.is_set() or task.cancelled():
            return
        error = task.exception()
        if error is None:
            self.log.critical(
                "required application task stopped",
                extra={"context": {"task": task.get_name()}},
            )
        else:
            self.log.critical(
                "required application task crashed",
                exc_info=(type(error), error, error.__traceback__),
                extra={"context": {"task": task.get_name()}},
            )
        self.request_stop()

    async def run(self) -> None:
        loop = asyncio.get_running_loop()
        for name in ("SIGINT", "SIGTERM"):
            if hasattr(signal, name):
                loop.add_signal_handler(getattr(signal, name), self.request_stop)
        self._start_caffeinate()
        await self.health.start()
        await self._resume_config_paused_work()
        await self.recovery.run()

        handlers = {
            WorkTopic.NEWS_PUBLISH: self._publish_news_work,
        }
        transient_delay = self.snapshot.publishing.retry.transient_base_delay_seconds
        transient_attempts = self.snapshot.publishing.retry.transient_attempts
        processor_tasks = [
            asyncio.create_task(
                ProcessorWorker(
                    self.queues[WorkTopic.RECORD_COLLECTED],
                    self.work_items,
                    self.dead_letters,
                    self._on_record,
                ).run(),
                name=f"processor-{index + 1}",
            )
            for index in range(self.snapshot.app.queues.processor_workers)
        ]
        publisher_tasks = [
            asyncio.create_task(
                PublisherWorker(
                    self.queues[WorkTopic.NEWS_PUBLISH],
                    self.work_items,
                    self.dead_letters,
                    handlers,
                    retry_delays={
                        WorkTopic.NEWS_PUBLISH: transient_delay,
                    },
                    max_attempts=transient_attempts,
                    retry_wake=self.retry_scheduler.wake,
                ).run(),
                name=f"publisher-{index + 1}",
            )
            for index in range(self.snapshot.app.queues.publisher_workers)
        ]
        self.tasks = [
            asyncio.create_task(self.dispatcher.run(), name="outbox-dispatcher"),
            *processor_tasks,
            *publisher_tasks,
            *(
                asyncio.create_task(
                    PublisherWorker(
                        self.queues[WorkTopic.VIDEO_PREPARE],
                        self.work_items,
                        self.dead_letters,
                        {WorkTopic.VIDEO_PREPARE: self._prepare_video_work},
                        retry_delays={WorkTopic.VIDEO_PREPARE: transient_delay},
                        max_attempts=transient_attempts,
                        retry_wake=self.retry_scheduler.wake,
                    ).run(),
                    name=f"video-preparation-{index + 1}",
                )
                for index in range(self.snapshot.publishing.videos.workers)
            ),
            asyncio.create_task(self.retry_scheduler.run(), name="retry-scheduler"),
            asyncio.create_task(self._news_recovery_loop(), name="news-recovery"),
            *(
                asyncio.create_task(
                    scheduler.run(),
                    name=f"news-scheduler-{plugin_id}",
                )
                for plugin_id, scheduler in self.news_schedulers.items()
            ),
            asyncio.create_task(
                self._initialize_recent_news(),
                name="startup-news-initialization",
            ),
            asyncio.create_task(
                self._daily_news_cleanup_loop(),
                name="daily-news-cleanup",
            ),
            asyncio.create_task(
                self.scheduled_news_cadence.run(),
                name="scheduled-news-cadence",
            ),
            asyncio.create_task(self._config_watch(), name="config-watcher"),
            asyncio.create_task(self._status_loop(), name="status-writer"),
            asyncio.create_task(
                RetentionWorker(
                    self._maintenance_enabled,
                    self._run_maintenance,
                ).run(),
                name="retention-worker",
            ),
        ]
        for task in self.tasks:
            task.add_done_callback(self._task_finished)
        self.source_scheduler = SourceScheduler(
            self.snapshot,
            self.registry,
            self.checkpoints,
            self.collector,
            self._on_source_batch,
        )
        await self.source_scheduler.start()
        self.status.update(ready=True, pid=os.getpid())
        try:
            await self.stop_event.wait()
        finally:
            self.status.update(ready=False)
            self.scheduled_news_cadence.stop()
            for scheduler in self.news_schedulers.values():
                scheduler.stop()
            if self.source_scheduler is not None:
                await self.source_scheduler.stop()
            self.dispatcher.stop()
            for task in self.tasks:
                task.cancel()
            await asyncio.gather(*self.tasks, return_exceptions=True)
            await self.health.close()
            if self.safari_session is not None:
                await self.safari_session.close()
            if self.caffeinate is not None and self.caffeinate.poll() is None:
                self.caffeinate.terminate()
                try:
                    await asyncio.to_thread(self.caffeinate.wait, 5)
                except subprocess.TimeoutExpired:
                    self.caffeinate.kill()
                    await asyncio.to_thread(self.caffeinate.wait, 2)
            self.status.update(
                ready=False,
                stopped_at=datetime.now(UTC).isoformat(),
                last_scheduled_run_at=self.scheduled_news_cadence.last_run_at.isoformat(),
            )
            self.database.close()


async def run_application(config_root: Path = CONFIG_ROOT) -> None:
    snapshot = load_snapshot(config_root)
    if snapshot.app.agents.enabled or snapshot.app.website.enabled:
        from xhs_local.website import run_website

        # Collector mode always sends retained records to Avalon, never Xiaohongshu.
        await run_website(snapshot)
        return
    application = await LocalApplication.create(config_root)
    await application.run()
