from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from xhs_local.storage.database import Database
from xhs_local.storage.schema import (
    applied_versions,
    assert_current,
    available_migrations,
    migrate,
)


def test_migrations_are_explicit_checksums_and_database_pragmas(tmp_path: Path) -> None:
    path = tmp_path / "app.sqlite3"
    with Database(path, busy_timeout_seconds=2.5) as database:
        assert migrate(database) == 5
        assert migrate(database) == 5
        assert assert_current(database) == 5
        expected = {item.version: (item.name, item.checksum) for item in available_migrations()}
        assert applied_versions(database) == expected
        with database.locked() as connection:
            assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
            assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
            assert connection.execute("PRAGMA busy_timeout").fetchone()[0] == 2500
        database.quick_check()


def test_transaction_rolls_back_all_statements(database: Database) -> None:
    with pytest.raises(RuntimeError, match="synthetic"), database.transaction() as connection:
        connection.execute(
            "INSERT INTO legacy_sync_state(key,value) VALUES('one','before failure')"
        )
        raise RuntimeError("synthetic")
    with database.locked() as connection:
        assert connection.execute("SELECT count(*) FROM legacy_sync_state").fetchone()[0] == 0


def test_startup_schema_check_does_not_silently_migrate(tmp_path: Path) -> None:
    path = tmp_path / "empty.sqlite3"
    sqlite3.connect(path).close()
    with Database(path) as database, pytest.raises(RuntimeError, match="run the migration command"):
        assert_current(database)
