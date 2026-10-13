"""Explicit, checksummed SQLite schema migrations."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from .database import Database

MIGRATIONS_ROOT = Path(__file__).with_name("migrations")


@dataclass(frozen=True, slots=True)
class Migration:
    version: int
    name: str
    path: Path
    checksum: str


def available_migrations(root: Path = MIGRATIONS_ROOT) -> tuple[Migration, ...]:
    migrations: list[Migration] = []
    for path in sorted(root.glob("[0-9][0-9][0-9]_*.sql")):
        prefix, _, _name = path.name.partition("_")
        sql = path.read_bytes()
        migrations.append(Migration(int(prefix), path.name, path, hashlib.sha256(sql).hexdigest()))
    expected = list(range(1, len(migrations) + 1))
    versions = [migration.version for migration in migrations]
    if versions != expected:
        raise RuntimeError(f"schema migrations must be contiguous: {versions}")
    return tuple(migrations)


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _ensure_ledger(database: Database) -> None:
    with database.locked() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                checksum TEXT NOT NULL,
                applied_at TEXT NOT NULL
            )
            """
        )


def applied_versions(database: Database) -> dict[int, tuple[str, str]]:
    with database.locked() as connection:
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
        ).fetchone()
        if exists is None:
            return {}
        rows = connection.execute(
            "SELECT version, name, checksum FROM schema_migrations ORDER BY version"
        ).fetchall()
    return {int(row["version"]): (row["name"], row["checksum"]) for row in rows}


def migrate(database: Database, *, target_version: int | None = None) -> int:
    """Apply missing migrations transactionally and return the resulting version."""

    migrations = available_migrations()
    latest = migrations[-1].version if migrations else 0
    target = latest if target_version is None else target_version
    if target < 0 or target > latest:
        raise ValueError(f"target_version must be between 0 and {latest}")
    _ensure_ledger(database)
    applied = applied_versions(database)
    for migration in migrations:
        existing = applied.get(migration.version)
        if existing is not None:
            if existing != (migration.name, migration.checksum):
                raise RuntimeError(
                    f"migration {migration.version} differs from the applied checksum"
                )
            continue
        if migration.version > target:
            break
        sql = migration.path.read_text(encoding="utf-8")
        ledger = (
            "INSERT INTO schema_migrations(version,name,checksum,applied_at) VALUES("
            f"{migration.version},{_sql_literal(migration.name)},"
            f"{_sql_literal(migration.checksum)},strftime('%Y-%m-%dT%H:%M:%fZ','now'));"
        )
        script = f"BEGIN IMMEDIATE;\n{sql}\n{ledger}\nCOMMIT;"
        with database.locked() as connection:
            try:
                connection.executescript(script)
            except BaseException:
                if connection.in_transaction:
                    connection.execute("ROLLBACK")
                raise
        applied[migration.version] = (migration.name, migration.checksum)
    return max((version for version in applied if version <= target), default=0)


def current_version(database: Database) -> int:
    versions = applied_versions(database)
    return max(versions, default=0)


def assert_current(database: Database) -> int:
    migrations = available_migrations()
    expected = migrations[-1].version if migrations else 0
    applied = applied_versions(database)
    actual = max(applied, default=0)
    if actual != expected:
        raise RuntimeError(
            f"database schema is version {actual}, expected {expected}; run the migration command"
        )
    for migration in migrations:
        if applied.get(migration.version) != (migration.name, migration.checksum):
            raise RuntimeError(f"database migration {migration.version} is missing or changed")
    return actual


def open_database(
    path: str | Path,
    *,
    busy_timeout_seconds: float = 30,
    apply_migrations: bool = False,
) -> Database:
    database = Database(path, busy_timeout_seconds=busy_timeout_seconds)
    if apply_migrations:
        migrate(database)
    else:
        assert_current(database)
    return database
