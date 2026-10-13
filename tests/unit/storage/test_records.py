from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from xhs_local.core.contracts import AttachmentInput, CollectBatch, SourceRecord
from xhs_local.core.identifiers import stable_record_id
from xhs_local.core.states import WorkTopic
from xhs_local.storage.checkpoints import CheckpointRepository
from xhs_local.storage.database import Database
from xhs_local.storage.outbox import OutboxRepository
from xhs_local.storage.records import RecordsRepository
from xhs_local.storage.work_items import PublicationLedger, WorkItemRepository

NOW = datetime(2026, 8, 19, 4, 0, tzinfo=UTC)


def record(
    external_id: str,
    *,
    target_id: str = "telegram-one",
    text: str | None = None,
    group_id: str | None = None,
    attachment: bytes | None = None,
) -> SourceRecord:
    return SourceRecord(
        record_id=stable_record_id("telegram-main", target_id, external_id),
        source_id="telegram-main",
        target_id=target_id,
        plugin_id="telegram",
        external_id=external_id,
        content_type="tech_news",
        occurred_at=NOW + timedelta(seconds=int(external_id)),
        observed_at=NOW,
        text=text or f"Detailed technology news number {external_id} with enough useful context.",
        source_name="Source",
        group_id=group_id,
        attachments=()
        if attachment is None
        else (AttachmentInput("image/gif", "motion.gif", attachment, 320, 240),),
    )


def test_collect_batch_atomically_commits_record_checkpoint_work_and_outbox(
    database: Database, runtime_root: Path
) -> None:
    repository = RecordsRepository(database, runtime_root)
    payload = b"GIF89a-original-animation"
    item = record("1", attachment=payload)
    batch = CollectBatch("telegram-main", "telegram-one", (item,), {"message_id": 1})

    result = repository.commit_batch(batch, config_revision="revision-one")

    assert result.inserted_record_ids == (item.record_id,)
    assert len(result.work_ids) == 1
    assert CheckpointRepository(database).get("telegram-main", "telegram-one") == {"message_id": 1}
    work = WorkItemRepository(database).get(result.work_ids[0])
    assert work is not None
    assert work.topic is WorkTopic.RECORD_COLLECTED
    assert work.config_revision == "revision-one"
    events = OutboxRepository(database).pending(WorkTopic.RECORD_COLLECTED)
    assert [event.work_id for event in events] == list(result.work_ids)
    stored = repository.get(item.record_id)
    assert stored is not None
    assert stored.attachments[0].sha256 == hashlib.sha256(payload).hexdigest()
    assert stored.attachments[0].absolute_path(runtime_root).read_bytes() == payload
    with database.locked() as connection:
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(attachments)")}
        assert "data" not in columns
        assert connection.execute("SELECT count(*) FROM record_versions").fetchone()[0] == 1

    duplicate = repository.commit_batch(batch)
    assert duplicate.inserted_record_ids == ()
    assert duplicate.updated_record_ids == ()
    assert duplicate.work_ids == ()


def test_record_update_versions_content_without_creating_duplicate_work(
    database: Database, runtime_root: Path
) -> None:
    repository = RecordsRepository(database, runtime_root)
    original = record("2")
    repository.commit_batch(
        CollectBatch("telegram-main", "telegram-one", (original,), {"message_id": 2})
    )
    changed = replace(
        original,
        text="Updated technology report with enough concrete information to publish.",
    )
    result = repository.commit_batch(
        CollectBatch("telegram-main", "telegram-one", (changed,), {"message_id": 2})
    )
    assert result.updated_record_ids == (original.record_id,)
    assert result.work_ids == ()
    with database.locked() as connection:
        assert connection.execute("SELECT count(*) FROM record_versions").fetchone()[0] == 2


def test_failed_batch_does_not_advance_checkpoint_or_expose_partial_work(
    database: Database, runtime_root: Path
) -> None:
    repository = RecordsRepository(database, runtime_root)
    valid = record("3", attachment=b"GIF89a-first")
    wrong_target = record("4", target_id="another-target", attachment=b"GIF89a-second")
    batch = CollectBatch("telegram-main", "telegram-one", (valid, wrong_target), {"message_id": 4})

    with pytest.raises(ValueError, match="match the batch"):
        repository.commit_batch(batch)

    assert repository.count() == 0
    assert CheckpointRepository(database).get("telegram-main", "telegram-one") is None
    assert WorkItemRepository(database).recoverable_ids() == []
    assert OutboxRepository(database).undispatched_count() == 0


def test_news_candidates_preserve_album_grouping_and_publication_marks(
    database: Database, runtime_root: Path
) -> None:
    repository = RecordsRepository(database, runtime_root)
    caption = record(
        "10",
        group_id="14294722741258525",
        attachment=b"GIF89a-caption",
    )
    image = record(
        "11",
        group_id="14294722741258525",
        text="",
        attachment=b"GIF89a-album",
    )
    # The helper's fallback text is non-empty, so recreate the media-only message.
    image = replace(image, text="", occurred_at=caption.occurred_at)
    repository.commit_batch(
        CollectBatch("telegram-main", "telegram-one", (caption, image), {"message_id": 11})
    )

    candidates = repository.news_candidates(
        NOW,
        NOW + timedelta(minutes=1),
        sink="xiaohongshu",
        account_id="main",
    )
    assert len(candidates) == 1
    assert candidates[0].group_record_ids == (caption.record_id, image.record_id)
    assert [
        attachment.absolute_path(runtime_root).read_bytes()
        for attachment in candidates[0].attachments
    ] == [b"GIF89a-caption", b"GIF89a-album"]

    PublicationLedger(database).mark_records(
        list(candidates[0].group_record_ids),
        "published",
        sink="xiaohongshu",
        account_id="main",
    )
    assert (
        repository.news_candidates(
            NOW,
            NOW + timedelta(minutes=1),
            sink="xiaohongshu",
            account_id="main",
        )
        == []
    )


def test_news_candidates_can_be_isolated_by_source_plugin(
    database: Database, runtime_root: Path
) -> None:
    repository = RecordsRepository(database, runtime_root)
    telegram = record("20")
    x_post = replace(
        record("21", target_id="x-karpathy"),
        record_id=stable_record_id("x-main", "x-karpathy", "21"),
        source_id="x-main",
        plugin_id="x",
        source_name="Andrej Karpathy @karpathy",
        payload={"avatar_attachment_index": 0},
        attachments=(
            AttachmentInput("image/webp", "avatar.webp", b"RIFF0000WEBPavatar", 96, 96),
            AttachmentInput("image/jpeg", "post.jpg", b"\xff\xd8\xffpost", 640, 480),
        ),
    )
    repository.commit_batch(
        CollectBatch("telegram-main", "telegram-one", (telegram,), {"message_id": 20})
    )
    repository.commit_batch(CollectBatch("x-main", "x-karpathy", (x_post,), {}))

    x_candidates = repository.news_candidates(
        NOW,
        NOW + timedelta(minutes=1),
        sink="xiaohongshu",
        account_id="main",
        plugin_ids=("x",),
    )
    telegram_candidates = repository.news_candidates(
        NOW,
        NOW + timedelta(minutes=1),
        sink="xiaohongshu",
        account_id="main",
        plugin_ids=("telegram",),
    )

    assert [candidate.source_name for candidate in x_candidates] == ["Andrej Karpathy @karpathy"]
    assert x_candidates[0].plugin_id == "x"
    assert x_candidates[0].avatar is not None
    assert x_candidates[0].avatar.file_name == "avatar.webp"
    assert [attachment.file_name for attachment in x_candidates[0].attachments] == ["post.jpg"]
    assert [candidate.record_id for candidate in telegram_candidates] == [telegram.record_id]
    assert telegram_candidates[0].plugin_id == "telegram"


def test_recent_published_counts_are_grouped_by_source_plugin(
    database: Database,
    runtime_root: Path,
) -> None:
    repository = RecordsRepository(database, runtime_root)
    telegram = record("24")
    x_post = replace(
        record("25", target_id="x-author"),
        record_id=stable_record_id("x-main", "x-author", "25"),
        source_id="x-main",
        plugin_id="x",
    )
    repository.upsert(telegram)
    repository.upsert(x_post)
    ledger = PublicationLedger(database)
    ledger.mark_records(
        [telegram.record_id],
        "published",
        sink="xiaohongshu",
        account_id="main",
        now=NOW,
    )
    ledger.mark_records(
        [x_post.record_id],
        "published",
        sink="xiaohongshu",
        account_id="main",
        now=NOW - timedelta(days=2),
    )

    assert repository.published_counts_by_plugin(
        NOW - timedelta(hours=24),
        sink="xiaohongshu",
        account_id="main",
        plugin_ids=("telegram", "x"),
    ) == {"telegram": 1, "x": 0}


def test_x_candidate_reuses_latest_stored_avatar_for_same_target(
    database: Database,
    runtime_root: Path,
) -> None:
    repository = RecordsRepository(database, runtime_root)
    avatar_record = replace(
        record("30", target_id="x-author"),
        record_id=stable_record_id("x-main", "x-author", "30"),
        source_id="x-main",
        plugin_id="x",
        source_name="Author @author",
        payload={"avatar_attachment_index": 0},
        attachments=(AttachmentInput("image/jpeg", "avatar.jpg", b"\xff\xd8\xffavatar", 96, 96),),
    )
    no_avatar_record = replace(
        record("31", target_id="x-author"),
        record_id=stable_record_id("x-main", "x-author", "31"),
        source_id="x-main",
        plugin_id="x",
        source_name="Author @author",
        payload={},
        attachments=(),
    )
    repository.upsert(avatar_record)
    repository.upsert(no_avatar_record)

    candidates = repository.news_candidates(
        NOW,
        NOW + timedelta(minutes=1),
        sink="xiaohongshu",
        account_id="main",
        plugin_ids=("x",),
    )
    reused = next(
        candidate for candidate in candidates if candidate.record_id == no_avatar_record.record_id
    )

    assert reused.avatar is not None
    assert reused.avatar.file_name == "avatar.jpg"
    assert reused.avatar.record_id == avatar_record.record_id
