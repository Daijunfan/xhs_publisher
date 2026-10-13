from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

from xhs_local.core.contracts import CollectBatch, SourceRecord
from xhs_local.core.identifiers import stable_record_id
from xhs_local.core.states import WorkState, WorkTopic
from xhs_local.pipeline.dispatcher import OutboxDispatcher
from xhs_local.pipeline.recovery import StartupRecovery
from xhs_local.storage.database import Database
from xhs_local.storage.outbox import OutboxRepository
from xhs_local.storage.records import RecordsRepository
from xhs_local.storage.schema import migrate
from xhs_local.storage.work_items import WorkItemRepository

NOW = datetime(2026, 8, 19, 6, 0, tzinfo=UTC)


def test_commit_then_crash_before_wake_is_replayed_on_startup(tmp_path: Path) -> None:
    async def scenario() -> None:
        runtime = tmp_path / "runtime"
        database = Database(runtime / "app.sqlite3")
        migrate(database)
        records = RecordsRepository(database, runtime)
        outbox = OutboxRepository(database)
        works = WorkItemRepository(database)
        record = SourceRecord(
            record_id=stable_record_id("telegram-main", "telegram-one", "101"),
            source_id="telegram-main",
            target_id="telegram-one",
            plugin_id="telegram",
            external_id="101",
            content_type="tech_news",
            occurred_at=NOW,
            observed_at=NOW,
            text="A detailed technology report committed before the simulated crash.",
            source_name="Fixture",
        )
        result = records.commit_batch(
            CollectBatch(
                "telegram-main",
                "telegram-one",
                (record,),
                {"max_message_id": 101},
            ),
            config_revision="revision-one",
        )
        assert len(result.work_ids) == 1
        assert outbox.undispatched_count(WorkTopic.RECORD_COLLECTED) == 1

        queue: asyncio.Queue[str] = asyncio.Queue(maxsize=1)
        dispatcher = OutboxDispatcher(outbox, {WorkTopic.RECORD_COLLECTED: queue})
        recovery = StartupRecovery(works, outbox, dispatcher)
        assert await recovery.run() == {"ready": 0, "reconcile_only": 0}
        dispatch_task = asyncio.create_task(dispatcher.run())
        try:
            work_id = await asyncio.wait_for(queue.get(), timeout=1)
            assert work_id == result.work_ids[0]
            queue.task_done()
            claimed = await asyncio.to_thread(works.claim, work_id, now=NOW)
            assert claimed is not None and claimed.state is WorkState.RUNNING
            assert await asyncio.to_thread(works.claim, work_id, now=NOW) is None
        finally:
            dispatcher.stop()
            await asyncio.wait_for(dispatch_task, timeout=1)
            database.close()

    asyncio.run(scenario())


def test_failed_transaction_exposes_neither_checkpoint_work_nor_notification(
    tmp_path: Path,
) -> None:
    runtime = tmp_path / "runtime"
    database = Database(runtime / "app.sqlite3")
    migrate(database)
    try:
        item = SourceRecord(
            record_id=stable_record_id("source", "wrong-target", "1"),
            source_id="source",
            target_id="wrong-target",
            plugin_id="telegram",
            external_id="1",
            content_type="tech_news",
            occurred_at=NOW,
            observed_at=NOW,
            text="This record deliberately belongs to the wrong target.",
            source_name="Fixture",
        )
        try:
            RecordsRepository(database, runtime).commit_batch(
                CollectBatch("source", "expected-target", (item,), {"max_message_id": 1})
            )
        except ValueError:
            pass
        else:
            raise AssertionError("invalid batch unexpectedly committed")
        assert WorkItemRepository(database).recoverable_ids() == []
        assert OutboxRepository(database).undispatched_count() == 0
        with database.locked() as connection:
            assert connection.execute("SELECT count(*) FROM checkpoints").fetchone()[0] == 0
            assert connection.execute("SELECT count(*) FROM records").fetchone()[0] == 0
    finally:
        database.close()
