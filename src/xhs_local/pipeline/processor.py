"""Long-lived record-collected worker; publication policy remains slot based."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from xhs_local.core.errors import concise_error
from xhs_local.storage.dead_letters import DeadLetterRepository
from xhs_local.storage.work_items import StoredWorkItem, WorkItemRepository


class ProcessorWorker:
    def __init__(
        self,
        queue: asyncio.Queue[str],
        work_items: WorkItemRepository,
        dead_letters: DeadLetterRepository,
        on_record: Callable[[StoredWorkItem], Awaitable[None]],
    ) -> None:
        self.queue = queue
        self.work_items = work_items
        self.dead_letters = dead_letters
        self.on_record = on_record
        self.log = logging.getLogger(__name__)

    async def run(self) -> None:
        while True:
            work_id = await self.queue.get()
            try:
                work = await asyncio.to_thread(self.work_items.claim, work_id)
                if work is None:
                    continue
                await self.on_record(work)
                await asyncio.to_thread(self.work_items.succeed, work_id)
            except asyncio.CancelledError:
                raise
            except Exception as error:
                self.log.exception(
                    "record processing failed",
                    extra={"context": {"work_id": work_id}},
                )
                await asyncio.to_thread(
                    self.dead_letters.move,
                    work_id,
                    error_class="PLUGIN_BUG",
                    error_summary=concise_error(error),
                )
            finally:
                self.queue.task_done()
