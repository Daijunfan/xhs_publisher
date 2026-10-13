from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

from xhs_local.core.states import WorkState, WorkTopic
from xhs_local.pipeline.dispatcher import OutboxDispatcher
from xhs_local.pipeline.recovery import StartupRecovery
from xhs_local.storage.database import Database
from xhs_local.storage.outbox import OutboxRepository
from xhs_local.storage.remote_operations import RemoteOperationRepository
from xhs_local.storage.schema import migrate
from xhs_local.storage.work_items import WorkItemRepository

NOW = datetime(2026, 8, 19, 7, 0, tzinfo=UTC)


def test_process_restart_recovers_local_work_and_quarantines_crossed_fence(
    tmp_path: Path,
) -> None:
    path = tmp_path / "runtime/app.sqlite3"
    before = Database(path)
    migrate(before)
    works = WorkItemRepository(before)
    outbox = OutboxRepository(before)
    local_id = works.create(WorkTopic.RECORD_COLLECTED, work_id="local", now=NOW)
    local_event = outbox.add(WorkTopic.RECORD_COLLECTED, local_id, event_id="local-event", now=NOW)
    outbox.mark_dispatched(local_event, now=NOW)
    assert works.claim(local_id, now=NOW) is not None
    remote_id = works.create(WorkTopic.NEWS_PUBLISH, work_id="remote", now=NOW)
    remote_event = outbox.add(WorkTopic.NEWS_PUBLISH, remote_id, event_id="remote-event", now=NOW)
    outbox.mark_dispatched(remote_event, now=NOW)
    assert works.claim(remote_id, now=NOW) is not None
    operation = RemoteOperationRepository(before).begin(
        remote_id,
        sink="xiaohongshu",
        account_id="main",
        operation="publish_note",
        idempotency_key="restart-fixture",
        now=NOW,
    )
    assert operation is not None
    before.close()

    async def after_restart() -> None:
        database = Database(path)
        works = WorkItemRepository(database)
        outbox = OutboxRepository(database)
        queues = {
            WorkTopic.RECORD_COLLECTED: asyncio.Queue(maxsize=2),
            WorkTopic.NEWS_PUBLISH: asyncio.Queue(maxsize=2),
        }
        dispatcher = OutboxDispatcher(outbox, queues)
        recovered = await StartupRecovery(works, outbox, dispatcher).run()
        assert recovered == {"ready": 1, "reconcile_only": 1}
        assert works.get(local_id).state is WorkState.READY
        assert works.get(remote_id).state is WorkState.RECONCILE_ONLY
        assert RemoteOperationRepository(database).get(operation.operation_id).state == "AMBIGUOUS"
        task = asyncio.create_task(dispatcher.run())
        try:
            assert await asyncio.wait_for(queues[WorkTopic.RECORD_COLLECTED].get(), 1) == local_id
            queues[WorkTopic.RECORD_COLLECTED].task_done()
            assert await asyncio.to_thread(works.claim, local_id, now=NOW + timedelta(seconds=1))
            assert (
                await asyncio.to_thread(works.claim, remote_id, now=NOW + timedelta(seconds=1))
                is None
            )
        finally:
            dispatcher.stop()
            await asyncio.wait_for(task, timeout=1)
            database.close()

    asyncio.run(after_restart())
