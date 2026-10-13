from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from xhs_local.core.states import WorkTopic
from xhs_local.pipeline.dispatcher import OutboxDispatcher
from xhs_local.pipeline.retry_scheduler import RetryScheduler
from xhs_local.storage.database import Database
from xhs_local.storage.outbox import OutboxRepository
from xhs_local.storage.schema import migrate
from xhs_local.storage.work_items import WorkItemRepository


def test_retry_scheduler_uses_durable_heap_and_wakes_for_an_earlier_retry(tmp_path) -> None:
    database = Database(tmp_path / "app.sqlite3")
    migrate(database)

    async def scenario() -> None:
        works = WorkItemRepository(database)
        outbox = OutboxRepository(database)
        queue: asyncio.Queue[str] = asyncio.Queue(maxsize=2)
        dispatcher = OutboxDispatcher(outbox, {WorkTopic.NEWS_PUBLISH: queue})
        scheduler = RetryScheduler(works, outbox, dispatcher)
        now = datetime.now(UTC)

        late_id = works.create(WorkTopic.NEWS_PUBLISH, now=now)
        late_event = outbox.add(WorkTopic.NEWS_PUBLISH, late_id, now=now)
        assert outbox.mark_dispatched(late_event, now=now)
        assert works.claim(late_id, now=now) is not None
        assert works.schedule_retry(
            late_id,
            retry_at=now + timedelta(seconds=30),
            error_class="TRANSIENT_NETWORK",
            error_summary="later",
            now=now,
        )

        task = asyncio.create_task(scheduler.run())
        try:
            await asyncio.sleep(0)
            early_id = works.create(WorkTopic.NEWS_PUBLISH, now=now)
            early_event = outbox.add(WorkTopic.NEWS_PUBLISH, early_id, now=now)
            assert outbox.mark_dispatched(early_event, now=now)
            assert works.claim(early_id, now=now) is not None
            assert works.schedule_retry(
                early_id,
                retry_at=datetime.now(UTC) + timedelta(milliseconds=30),
                error_class="TRANSIENT_NETWORK",
                error_summary="earlier",
            )
            scheduler.wake()

            async with asyncio.timeout(1):
                while not outbox.pending(WorkTopic.NEWS_PUBLISH):
                    await asyncio.sleep(0.01)

            assert [item.work_id for item in outbox.pending(WorkTopic.NEWS_PUBLISH)] == [early_id]
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    try:
        asyncio.run(scenario())
    finally:
        database.close()
