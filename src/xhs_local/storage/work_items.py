"""Durable processing/publication work state and legacy publication ledgers."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from xhs_local.core.clock import utc_iso
from xhs_local.core.identifiers import new_id
from xhs_local.core.states import WorkState, WorkTopic

from .database import Database


def _timestamp(value: datetime | None = None) -> str:
    return utc_iso(value)


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True, slots=True)
class StoredWorkItem:
    work_id: str
    topic: WorkTopic
    state: WorkState
    record_id: str | None
    payload: dict[str, Any]
    config_revision: str | None
    trace_id: str
    attempt: int
    next_retry_at: str | None
    started_at: str | None
    completed_at: str | None
    error_class: str | None
    error_code: str | None
    error_summary: str | None
    created_at: str
    updated_at: str


def _work_item(row: sqlite3.Row) -> StoredWorkItem:
    return StoredWorkItem(
        work_id=row["work_id"],
        topic=WorkTopic(row["topic"]),
        state=WorkState(row["state"]),
        record_id=row["record_id"],
        payload=json.loads(row["payload_json"]),
        config_revision=row["config_revision"],
        trace_id=row["trace_id"],
        attempt=int(row["attempt"]),
        next_retry_at=row["next_retry_at"],
        started_at=row["started_at"],
        completed_at=row["completed_at"],
        error_class=row["error_class"],
        error_code=row["error_code"],
        error_summary=row["error_summary"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class WorkItemRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    @staticmethod
    def create_in(
        connection: sqlite3.Connection,
        topic: WorkTopic | str,
        *,
        record_id: str | None = None,
        payload: dict[str, Any] | None = None,
        config_revision: str | None = None,
        trace_id: str | None = None,
        work_id: str | None = None,
        now: datetime | None = None,
    ) -> str:
        resolved_topic = WorkTopic(topic)
        created = _timestamp(now)
        resolved_id = work_id or new_id()
        connection.execute(
            """
            INSERT INTO work_items(
                work_id,topic,state,record_id,payload_json,config_revision,trace_id,
                attempt,created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,0,?,?)
            """,
            (
                resolved_id,
                resolved_topic.value,
                WorkState.READY.value,
                record_id,
                _json(payload or {}),
                config_revision,
                trace_id or new_id(),
                created,
                created,
            ),
        )
        return resolved_id

    def create(self, topic: WorkTopic | str, **kwargs: Any) -> str:
        with self.database.transaction() as connection:
            return self.create_in(connection, topic, **kwargs)

    def get(self, work_id: str) -> StoredWorkItem | None:
        with self.database.locked() as connection:
            row = connection.execute(
                "SELECT * FROM work_items WHERE work_id=?", (work_id,)
            ).fetchone()
        return None if row is None else _work_item(row)

    def claim(self, work_id: str, *, now: datetime | None = None) -> StoredWorkItem | None:
        claimed_at = _timestamp(now)
        with self.database.transaction() as connection:
            result = connection.execute(
                """
                UPDATE work_items
                   SET state=?, attempt=attempt+1, started_at=?, completed_at=NULL,
                       error_class=NULL,error_code=NULL,error_summary=NULL,updated_at=?
                 WHERE work_id=?
                   AND (
                       state=? OR
                       (state=? AND next_retry_at IS NOT NULL AND next_retry_at<=?)
                   )
                """,
                (
                    WorkState.RUNNING.value,
                    claimed_at,
                    claimed_at,
                    work_id,
                    WorkState.READY.value,
                    WorkState.RETRY_WAIT.value,
                    claimed_at,
                ),
            )
            if result.rowcount != 1:
                return None
            row = connection.execute(
                "SELECT * FROM work_items WHERE work_id=?", (work_id,)
            ).fetchone()
        return _work_item(row)

    def _transition(
        self,
        work_id: str,
        *,
        from_states: tuple[WorkState, ...],
        to_state: WorkState,
        now: datetime | None = None,
        next_retry_at: datetime | None = None,
        error_class: str | None = None,
        error_code: str | None = None,
        error_summary: str | None = None,
        terminal: bool = False,
    ) -> bool:
        changed_at = _timestamp(now)
        placeholders = ",".join("?" for _state in from_states)
        values: list[object] = [
            to_state.value,
            _timestamp(next_retry_at) if next_retry_at else None,
            changed_at if terminal else None,
            error_class,
            error_code,
            error_summary,
            changed_at,
            work_id,
            *(state.value for state in from_states),
        ]
        with self.database.transaction() as connection:
            result = connection.execute(
                f"""
                UPDATE work_items
                   SET state=?,next_retry_at=?,completed_at=?,error_class=?,
                       error_code=?,error_summary=?,updated_at=?
                 WHERE work_id=? AND state IN ({placeholders})
                """,
                values,
            )
        return result.rowcount == 1

    def succeed(self, work_id: str, *, now: datetime | None = None) -> bool:
        return self._transition(
            work_id,
            from_states=(WorkState.RUNNING, WorkState.SUBMITTING, WorkState.RECONCILE_ONLY),
            to_state=WorkState.SUCCEEDED,
            now=now,
            terminal=True,
        )

    def reject(
        self,
        work_id: str,
        *,
        error_class: str,
        error_summary: str,
        error_code: str | None = None,
        now: datetime | None = None,
    ) -> bool:
        return self._transition(
            work_id,
            from_states=(WorkState.RUNNING,),
            to_state=WorkState.REJECTED,
            now=now,
            error_class=error_class,
            error_code=error_code,
            error_summary=error_summary,
            terminal=True,
        )

    def schedule_retry(
        self,
        work_id: str,
        *,
        retry_at: datetime,
        error_class: str,
        error_summary: str,
        error_code: str | None = None,
        from_states: tuple[WorkState, ...] = (WorkState.RUNNING,),
        now: datetime | None = None,
    ) -> bool:
        return self._transition(
            work_id,
            from_states=from_states,
            to_state=WorkState.RETRY_WAIT,
            now=now,
            next_retry_at=retry_at,
            error_class=error_class,
            error_code=error_code,
            error_summary=error_summary,
        )

    def wait_for_operator(
        self,
        work_id: str,
        *,
        error_class: str,
        error_summary: str,
        now: datetime | None = None,
    ) -> bool:
        return self._transition(
            work_id,
            from_states=(WorkState.RUNNING,),
            to_state=WorkState.WAITING_OPERATOR,
            now=now,
            error_class=error_class,
            error_summary=error_summary,
        )

    def resume_waiting(
        self,
        *,
        error_class: str,
        topics: tuple[WorkTopic, ...],
        now: datetime | None = None,
    ) -> list[str]:
        """Resume only work paused by a matching, now-resolved local condition."""

        if not error_class or not topics:
            return []
        changed_at = _timestamp(now)
        placeholders = ",".join("?" for _topic in topics)
        with self.database.transaction() as connection:
            rows = connection.execute(
                f"""
                SELECT work_id FROM work_items
                 WHERE state=? AND error_class=? AND topic IN ({placeholders})
                 ORDER BY created_at,work_id
                """,
                (
                    WorkState.WAITING_OPERATOR.value,
                    error_class,
                    *(topic.value for topic in topics),
                ),
            ).fetchall()
            work_ids = [row["work_id"] for row in rows]
            connection.executemany(
                """
                UPDATE work_items SET state=?,started_at=NULL,error_class=NULL,
                       error_code=NULL,error_summary=NULL,updated_at=? WHERE work_id=?
                """,
                [(WorkState.READY.value, changed_at, work_id) for work_id in work_ids],
            )
        return work_ids

    def reconcile_only(
        self,
        work_id: str,
        *,
        error_class: str = "REMOTE_AMBIGUOUS",
        error_summary: str,
        error_code: str | None = None,
        now: datetime | None = None,
    ) -> bool:
        """Conservatively stop automatic retries after a remote-call fence."""

        return self._transition(
            work_id,
            from_states=(WorkState.RUNNING, WorkState.SUBMITTING),
            to_state=WorkState.RECONCILE_ONLY,
            now=now,
            error_class=error_class,
            error_code=error_code,
            error_summary=error_summary,
        )

    def due_retry_ids(
        self,
        *,
        now: datetime | None = None,
        limit: int = 100,
    ) -> list[str]:
        if limit < 1:
            raise ValueError("limit must be positive")
        with self.database.locked() as connection:
            rows = connection.execute(
                """
                SELECT work_id FROM work_items
                 WHERE state=? AND next_retry_at<=?
                 ORDER BY next_retry_at,created_at LIMIT ?
                """,
                (WorkState.RETRY_WAIT.value, _timestamp(now), limit),
            ).fetchall()
        return [row["work_id"] for row in rows]

    def retry_schedule(
        self, *, limit: int = 10_000, topic: WorkTopic | str | None = None
    ) -> list[tuple[str, str]]:
        """Return the durable retry clock used to rebuild the in-memory heap."""

        if limit < 1:
            raise ValueError("limit must be positive")
        topic_value = None if topic is None else WorkTopic(topic).value
        with self.database.locked() as connection:
            rows = connection.execute(
                """
                SELECT work_id,next_retry_at FROM work_items
                 WHERE state=? AND next_retry_at IS NOT NULL
                   AND (? IS NULL OR topic=?)
                 ORDER BY next_retry_at,created_at,work_id LIMIT ?
                """,
                (WorkState.RETRY_WAIT.value, topic_value, topic_value, limit),
            ).fetchall()
        return [(row["next_retry_at"], row["work_id"]) for row in rows]

    def recover_interrupted(
        self, *, now: datetime | None = None, topic: WorkTopic | str | None = None
    ) -> dict[str, int]:
        """Recover selected local work; only full startup reconciles remote operations."""

        recovered_at = _timestamp(now)
        topic_value = None if topic is None else WorkTopic(topic).value
        with self.database.transaction() as connection:
            local = connection.execute(
                """
                UPDATE work_items
                   SET state=?,started_at=NULL,updated_at=?,error_summary=?
                 WHERE state=? AND (? IS NULL OR topic=?)
                """,
                (
                    WorkState.READY.value,
                    recovered_at,
                    "recovered interrupted local work",
                    WorkState.RUNNING.value,
                    topic_value,
                    topic_value,
                ),
            ).rowcount
            remote = connection.execute(
                """
                UPDATE work_items
                   SET state=?,updated_at=?,error_summary=?
                 WHERE state=? AND (? IS NULL OR topic=?)
                """,
                (
                    WorkState.RECONCILE_ONLY.value,
                    recovered_at,
                    "remote submission was interrupted after its fence",
                    WorkState.SUBMITTING.value,
                    topic_value,
                    topic_value,
                ),
            ).rowcount
            if topic is None:
                connection.execute(
                    """
                    UPDATE remote_operations SET state='AMBIGUOUS',updated_at=?,
                           error_summary=coalesce(error_summary,?)
                     WHERE state='SUBMITTING'
                    """,
                    (recovered_at, "application stopped after remote fence"),
                )
        return {"ready": local, "reconcile_only": remote}

    def counts_by_state(self) -> dict[str, int]:
        with self.database.locked() as connection:
            rows = connection.execute(
                "SELECT state,count(*) AS count FROM work_items GROUP BY state"
            ).fetchall()
        return {row["state"]: int(row["count"]) for row in rows}

    def recoverable_ids(
        self,
        states: tuple[WorkState, ...] = (
            WorkState.READY,
            WorkState.RETRY_WAIT,
            WorkState.RECONCILE_ONLY,
        ),
        *,
        topic: WorkTopic | str | None = None,
    ) -> list[str]:
        """Return durable work IDs Startup Recovery must re-notify."""

        if not states:
            return []
        placeholders = ",".join("?" for _state in states)
        parameters: list[object] = [state.value for state in states]
        topic_clause = ""
        if topic is not None:
            topic_clause = " AND topic=?"
            parameters.append(WorkTopic(topic).value)
        with self.database.locked() as connection:
            rows = connection.execute(
                f"""
                SELECT work_id FROM work_items WHERE state IN ({placeholders})
                 {topic_clause} ORDER BY created_at,work_id
                """,
                parameters,
            ).fetchall()
        return [row["work_id"] for row in rows]


@dataclass(frozen=True, slots=True)
class PublicationSlot:
    start: str
    end: str


def _slot(now: datetime, interval_minutes: float) -> PublicationSlot:
    if interval_minutes <= 0:
        raise ValueError("interval_minutes must be positive")
    current = now if now.tzinfo else now.replace(tzinfo=UTC)
    end = current.astimezone(UTC)
    start = end - timedelta(minutes=interval_minutes)
    return PublicationSlot(_timestamp(start), _timestamp(end))


class PublicationLedger:
    """Generic equivalent of the legacy rolling-slot and published ledgers."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def latest_published_at(self, *, sink: str, account_id: str) -> datetime | None:
        with self.database.locked() as connection:
            row = connection.execute(
                """
                SELECT max(marked_at) AS published_at FROM publication_marks
                 WHERE sink=? AND account_id=? AND status='published'
                """,
                (sink, account_id),
            ).fetchone()
        value = None if row is None else row["published_at"]
        return None if value is None else datetime.fromisoformat(value.replace("Z", "+00:00"))

    def claim_rolling_slot(
        self,
        now: datetime,
        *,
        interval_minutes: float,
    ) -> PublicationSlot | None:
        slot = _slot(now, interval_minutes)
        with self.database.transaction() as connection:
            previous = connection.execute(
                "SELECT slot_end FROM publish_slots WHERE slot_end<? "
                "ORDER BY slot_end DESC LIMIT 1",
                (slot.end,),
            ).fetchone()
            if previous is not None:
                slot = PublicationSlot(previous["slot_end"], slot.end)
            inserted = connection.execute(
                """
                INSERT OR IGNORE INTO publish_slots(slot_start,slot_end,status,started_at)
                VALUES(?,?,'processing',?)
                """,
                (slot.start, slot.end, _timestamp()),
            )
        return slot if inserted.rowcount == 1 else None

    def claim_ad_hoc_slot(self, now: datetime) -> PublicationSlot | None:
        """Claim a unique slot for one-time startup publication work."""

        current = now if now.tzinfo else now.replace(tzinfo=UTC)
        slot = PublicationSlot(
            _timestamp(current),
            _timestamp(current + timedelta(milliseconds=1)),
        )
        with self.database.transaction() as connection:
            inserted = connection.execute(
                """
                INSERT OR IGNORE INTO publish_slots(slot_start,slot_end,status,started_at)
                VALUES(?,?,'processing',?)
                """,
                (slot.start, slot.end, _timestamp()),
            )
        return slot if inserted.rowcount == 1 else None

    def discard_unpublished_news_before(
        self,
        cutoff: datetime,
        *,
        sink: str,
        account_id: str,
        plugin_id: str | None = None,
        now: datetime | None = None,
    ) -> int:
        """Permanently skip unpublished news that predates a configured cutoff."""

        marked_at = _timestamp(now)
        with self.database.transaction() as connection:
            inserted = connection.execute(
                """
                INSERT OR IGNORE INTO publication_marks(
                    record_id,sink,account_id,status,marked_at
                )
                SELECT r.record_id,?,?,'skipped',?
                  FROM records r
                 WHERE r.content_type='tech_news'
                   AND coalesce(json_extract(r.payload_json,'$.ready_at'),r.occurred_at)<?
                   AND (? IS NULL OR r.plugin_id=?)
                """,
                (sink, account_id, marked_at, _timestamp(cutoff), plugin_id, plugin_id),
            )
        return inserted.rowcount

    def mark_records(
        self,
        record_ids: list[str] | tuple[str, ...],
        status: str,
        *,
        sink: str,
        account_id: str,
        now: datetime | None = None,
    ) -> None:
        marked_at = _timestamp(now)
        with self.database.transaction() as connection:
            connection.executemany(
                """
                INSERT INTO publication_marks(record_id,sink,account_id,status,marked_at)
                VALUES(?,?,?,?,?)
                ON CONFLICT(record_id,sink,account_id) DO UPDATE SET
                    status=excluded.status,marked_at=excluded.marked_at
                """,
                [(record_id, sink, account_id, status, marked_at) for record_id in record_ids],
            )

    def get_slot(self, slot: PublicationSlot) -> dict[str, Any] | None:
        with self.database.locked() as connection:
            row = connection.execute(
                "SELECT * FROM publish_slots WHERE slot_start=? AND slot_end=?",
                (slot.start, slot.end),
            ).fetchone()
        return None if row is None else dict(row)

    def is_marked(
        self,
        record_id: str,
        *,
        sink: str,
        account_id: str,
    ) -> bool:
        with self.database.locked() as connection:
            row = connection.execute(
                """
                SELECT 1 FROM publication_marks
                 WHERE record_id=? AND sink=? AND account_id=?
                """,
                (record_id, sink, account_id),
            ).fetchone()
        return row is not None

    def marked_record_ids(
        self,
        record_ids: list[str] | tuple[str, ...],
        *,
        sink: str,
        account_id: str,
    ) -> set[str]:
        if not record_ids:
            return set()
        placeholders = ",".join("?" for _record_id in record_ids)
        with self.database.locked() as connection:
            rows = connection.execute(
                f"""
                SELECT record_id FROM publication_marks
                 WHERE record_id IN ({placeholders}) AND sink=? AND account_id=?
                """,
                (*record_ids, sink, account_id),
            ).fetchall()
        return {row["record_id"] for row in rows}

    def authorize_publish(
        self,
        slot: PublicationSlot,
        record_ids: list[str] | tuple[str, ...],
        *,
        title: str,
        item_count: int,
        sink: str,
        account_id: str,
        now: datetime | None = None,
    ) -> bool:
        if not record_ids:
            raise ValueError("record_ids must not be empty")
        invoked_at = _timestamp(now)
        with self.database.transaction() as connection:
            updated = connection.execute(
                """
                UPDATE publish_slots SET status='publishing',publish_invoked_at=?,
                       title=?,item_count=?
                 WHERE slot_start=? AND slot_end=? AND publish_invoked_at IS NULL
                """,
                (invoked_at, title, item_count, slot.start, slot.end),
            )
            if updated.rowcount != 1:
                return False
            connection.executemany(
                """
                INSERT INTO publication_marks(record_id,sink,account_id,status,marked_at)
                VALUES(?,?,?,'publishing',?)
                """,
                [(record_id, sink, account_id, invoked_at) for record_id in record_ids],
            )
        return True

    def finish(
        self,
        slot: PublicationSlot,
        status: str,
        *,
        title: str | None = None,
        item_count: int = 0,
        details: dict[str, Any] | None = None,
        error: str | None = None,
        now: datetime | None = None,
    ) -> None:
        with self.database.transaction() as connection:
            connection.execute(
                """
                UPDATE publish_slots SET status=?,completed_at=?,title=coalesce(?,title),
                       item_count=?,details=?,error=?
                 WHERE slot_start=? AND slot_end=?
                """,
                (
                    status,
                    _timestamp(now),
                    title,
                    item_count,
                    None if details is None else _json(details),
                    error,
                    slot.start,
                    slot.end,
                ),
            )

    def release_records(
        self,
        record_ids: list[str] | tuple[str, ...],
        *,
        sink: str,
        account_id: str,
    ) -> int:
        """Release only reservations proven not to have reached the remote sink."""

        if not record_ids:
            return 0
        placeholders = ",".join("?" for _record_id in record_ids)
        with self.database.transaction() as connection:
            result = connection.execute(
                f"""
                DELETE FROM publication_marks WHERE record_id IN ({placeholders})
                 AND sink=? AND account_id=? AND status='publishing'
                """,
                (*record_ids, sink, account_id),
            )
        return result.rowcount

    def release_rejected_records(
        self,
        record_ids: list[str] | tuple[str, ...],
        *,
        sink: str,
        account_id: str,
    ) -> int:
        """Release failed marks only after reconciliation proves the remote note absent."""

        if not record_ids:
            return 0
        placeholders = ",".join("?" for _record_id in record_ids)
        with self.database.transaction() as connection:
            result = connection.execute(
                f"""
                DELETE FROM publication_marks WHERE record_id IN ({placeholders})
                 AND sink=? AND account_id=? AND status='failed'
                """,
                (*record_ids, sink, account_id),
            )
        return result.rowcount
