"""Per-target durable collection checkpoints."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any

from xhs_local.core.clock import utc_iso

from .database import Database


def _timestamp(value: datetime | None = None) -> str:
    return utc_iso(value)


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class CheckpointRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    @staticmethod
    def put_in(
        connection: sqlite3.Connection,
        source_id: str,
        target_id: str,
        checkpoint: dict[str, Any],
        *,
        now: datetime | None = None,
    ) -> None:
        if not source_id or not target_id:
            raise ValueError("source_id and target_id are required")
        connection.execute(
            """
            INSERT INTO checkpoints(source_id,target_id,checkpoint_json,updated_at)
            VALUES(?,?,?,?)
            ON CONFLICT(source_id,target_id) DO UPDATE SET
                checkpoint_json=excluded.checkpoint_json,
                updated_at=excluded.updated_at
            """,
            (source_id, target_id, _json(checkpoint), _timestamp(now)),
        )

    def put(
        self,
        source_id: str,
        target_id: str,
        checkpoint: dict[str, Any],
        *,
        now: datetime | None = None,
    ) -> None:
        with self.database.transaction() as connection:
            self.put_in(connection, source_id, target_id, checkpoint, now=now)

    def get(self, source_id: str, target_id: str) -> dict[str, Any] | None:
        with self.database.locked() as connection:
            row = connection.execute(
                "SELECT checkpoint_json FROM checkpoints WHERE source_id=? AND target_id=?",
                (source_id, target_id),
            ).fetchone()
        return None if row is None else json.loads(row["checkpoint_json"])

    def initialize(self, source_id: str, target_id: str, value: dict[str, Any]) -> dict[str, Any]:
        """Persist a first-use boundary once, before any external collection can fail."""
        with self.database.transaction() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO checkpoints VALUES(?,?,?,?)",
                (source_id, target_id, _json(value), _timestamp()),
            )
            row = connection.execute(
                "SELECT checkpoint_json FROM checkpoints WHERE source_id=? AND target_id=?",
                (source_id, target_id),
            ).fetchone()
            return json.loads(row["checkpoint_json"])

    def delete(self, source_id: str, target_id: str) -> bool:
        with self.database.transaction() as connection:
            result = connection.execute(
                "DELETE FROM checkpoints WHERE source_id=? AND target_id=?",
                (source_id, target_id),
            )
        return result.rowcount == 1

    def list_all(self) -> list[dict[str, Any]]:
        with self.database.locked() as connection:
            rows = connection.execute(
                "SELECT source_id,target_id,checkpoint_json,updated_at "
                "FROM checkpoints ORDER BY source_id,target_id"
            ).fetchall()
        return [
            {
                "source_id": row["source_id"],
                "target_id": row["target_id"],
                "checkpoint": json.loads(row["checkpoint_json"]),
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]
