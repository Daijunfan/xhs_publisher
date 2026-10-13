from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from xhs_local.core.states import WorkState, WorkTopic
from xhs_local.pipeline.dispatcher import OutboxDispatcher
from xhs_local.storage.database import Database
from xhs_local.storage.outbox import OutboxRepository
from xhs_local.storage.schema import migrate
from xhs_local.storage.work_items import WorkItemRepository


def _add(database: Database, topic: WorkTopic, suffix: str) -> tuple[str, str]:
    works = WorkItemRepository(database)
    outbox = OutboxRepository(database)
    work_id = works.create(topic, work_id=f"work-{suffix}")
    event_id = outbox.add(topic, work_id, event_id=f"event-{suffix}")
    return work_id, event_id


def test_bounded_queue_applies_backpressure_without_deleting_outbox(tmp_path: Path) -> None:
    async def scenario() -> None:
        database = Database(tmp_path / "app.sqlite3")
        migrate(database)
        first, _ = _add(database, WorkTopic.NEWS_PUBLISH, "1")
        second, _ = _add(database, WorkTopic.NEWS_PUBLISH, "2")
        outbox = OutboxRepository(database)
        queue: asyncio.Queue[str] = asyncio.Queue(maxsize=1)
        dispatcher = OutboxDispatcher(outbox, {WorkTopic.NEWS_PUBLISH: queue})
        task = asyncio.create_task(dispatcher.run())
        try:
            while queue.qsize() != 1 or outbox.undispatched_count() != 1:
                await asyncio.sleep(0)
            assert queue.maxsize == 1
            assert await queue.get() == first
            queue.task_done()
            assert await asyncio.wait_for(queue.get(), timeout=1) == second
            queue.task_done()
            while outbox.undispatched_count() != 0:
                await asyncio.sleep(0)
        finally:
            dispatcher.stop()
            await asyncio.wait_for(task, timeout=1)
            database.close()

    asyncio.run(scenario())


def test_duplicate_dispatch_after_put_before_mark_is_safe_by_conditional_claim(
    tmp_path: Path,
) -> None:
    class CrashOnMark:
        def __init__(self, repository: OutboxRepository) -> None:
            self.repository = repository

        def pending(self, *args, **kwargs):
            return self.repository.pending(*args, **kwargs)

        def mark_dispatched(self, _event_id: str) -> bool:
            raise RuntimeError("simulated crash after queue put")

    async def scenario() -> None:
        database = Database(tmp_path / "app.sqlite3")
        migrate(database)
        work_id, _ = _add(database, WorkTopic.NEWS_PUBLISH, "duplicate")
        repository = OutboxRepository(database)
        first_queue: asyncio.Queue[str] = asyncio.Queue(maxsize=1)
        crashing = OutboxDispatcher(
            CrashOnMark(repository),  # type: ignore[arg-type]
            {WorkTopic.NEWS_PUBLISH: first_queue},
        )
        first_task = asyncio.create_task(crashing._run_topic(WorkTopic.NEWS_PUBLISH))
        crashing.wake(WorkTopic.NEWS_PUBLISH)
        assert await asyncio.wait_for(first_queue.get(), timeout=1) == work_id
        first_queue.task_done()
        with pytest.raises(RuntimeError, match="simulated crash"):
            await first_task
        assert repository.undispatched_count() == 1

        second_queue: asyncio.Queue[str] = asyncio.Queue(maxsize=1)
        restarted = OutboxDispatcher(repository, {WorkTopic.NEWS_PUBLISH: second_queue})
        restarted_task = asyncio.create_task(restarted.run())
        try:
            assert await asyncio.wait_for(second_queue.get(), timeout=1) == work_id
            second_queue.task_done()
            works = WorkItemRepository(database)
            first_claim = await asyncio.to_thread(works.claim, work_id)
            duplicate_claim = await asyncio.to_thread(works.claim, work_id)
            assert first_claim is not None and first_claim.state is WorkState.RUNNING
            assert duplicate_claim is None
        finally:
            restarted.stop()
            await asyncio.wait_for(restarted_task, timeout=1)
            database.close()

    asyncio.run(scenario())


def test_full_publish_queue_does_not_block_ingest_topic(tmp_path: Path) -> None:
    async def scenario() -> None:
        database = Database(tmp_path / "app.sqlite3")
        migrate(database)
        publish_id, _ = _add(database, WorkTopic.NEWS_PUBLISH, "publish")
        ingest_id, _ = _add(database, WorkTopic.RECORD_COLLECTED, "ingest")
        publish_queue: asyncio.Queue[str] = asyncio.Queue(maxsize=1)
        ingest_queue: asyncio.Queue[str] = asyncio.Queue(maxsize=1)
        publish_queue.put_nowait("existing-item")
        dispatcher = OutboxDispatcher(
            OutboxRepository(database),
            {
                WorkTopic.NEWS_PUBLISH: publish_queue,
                WorkTopic.RECORD_COLLECTED: ingest_queue,
            },
        )
        task = asyncio.create_task(dispatcher.run())
        try:
            assert await asyncio.wait_for(ingest_queue.get(), timeout=1) == ingest_id
            ingest_queue.task_done()
            assert publish_id not in tuple(publish_queue._queue)
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            database.close()

    asyncio.run(scenario())
