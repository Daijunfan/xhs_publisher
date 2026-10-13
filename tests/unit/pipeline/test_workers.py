from __future__ import annotations

import asyncio

from xhs_local.core.errors import TransientError
from xhs_local.core.states import WorkState, WorkTopic
from xhs_local.pipeline.processor import ProcessorWorker
from xhs_local.pipeline.publisher import PublisherWorker
from xhs_local.storage.database import Database
from xhs_local.storage.dead_letters import DeadLetterRepository
from xhs_local.storage.schema import migrate
from xhs_local.storage.work_items import WorkItemRepository


def test_exhausted_worker_failures_enter_audited_dead_letter_queue(tmp_path) -> None:
    database = Database(tmp_path / "app.sqlite3")
    migrate(database)

    async def scenario() -> None:
        works = WorkItemRepository(database)
        dead_letters = DeadLetterRepository(database)

        async def fail(_work) -> None:
            raise RuntimeError("fixture bug")

        publish_id = works.create(WorkTopic.NEWS_PUBLISH)
        publish_queue: asyncio.Queue[str] = asyncio.Queue()
        publisher = PublisherWorker(
            publish_queue,
            works,
            dead_letters,
            {WorkTopic.NEWS_PUBLISH: fail},
            max_attempts=1,
        )
        publisher_task = asyncio.create_task(publisher.run())
        await publish_queue.put(publish_id)
        await publish_queue.join()
        publisher_task.cancel()
        await asyncio.gather(publisher_task, return_exceptions=True)
        assert works.get(publish_id).state is WorkState.DEAD_LETTER

        process_id = works.create(WorkTopic.RECORD_COLLECTED)
        process_queue: asyncio.Queue[str] = asyncio.Queue()
        processor = ProcessorWorker(process_queue, works, dead_letters, fail)
        processor_task = asyncio.create_task(processor.run())
        await process_queue.put(process_id)
        await process_queue.join()
        processor_task.cancel()
        await asyncio.gather(processor_task, return_exceptions=True)
        assert works.get(process_id).state is WorkState.DEAD_LETTER
        assert {item.work_id for item in dead_letters.list_open()} == {publish_id, process_id}

    try:
        asyncio.run(scenario())
    finally:
        database.close()


def test_transient_network_failure_keeps_retrying_after_attempt_limit(tmp_path) -> None:
    database = Database(tmp_path / "app.sqlite3")
    migrate(database)

    async def scenario() -> None:
        works = WorkItemRepository(database)
        dead_letters = DeadLetterRepository(database)

        async def transient(_work) -> None:
            raise TransientError("temporary network outage")

        work_id = works.create(WorkTopic.NEWS_PUBLISH)
        queue: asyncio.Queue[str] = asyncio.Queue()
        worker = PublisherWorker(
            queue,
            works,
            dead_letters,
            {WorkTopic.NEWS_PUBLISH: transient},
            retry_delays={WorkTopic.NEWS_PUBLISH: 60},
            max_attempts=1,
        )
        task = asyncio.create_task(worker.run())
        await queue.put(work_id)
        await queue.join()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

        stored = works.get(work_id)
        assert stored.state is WorkState.RETRY_WAIT
        assert stored.error_class == "TRANSIENT_NETWORK"
        assert dead_letters.list_open() == []

    try:
        asyncio.run(scenario())
    finally:
        database.close()
