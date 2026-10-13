from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from threading import get_ident

import pytest
from PIL import Image

from xhs_local.core.contracts import CollectBatch, SourceRecord
from xhs_local.core.errors import TransientError, ValidationFailure
from xhs_local.core.identifiers import stable_record_id
from xhs_local.core.states import WorkState, WorkTopic
from xhs_local.pipeline.video import VideoPreparationService
from xhs_local.processing.provider import DeepSeekResponseError
from xhs_local.processing.video_summary import translation_chunks
from xhs_local.storage.database import Database
from xhs_local.storage.records import RecordsRepository
from xhs_local.storage.schema import migrate
from xhs_local.storage.video_artifacts import VideoArtifacts
from xhs_local.storage.work_items import WorkItemRepository


class Client:
    def __init__(self, published_at):
        self.published_at = published_at.replace(microsecond=0)
        self.downloads = 0
        self.metadata_calls = 0
        self.audio_duration = 60

    async def metadata(self, url):
        self.metadata_calls += 1
        return {
            "id": "new",
            "title": "完整视频标题",
            "timestamp": self.published_at.timestamp(),
            "duration": 60,
            "webpage_url": url,
            "uploader": "作者",
            "uploader_id": "creator",
        }

    async def images(self, record, metadata, directory):
        for name in ("avatar.png", "cover.png"):
            Image.new("RGB", (160, 90), "#e8ddff").save(directory / name)
        return ["avatar.png", "cover.png"]

    async def audio(self, url, directory, *, expected_duration=None):
        self.downloads += 1
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "audio.mp3"
        path.write_bytes(b"test-audio")
        return path

    async def duration(self, audio):
        return self.audio_duration


class Transcription:
    def __init__(self, *, pending=False, failure=None):
        self.pending, self.failure = pending, failure
        self.uploads = self.submits = self.polls = 0

    async def upload(self, audio):
        self.uploads += 1
        return "oss://test-audio"

    async def submit(self, url):
        self.submits += 1
        return "saved-task-id"

    async def result(self, task_id, *, expected_duration):
        assert task_id == "saved-task-id"
        self.polls += 1
        if self.failure:
            raise self.failure
        if self.pending:
            return None
        return {"text": "完整的音频转写内容，包括方法和数字。", "duration": 60, "raw": {}}


class Summarizer:
    def __init__(self, failure=None):
        self.calls, self.failure = 0, failure

    async def summarize(self, title, transcript):
        self.calls += 1
        if self.failure:
            raise self.failure
        assert title == "完整视频标题"
        assert "完整的音频" in transcript
        return "核心方法与具体信息。" * 35


@pytest.fixture
def environment(tmp_path):
    db = Database(tmp_path / "app.sqlite3")
    migrate(db)
    yield db, RecordsRepository(db, tmp_path), WorkItemRepository(db), tmp_path
    db.close()


def setup_job(
    environment,
    *,
    platform="youtube",
    client=None,
    transcription=None,
    summarizer=None,
    channel_mode=False,
    commit_ready=None,
):
    db, records, works, root = environment
    now = datetime.now(UTC)
    record = SourceRecord(
        record_id=stable_record_id(platform, platform, "new"),
        source_id=platform,
        target_id=platform + "-creator",
        plugin_id=platform,
        external_id="new",
        content_type="video_pending",
        occurred_at=now,
        observed_at=now,
        text="",
        source_name="作者",
        source_url="https://example.test/video",
        payload={"activated_at": (now - timedelta(hours=1)).isoformat(), "creator_id": "creator"},
    )
    batch = CollectBatch(
        platform,
        record.target_id,
        (record,),
        {},
        work_topic=WorkTopic.VIDEO_PREPARE,
        preserve_existing=True,
    )
    committed = records.commit_batch(batch, work_topic=batch.work_topic)
    work = works.claim(committed.work_ids[0])
    client = client or Client(now - timedelta(minutes=5))
    transcription = transcription or Transcription()
    summarizer = summarizer or Summarizer()
    service = VideoPreparationService(
        records=records,
        work_items=works,
        runtime_root=root,
        client_for=lambda _source: client,
        transcription=transcription,
        summarizer=summarizer,
        channel_mode=channel_mode,
        commit_ready=commit_ready,
    )
    return service, work, record, batch, client, transcription, summarizer


@pytest.mark.parametrize("platform", ["youtube"])
def test_complete_pipeline_resumes_without_duplicate_download_transcription_or_work(
    environment, platform
):
    db, records, works, root = environment
    transcription = Transcription(pending=True)
    service, work, original, batch, client, transcription, summarizer = setup_job(
        environment, platform=platform, transcription=transcription
    )
    asyncio.run(service(work))
    assert works.get(work.work_id).state == WorkState.RETRY_WAIT
    assert records.get(original.record_id).record.content_type == "video_pending"
    assert client.downloads == transcription.submits == 1
    assert summarizer.calls == 0
    assert records.commit_batch(batch, work_topic=batch.work_topic).work_ids == ()
    transcription.pending = False
    restarted = VideoPreparationService(
        records=records,
        work_items=works,
        runtime_root=root,
        client_for=lambda _source: client,
        transcription=transcription,
        summarizer=summarizer,
    )
    asyncio.run(restarted(work))
    ready = records.get(original.record_id)
    assert ready.record.content_type == "tech_news"
    assert ready.record.title == "完整视频标题"
    assert ready.record.payload["video_verified"] is True
    assert len(ready.attachments) == 2
    assert ready.record.source_url == original.source_url
    assert ready.record.occurred_at == client.published_at
    artifacts = VideoArtifacts(root, platform, "new")
    assert artifacts.read("state.json")["stage"] == "ready"
    assert artifacts.read("transcript-1.json")["text"]
    assert artifacts.read("summary.json")["text"] == ready.record.text
    asyncio.run(restarted(work))
    records.commit_batch(batch, work_topic=batch.work_topic)
    assert records.get(original.record_id).record.content_type == "tech_news"
    assert (
        client.metadata_calls
        == client.downloads
        == transcription.uploads
        == transcription.submits
        == summarizer.calls
        == 1
    )
    with db.locked() as connection:
        assert connection.execute("SELECT count(*) FROM work_items").fetchone()[0] == 1


def test_history_is_rejected_before_audio_or_transcription(environment):
    client = Client(datetime.now(UTC) - timedelta(days=1))
    service, work, record, _, client, speech, summary = setup_job(environment, client=client)
    asyncio.run(service(work))
    assert environment[1].get(record.record_id).record.content_type == "video_ignored"
    assert client.downloads == speech.submits == summary.calls == 0


@pytest.mark.parametrize("phase", ["audio", "transcription", "summary"])
def test_failed_or_incomplete_video_never_becomes_publishable(environment, phase):
    client = Client(datetime.now(UTC) - timedelta(minutes=2))
    if phase == "audio":
        client.audio_duration = 12
    transcription = Transcription(
        failure=ValidationFailure("partial") if phase == "transcription" else None
    )
    summarizer = Summarizer(
        failure=(
            ValidationFailure("incomplete")
            if phase == "summary"
            else None
        )
    )
    service, work, record, _, client, speech, summary = setup_job(
        environment,
        client=client,
        transcription=transcription,
        summarizer=summarizer,
    )
    with pytest.raises(ValidationFailure):
        asyncio.run(service(work))
    assert environment[1].get(record.record_id).record.content_type == "video_pending"
    assert (
        environment[1].news_candidates(
            datetime.now(UTC) - timedelta(days=2),
            datetime.now(UTC),
            sink="xiaohongshu",
            account_id="main",
        )
        == []
    )
    if phase == "image":
        assert client.downloads == speech.submits == 0


def test_network_failure_preserves_cloud_task_and_retries_only_result(environment):
    speech = Transcription(failure=TransientError("offline"))
    service, work, _, _, client, speech, summary = setup_job(environment, transcription=speech)
    with pytest.raises(TransientError):
        asyncio.run(service(work))
    speech.failure = None
    asyncio.run(service(work))
    assert client.downloads == speech.uploads == speech.submits == summary.calls == 1


def test_ambiguous_cloud_submission_is_not_submitted_again(environment):
    class AmbiguousSpeech(Transcription):
        async def submit(self, url):
            self.submits += 1
            raise TransientError("response lost")

    speech = AmbiguousSpeech()
    service, work, _, _, client, speech, summary = setup_job(environment, transcription=speech)
    with pytest.raises(TransientError):
        asyncio.run(service(work))
    asyncio.run(service(work))
    assert environment[2].get(work.work_id).state == WorkState.WAITING_OPERATOR
    assert speech.submits == 1
    assert summary.calls == 0


class Translator(Summarizer):
    def __init__(self, *, fail_chunk=None):
        super().__init__()
        self.translations = []
        self.fail_chunk = fail_chunk

    async def translate_piece(self, title, source):
        assert title == "完整视频标题"
        self.translations.append(source)
        if len(self.translations) == self.fail_chunk:
            raise DeepSeekResponseError("fixture translation interrupted")
        return "译文：" + source


def test_channel_translation_resumes_chunks_preserves_timestamp_and_republishes(environment):
    db, records, works, root = environment
    full = "完整的音频" + "first section. " * 600 + "\n\n" + "最后一段不能丢。" * 650

    class LongSpeech(Transcription):
        async def result(self, task_id, *, expected_duration):
            result = await super().result(task_id, expected_duration=expected_duration)
            return {**result, "text": full}

    translator = Translator(fail_chunk=2)
    service, work, original, _batch, client, speech, _summary = setup_job(
        environment, channel_mode=True, transcription=LongSpeech(), summarizer=translator
    )
    raw = records.get(original.record_id)
    records.mark_agents_news(original.record_id, "core-source", raw.content_hash, "created")
    sources = {("youtube", original.target_id): "core-source"}
    since = original.occurred_at - timedelta(days=1)
    assert records.pending_agents_news(sources, since) == []
    with pytest.raises(DeepSeekResponseError, match="translation interrupted"):
        asyncio.run(service(work))
    pending = records.get(original.record_id)
    assert pending.record.content_type == "video_pending"
    assert pending.record.text == "" and pending.attachments == ()
    assert pending.content_hash == raw.content_hash
    cache = VideoArtifacts(root, "youtube", "new")
    assert cache.read("translation-1.json")
    assert cache.read("translation-2.json") is None
    assert "images_approved" not in cache.read("state.json")

    resumed = VideoPreparationService(
        records=records, work_items=works, runtime_root=root,
        client_for=lambda _source: client, transcription=speech, summarizer=translator,
        channel_mode=True,
    )
    asyncio.run(resumed(work))
    ready = records.get(original.record_id)
    chunks = translation_chunks(full)
    assert len(chunks) > 1 and "".join(chunks) == full
    assert translator.translations == [chunks[0], chunks[1], *chunks[1:]]
    assert ready.record.text == (
        "## 视频总结\n\n" + cache.read("summary.json")["text"]
        + "\n\n## 全文中文翻译\n\n" + "\n\n".join("译文：" + part for part in chunks)
    )
    assert ready.record.text.endswith("最后一段不能丢。")
    assert ready.record.occurred_at == raw.record.occurred_at
    assert ready.record.occurred_at != client.published_at
    assert ready.record.record_id == original.record_id
    assert ready.record.external_id == original.external_id
    assert ready.record.content_type == "tech_news" and len(ready.attachments) == 2
    assert cache.read("state.json")["stage"] == "ready"
    assert client.downloads == speech.submits == speech.polls == translator.calls == 1
    assert records.pending_agents_news(sources, since) == [(original.record_id, "core-source")]
    asyncio.run(resumed(work))
    assert translator.translations == [chunks[0], chunks[1], *chunks[1:]]


def test_channel_commit_false_discards_without_publishing_partial_record(environment):
    _db, records, _works, root = environment
    calls, threads = [], []
    caller_thread = get_ident()

    def commit(record):
        calls.append(record)
        threads.append(get_ident())
        return False

    service, work, original, *_rest = setup_job(
        environment, channel_mode=True, summarizer=Translator(), commit_ready=commit
    )
    asyncio.run(service(work))
    assert len(calls) == 1 and calls[0].content_type == "tech_news"
    assert "## 全文中文翻译" in calls[0].text
    assert threads[0] != caller_thread
    assert records.get(original.record_id).record.content_type == "video_pending"
    assert VideoArtifacts(root, "youtube", "new").read("state.json")["stage"] == "discarded"


def test_channel_historical_record_does_not_bypass_guarded_commit(environment):
    from dataclasses import replace

    _db, records, _works, root = environment
    calls = []
    service, work, original, _batch, client, speech, summary = setup_job(
        environment, channel_mode=True, summarizer=Translator(), commit_ready=calls.append
    )
    old = replace(original, occurred_at=original.occurred_at - timedelta(days=1))
    records.upsert(old)
    stored_old = records.get(original.record_id)
    asyncio.run(service(work))
    assert records.get(original.record_id).record.content_type == "video_pending"
    assert records.get(original.record_id).record.occurred_at == stored_old.record.occurred_at
    assert calls == [] and client.downloads == speech.submits == summary.calls == 0
    assert VideoArtifacts(root, "youtube", "new").read("state.json")["stage"] == "discarded"


def test_publisher_video_preparation_keeps_transcript_without_model_call(environment):
    service, work, record, _, client, speech, summary = setup_job(environment)
    service.summarizer = None
    asyncio.run(service(work))
    ready = environment[1].get(record.record_id)
    assert ready.record.content_type == "tech_news"
    assert ready.record.text == "完整的音频转写内容，包括方法和数字。"
    assert summary.calls == 0
    assert speech.submits == 1
