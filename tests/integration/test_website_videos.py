from __future__ import annotations

import asyncio
import base64
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from xhs_local.configuration.models import AgentsTarget
from xhs_local.core.contracts import AttachmentInput, SourceRecord
from xhs_local.core.states import WorkState, WorkTopic
from xhs_local.pipeline.agents import AgentsPublisher
from xhs_local.storage.outbox import OutboxRepository
from xhs_local.storage.records import RecordsRepository
from xhs_local.storage.schema import open_database
from xhs_local.storage.work_items import WorkItemRepository
from xhs_local.website import WebsiteVideos


def video(key="video", **changes):
    now = datetime.now(UTC)
    return replace(SourceRecord(
        record_id=key, source_id="youtube-local", target_id="creator", plugin_id="youtube",
        external_id="platform-" + key, content_type="video_pending", occurred_at=now,
        observed_at=now, title="Original title", text="", source_name="Original creator",
        source_url="https://www.youtube.com/watch?v=" + key,
    ), **changes)


def completed(record):
    return replace(
        record, content_type="tech_news",
        text="## 视频总结\n\n完整总结。\n\n## 全文中文翻译\n\n第一段译文。\n\n最后一段译文。",
        attachments=(AttachmentInput("image/png", "cover.png", b"original-cover-bytes"),),
    )


@pytest.fixture
def records(tmp_path):
    with open_database(tmp_path / "test.sqlite3", apply_migrations=True) as database:
        yield RecordsRepository(database, tmp_path / "runtime")


def make_videos(monkeypatch, tmp_path, records):
    started, gate, cancelled, preparations, providers = asyncio.Queue(), asyncio.Event(), [], [], []

    class Provider:
        def __init__(self, **options):
            providers.append(options)

        async def complete(self, *_args, **_kwargs):
            raise AssertionError("This integration test must not request a model")

    class Preparation:
        def __init__(self, **options):
            self.options = options
            preparations.append(self)

        async def __call__(self, work):
            started.put_nowait(work.record_id)
            try:
                await gate.wait()
            except asyncio.CancelledError:
                cancelled.append(work.record_id)
                raise

    def no_review(*_args, **_kwargs):
        raise AssertionError("Website video enrichment must not construct legacy review")

    monkeypatch.setattr("xhs_local.processing.provider.DeepSeekProvider", Provider)
    monkeypatch.setattr("xhs_local.pipeline.video.VideoPreparationService", Preparation)
    monkeypatch.setattr(
        "xhs_local.plugins.sources.youtube.client.YouTubeClient",
        lambda **options: SimpleNamespace(options=options),
    )
    monkeypatch.setattr(
        "xhs_local.processing.transcription.LocalWhisperClient",
        lambda _root: SimpleNamespace(),
    )
    snapshot = SimpleNamespace(
        revision="fixture-revision", runtime_root=tmp_path / "runtime",
        resolve=lambda value: tmp_path / value,
        app=SimpleNamespace(
            queues=SimpleNamespace(ingest_maxsize=8),
            agents=SimpleNamespace(
                enabled=True, endpoint="http://127.0.0.1:1", token_file="unused-token",
                poll_seconds=5,
            ),
        ),
        publishing=SimpleNamespace(news=SimpleNamespace(deepseek_key_path="unused-key")),
        sources=SimpleNamespace(sources=[SimpleNamespace(
            id="youtube-local", plugin="youtube", options={},
        )]),
    )
    scheduler = SimpleNamespace(
        snapshot=snapshot, collector=SimpleNamespace(targets={("youtube-local", "creator")}),
    )
    status = {}
    videos = WebsiteVideos(scheduler, records, SimpleNamespace(update=status.update))
    return SimpleNamespace(
        videos=videos, snapshot=snapshot, status=status, started=started, gate=gate,
        cancelled=cancelled, preparation=preparations[0], providers=providers,
    )


def test_pending_video_enqueue_is_atomic_idempotent_and_video_only(records):
    since = datetime.now(UTC) - timedelta(hours=48)
    candidates = [
        video(), video("expired", occurred_at=since - timedelta(seconds=1)),
        video("disabled", target_id="disabled"), video("other-platform", plugin_id="x"),
        video("ready", content_type="tech_news"), video("terminal"),
    ]
    for record in candidates:
        records.upsert(record)
    terminal = records.get("terminal")
    records.mark_agents_news("terminal", "core-source", terminal.content_hash, "deleted")
    targets = {("youtube-local", "creator")}

    def enqueue(_index):
        return records.enqueue_pending_videos(targets, since, config_revision="accepted-config")

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(enqueue, range(4))) == 1
    assert enqueue(5) == 0
    with records.database.locked() as connection:
        works = connection.execute("SELECT * FROM work_items").fetchall()
        outbox = connection.execute("SELECT * FROM outbox").fetchall()
    assert len(works) == len(outbox) == 1
    assert works[0]["record_id"] == "video"
    assert works[0]["topic"] == outbox[0]["topic"] == WorkTopic.VIDEO_PREPARE.value
    assert works[0]["config_revision"] == "accepted-config"
    assert outbox[0]["work_id"] == works[0]["work_id"]


def test_pending_youtube_is_not_exported_then_ready_updates_same_id_and_media(
    records, monkeypatch, tmp_path,
):
    fixture = make_videos(monkeypatch, tmp_path, records)
    original = video()
    records.upsert(original)
    raw = records.get(original.record_id)
    target = AgentsTarget(
        sourceId="core-source", targetId="creator", plugin="youtube",
        locator="https://www.youtube.com/@Creator", name="Creator", enabled=True,
        pollSeconds=3600,
    )
    calls = []

    async def apply(_targets):
        raise AssertionError("No subscription refresh is needed in this fixture")

    async def call(command, args):
        calls.append((command, args))
        if command == "channel.media-put":
            return {"media": {"id": "core-cover"}}
        assert command == "channel.publish"
        return {"status": "updated"}

    async def run():
        publisher = AgentsPublisher(fixture.snapshot, records, apply, lambda **_values: None)
        publisher.targets = {("youtube", "creator"): target}
        publisher.last_refresh = asyncio.get_running_loop().time()
        monkeypatch.setattr(publisher, "_call", call)
        await publisher.publish_pending(asyncio.Event())
        assert calls == [], "raw video_pending must never reach Agents"
        # An old raw version may already exist in Core; enrichment must update its identity.
        records.mark_agents_news(original.record_id, target.sourceId, raw.content_hash, "created")
        ready = completed(original)
        assert fixture.videos._commit_ready(ready)
        stored = records.get(original.record_id)
        assert stored.content_hash != raw.content_hash
        assert stored.record.external_id == original.external_id
        assert stored.record.text == ready.text
        assert stored.attachments[0].absolute_path(records.media.runtime_root).read_bytes() == (
            b"original-cover-bytes"
        )
        await publisher.publish_pending(asyncio.Event())
        assert [command for command, _args in calls] == ["channel.media-put", "channel.publish"]
        assert base64.b64decode(calls[0][1]["data"]) == b"original-cover-bytes"
        sent = calls[1][1]
        assert sent["externalId"] == original.external_id
        assert sent["sourceId"] == target.sourceId
        assert sent["contentHash"] == stored.content_hash
        assert sent["body"] == ready.text and sent["mediaIds"] == ["core-cover"]
        assert sent["publishedAt"] == int(original.occurred_at.timestamp() * 1000)
        await publisher.publish_pending(asyncio.Event())
        assert len(calls) == 2, "confirmed enriched hash is not resent"

    asyncio.run(run())


@pytest.mark.parametrize("reason", ["deleted", "expired", "disabled"])
def test_commit_ready_rechecks_current_state_under_lock_without_resurrection(
    records, monkeypatch, tmp_path, reason,
):
    fixture = make_videos(monkeypatch, tmp_path, records)
    original = video()
    if reason == "expired":
        original = replace(original, occurred_at=datetime.now(UTC) - timedelta(hours=49))
    records.upsert(original)
    before = records.get(original.record_id)
    started = threading.Event()

    def finish():
        started.set()
        return fixture.videos._commit_ready(completed(original))

    with ThreadPoolExecutor(max_workers=1) as pool:
        with records.database.locked():
            future = pool.submit(finish)
            assert started.wait(2)
            if reason == "deleted":
                records.delete_news(original.record_id)
            elif reason == "disabled":
                fixture.videos.scheduler.collector.targets.clear()
        assert future.result(timeout=2) is False
    after = records.get(original.record_id)
    if reason == "deleted":
        assert after is None
        assert records.deleted_news_ids((original.record_id,)) == {original.record_id}
    else:
        assert after.content_hash == before.content_hash
        assert after.record.content_type == "video_pending"
    assert not any(path.is_file() for path in records.media.root.rglob("*"))


def test_start_close_uses_only_video_workers_and_does_not_recover_legacy_work(
    records, monkeypatch, tmp_path,
):
    async def run():
        fixture = make_videos(monkeypatch, tmp_path, records)
        videos = fixture.videos
        options = fixture.preparation.options
        assert not options.get("channel_mode", False) and "image_review" not in options
        assert options["summarizer"] is None
        assert fixture.providers == []
        assert set(videos.dispatcher.queues) == {WorkTopic.VIDEO_PREPARE}
        assert all(set(worker.handlers) == {WorkTopic.VIDEO_PREPARE} for worker in videos.workers)
        assert videos.recovery.topic == videos.retries.topic == WorkTopic.VIDEO_PREPARE
        records.upsert(video())
        with records.database.transaction() as connection:
            legacy = WorkItemRepository.create_in(connection, WorkTopic.NEWS_PUBLISH)
            OutboxRepository.add_in(connection, WorkTopic.NEWS_PUBLISH, legacy)
        videos.works.claim(legacy)
        await videos.start()
        try:
            assert await asyncio.wait_for(fixture.started.get(), 2) == "video"
            assert videos.active == {"video"}
            assert fixture.status["video_enrichment"]["active"] == ["video"]
            assert videos.works.get(legacy).state is WorkState.RUNNING
            assert len(OutboxRepository(records.database).pending(WorkTopic.NEWS_PUBLISH)) == 1
            fixture.gate.set()
            async with asyncio.timeout(2):
                while videos.active:
                    await asyncio.sleep(0.01)
            await videos.workers[0].queue.join()
            with records.database.locked() as connection:
                completed_work = connection.execute(
                    "SELECT state FROM work_items WHERE record_id='video'"
                ).fetchone()
            assert completed_work["state"] == WorkState.SUCCEEDED.value
            fixture.gate.clear()
            records.upsert(video("second"))
            await videos.enqueue()
            assert await asyncio.wait_for(fixture.started.get(), 2) == "second"
        finally:
            await videos.close()
        assert fixture.cancelled == ["second"]
        assert all(task.done() for task in videos.tasks)
        assert videos.active == set() and fixture.status["video_enrichment"]["active"] == []
        assert videos.works.get(legacy).state is WorkState.RUNNING
        assert len(OutboxRepository(records.database).pending(WorkTopic.NEWS_PUBLISH)) == 1

    asyncio.run(run())
