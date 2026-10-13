from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from xhs_local.core.contracts import SourceRecord
from xhs_local.core.identifiers import stable_record_id
from xhs_local.core.states import WorkState, WorkTopic
from xhs_local.storage.database import Database
from xhs_local.storage.dead_letters import DeadLetterRepository
from xhs_local.storage.outbox import OutboxRepository
from xhs_local.storage.records import RecordsRepository
from xhs_local.storage.remote_operations import RemoteOperationRepository
from xhs_local.storage.work_items import (
    PublicationLedger,
    WorkItemRepository,
)

NOW = datetime(2026, 8, 19, 5, 0, tzinfo=UTC)


def test_claim_is_conditional_and_recovery_restores_dispatched_notification(
    database: Database,
) -> None:
    work_items = WorkItemRepository(database)
    outbox = OutboxRepository(database)
    work_id = work_items.create(WorkTopic.NEWS_PUBLISH, now=NOW)
    event_id = outbox.add(WorkTopic.NEWS_PUBLISH, work_id, now=NOW)
    assert outbox.mark_dispatched(event_id, now=NOW)
    assert work_items.recoverable_ids(topic=WorkTopic.NEWS_PUBLISH) == [work_id]
    assert outbox.restore_for_works(work_items.recoverable_ids()) == 1
    assert [event.event_id for event in outbox.pending(WorkTopic.NEWS_PUBLISH)] == [event_id]

    claimed = work_items.claim(work_id, now=NOW)
    assert claimed is not None
    assert claimed.state is WorkState.RUNNING
    assert claimed.attempt == 1
    assert work_items.claim(work_id, now=NOW) is None

    recovered = work_items.recover_interrupted(now=NOW + timedelta(seconds=1))
    assert recovered == {"ready": 1, "reconcile_only": 0}
    assert work_items.get(work_id).state is WorkState.READY


def test_two_remote_steps_use_separate_fences_and_only_final_step_finishes_work(
    database: Database,
) -> None:
    work_items = WorkItemRepository(database)
    remote = RemoteOperationRepository(database)
    work_id = work_items.create(WorkTopic.NEWS_PUBLISH, now=NOW)
    assert work_items.claim(work_id, now=NOW) is not None

    first_step = remote.begin(
        work_id,
        sink="preparation",
        account_id="account",
        operation="prepare",
        idempotency_key="news-1:prepare",
        now=NOW,
    )
    assert first_step is not None
    assert remote.complete_step(first_step.operation_id, result={"ready": True}, now=NOW)
    assert work_items.get(work_id).state is WorkState.RUNNING
    assert (
        remote.begin(
            work_id,
            sink="preparation",
            account_id="account",
            operation="prepare",
            idempotency_key="news-1:prepare",
            now=NOW,
        )
        is None
    )

    xhs = remote.begin(
        work_id,
        sink="xiaohongshu",
        account_id="main",
        operation="publish_note",
        idempotency_key="news-1:xhs",
        now=NOW,
    )
    assert xhs is not None
    assert remote.succeed(xhs.operation_id, result={"ok": True}, now=NOW)
    assert work_items.get(work_id).state is WorkState.SUCCEEDED


def test_proven_not_submitted_operation_reuses_its_idempotency_fence_on_retry(
    database: Database,
) -> None:
    work_items = WorkItemRepository(database)
    remote = RemoteOperationRepository(database)
    work_id = work_items.create(WorkTopic.NEWS_PUBLISH, now=NOW)
    assert work_items.claim(work_id, now=NOW) is not None
    first = remote.begin(
        work_id,
        sink="xiaohongshu",
        account_id="main",
        operation="publish_note",
        idempotency_key="resource-1:xhs",
        request={"images": 3},
        now=NOW,
    )
    assert first is not None
    retry_at = NOW + timedelta(seconds=10)
    assert remote.not_submitted(
        first.operation_id,
        error_summary="composer unavailable before submit",
        retry_at=retry_at,
        now=NOW,
    )
    assert work_items.claim(work_id, now=retry_at) is not None

    second = remote.begin(
        work_id,
        sink="xiaohongshu",
        account_id="main",
        operation="publish_note",
        idempotency_key="resource-1:xhs",
        request={"images": 3},
        now=retry_at,
    )

    assert second is not None
    assert second.operation_id == first.operation_id
    assert second.attempt == 2
    assert second.state == "SUBMITTING"


def test_crossed_fence_recovers_to_reconcile_and_cannot_be_claimed_again(
    database: Database,
) -> None:
    work_items = WorkItemRepository(database)
    remote = RemoteOperationRepository(database)
    work_id = work_items.create(WorkTopic.NEWS_PUBLISH, now=NOW)
    work_items.claim(work_id, now=NOW)
    operation = remote.begin(
        work_id,
        sink="xiaohongshu",
        account_id="main",
        operation="publish_note",
        idempotency_key="slot-one",
        now=NOW,
    )
    assert operation is not None

    assert work_items.recover_interrupted(now=NOW + timedelta(seconds=2)) == {
        "ready": 0,
        "reconcile_only": 1,
    }
    assert work_items.get(work_id).state is WorkState.RECONCILE_ONLY
    assert remote.get(operation.operation_id).state == "AMBIGUOUS"
    assert work_items.claim(work_id, now=NOW + timedelta(minutes=1)) is None

    assert remote.reject_absent(
        operation.operation_id,
        evidence="note manager all/review/rejected tabs contain no matching title",
        now=NOW + timedelta(minutes=2),
    )
    assert remote.get(operation.operation_id).state == "REJECTED"
    assert work_items.get(work_id).state is WorkState.REJECTED
    assert remote.unresolved() == []


def test_explicit_remote_rejection_closes_submitting_work(database: Database) -> None:
    works = WorkItemRepository(database)
    remote = RemoteOperationRepository(database)
    work_id = works.create(WorkTopic.NEWS_PUBLISH, now=NOW)
    assert works.claim(work_id, now=NOW) is not None
    operation = remote.begin(
        work_id,
        sink="xiaohongshu",
        account_id="main",
        operation="publish_note",
        idempotency_key="explicit-rejection",
        now=NOW,
    )
    assert operation is not None

    assert remote.reject_submission(
        operation.operation_id,
        evidence="note manager total did not increase",
        now=NOW,
    )

    assert remote.get(operation.operation_id).state == "REJECTED"
    assert works.get(work_id).state is WorkState.REJECTED


def test_daily_limit_blocks_until_retry_time_then_closes_without_replaying(
    database: Database,
) -> None:
    works = WorkItemRepository(database)
    remote = RemoteOperationRepository(database)
    work_id = works.create(WorkTopic.NEWS_PUBLISH, now=NOW)
    assert works.claim(work_id, now=NOW) is not None
    operation = remote.begin(
        work_id,
        sink="xiaohongshu",
        account_id="main",
        operation="publish_note",
        idempotency_key="daily-limit-slot",
        now=NOW,
    )
    assert operation is not None
    retry_at = NOW + timedelta(hours=19)

    assert remote.hold_rate_limit(
        operation.operation_id,
        retry_at=retry_at,
        evidence="今日发布数达到上限，请明天再试试",
        now=NOW,
    )
    assert remote.unresolved()[0].state == "RATE_LIMITED"
    assert works.get(work_id).state is WorkState.WAITING_OPERATOR
    assert remote.release_expired_rate_limits(now=retry_at - timedelta(seconds=1)) == 0
    assert remote.release_expired_rate_limits(now=retry_at) == 1
    assert remote.get(operation.operation_id).state == "REJECTED"
    assert works.get(work_id).state is WorkState.REJECTED
    assert remote.unresolved() == []


def test_dead_letter_replay_is_audited_and_emits_a_new_outbox_event(
    database: Database,
) -> None:
    work_items = WorkItemRepository(database)
    dead_letters = DeadLetterRepository(database)
    work_id = work_items.create(WorkTopic.RECORD_COLLECTED, payload={"record": "one"})
    work_items.claim(work_id)
    dead_letter_id = dead_letters.move(
        work_id,
        error_class="PLUGIN_BUG",
        error_summary="mapper failed",
        now=NOW,
    )
    assert work_items.get(work_id).state is WorkState.DEAD_LETTER
    assert dead_letters.list_open()[0].dead_letter_id == dead_letter_id

    event_id = dead_letters.replay(
        dead_letter_id,
        actor="owner",
        reason="plugin fixed",
        now=NOW + timedelta(minutes=1),
    )
    assert work_items.get(work_id).state is WorkState.READY
    assert dead_letters.list_open() == []
    assert OutboxRepository(database).pending(WorkTopic.RECORD_COLLECTED)[0].event_id == event_id


def test_only_configuration_paused_publications_resume(database: Database) -> None:
    works = WorkItemRepository(database)
    news_id = works.create(WorkTopic.NEWS_PUBLISH, now=NOW)
    resource_id = works.create(WorkTopic.VIDEO_PREPARE, now=NOW)
    auth_id = works.create(WorkTopic.NEWS_PUBLISH, now=NOW)
    for work_id in (news_id, resource_id, auth_id):
        assert works.claim(work_id, now=NOW) is not None
    assert works.wait_for_operator(
        news_id,
        error_class="SINK_DISABLED",
        error_summary="disabled",
        now=NOW,
    )
    assert works.wait_for_operator(
        resource_id,
        error_class="SINK_DISABLED",
        error_summary="disabled",
        now=NOW,
    )
    assert works.wait_for_operator(
        auth_id,
        error_class="AUTH_REQUIRED",
        error_summary="login required",
        now=NOW,
    )

    resumed = works.resume_waiting(
        error_class="SINK_DISABLED",
        topics=(WorkTopic.NEWS_PUBLISH,),
        now=NOW,
    )

    assert resumed == [news_id]
    assert works.get(news_id).state is WorkState.READY
    assert works.get(resource_id).state is WorkState.WAITING_OPERATOR
    assert works.get(auth_id).state is WorkState.WAITING_OPERATOR




def test_publication_ledger_preserves_rolling_slot_and_record_fence(
    database: Database, runtime_root: Path
) -> None:
    record_id = stable_record_id("source", "target", "one")
    RecordsRepository(database, runtime_root).upsert(
        SourceRecord(
            record_id=record_id,
            source_id="source",
            target_id="target",
            plugin_id="telegram",
            external_id="one",
            content_type="tech_news",
            occurred_at=NOW,
            observed_at=NOW,
            text="A detailed technology report for the publication ledger test.",
            source_name="Source",
        )
    )
    ledger = PublicationLedger(database)
    slot = ledger.claim_rolling_slot(NOW, interval_minutes=15)
    assert slot is not None
    assert ledger.claim_rolling_slot(NOW, interval_minutes=15) is None
    assert ledger.authorize_publish(
        slot,
        [record_id],
        title="科技快讯",
        item_count=1,
        sink="xiaohongshu",
        account_id="main",
        now=NOW,
    )
    assert ledger.is_marked(record_id, sink="xiaohongshu", account_id="main")
    assert ledger.get_slot(slot)["status"] == "publishing"
    assert ledger.release_records([record_id], sink="xiaohongshu", account_id="main") == 1
    assert not ledger.is_marked(record_id, sink="xiaohongshu", account_id="main")
    ledger.finish(slot, "failed", error="pre-submit failure", now=NOW)
    assert ledger.get_slot(slot)["status"] == "failed"


def test_startup_slots_are_unique_and_stale_unpublished_news_is_discarded(
    database: Database,
    runtime_root: Path,
) -> None:
    records = RecordsRepository(database, runtime_root)
    old_unpublished = stable_record_id("source", "target", "old-unpublished")
    old_published = stable_record_id("source", "target", "old-published")
    recent = stable_record_id("source", "target", "recent")
    for record_id, external_id, occurred_at in (
        (old_unpublished, "old-unpublished", NOW - timedelta(hours=2)),
        (old_published, "old-published", NOW - timedelta(hours=2)),
        (recent, "recent", NOW - timedelta(minutes=10)),
    ):
        records.upsert(
            SourceRecord(
                record_id=record_id,
                source_id="source",
                target_id="target",
                plugin_id="telegram",
                external_id=external_id,
                content_type="tech_news",
                occurred_at=occurred_at,
                observed_at=NOW,
                text="A detailed technology report for startup initialization.",
                source_name="Source",
            )
        )
    ledger = PublicationLedger(database)
    ledger.mark_records(
        [old_published],
        "published",
        sink="xiaohongshu",
        account_id="main",
        now=NOW,
    )
    assert ledger.latest_published_at(sink="xiaohongshu", account_id="main") == NOW

    assert (
        ledger.discard_unpublished_news_before(
            NOW - timedelta(minutes=30),
            sink="xiaohongshu",
            account_id="main",
            now=NOW,
        )
        == 1
    )
    first = ledger.claim_ad_hoc_slot(NOW)
    second = ledger.claim_ad_hoc_slot(NOW + timedelta(milliseconds=2))
    assert first is not None
    assert second is not None
    assert first != second
    with database.locked() as connection:
        statuses = {
            row["record_id"]: row["status"]
            for row in connection.execute(
                "SELECT record_id,status FROM publication_marks ORDER BY record_id"
            )
        }
    assert statuses == {old_unpublished: "skipped", old_published: "published"}
    assert recent not in statuses
    ledger.mark_records(
        [recent],
        "failed",
        sink="xiaohongshu",
        account_id="main",
        now=NOW,
    )
    assert (
        ledger.release_rejected_records(
            [recent, old_published],
            sink="xiaohongshu",
            account_id="main",
        )
        == 1
    )
    assert not ledger.is_marked(recent, sink="xiaohongshu", account_id="main")
    assert ledger.is_marked(old_published, sink="xiaohongshu", account_id="main")
