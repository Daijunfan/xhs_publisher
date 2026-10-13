"""Event-driven transactional-outbox dispatch into bounded asyncio queues."""

from __future__ import annotations

import asyncio
import logging

from xhs_local.core.states import WorkTopic
from xhs_local.storage.outbox import OutboxRepository


class OutboxDispatcher:
    def __init__(
        self,
        outbox: OutboxRepository,
        queues: dict[WorkTopic, asyncio.Queue[str]],
    ) -> None:
        self.outbox = outbox
        self.queues = queues
        self.events = {topic: asyncio.Event() for topic in queues}
        self.stopping = asyncio.Event()
        self.log = logging.getLogger(__name__)

    def wake(self, topic: WorkTopic | None = None) -> None:
        if topic is None:
            for event in self.events.values():
                event.set()
        elif topic in self.events:
            self.events[topic].set()

    async def run(self) -> None:
        self.wake()
        async with asyncio.TaskGroup() as group:
            for topic in self.queues:
                group.create_task(self._run_topic(topic), name=f"outbox-{topic.value}")

    async def _run_topic(self, topic: WorkTopic) -> None:
        event = self.events[topic]
        queue = self.queues[topic]
        while not self.stopping.is_set():
            await event.wait()
            event.clear()
            while not self.stopping.is_set():
                pending = await asyncio.to_thread(self.outbox.pending, topic, limit=100)
                if not pending:
                    break
                for item in pending:
                    queued: object = item.work_id
                    if isinstance(queue, asyncio.PriorityQueue):
                        queued = (1, item.work_id)
                    await queue.put(queued)
                    await asyncio.to_thread(self.outbox.mark_dispatched, item.event_id)
                if len(pending) < 100:
                    break

    def stop(self) -> None:
        self.stopping.set()
        self.wake()
