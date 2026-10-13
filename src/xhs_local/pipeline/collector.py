"""Persist one plugin batch atomically and wake its outbox topic."""

from __future__ import annotations

import asyncio

from xhs_local.core.contracts import CollectBatch
from xhs_local.storage.records import CommitResult, RecordsRepository

from .dispatcher import OutboxDispatcher


class Collector:
    def __init__(
        self, records: RecordsRepository, dispatcher: OutboxDispatcher | None = None
    ) -> None:
        self.records = records
        self.dispatcher = dispatcher

    async def commit(self, batch: CollectBatch, *, config_revision: str) -> CommitResult:
        result = await asyncio.to_thread(
            self.records.commit_batch,
            batch,
            work_topic=batch.work_topic,
            config_revision=config_revision,
            create_work=self.dispatcher is not None,
        )
        if result.work_ids and self.dispatcher is not None:
            self.dispatcher.wake(batch.work_topic)
        return result
