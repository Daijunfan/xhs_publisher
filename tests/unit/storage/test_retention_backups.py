from __future__ import annotations

import json
import os
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

from xhs_local.core.contracts import AttachmentInput, SourceRecord
from xhs_local.core.identifiers import stable_record_id
from xhs_local.core.states import WorkTopic
from xhs_local.storage.backups import BackupService
from xhs_local.storage.database import Database
from xhs_local.storage.outbox import OutboxRepository
from xhs_local.storage.records import RecordsRepository
from xhs_local.storage.retention import RetentionService
from xhs_local.storage.video_artifacts import VideoArtifacts
from xhs_local.storage.work_items import WorkItemRepository

NOW = datetime(2026, 8, 19, 6, 0, tzinfo=UTC)


def test_online_backup_captures_schema_and_config_snapshot(
    database: Database, runtime_root: Path, tmp_path: Path
) -> None:
    with database.transaction() as connection:
        connection.execute("INSERT INTO legacy_sync_state(key,value) VALUES('proof','one')")
    config = tmp_path / "app.yaml"
    config.write_text("version: 1\n", encoding="utf-8")
    service = BackupService(database)

    first = service.create(runtime_root / "backups", config_paths=[config], now=NOW)
    service.verify(first.database_path, expected_schema_version=5)
    assert "20260819T140000+0800" in first.database_path.name
    metadata = json.loads(first.metadata_path.read_text(encoding="utf-8"))
    assert datetime.fromisoformat(metadata["created_at"]).utcoffset() == timedelta(hours=8)
    assert (first.config_directory / "app.yaml").read_text(encoding="utf-8") == "version: 1\n"
    with Database(first.database_path, read_only=True) as backup, backup.locked() as connection:
        assert (
            connection.execute("SELECT value FROM legacy_sync_state WHERE key='proof'").fetchone()[
                0
            ]
            == "one"
        )

    second = service.create(runtime_root / "backups", now=NOW + timedelta(seconds=1))
    os.utime(first.database_path, (NOW.timestamp(), NOW.timestamp()))
    os.utime(second.database_path, (NOW.timestamp() + 1, NOW.timestamp() + 1))
    removed = service.prune(runtime_root / "backups", keep=1)
    assert removed == [first.database_path]
    assert second.database_path.exists()


def test_retention_deletes_only_safe_terminal_state_and_unreferenced_files(
    database: Database, runtime_root: Path
) -> None:
    work_items = WorkItemRepository(database)
    outbox = OutboxRepository(database)
    work_id = work_items.create(WorkTopic.RECORD_COLLECTED, now=NOW)
    event_id = outbox.add(WorkTopic.RECORD_COLLECTED, work_id, now=NOW)
    outbox.mark_dispatched(event_id, now=NOW)
    work_items.claim(work_id, now=NOW)
    work_items.succeed(work_id, now=NOW)

    orphan = runtime_root / "media" / "sha256" / "aa" / ("a" * 64)
    orphan.parent.mkdir(parents=True)
    orphan.write_bytes(b"orphan")
    old = (NOW - timedelta(days=2)).timestamp()
    os.utime(orphan, (old, old))
    service = RetentionService(database, runtime_root)
    cutoff = NOW + timedelta(days=1)
    assert service.purge_dispatched_outbox(cutoff) == 1
    assert service.purge_terminal_work(cutoff) == 1
    assert service.purge_orphan_media(NOW - timedelta(days=1)) == 1
    assert not orphan.exists()


def test_referenced_media_is_never_removed_as_an_orphan(
    database: Database, runtime_root: Path
) -> None:
    data = b"GIF89a-retained"
    item = SourceRecord(
        record_id=stable_record_id("source", "target", "one"),
        source_id="source",
        target_id="target",
        plugin_id="telegram",
        external_id="one",
        content_type="tech_news",
        occurred_at=NOW,
        observed_at=NOW,
        text="A sufficiently detailed technology report for retention testing.",
        source_name="Source",
        attachments=(AttachmentInput("image/gif", "one.gif", data),),
    )
    repository = RecordsRepository(database, runtime_root)
    repository.upsert(item)
    path = repository.get(item.record_id).attachments[0].absolute_path(runtime_root)
    old = (NOW - timedelta(days=2)).timestamp()
    os.utime(path, (old, old))

    assert RetentionService(database, runtime_root).purge_orphan_media(NOW - timedelta(days=1)) == 0
    assert path.read_bytes() == data


def test_news_cleanup_removes_only_orphan_video_caches(
    database: Database, runtime_root: Path
) -> None:
    repository = RecordsRepository(database, runtime_root)
    service = RetentionService(database, runtime_root)
    works = WorkItemRepository(database)
    base = SourceRecord(
        record_id="retained", source_id="youtube-source", target_id="creator",
        plugin_id="youtube", external_id="retained", content_type="tech_news",
        occurred_at=NOW - timedelta(days=6), observed_at=NOW,
        text="Retained full article", source_name="Creator",
    )
    values = [
        base,
        replace(
            base, record_id="favorite", external_id="favorite",
            occurred_at=NOW - timedelta(days=9),
        ),
        replace(
            base, record_id="expired", external_id="expired",
            occurred_at=NOW - timedelta(days=8),
        ),
        replace(base, record_id="deleted", external_id="deleted"),
        replace(base, record_id="active", external_id="active", content_type="video_pending"),
    ]
    caches = {}
    for record in values:
        repository.upsert(record)
        cache = VideoArtifacts(runtime_root, record.plugin_id, record.external_id)
        cache.save("transcript.json", {"text": "Complete source text"})
        (cache.root / "audio.mp3").write_bytes(b"retained audio")
        caches[record.record_id] = cache.root
    repository.set_news_favorite("favorite", True)
    active = works.create(WorkTopic.VIDEO_PREPARE, record_id="active", now=NOW)
    works.claim(active, now=NOW)
    orphan = VideoArtifacts(runtime_root, "youtube", "no-record")
    orphan.save("state.json", {"stage": "abandoned"})
    models = runtime_root / "models" / "whisper-turbo"
    models.mkdir(parents=True)
    (models / "model.bin").write_bytes(b"model must stay")
    unmanaged = runtime_root / "videos" / "user-notes"
    unmanaged.mkdir()
    (unmanaged / "keep.txt").write_text("not a VideoArtifacts directory")
    link = runtime_root / "videos" / ("a" * 64)
    link.symlink_to(models, target_is_directory=True)

    repository.delete_news("deleted")
    assert service.purge_news(NOW - timedelta(days=7)) == 2
    service.purge_news_posters()
    for key in ("retained", "active"):
        assert (caches[key] / "audio.mp3").read_bytes() == b"retained audio"
        assert repository.get(key) is not None
    assert not caches["deleted"].exists() and not caches["expired"].exists()
    assert not caches["favorite"].exists()
    assert not orphan.root.exists()
    assert link.is_symlink() and (models / "model.bin").read_bytes() == b"model must stay"
    assert (unmanaged / "keep.txt").read_text() == "not a VideoArtifacts directory"
    assert works.get(active).state.value == "RUNNING"
    assert repository.news_feed(favorites=True)["favorite_count"] == 0


def test_video_cache_is_retained_until_last_platform_record_is_removed(
    database: Database, runtime_root: Path
) -> None:
    repository = RecordsRepository(database, runtime_root)
    first = SourceRecord(
        record_id="one-source", source_id="source-one", target_id="one", plugin_id="youtube",
        external_id="shared-video", content_type="video_pending", occurred_at=NOW,
        observed_at=NOW, text="", source_name="Creator",
    )
    second = replace(first, record_id="another-source", source_id="source-two", target_id="two")
    repository.upsert(first)
    repository.upsert(second)
    cache = VideoArtifacts(runtime_root, "youtube", "shared-video")
    cache.save("summary.json", {"text": "Shared cached summary"})
    service = RetentionService(database, runtime_root)
    repository.delete_news(first.record_id)
    service.purge_news_posters()
    assert cache.read("summary.json") == {"text": "Shared cached summary"}
    repository.delete_news(second.record_id)
    service.purge_news_posters()
    assert not cache.root.exists()


def test_video_cache_root_symlink_never_purges_models(
    database: Database, runtime_root: Path
) -> None:
    models = runtime_root / "models"
    model = models / ("b" * 64)
    model.mkdir(parents=True)
    (model / "model.bin").write_bytes(b"model data")
    (runtime_root / "videos").symlink_to(models, target_is_directory=True)
    RetentionService(database, runtime_root).purge_news_posters()
    assert (model / "model.bin").read_bytes() == b"model data"
