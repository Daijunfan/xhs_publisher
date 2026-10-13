"""SQLite connection ownership and short, explicit transactions."""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


class Database:
    """Own one SQLite connection configured for the local single-process runtime.

    The re-entrant lock serializes the connection when blocking store calls are
    delegated to worker threads.  Network and browser calls must never run while
    a :meth:`transaction` context is open.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        busy_timeout_seconds: float = 30,
        read_only: bool = False,
    ) -> None:
        if busy_timeout_seconds <= 0:
            raise ValueError("busy_timeout_seconds must be positive")
        self.path = Path(path).expanduser().resolve()
        if not read_only:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        target = f"file:{self.path}?mode=ro" if read_only else str(self.path)
        self._lock = threading.RLock()
        self.connection = sqlite3.connect(
            target,
            timeout=busy_timeout_seconds,
            isolation_level=None,
            check_same_thread=False,
            uri=read_only,
        )
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.connection.execute(f"PRAGMA busy_timeout={int(busy_timeout_seconds * 1000)}")
        if not read_only:
            self.connection.execute("PRAGMA journal_mode=WAL")
            self.connection.execute("PRAGMA synchronous=NORMAL")

    @contextmanager
    def locked(self) -> Iterator[sqlite3.Connection]:
        """Serialize a group of read statements without opening a transaction."""

        with self._lock:
            yield self.connection

    @contextmanager
    def transaction(self, mode: str = "IMMEDIATE") -> Iterator[sqlite3.Connection]:
        """Open a short transaction and always commit or roll back it."""

        normalized = mode.upper()
        if normalized not in {"DEFERRED", "IMMEDIATE", "EXCLUSIVE"}:
            raise ValueError("transaction mode must be DEFERRED, IMMEDIATE, or EXCLUSIVE")
        with self._lock:
            if self.connection.in_transaction:
                raise RuntimeError("nested SQLite transactions are not supported")
            self.connection.execute(f"BEGIN {normalized}")
            try:
                yield self.connection
            except BaseException:
                self.connection.execute("ROLLBACK")
                raise
            else:
                self.connection.execute("COMMIT")

    def quick_check(self) -> None:
        with self.locked() as connection:
            rows = connection.execute("PRAGMA quick_check").fetchall()
        if len(rows) != 1 or rows[0][0] != "ok":
            raise RuntimeError(f"SQLite quick_check failed: {[tuple(row) for row in rows]}")

    def wal_checkpoint(self, mode: str = "PASSIVE") -> tuple[int, int, int]:
        normalized = mode.upper()
        if normalized not in {"PASSIVE", "FULL", "RESTART", "TRUNCATE"}:
            raise ValueError("unsupported WAL checkpoint mode")
        with self.locked() as connection:
            row = connection.execute(f"PRAGMA wal_checkpoint({normalized})").fetchone()
        return int(row[0]), int(row[1]), int(row[2])

    def close(self) -> None:
        with self._lock:
            self.connection.close()

    def __enter__(self) -> Database:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


SQLiteDatabase = Database
