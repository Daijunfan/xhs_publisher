"""Durable fences around irreversible remote side effects."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from xhs_local.core.clock import utc_iso
from xhs_local.core.identifiers import new_id
from xhs_local.core.states import WorkState

from .database import Database


def _timestamp(value: datetime | None = None) -> str:
    return utc_iso(value)


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True, slots=True)
class RemoteOperation:
    operation_id: str
    work_id: str
    sink: str
    account_id: str
    operation: str
    idempotency_key: str
    state: str
    attempt: int
    request: dict[str, Any] | None
    result: dict[str, Any] | None
    error_summary: str | None
    created_at: str
    updated_at: str


def _operation(row: sqlite3.Row) -> RemoteOperation:
    return RemoteOperation(
        operation_id=row["operation_id"],
        work_id=row["work_id"],
        sink=row["sink"],
        account_id=row["account_id"],
        operation=row["operation"],
        idempotency_key=row["idempotency_key"],
        state=row["state"],
        attempt=int(row["attempt"]),
        request=None if row["request_json"] is None else json.loads(row["request_json"]),
        result=None if row["result_json"] is None else json.loads(row["result_json"]),
        error_summary=row["error_summary"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class RemoteOperationRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def begin(
        self,
        work_id: str,
        *,
        sink: str,
        account_id: str,
        operation: str,
        idempotency_key: str,
        request: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> RemoteOperation | None:
        """Atomically cross a remote fence; duplicates never reach the sink."""

        if not all((work_id, sink, account_id, operation, idempotency_key)):
            raise ValueError("remote operation identifiers must be non-empty")
        started_at = _timestamp(now)
        with self.database.transaction() as connection:
            work = connection.execute(
                "SELECT state,attempt FROM work_items WHERE work_id=?", (work_id,)
            ).fetchone()
            if work is None:
                raise KeyError(f"unknown work item: {work_id}")
            if work["state"] != WorkState.RUNNING.value:
                return None
            existing = connection.execute(
                """
                SELECT * FROM remote_operations
                 WHERE sink=? AND account_id=? AND idempotency_key=?
                """,
                (sink, account_id, idempotency_key),
            ).fetchone()
            if existing is None:
                operation_id = new_id()
                connection.execute(
                    """
                    INSERT INTO remote_operations(
                        operation_id,work_id,sink,account_id,operation,idempotency_key,
                        state,attempt,request_json,created_at,updated_at
                    ) VALUES(?,?,?,?,?,?,'SUBMITTING',?,?,?,?)
                    """,
                    (
                        operation_id,
                        work_id,
                        sink,
                        account_id,
                        operation,
                        idempotency_key,
                        max(1, int(work["attempt"])),
                        None if request is None else _json(request),
                        started_at,
                        started_at,
                    ),
                )
            else:
                if existing["work_id"] != work_id or existing["state"] != "NOT_SUBMITTED":
                    return None
                operation_id = existing["operation_id"]
                connection.execute(
                    """
                    UPDATE remote_operations
                       SET state='SUBMITTING',operation=?,attempt=?,request_json=?,
                           result_json=NULL,error_summary=NULL,updated_at=?
                     WHERE operation_id=? AND state='NOT_SUBMITTED'
                    """,
                    (
                        operation,
                        max(1, int(work["attempt"])),
                        None if request is None else _json(request),
                        started_at,
                        operation_id,
                    ),
                )
            updated = connection.execute(
                "UPDATE work_items SET state=?,updated_at=? WHERE work_id=? AND state=?",
                (
                    WorkState.SUBMITTING.value,
                    started_at,
                    work_id,
                    WorkState.RUNNING.value,
                ),
            )
            if updated.rowcount != 1:
                raise RuntimeError("work item changed while its remote fence was created")
            row = connection.execute(
                "SELECT * FROM remote_operations WHERE operation_id=?", (operation_id,)
            ).fetchone()
        return _operation(row)

    def get(self, operation_id: str) -> RemoteOperation | None:
        with self.database.locked() as connection:
            row = connection.execute(
                "SELECT * FROM remote_operations WHERE operation_id=?", (operation_id,)
            ).fetchone()
        return None if row is None else _operation(row)

    def get_by_key(
        self, sink: str, account_id: str, idempotency_key: str
    ) -> RemoteOperation | None:
        with self.database.locked() as connection:
            row = connection.execute(
                """
                SELECT * FROM remote_operations
                 WHERE sink=? AND account_id=? AND idempotency_key=?
                """,
                (sink, account_id, idempotency_key),
            ).fetchone()
        return None if row is None else _operation(row)

    def succeeded_at_since(
        self,
        *,
        sink: str,
        account_id: str,
        since: datetime,
    ) -> list[datetime]:
        with self.database.locked() as connection:
            rows = connection.execute(
                """
                SELECT updated_at FROM remote_operations
                 WHERE sink=? AND account_id=? AND state='SUCCEEDED' AND updated_at>=?
                 ORDER BY updated_at
                """,
                (sink, account_id, _timestamp(since)),
            ).fetchall()
        return [datetime.fromisoformat(row["updated_at"].replace("Z", "+00:00")) for row in rows]

    def work_succeeded(self, work_id: str) -> bool:
        with self.database.locked() as connection:
            return (
                connection.execute(
                    "SELECT 1 FROM remote_operations WHERE work_id=? AND state='SUCCEEDED' LIMIT 1",
                    (work_id,),
                ).fetchone()
                is not None
            )

    def succeed(
        self,
        operation_id: str,
        *,
        result: dict[str, Any],
        finalize_work: bool = True,
        now: datetime | None = None,
    ) -> bool:
        completed_at = _timestamp(now)
        with self.database.transaction() as connection:
            operation = connection.execute(
                "SELECT work_id,state FROM remote_operations WHERE operation_id=?",
                (operation_id,),
            ).fetchone()
            if operation is None or operation["state"] not in {"SUBMITTING", "AMBIGUOUS"}:
                return False
            connection.execute(
                """
                UPDATE remote_operations SET state='SUCCEEDED',result_json=?,
                       error_summary=NULL,updated_at=? WHERE operation_id=?
                """,
                (_json(result), completed_at, operation_id),
            )
            target_state = WorkState.SUCCEEDED if finalize_work else WorkState.RUNNING
            accepted_states = (
                (WorkState.SUBMITTING.value, WorkState.RECONCILE_ONLY.value)
                if finalize_work
                else (WorkState.SUBMITTING.value, WorkState.SUBMITTING.value)
            )
            work = connection.execute(
                """
                UPDATE work_items SET state=?,completed_at=?,updated_at=?,
                       error_class=NULL,error_code=NULL,error_summary=NULL
                 WHERE work_id=? AND state IN (?,?)
                """,
                (
                    target_state.value,
                    completed_at if finalize_work else None,
                    completed_at,
                    operation["work_id"],
                    *accepted_states,
                ),
            )
            if work.rowcount != 1:
                raise RuntimeError("remote operation and work item states diverged")
        return True

    def complete_step(
        self,
        operation_id: str,
        *,
        result: dict[str, Any],
        now: datetime | None = None,
    ) -> bool:
        """Finish one remote step and return its work to RUNNING for the next sink."""

        return self.succeed(
            operation_id,
            result=result,
            finalize_work=False,
            now=now,
        )

    def finalize_work(
        self,
        operation_id: str,
        *,
        now: datetime | None = None,
    ) -> bool:
        """Finalize local work after all post-publish cleanup has succeeded."""

        completed_at = _timestamp(now)
        with self.database.transaction() as connection:
            operation = connection.execute(
                "SELECT work_id,state FROM remote_operations WHERE operation_id=?",
                (operation_id,),
            ).fetchone()
            if operation is None or operation["state"] != "SUCCEEDED":
                return False
            result = connection.execute(
                """
                UPDATE work_items SET state=?,completed_at=?,updated_at=?,
                       error_class=NULL,error_code=NULL,error_summary=NULL
                 WHERE work_id=? AND state=?
                """,
                (
                    WorkState.SUCCEEDED.value,
                    completed_at,
                    completed_at,
                    operation["work_id"],
                    WorkState.RUNNING.value,
                ),
            )
        return result.rowcount == 1

    def not_submitted(
        self,
        operation_id: str,
        *,
        error_summary: str,
        retry_at: datetime | None = None,
        now: datetime | None = None,
    ) -> bool:
        changed_at = _timestamp(now)
        with self.database.transaction() as connection:
            operation = connection.execute(
                "SELECT work_id,state FROM remote_operations WHERE operation_id=?",
                (operation_id,),
            ).fetchone()
            if operation is None or operation["state"] != "SUBMITTING":
                return False
            connection.execute(
                """
                UPDATE remote_operations SET state='NOT_SUBMITTED',error_summary=?,updated_at=?
                 WHERE operation_id=?
                """,
                (error_summary, changed_at, operation_id),
            )
            state = WorkState.RETRY_WAIT if retry_at else WorkState.READY
            work = connection.execute(
                """
                UPDATE work_items SET state=?,next_retry_at=?,started_at=NULL,
                       error_class='REMOTE_NOT_SUBMITTED',error_summary=?,updated_at=?
                 WHERE work_id=? AND state=?
                """,
                (
                    state.value,
                    None if retry_at is None else _timestamp(retry_at),
                    error_summary,
                    changed_at,
                    operation["work_id"],
                    WorkState.SUBMITTING.value,
                ),
            )
            if work.rowcount != 1:
                raise RuntimeError("remote operation and work item states diverged")
        return True

    def ambiguous(
        self,
        operation_id: str,
        *,
        error_summary: str,
        now: datetime | None = None,
    ) -> bool:
        changed_at = _timestamp(now)
        with self.database.transaction() as connection:
            operation = connection.execute(
                "SELECT work_id,state FROM remote_operations WHERE operation_id=?",
                (operation_id,),
            ).fetchone()
            if operation is None or operation["state"] != "SUBMITTING":
                return False
            connection.execute(
                """
                UPDATE remote_operations SET state='AMBIGUOUS',error_summary=?,updated_at=?
                 WHERE operation_id=?
                """,
                (error_summary, changed_at, operation_id),
            )
            work = connection.execute(
                """
                UPDATE work_items SET state=?,error_class='REMOTE_AMBIGUOUS',
                       error_summary=?,updated_at=? WHERE work_id=? AND state=?
                """,
                (
                    WorkState.RECONCILE_ONLY.value,
                    error_summary,
                    changed_at,
                    operation["work_id"],
                    WorkState.SUBMITTING.value,
                ),
            )
            if work.rowcount != 1:
                raise RuntimeError("remote operation and work item states diverged")
        return True

    def reject_absent(
        self,
        operation_id: str,
        *,
        evidence: str,
        now: datetime | None = None,
    ) -> bool:
        """Close an ambiguous operation after read-only reconciliation proves no remote note."""

        if not evidence.strip():
            raise ValueError("reconciliation evidence is required")
        changed_at = _timestamp(now)
        with self.database.transaction() as connection:
            operation = connection.execute(
                "SELECT work_id,state FROM remote_operations WHERE operation_id=?",
                (operation_id,),
            ).fetchone()
            if operation is None or operation["state"] != "AMBIGUOUS":
                return False
            connection.execute(
                """
                UPDATE remote_operations SET state='REJECTED',result_json=?,error_summary=?,
                       updated_at=? WHERE operation_id=?
                """,
                (
                    _json({"reconciled": True, "found": False, "evidence": evidence}),
                    evidence,
                    changed_at,
                    operation_id,
                ),
            )
            work = connection.execute(
                """
                UPDATE work_items SET state=?,completed_at=?,updated_at=?,
                       error_class='REMOTE_REJECTED',error_summary=?
                 WHERE work_id=? AND state=?
                """,
                (
                    WorkState.REJECTED.value,
                    changed_at,
                    changed_at,
                    evidence,
                    operation["work_id"],
                    WorkState.RECONCILE_ONLY.value,
                ),
            )
            if work.rowcount != 1:
                raise RuntimeError("remote operation and work item states diverged")
        return True

    def reject_submission(
        self,
        operation_id: str,
        *,
        evidence: str,
        now: datetime | None = None,
    ) -> bool:
        """Close a submitted operation when the remote result explicitly proves rejection."""

        if not evidence.strip():
            raise ValueError("rejection evidence is required")
        changed_at = _timestamp(now)
        with self.database.transaction() as connection:
            operation = connection.execute(
                "SELECT work_id,state FROM remote_operations WHERE operation_id=?",
                (operation_id,),
            ).fetchone()
            if operation is None or operation["state"] != "SUBMITTING":
                return False
            connection.execute(
                """
                UPDATE remote_operations SET state='REJECTED',result_json=?,error_summary=?,
                       updated_at=? WHERE operation_id=?
                """,
                (
                    _json({"found": False, "evidence": evidence}),
                    evidence,
                    changed_at,
                    operation_id,
                ),
            )
            work = connection.execute(
                """
                UPDATE work_items SET state=?,completed_at=?,updated_at=?,
                       error_class='REMOTE_REJECTED',error_summary=?
                 WHERE work_id=? AND state=?
                """,
                (
                    WorkState.REJECTED.value,
                    changed_at,
                    changed_at,
                    evidence,
                    operation["work_id"],
                    WorkState.SUBMITTING.value,
                ),
            )
            if work.rowcount != 1:
                raise RuntimeError("remote operation and work item states diverged")
        return True

    def hold_rate_limit(
        self,
        operation_id: str,
        *,
        retry_at: datetime,
        evidence: str,
        now: datetime | None = None,
    ) -> bool:
        """Persist a remote daily limit as a circuit barrier until its reset time."""

        if not evidence.strip():
            raise ValueError("rate-limit evidence is required")
        changed_at = _timestamp(now)
        retry_at_text = _timestamp(retry_at)
        with self.database.transaction() as connection:
            operation = connection.execute(
                "SELECT work_id,state FROM remote_operations WHERE operation_id=?",
                (operation_id,),
            ).fetchone()
            if operation is None or operation["state"] not in {"SUBMITTING", "AMBIGUOUS"}:
                return False
            connection.execute(
                """
                UPDATE remote_operations SET state='RATE_LIMITED',result_json=?,
                       error_summary=?,updated_at=? WHERE operation_id=?
                """,
                (
                    _json({"retry_at": retry_at_text, "evidence": evidence}),
                    evidence,
                    changed_at,
                    operation_id,
                ),
            )
            work = connection.execute(
                """
                UPDATE work_items SET state=?,next_retry_at=?,updated_at=?,
                       error_class='RATE_LIMITED',error_summary=?
                 WHERE work_id=? AND state IN (?,?)
                """,
                (
                    WorkState.WAITING_OPERATOR.value,
                    retry_at_text,
                    changed_at,
                    evidence,
                    operation["work_id"],
                    WorkState.SUBMITTING.value,
                    WorkState.RECONCILE_ONLY.value,
                ),
            )
            if work.rowcount != 1:
                raise RuntimeError("remote operation and work item states diverged")
        return True

    def release_expired_rate_limits(self, *, now: datetime | None = None) -> int:
        """Close expired barriers; rejected content remains eligible through released marks."""

        changed_at = _timestamp(now)
        with self.database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT operation_id,work_id FROM remote_operations
                 WHERE state='RATE_LIMITED'
                   AND json_extract(result_json,'$.retry_at')<=?
                """,
                (changed_at,),
            ).fetchall()
            if not rows:
                return 0
            connection.executemany(
                """
                UPDATE remote_operations SET state='REJECTED',updated_at=?
                 WHERE operation_id=? AND state='RATE_LIMITED'
                """,
                [(changed_at, row["operation_id"]) for row in rows],
            )
            connection.executemany(
                """
                UPDATE work_items SET state=?,completed_at=?,updated_at=?
                 WHERE work_id=? AND state=?
                """,
                [
                    (
                        WorkState.REJECTED.value,
                        changed_at,
                        changed_at,
                        row["work_id"],
                        WorkState.WAITING_OPERATOR.value,
                    )
                    for row in rows
                ],
            )
        return len(rows)

    def unresolved(self, *, limit: int = 100) -> list[RemoteOperation]:
        if limit < 1:
            raise ValueError("limit must be positive")
        with self.database.locked() as connection:
            rows = connection.execute(
                """
                SELECT * FROM remote_operations WHERE state IN ('AMBIGUOUS','RATE_LIMITED')
                 ORDER BY updated_at LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [_operation(row) for row in rows]
