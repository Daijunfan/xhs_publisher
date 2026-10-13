"""Dead-letter storage and audited manual replay."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from xhs_local.core.clock import utc_iso
from xhs_local.core.identifiers import new_id
from xhs_local.core.states import WorkState

from .database import Database
from .outbox import OutboxRepository


def _timestamp(value: datetime | None = None) -> str:
    return utc_iso(value)


@dataclass(frozen=True, slots=True)
class DeadLetter:
    dead_letter_id: str
    work_id: str
    topic: str
    payload: dict[str, Any]
    error_class: str | None
    error_code: str | None
    error_summary: str
    attempt: int
    created_at: str
    replayed_at: str | None
    replay_actor: str | None
    replay_reason: str | None


class DeadLetterRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def move(
        self,
        work_id: str,
        *,
        error_summary: str,
        error_class: str | None = None,
        error_code: str | None = None,
        now: datetime | None = None,
    ) -> str:
        dead_letter_id = new_id()
        created_at = _timestamp(now)
        with self.database.transaction() as connection:
            work = connection.execute(
                "SELECT topic,payload_json,attempt,state FROM work_items WHERE work_id=?",
                (work_id,),
            ).fetchone()
            if work is None:
                raise KeyError(f"unknown work item: {work_id}")
            if work["state"] in {
                WorkState.SUCCEEDED.value,
                WorkState.REJECTED.value,
                WorkState.DEAD_LETTER.value,
            }:
                raise ValueError(f"terminal work cannot enter DLQ from {work['state']}")
            connection.execute(
                """
                INSERT INTO dead_letters(
                    dead_letter_id,work_id,topic,payload_json,error_class,error_code,
                    error_summary,attempt,created_at
                ) VALUES(?,?,?,?,?,?,?,?,?)
                """,
                (
                    dead_letter_id,
                    work_id,
                    work["topic"],
                    work["payload_json"],
                    error_class,
                    error_code,
                    error_summary,
                    int(work["attempt"]),
                    created_at,
                ),
            )
            connection.execute(
                """
                UPDATE work_items SET state=?,completed_at=?,error_class=?,error_code=?,
                       error_summary=?,updated_at=? WHERE work_id=?
                """,
                (
                    WorkState.DEAD_LETTER.value,
                    created_at,
                    error_class,
                    error_code,
                    error_summary,
                    created_at,
                    work_id,
                ),
            )
        return dead_letter_id

    def list_open(self, *, limit: int = 100) -> list[DeadLetter]:
        if limit < 1:
            raise ValueError("limit must be positive")
        with self.database.locked() as connection:
            rows = connection.execute(
                """
                SELECT * FROM dead_letters WHERE replayed_at IS NULL
                 ORDER BY created_at LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            DeadLetter(
                dead_letter_id=row["dead_letter_id"],
                work_id=row["work_id"],
                topic=row["topic"],
                payload=json.loads(row["payload_json"]),
                error_class=row["error_class"],
                error_code=row["error_code"],
                error_summary=row["error_summary"],
                attempt=int(row["attempt"]),
                created_at=row["created_at"],
                replayed_at=row["replayed_at"],
                replay_actor=row["replay_actor"],
                replay_reason=row["replay_reason"],
            )
            for row in rows
        ]

    def replay(
        self,
        dead_letter_id: str,
        *,
        actor: str,
        reason: str,
        now: datetime | None = None,
    ) -> str:
        if not actor.strip() or not reason.strip():
            raise ValueError("DLQ replay requires actor and reason")
        replayed_at = _timestamp(now)
        with self.database.transaction() as connection:
            letter = connection.execute(
                """
                SELECT work_id,topic,payload_json FROM dead_letters
                 WHERE dead_letter_id=? AND replayed_at IS NULL
                """,
                (dead_letter_id,),
            ).fetchone()
            if letter is None:
                raise ValueError("dead letter does not exist or was already replayed")
            connection.execute(
                """
                UPDATE dead_letters SET replayed_at=?,replay_actor=?,replay_reason=?
                 WHERE dead_letter_id=?
                """,
                (replayed_at, actor.strip(), reason.strip(), dead_letter_id),
            )
            restored = connection.execute(
                """
                UPDATE work_items SET state=?,next_retry_at=NULL,started_at=NULL,
                       completed_at=NULL,error_class=NULL,error_code=NULL,error_summary=NULL,
                       updated_at=? WHERE work_id=? AND state=?
                """,
                (
                    WorkState.READY.value,
                    replayed_at,
                    letter["work_id"],
                    WorkState.DEAD_LETTER.value,
                ),
            )
            if restored.rowcount != 1:
                raise RuntimeError("dead letter and work item states diverged")
            event_id = OutboxRepository.add_in(
                connection,
                letter["topic"],
                letter["work_id"],
                payload=json.loads(letter["payload_json"]),
                now=now,
            )
        return event_id
