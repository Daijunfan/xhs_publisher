from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from xhs_local.core.clock import utc_iso
from xhs_local.core.states import WorkState, WorkTopic
from xhs_local.pipeline.dispatcher import OutboxDispatcher
from xhs_local.pipeline.recovery import StartupRecovery
from xhs_local.pipeline.retry_scheduler import RetryScheduler
from xhs_local.storage.database import Database
from xhs_local.storage.outbox import OutboxRepository
from xhs_local.storage.remote_operations import RemoteOperationRepository
from xhs_local.storage.schema import migrate
from xhs_local.storage.work_items import WorkItemRepository


def _snapshot(database: Database) -> dict[str, list[dict]]:
    """Exact unrelated rows, including timestamps and remote publication fences."""
    with database.locked() as connection:
        return {
            table: [dict(row) for row in connection.execute(query)]
            for table, query in {
                "work_items": (
                    "SELECT * FROM work_items WHERE topic!='video_prepare' ORDER BY work_id"
                ),
                "outbox": "SELECT * FROM outbox WHERE topic!='video_prepare' ORDER BY event_id",
                "remote_operations": "SELECT * FROM remote_operations ORDER BY operation_id",
            }.items()
        }


def _work(database: Database, topic: WorkTopic, state: WorkState, now: datetime) -> str:
    works, outbox = WorkItemRepository(database), OutboxRepository(database)
    work_id = works.create(topic, now=now)
    event_id = outbox.add(topic, work_id, now=now)
    assert outbox.mark_dispatched(event_id, now=now)
    if state is WorkState.SUBMITTING:
        assert works.claim(work_id, now=now)
        assert RemoteOperationRepository(database).begin(
            work_id,
            sink="xiaohongshu",
            account_id="fixture",
            operation="publish_note",
            idempotency_key=work_id,
            now=now,
        )
    else:
        # Seed persisted startup states, without starting any worker or remote service.
        with database.transaction() as connection:
            connection.execute(
                "UPDATE work_items SET state=?,next_retry_at=? WHERE work_id=?",
                (
                    state.value,
                    utc_iso(now) if state is WorkState.RETRY_WAIT else None,
                    work_id,
                ),
            )
    return work_id


def test_video_startup_leaves_news_review_publication_and_remote_operations_untouched(
    tmp_path,
) -> None:
    database = Database(tmp_path / "startup.sqlite3")
    migrate(database)
    now = datetime.now(UTC) - timedelta(seconds=1)
    states = (
        WorkState.READY,
        WorkState.RUNNING,
        WorkState.SUBMITTING,
        WorkState.RETRY_WAIT,
        WorkState.WAITING_OPERATOR,
        WorkState.RECONCILE_ONLY,
        WorkState.SUCCEEDED,
    )
    try:
        video = {state: _work(database, WorkTopic.VIDEO_PREPARE, state, now) for state in states}
        for topic in (WorkTopic.NEWS_PUBLISH, WorkTopic.RECORD_COLLECTED):
            for state in states:
                _work(database, topic, state, now)
        before = _snapshot(database)

        async def scenario() -> None:
            works, outbox = WorkItemRepository(database), OutboxRepository(database)
            dispatcher = OutboxDispatcher(
                outbox,
                {WorkTopic.VIDEO_PREPARE: asyncio.Queue(), WorkTopic.NEWS_PUBLISH: asyncio.Queue()},
            )
            result = await StartupRecovery(
                works, outbox, dispatcher, topic="video_prepare"
            ).run()
            assert result == {"ready": 1, "reconcile_only": 1}
            assert works.get(video[WorkState.RUNNING]).state is WorkState.READY
            assert works.get(video[WorkState.SUBMITTING]).state is WorkState.RECONCILE_ONLY
            assert set(event.work_id for event in outbox.pending(WorkTopic.VIDEO_PREPARE)) == {
                video[WorkState.READY], video[WorkState.RUNNING]
            }
            for state in states[3:]:
                assert works.get(video[state]).state is state
            assert dispatcher.events[WorkTopic.VIDEO_PREPARE].is_set()
            assert not dispatcher.events[WorkTopic.NEWS_PUBLISH].is_set()
            assert _snapshot(database) == before

        asyncio.run(scenario())
    finally:
        database.close()


def test_video_retry_heap_and_notifications_preserve_unrelated_durable_rows(tmp_path) -> None:
    database = Database(tmp_path / "retry.sqlite3")
    migrate(database)
    now = datetime.now(UTC) - timedelta(seconds=1)
    try:
        news = _work(database, WorkTopic.NEWS_PUBLISH, WorkState.RETRY_WAIT, now)
        video = _work(database, WorkTopic.VIDEO_PREPARE, WorkState.RETRY_WAIT, now)
        _work(database, WorkTopic.NEWS_PUBLISH, WorkState.WAITING_OPERATOR, now)
        _work(database, WorkTopic.NEWS_PUBLISH, WorkState.SUBMITTING, now)
        before = _snapshot(database)

        async def scenario() -> None:
            works, outbox = WorkItemRepository(database), OutboxRepository(database)
            dispatcher = OutboxDispatcher(
                outbox,
                {WorkTopic.VIDEO_PREPARE: asyncio.Queue(), WorkTopic.NEWS_PUBLISH: asyncio.Queue()},
            )
            scheduler = RetryScheduler(works, outbox, dispatcher, topic=WorkTopic.VIDEO_PREPARE)
            assert works.retry_schedule(topic=WorkTopic.VIDEO_PREPARE, limit=1) == [
                (utc_iso(now), video)
            ]
            assert {work_id for _, work_id in works.retry_schedule()} == {news, video}
            assert [work_id for _, work_id in await scheduler._schedule()] == [video]
            task = asyncio.create_task(scheduler.run())
            try:
                async with asyncio.timeout(1):
                    while not outbox.pending(WorkTopic.VIDEO_PREPARE):
                        await asyncio.sleep(0.01)
                pending = outbox.pending(WorkTopic.VIDEO_PREPARE)
                assert [event.work_id for event in pending] == [video]
                assert dispatcher.events[WorkTopic.VIDEO_PREPARE].is_set()
                assert not dispatcher.events[WorkTopic.NEWS_PUBLISH].is_set()
                assert _snapshot(database) == before
            finally:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

        asyncio.run(scenario())
    finally:
        database.close()
