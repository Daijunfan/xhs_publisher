#!/usr/bin/env python3
"""Run the existing Linux collectors against Aexus Bot's scoped channel API."""
from __future__ import annotations

import argparse
import asyncio
import fcntl
import os
import signal
import socket
import sys
from contextlib import suppress
from dataclasses import replace
from pathlib import Path


def telegram_target_options(options):
    return {**options, "collect_documents": True,
            "document_metadata_only": options.get("prefetch_documents") is not True,
            "lookback_hours": 168, "max_documents": 100}


async def run(args):
    sys.path.insert(0, str(args.root / "src"))
    from xhs_local.configuration.loader import load_snapshot, snapshot_data, snapshot_from_data
    import xhs_local.pipeline.agents as agents_module
    # This archive is capacity-managed; old document metadata must not block its queue.
    agents_module.PUBLISH_HOURS = 24 * 365 * 100
    agents_module.DOCUMENT_HOURS = agents_module.PUBLISH_HOURS
    from xhs_local.frontier.collector import FrontierCollector, FrontierScheduler
    from xhs_local.observability.logging import configure_logging
    from xhs_local.observability.status import StatusStore
    from subscription_sync import CorePublisher
    from channel_content import ChannelContentStore, serve_channel_storage
    from channel_documents import ChannelDocumentRequests
    from channel_avatars import ChannelAuthorAvatars
    from xhs_local.plugins.registry import SourcePluginRegistry
    from xhs_local.storage.checkpoints import CheckpointRepository
    from xhs_local.storage.records import RecordsRepository
    from xhs_local.storage.schema import open_database
    from xhs_local.website import WebsiteSubscriptions, WebsiteVideos

    class CoreSubscriptions(WebsiteSubscriptions):
        async def _apply(self, current, sources):
            # Core owns this worker's subscriptions; Frontier's separate config stays intact.
            data = snapshot_data(current)
            data["sources"] = sources.model_dump(mode="json")
            for item in data["sources"]["sources"]:
                if item["plugin"] == "telegram":
                    for target in item["targets"]:
                        target["options"] = telegram_target_options(target.get("options", {}))

            candidate = snapshot_from_data(current.config_root, data)
            for source in candidate.sources.sources:
                if source.enabled:
                    self.scheduler.registry.prepare(
                        source, config_root=candidate.config_root, runtime_root=candidate.runtime_root
                    )
            self.scheduler.collector.set_sources(candidate)
            await self.scheduler.update_targets(candidate)

    os.environ.update({
        "DEEPSEEK_VIDEO_KEY_FILE": str(args.deepseek_key_file),
        "DEEPSEEK_VIDEO_ENDPOINT": "https://api.deepseek.com/chat/completions",
        "DEEPSEEK_VIDEO_MODEL": "deepseek-flash",
        "DEEPSEEK_VIDEO_SUMMARY_ONLY": "1",
        "YOUTUBE_WHISPER_DEVICE": "cpu",
        "YOUTUBE_WHISPER_COMPUTE_TYPE": "int8",
    })
    snapshot = load_snapshot(args.root / "config")
    agents = snapshot.app.agents.model_copy(update={
        "enabled": True, "endpoint": args.endpoint, "token_file": str(args.token_file)
    })
    snapshot = replace(snapshot, app=snapshot.app.model_copy(update={"agents": agents}))
    runtime = snapshot.runtime_root
    work = runtime / "aexus-bot"
    work.mkdir(parents=True, exist_ok=True)
    lock = (runtime / "frontier/collector.lock").open("a")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    configure_logging(work / "logs", timezone=snapshot.app.timezone, console=False)
    status = StatusStore(work / "status.json", snapshot.app.timezone)
    database = open_database(runtime / "app.sqlite3",
                             busy_timeout_seconds=snapshot.app.sqlite.busy_timeout_seconds,
                             apply_migrations=True)
    records = RecordsRepository(database, runtime)
    stop = asyncio.Event()
    videos = None

    async def collected(source_id, *_):
        if videos is not None and any(s.id == source_id and s.plugin == "youtube"
                                      for s in scheduler.snapshot.sources.sources):
            await videos.enqueue()

    scheduler = FrontierScheduler(snapshot, SourcePluginRegistry(), CheckpointRepository(database),
                                  FrontierCollector(records), collected)
    subscriptions = CoreSubscriptions(scheduler, records)
    publisher = CorePublisher(snapshot, records, subscriptions.apply_agents_targets, status.update)
    publisher.server_owned_media = True
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    task = None
    sync_task = None
    storage_task = None
    avatar_task = None
    prefetch_task = None
    content_store = ChannelContentStore(work / "channel-content", runtime / "media" / "sha256")
    documents = ChannelDocumentRequests(content_store, scheduler, publisher)
    try:
        await publisher.start()
        storage_task = asyncio.create_task(serve_channel_storage(publisher, content_store, stop, documents.handle))
        await scheduler.start()
        prefetch_task = asyncio.create_task(documents.run_prefetch(stop))
        avatar_task = asyncio.create_task(ChannelAuthorAvatars(publisher, scheduler, records, content_store).run(stop))
        videos = WebsiteVideos(scheduler, records, status)
        videos.workers = videos.workers[:1]
        await videos.start()
        task = asyncio.create_task(publisher.run(stop))
        sync_task = asyncio.create_task(publisher.watch_subscriptions(stop))
        status.update(ready=True, execution_host=socket.gethostname(), mode="aexus-bot",
                      video_summary_only=True, external_publication=False, transcription_device="cpu")
        while not stop.is_set():
            status.update(source_targets=scheduler.status_snapshot())
            with suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=5)
    finally:
        for pending in (task, sync_task, storage_task, avatar_task, prefetch_task):
            if pending is not None:
                pending.cancel()
        await asyncio.gather(*(pending for pending in (task, sync_task, storage_task, avatar_task, prefetch_task) if pending is not None),
                             return_exceptions=True)
        await documents.close()
        await scheduler.stop()
        if videos is not None:
            await videos.close()
        await publisher.close()
        content_store.close()
        database.close()
        status.update(ready=False)
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.remove_signal_handler(sig)
        lock.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True, help="Existing Frontier/Xhs source root")
    parser.add_argument("--endpoint", default="http://127.0.0.1:5152")
    parser.add_argument("--token-file", type=Path, required=True)
    parser.add_argument("--deepseek-key-file", type=Path, required=True)
    asyncio.run(run(parser.parse_args()))
