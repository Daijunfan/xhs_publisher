"""Durable retry timestamps rebuilt into an event-driven in-memory heap."""

from __future__ import annotations

import asyncio
import heapq
from contextlib import suppress
from datetime import UTC, datetime

from xhs_local.core.states import WorkTopic
from xhs_local.storage.outbox import OutboxRepository
from xhs_local.storage.work_items import WorkItemRepository

from .dispatcher import OutboxDispatcher


class RetryScheduler:
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
        self.wake_event = asyncio.Event()

    def wake(self) -> None:
        self.wake_event.set()

    async def _schedule(self) -> list[tuple[float, str]]:
        rows = await asyncio.to_thread(self.work_items.retry_schedule, topic=self.topic)
        heap = [
            (
                datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                .astimezone(UTC)
                .timestamp(),
                work_id,
            )
            for timestamp, work_id in rows
        ]
        heapq.heapify(heap)
        return heap

    async def run(self) -> None:
        while True:
            self.wake_event.clear()
            heap = await self._schedule()
            while True:
                now = datetime.now(UTC).timestamp()
                while heap and heap[0][0] <= now:
                    _due_at, work_id = heapq.heappop(heap)
                    work = await asyncio.to_thread(self.work_items.get, work_id)
                    if work is None or work.next_retry_at is None:
                        continue
                    await asyncio.to_thread(self.outbox.restore_for_work, work_id)
                    self.dispatcher.wake(work.topic)
                if self.wake_event.is_set():
                    break
                if not heap:
                    await self.wake_event.wait()
                else:
                    timeout = max(0.0, heap[0][0] - datetime.now(UTC).timestamp())
                    with suppress(TimeoutError):
                        await asyncio.wait_for(self.wake_event.wait(), timeout=timeout)
                if self.wake_event.is_set():
                    break
