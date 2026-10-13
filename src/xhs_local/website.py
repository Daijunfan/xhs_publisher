"""Local news website: existing collectors -> SQLite -> feed and saved favorites."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import shutil
import signal
from contextlib import suppress
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import monotonic

from aiohttp import web
from pydantic import ValidationError

from xhs_local.configuration.loader import (
    ConfigSnapshot,
    load_snapshot,
    snapshot_data,
    snapshot_from_data,
)
from xhs_local.configuration.models import AgentsTarget, SourcesConfig, TargetConfig
from xhs_local.configuration.subscriptions import (
    collector_locator,
    creator_key,
    parse_creator_link,
    save_sources,
)
from xhs_local.core.contracts import CollectBatch
from xhs_local.core.errors import TransientError
from xhs_local.core.states import WorkTopic
from xhs_local.observability.health import HealthServer
from xhs_local.observability.logging import configure_logging
from xhs_local.observability.status import StatusStore
from xhs_local.pipeline.agents import AgentsPublisher
from xhs_local.pipeline.collector import Collector
from xhs_local.pipeline.source_scheduler import SourceScheduler
from xhs_local.plugins.registry import SourcePluginRegistry
from xhs_local.rendering.layout import derive_headline, paginate_text
from xhs_local.rendering.renderer import HtmlPhotoGenerator
from xhs_local.storage.checkpoints import CheckpointRepository
from xhs_local.storage.records import CommitResult, RecordsRepository
from xhs_local.storage.retention import RetentionService
from xhs_local.storage.schema import open_database

INDEX = Path(__file__).parent / "rendering/templates/website.html"
RETENTION_DAYS = 2
CLEANUP_SECONDS = 300


class WebsiteCollector(Collector):
    def __init__(self, records: RecordsRepository, reset_at: datetime) -> None:
        super().__init__(records)
        self.reset_at = reset_at
        self.targets: set[tuple[str, str]] | None = None

    def set_sources(self, snapshot: ConfigSnapshot) -> None:
        self.targets = {
            (s.id, t.id)
            for s in snapshot.sources.sources
            for t in s.targets
            if s.enabled and t.enabled
        }

    async def commit(self, batch: CollectBatch, *, config_revision: str) -> CommitResult:
        cutoff = max(self.reset_at, datetime.now(UTC) - timedelta(days=RETENTION_DAYS))
        fresh = []
        for record in batch.records:
            timestamp = record.payload.get("video_metadata", {}).get("timestamp")
            if timestamp:
                record = replace(record, occurred_at=datetime.fromtimestamp(timestamp, UTC))
            if record.occurred_at >= cutoff:
                fresh.append(record)

        def commit() -> CommitResult:
            # Serialize file materialization with cleanup of unreferenced media.
            with self.records.database.locked():
                if (
                    self.targets is not None
                    and (batch.source_id, batch.target_id) not in self.targets
                ):
                    return CommitResult((), (), ())
                deleted = self.records.deleted_news_ids(tuple(record.record_id for record in fresh))
                return self.records.commit_batch(
                    replace(batch, records=tuple(r for r in fresh if r.record_id not in deleted)),
                    create_work=False,
                    config_revision=config_revision,
                )

        return await asyncio.to_thread(commit)


def clean_expired_news(records: RecordsRepository, now: datetime) -> dict[str, int]:
    retention = RetentionService(records.database, records.media.runtime_root)
    removed = media = 0
    with records.database.locked():
        while count := retention.purge_news(
            now - timedelta(days=RETENTION_DAYS),
            documents_before=now - timedelta(days=RETENTION_DAYS),
        ):
            removed += count
        while count := retention.purge_orphan_media(now):
            media += count
        cutoff = now - timedelta(days=RETENTION_DAYS)
        for directory in ("cache/source_media", "tmp", "generated/manual"):
            while retention.purge_directory(directory, cutoff):
                pass
        retention.purge_completed_remote_operations(cutoff)
        while retention.purge_terminal_work(cutoff):
            pass
        retention.purge_news_posters()
    return {"records": removed, "media": media}


class WebsiteVideos:
    """Only video enrichment runs here; the former review/publication pipeline stays off."""

    def __init__(self, scheduler: SourceScheduler, records: RecordsRepository, status: StatusStore):
        from xhs_local.pipeline.dispatcher import OutboxDispatcher
        from xhs_local.pipeline.publisher import PublisherWorker
        from xhs_local.pipeline.recovery import StartupRecovery
        from xhs_local.pipeline.retry_scheduler import RetryScheduler
        from xhs_local.pipeline.video import VideoPreparationService
        from xhs_local.processing.transcription import LocalWhisperClient
        from xhs_local.storage.dead_letters import DeadLetterRepository
        from xhs_local.storage.outbox import OutboxRepository
        from xhs_local.storage.work_items import WorkItemRepository

        self.scheduler, self.records, self.status = scheduler, records, status
        self.active: set[str] = set()
        self.tasks: list[asyncio.Task] = []
        snapshot = scheduler.snapshot
        self.works = WorkItemRepository(records.database)
        outbox = OutboxRepository(records.database)
        queue: asyncio.Queue = asyncio.Queue(maxsize=snapshot.app.queues.ingest_maxsize)
        self.dispatcher = OutboxDispatcher(outbox, {WorkTopic.VIDEO_PREPARE: queue})
        self.retries = RetryScheduler(
            self.works, outbox, self.dispatcher, topic=WorkTopic.VIDEO_PREPARE
        )
        self.recovery = StartupRecovery(
            self.works, outbox, self.dispatcher, topic=WorkTopic.VIDEO_PREPARE
        )
        self.service = VideoPreparationService(
            records=records, work_items=self.works, runtime_root=snapshot.runtime_root,
            client_for=lambda source_id: getattr(scheduler.plugins.get(source_id), "client", None),
            transcription=LocalWhisperClient(snapshot.runtime_root / "models" / "whisper-turbo"),
            summarizer=None, commit_ready=self._commit_ready,
        )
        self.workers = [PublisherWorker(
            queue, self.works, DeadLetterRepository(records.database),
            {WorkTopic.VIDEO_PREPARE: self._process},
            retry_delays={WorkTopic.VIDEO_PREPARE: 60}, retry_wake=self.retries.wake,
        ) for _ in range(2)]

    def _eligible(self, record) -> bool:
        return (
            (record.source_id, record.target_id) in (self.scheduler.collector.targets or set())
            and record.occurred_at >= datetime.now(UTC) - timedelta(days=RETENTION_DAYS)
        )

    def _commit_ready(self, record) -> bool:
        # Match website deletion/retention's lock across media materialization and upsert.
        with self.records.database.locked():
            current = self.records.get(record.record_id)
            if current is None or not self._eligible(record) or self.records.deleted_news_ids(
                (record.record_id,)
            ):
                return False
            self.records.upsert(record)
            return True

    async def _process(self, work) -> None:
        stored = await asyncio.to_thread(self.records.get, work.record_id)
        if stored is None or not self._eligible(stored.record):
            return
        self.active.add(work.record_id)
        self.status.update(video_enrichment={"active": sorted(self.active), "enabled": True})
        try:
            await self.service(work)
        except TransientError as error:
            if error.code != "YOUTUBE_RATE_LIMITED":
                raise
            client = getattr(self.scheduler.plugins.get(stored.record.source_id), "client", None)
            until = getattr(client, "cooldown_until", 0)
            delay = max(1, until - monotonic()) if until else 3600
            await asyncio.to_thread(
                self.works.schedule_retry, work.work_id,
                retry_at=datetime.now(UTC) + timedelta(seconds=delay),
                error_class=error.error_class.value, error_code=error.code,
                error_summary="YouTube rate limit; saved progress will resume after cooldown",
            )
        finally:
            self.active.discard(work.record_id)
            self.status.update(video_enrichment={"active": sorted(self.active), "enabled": True})

    async def enqueue(self) -> None:
        await asyncio.to_thread(
            self.records.enqueue_pending_videos,
            self.scheduler.collector.targets or set(),
            datetime.now(UTC) - timedelta(days=RETENTION_DAYS),
            config_revision=self.scheduler.snapshot.revision,
        )
        self.dispatcher.wake(WorkTopic.VIDEO_PREPARE)

    async def start(self) -> None:
        self.status.update(video_enrichment={"active": [], "enabled": True})
        await self.enqueue()
        await self.recovery.run()
        self.tasks = [asyncio.create_task(worker.run()) for worker in self.workers]
        self.tasks.extend([
            asyncio.create_task(self.dispatcher.run()), asyncio.create_task(self.retries.run())
        ])

    async def close(self) -> None:
        self.dispatcher.stop()
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)


class WebsiteSubscriptions:
    def __init__(self, scheduler: SourceScheduler, records: RecordsRepository) -> None:
        self.scheduler = scheduler
        self.records = records
        self.lock = asyncio.Lock()
        self.scheduler.collector.set_sources(scheduler.snapshot)

    def following(self, source_id: str, target_id: str) -> bool:
        return (source_id, target_id) in self.scheduler.collector.targets

    async def _apply(self, current: ConfigSnapshot, sources: SourcesConfig) -> None:
        data = snapshot_data(current)
        data["sources"] = sources.model_dump(mode="json")
        updated = snapshot_from_data(current.config_root, data)
        # Validate through the same plugin interfaces before changing the config file.
        for source in updated.sources.sources:
            if source.enabled:
                self.scheduler.registry.prepare(
                    source,
                    config_root=updated.config_root,
                    runtime_root=updated.runtime_root,
                )
        await asyncio.to_thread(save_sources, updated.config_root, updated.sources)
        # A cancelled collector thread may still finish: block its write before cancelling.
        self.scheduler.collector.set_sources(updated)
        await self.scheduler.update_targets(updated)

    async def apply_agents_targets(self, targets: list[AgentsTarget]) -> None:
        """Core owns targets; local source IDs, credentials and options stay local."""
        async with self.lock:
            current = self.scheduler.snapshot
            remaining = {(t.plugin, t.targetId): t for t in targets}
            owners = {}
            for source in current.sources.sources:
                owners.setdefault(source.plugin, source.id)
                for target in source.targets:
                    if (source.plugin, target.id) in remaining:
                        owners[(source.plugin, target.id)] = source.id
            sources = []
            for source in current.sources.sources:
                updated = []
                for old in source.targets:
                    item = remaining.pop((source.plugin, old.id), None)
                    updated.append(
                        old.model_copy(
                            update={
                                "enabled": item.enabled if item else False,
                                **(
                                    {
                                        "locator": old.locator
                                        if item.locator == old.locator
                                        else collector_locator(item.plugin, item.locator),
                                        "name": item.name,
                                        "poll_seconds": item.pollSeconds,
                                        "options": {
                                            **dict(old.options),
                                            **(
                                                {
                                                    "collect_documents": True,
                                                    "lookback_hours": 48,
                                                    "max_documents": 1,
                                                    "collect_timeout_seconds": 900,
                                                }
                                                if item.collectFiles
                                                else (
                                                    {"collect_documents": False}
                                                    if "collect_documents" in old.options
                                                    else {}
                                                )
                                            ),
                                        },
                                    }
                                    if item
                                    else {}
                                ),
                            }
                        )
                    )
                for key, item in list(remaining.items()):
                    if owners.get(key, owners.get(item.plugin)) == source.id:
                        updated.append(
                            TargetConfig(
                                id=item.targetId,
                                locator=collector_locator(item.plugin, item.locator),
                                name=item.name,
                                enabled=item.enabled,
                                poll_seconds=item.pollSeconds,
                                options={
                                    "collect_documents": True,
                                    "lookback_hours": 48,
                                    "max_documents": 1,
                                    "collect_timeout_seconds": 900,
                                }
                                if item.collectFiles
                                else {},
                            )
                        )
                        remaining.pop(key)
                sources.append(source.model_copy(update={
                    "targets": tuple(updated),
                    "enabled": any(t.enabled for t in updated),
                }))
            if remaining:
                raise ValueError("Core requested a source plugin not configured on this worker")
            candidate = SourcesConfig(version=current.sources.version, sources=tuple(sources))
            if candidate != current.sources:
                await self._apply(current, candidate)

    def _require_local_management(self) -> None:
        if self.scheduler.snapshot.app.agents.enabled:
            raise web.HTTPConflict(text="Subscriptions are managed by Agents Company")

    async def import_links(self, links: list[str]) -> list[dict]:
        self._require_local_management()
        parsed = [parse_creator_link(link) for link in links]
        async with self.lock:
            current = await asyncio.to_thread(load_snapshot, self.scheduler.snapshot.config_root)
            sources = list(current.sources.sources)
            results = []
            for platform, target in parsed:
                key = creator_key(platform, target.locator)
                matches = [
                    (index, old)
                    for index, source in enumerate(sources)
                    if source.plugin == platform
                    for old in source.targets
                    if creator_key(platform, old.locator) == key
                ]
                if any(sources[i].enabled and old.enabled for i, old in matches):
                    result = "existing"
                else:
                    if matches:
                        index, old = matches[0]
                        targets = tuple(
                            t.model_copy(update={"enabled": True}) if t.id == old.id else t
                            for t in sources[index].targets
                        )
                        result = "restored"
                    else:
                        index = next(
                            (i for i, s in enumerate(sources) if s.plugin == platform), None
                        )
                        if index is None:
                            raise ValueError(f"{platform} 采集来源尚未配置")
                        targets = (*sources[index].targets, target)
                        result = "added"
                    sources[index] = sources[index].model_copy(
                        update={"enabled": True, "targets": targets}
                    )
                results.append({"platform": platform, "name": target.name, "status": result})
            updated = SourcesConfig(version=current.sources.version, sources=tuple(sources))
            if updated != current.sources:
                await self._apply(current, updated)
            return results

    async def unfollow(self, record_id: str) -> dict:
        self._require_local_management()
        async with self.lock:
            stored = await asyncio.to_thread(self.records.get, record_id)
            if stored is None:
                raise web.HTTPNotFound()
            record = stored.record
            if record.plugin_id not in {"x", "youtube"}:
                raise ValueError("仅支持取消关注 X 和 YouTube 博主")
            current = await asyncio.to_thread(load_snapshot, self.scheduler.snapshot.config_root)
            target = next(
                (
                    t
                    for s in current.sources.sources
                    if s.id == record.source_id
                    for t in s.targets
                    if t.id == record.target_id
                ),
                None,
            )
            if target is None:
                raise ValueError("没有找到该博主的采集配置")
            key = creator_key(record.plugin_id, target.locator)
            pairs = set()
            sources = []
            for source in current.sources.sources:
                targets = []
                for old in source.targets:
                    if (
                        source.plugin == record.plugin_id
                        and creator_key(source.plugin, old.locator) == key
                    ):
                        pairs.add((source.id, old.id))
                        old = old.model_copy(update={"enabled": False})
                    targets.append(old)
                sources.append(source.model_copy(update={"targets": tuple(targets)}))
            await self._apply(
                current, SourcesConfig(version=current.sources.version, sources=tuple(sources))
            )

            def remove() -> int:
                with self.records.database.locked():
                    count = sum(self.records.remove_source_news(*pair) for pair in pairs)
                    clean_expired_news(self.records, datetime.now(UTC))
                    return count

            removed = await asyncio.to_thread(remove)
            return {"name": target.name, "removed": removed}


class WebsitePosters:
    """Reuse the original renderer, with one bounded render and a disk cache."""

    def __init__(self, records: RecordsRepository) -> None:
        self.records = records
        self.root = records.media.runtime_root / "generated" / "website"
        self.lock = asyncio.Lock()

    def directory(self, record_id: str) -> Path:
        return self.root / hashlib.sha256(record_id.encode()).hexdigest()

    async def cards(self, record_id: str) -> list[str]:
        async with self.lock:
            stored = await asyncio.to_thread(self.records.get, record_id)
            if stored is None or stored.record.content_type not in {"tech_news", "video_pending"}:
                raise web.HTTPNotFound()
            directory = self.directory(record_id)
            manifest = directory / "cards.json"
            if manifest.is_file():
                cache = json.loads(manifest.read_text())
                if cache["hash"] == stored.content_hash and all(
                    (directory / name).is_file() for name in cache["images"]
                ):
                    return cache["images"]
            record = stored.record
            text = record.text.strip() or record.title.strip() or record.source_name
            headline = record.title.strip() or derive_headline(text)
            avatar_index = record.payload.get("avatar_attachment_index")
            avatar = next((a for a in stored.attachments if a.index == avatar_index), None)
            attachments = tuple(a for a in stored.attachments if a.index != avatar_index)
            renderer = HtmlPhotoGenerator(
                output_dir=directory,
                runtime_root=self.records.media.runtime_root,
            )
            pages = (
                await renderer.paginate_x_story(text, headline=headline, attachments=attachments)
                if record.plugin_id == "x"
                else paginate_text(text)
                if record.plugin_id == "youtube"
                else [text]
            )
            cards = [
                {
                    "record_id": record_id,
                    "headline": headline,
                    "text": page,
                    "source": record.source_name,
                    "occurred_at": record.occurred_at,
                    "source_platform": record.plugin_id,
                    "avatar": avatar,
                    "attachments": () if record.plugin_id == "x" and index else attachments,
                    "story_has_media": bool(attachments),
                    "story_page": index + 1,
                    "story_pages": len(pages),
                    "template_name": "x_post.html"
                    if record.plugin_id in {"x", "youtube"}
                    else None,
                }
                for index, page in enumerate(pages)
            ]
            shutil.rmtree(directory, ignore_errors=True)
            try:
                paths = await renderer.generate_news_cards(cards)
                if await asyncio.to_thread(self.records.get, record_id) is None:
                    raise web.HTTPNotFound()
                images = [path.name for path in paths]
                manifest.write_text(json.dumps({"hash": stored.content_hash, "images": images}))
                return images
            except BaseException:
                shutil.rmtree(directory, ignore_errors=True)
                raise


def create_website(
    records: RecordsRepository,
    subscriptions: WebsiteSubscriptions | None = None,
    publication_api=None,
) -> web.Application:
    posters = WebsitePosters(records)

    async def index(_request: web.Request) -> web.StreamResponse:
        return web.FileResponse(INDEX, headers={"Cache-Control": "no-cache"})

    async def news(request: web.Request) -> web.Response:
        try:
            page = int(request.query.get("page", "1"))
            if page < 1 or page > 1_000_000:
                raise ValueError
        except ValueError:
            raise web.HTTPBadRequest(text="Invalid page") from None
        feed = await asyncio.to_thread(
            records.news_feed,
            source=request.query.get("source", ""),
            query=request.query.get("q", "").strip()[:200],
            favorites=request.query.get("favorites") == "1",
            page=page,
        )
        if subscriptions is not None:
            for item in feed["items"]:
                item["following"] = subscriptions.following(item["source_id"], item["target_id"])
        return web.json_response(feed, headers={"Cache-Control": "no-store"})

    async def import_links(request: web.Request) -> web.Response:
        if subscriptions is None:
            raise web.HTTPServiceUnavailable()
        if request.content_type != "application/json":
            raise web.HTTPUnsupportedMediaType()
        try:
            data = await request.json()
            links = data.get("links") if isinstance(data, dict) else None
            if (
                not isinstance(links, list)
                or not 1 <= len(links) <= 100
                or any(not isinstance(link, str) or not link.strip() for link in links)
            ):
                raise ValueError("请输入 1–100 个 X 或 YouTube 博主主页链接")
            results = await subscriptions.import_links(links)
        except ValidationError:
            return web.json_response(
                {"error": "链接与已有博主标识冲突，请检查主页链接"}, status=400
            )
        except ValueError as error:
            return web.json_response({"error": str(error)}, status=400)
        return web.json_response({"results": results})

    async def unfollow(request: web.Request) -> web.Response:
        if subscriptions is None:
            raise web.HTTPServiceUnavailable()
        try:
            result = await subscriptions.unfollow(request.match_info["id"])
        except ValueError as error:
            return web.json_response({"error": str(error)}, status=400)
        return web.json_response(result)

    async def favorite(request: web.Request) -> web.Response:
        if request.content_type != "application/json":
            raise web.HTTPUnsupportedMediaType()
        try:
            data = await request.json()
        except ValueError:
            raise web.HTTPBadRequest(text="Invalid JSON") from None
        if not isinstance(data, dict) or not isinstance(data.get("favorite"), bool):
            raise web.HTTPBadRequest(text="favorite must be a boolean")
        found = await asyncio.to_thread(
            records.set_news_favorite, request.match_info["id"], data["favorite"]
        )
        if not found:
            raise web.HTTPNotFound()
        if subscriptions is not None and not data["favorite"]:
            stored = await asyncio.to_thread(records.get, request.match_info["id"])
            if (
                stored
                and stored.record.plugin_id in {"x", "youtube"}
                and not subscriptions.following(stored.record.source_id, stored.record.target_id)
            ):
                await asyncio.to_thread(
                    records.remove_source_news,
                    stored.record.source_id,
                    stored.record.target_id,
                )
                await asyncio.to_thread(clean_expired_news, records, datetime.now(UTC))
        return web.json_response({"favorite": data["favorite"]})

    async def delete(request: web.Request) -> web.Response:
        def remove() -> None:
            with records.database.locked():
                records.delete_news(request.match_info["id"])
                clean_expired_news(records, datetime.now(UTC))

        await asyncio.to_thread(remove)
        return web.Response(status=204)

    async def cards(request: web.Request) -> web.Response:
        record_id = request.match_info["id"]
        images = await posters.cards(record_id)
        return web.json_response(
            {"images": [f"/posters/{record_id}/{name}" for name in images]},
            headers={"Cache-Control": "no-store"},
        )

    async def poster_image(request: web.Request) -> web.StreamResponse:
        record_id = request.match_info["id"]
        if await asyncio.to_thread(records.get, record_id) is None:
            raise web.HTTPNotFound()
        name = request.match_info["name"]
        path = posters.directory(record_id) / name
        if Path(name).name != name or path.suffix != ".png" or not path.is_file():
            raise web.HTTPNotFound()
        return web.FileResponse(path, headers={"Cache-Control": "no-cache"})

    async def media(request: web.Request) -> web.StreamResponse:
        attachment = await asyncio.to_thread(records.news_image, request.match_info["id"])
        if attachment is None:
            raise web.HTTPNotFound()
        path, mime_type = attachment
        return web.FileResponse(
            path,
            headers={
                "Content-Type": mime_type,
                "Cache-Control": "public, max-age=86400, immutable",
                "X-Content-Type-Options": "nosniff",
            },
        )

    async def health(_request: web.Request) -> web.Response:
        # A real DB read also verifies that the feed's storage remains usable.
        await asyncio.to_thread(records.count)
        return web.json_response({"ready": True, "mode": "website"})

    application = web.Application()
    from xhs_local.plugins.sinks.xiaohongshu.http import add_publish_routes

    add_publish_routes(application, records, api=publication_api)
    application.add_routes(
        [
            web.get("/", index),
            web.get("/api/news", news),
            web.post("/api/subscriptions", import_links),
            web.delete("/api/news/{id}/author", unfollow),
            web.put("/api/news/{id}/favorite", favorite),
            web.delete("/api/news/{id}", delete),
            web.get("/api/news/{id}/cards", cards),
            web.get("/posters/{id}/{name}", poster_image),
            web.get("/media/{id}", media),
            web.get("/health/ready", health),
        ]
    )
    return application


async def run_website(snapshot: ConfigSnapshot) -> None:
    runtime = snapshot.runtime_root
    configure_logging(runtime / "logs", timezone=snapshot.app.timezone, console=False)
    database = open_database(
        snapshot.database_path,
        busy_timeout_seconds=snapshot.app.sqlite.busy_timeout_seconds,
        apply_migrations=True,
    )
    records = RecordsRepository(database, runtime)
    status = StatusStore(runtime / "status.json", snapshot.app.timezone)
    stop = asyncio.Event()
    checkpoints = CheckpointRepository(database)
    reset = checkpoints.get("website", "reset") or {}
    reset_at = datetime.fromisoformat(reset["at"]) if reset else datetime(1970, 1, 1, tzinfo=UTC)

    videos = None

    async def on_batch(source_id, *_args: object) -> None:
        if videos is not None and any(
            source.id == source_id and source.plugin == "youtube"
            for source in scheduler.snapshot.sources.sources
        ):
            await videos.enqueue()

    scheduler = SourceScheduler(
        snapshot,
        SourcePluginRegistry(),
        checkpoints,
        WebsiteCollector(records, reset_at),
        on_batch,
    )

    def status_snapshot() -> dict:
        return {**status.snapshot(), "source_targets": scheduler.status_snapshot()}

    health = HealthServer(snapshot.app.status.host, snapshot.app.status.port, status_snapshot)
    subscriptions = WebsiteSubscriptions(scheduler, records)
    agents = (
        AgentsPublisher(snapshot, records, subscriptions.apply_agents_targets, status.update)
        if snapshot.app.agents.enabled else None
    )
    agents_task = None
    runner = web.AppRunner(create_website(records, subscriptions), access_log=None)
    website = snapshot.app.website
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    try:
        next_cleanup = 0.0
        await runner.setup()
        await web.TCPSite(runner, website.host, website.port).start()
        await health.start()
        if agents is not None:
            await agents.start()
        await scheduler.start()
        if any(s.enabled and s.plugin == "youtube" for s in snapshot.sources.sources):
            videos = WebsiteVideos(scheduler, records, status)
            await videos.start()
        if agents is not None:
            agents_task = asyncio.create_task(agents.run(stop), name="agents-publisher")
        status.update(
            ready=True,
            mode="website",
            config_revision=snapshot.revision,
            website={"host": website.host, "port": website.port},
        )
        logging.getLogger(__name__).info("News website listening on port %s", website.port)
        while not stop.is_set():
            if loop.time() >= next_cleanup:
                cleaned = await asyncio.to_thread(clean_expired_news, records, datetime.now(UTC))
                status.update(
                    last_cleanup={
                        "at": datetime.now(UTC).isoformat(),
                        **cleaned,
                    }
                )
                next_cleanup = loop.time() + CLEANUP_SECONDS
            status.update(
                source_targets=scheduler.status_snapshot(),
                config_revision=scheduler.snapshot.revision,
            )
            with suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=30)
    finally:
        if videos is not None:
            await videos.close()
        if agents_task is not None:
            agents_task.cancel()
            await asyncio.gather(agents_task, return_exceptions=True)
        if agents is not None:
            await agents.close()
        await scheduler.stop()
        await health.close()
        await runner.cleanup()
        status.update(ready=False, stopped_at=datetime.now(UTC).isoformat())
        database.close()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.remove_signal_handler(sig)
