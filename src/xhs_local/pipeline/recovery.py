"""Explicit startup recovery; normal workers never poll SQLite for work."""

from __future__ import annotations

import asyncio

from xhs_local.core.states import WorkState, WorkTopic
from xhs_local.storage.outbox import OutboxRepository
from xhs_local.storage.work_items import WorkItemRepository

from .dispatcher import OutboxDispatcher


class StartupRecovery:
    def __init__(
        self,
        work_items: WorkItemRepository,
        outbox: OutboxRepository,
        dispatcher: OutboxDispatcher,
        *,
        topic: WorkTopic | str | None = None,
    ) -> None:
        self.work_items = work_items
        self.outbox = outbox
        self.dispatcher = dispatcher
        self.topic = None if topic is None else WorkTopic(topic)

    async def run(self) -> dict[str, int]:
        recovered = await asyncio.to_thread(
            self.work_items.recover_interrupted, topic=self.topic
        )
        if hasattr(self.work_items, "recoverable_ids"):
            work_ids = await asyncio.to_thread(
                self.work_items.recoverable_ids,
                (WorkState.READY,),
                topic=self.topic,
            )
            if hasattr(self.outbox, "restore_for_works"):
                await asyncio.to_thread(self.outbox.restore_for_works, work_ids)
            else:
                for work_id in work_ids:
                    await asyncio.to_thread(self.outbox.restore_for_work, work_id)
        self.dispatcher.wake(self.topic)
        return recovered
