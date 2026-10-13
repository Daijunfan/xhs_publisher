"""Transactional notifications from durable work into in-process queues."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from xhs_local.core.clock import utc_iso
from xhs_local.core.identifiers import new_id
from xhs_local.core.states import WorkTopic

from .database import Database


def _timestamp(value: datetime | None = None) -> str:
    return utc_iso(value)


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True, slots=True)
class OutboxEvent:
    event_id: str
    topic: WorkTopic
    work_id: str
    payload: dict[str, Any]
    created_at: str


class OutboxRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    @staticmethod
    def add_in(
        connection: sqlite3.Connection,
        topic: WorkTopic | str,
        work_id: str,
        *,
        payload: dict[str, Any] | None = None,
        event_id: str | None = None,
        now: datetime | None = None,
    ) -> str:
        resolved_id = event_id or new_id()
        connection.execute(
            """
            INSERT INTO outbox(event_id,topic,work_id,payload_json,state,created_at)
            VALUES(?,?,?,?, 'NEW', ?)
            """,
            (
                resolved_id,
                WorkTopic(topic).value,
                work_id,
                _json(payload or {}),
                _timestamp(now),
            ),
        )
        return resolved_id

    def add(self, topic: WorkTopic | str, work_id: str, **kwargs: Any) -> str:
        with self.database.transaction() as connection:
            return self.add_in(connection, topic, work_id, **kwargs)

    def pending(
        self,
        topic: WorkTopic | str,
        *,
        limit: int = 100,
    ) -> list[OutboxEvent]:
        if limit < 1:
            raise ValueError("limit must be positive")
        with self.database.locked() as connection:
            rows = connection.execute(
                """
                SELECT event_id,topic,work_id,payload_json,created_at FROM outbox
                 WHERE topic=? AND state='NEW' ORDER BY created_at,event_id LIMIT ?
                """,
                (WorkTopic(topic).value, limit),
            ).fetchall()
        return [
            OutboxEvent(
                event_id=row["event_id"],
                topic=WorkTopic(row["topic"]),
                work_id=row["work_id"],
                payload=json.loads(row["payload_json"]),
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def mark_dispatched(self, event_id: str, *, now: datetime | None = None) -> bool:
        with self.database.transaction() as connection:
            result = connection.execute(
                """
                UPDATE outbox SET state='DISPATCHED',dispatched_at=?
                 WHERE event_id=? AND state='NEW'
                """,
                (_timestamp(now), event_id),
            )
        return result.rowcount == 1

    def restore_for_work(self, work_id: str) -> int:
        """Make notifications replayable during explicit startup recovery."""

        with self.database.transaction() as connection:
            result = connection.execute(
                """
                UPDATE outbox SET state='NEW',dispatched_at=NULL
                 WHERE work_id=? AND state='DISPATCHED'
                   AND EXISTS(
                       SELECT 1 FROM work_items w WHERE w.work_id=outbox.work_id
                        AND w.state IN ('READY','RETRY_WAIT')
                   )
                """,
                (work_id,),
            )
        return result.rowcount

    def restore_for_works(self, work_ids: list[str] | tuple[str, ...]) -> int:
        if not work_ids:
            return 0
        placeholders = ",".join("?" for _work_id in work_ids)
        with self.database.transaction() as connection:
            result = connection.execute(
                f"""
                UPDATE outbox SET state='NEW',dispatched_at=NULL
                 WHERE work_id IN ({placeholders}) AND state='DISPATCHED'
                """,
                tuple(work_ids),
            )
        return result.rowcount

    def undispatched_count(self, topic: WorkTopic | str | None = None) -> int:
        query = "SELECT count(*) FROM outbox WHERE state='NEW'"
        parameters: tuple[object, ...] = ()
        if topic is not None:
            query += " AND topic=?"
            parameters = (WorkTopic(topic).value,)
        with self.database.locked() as connection:
            return int(connection.execute(query, parameters).fetchone()[0])
