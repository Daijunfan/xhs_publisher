"""SQLite online backups with verification and small local retention."""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from xhs_local.core.identifiers import new_id

from .database import Database
from .schema import current_version

BEIJING = ZoneInfo("Asia/Shanghai")


def _stamp(value: datetime | None = None) -> str:
    current = value or datetime.now(BEIJING)
    if current.tzinfo is None:
        current = current.replace(tzinfo=BEIJING)
    return current.astimezone(BEIJING).strftime("%Y%m%dT%H%M%S+0800")


@dataclass(frozen=True, slots=True)
class BackupResult:
    database_path: Path
    metadata_path: Path
    config_directory: Path | None
    schema_version: int


class BackupService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create(
        self,
        backup_directory: str | Path,
        *,
        config_paths: tuple[Path, ...] | list[Path] = (),
        now: datetime | None = None,
    ) -> BackupResult:
        root = Path(backup_directory).expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        stem = f"app-{_stamp(now)}-{new_id()[:8]}"
        destination = root / f"{stem}.sqlite3"
        temporary = root / f".{stem}.sqlite3.tmp"
        metadata = root / f"{stem}.json"
        temporary_metadata = root / f".{stem}.json.tmp"
        config_directory: Path | None = None
        version = current_version(self.database)
        target = sqlite3.connect(temporary)
        try:
            with self.database.locked() as connection:
                connection.backup(target)
            target.close()
            self.verify(temporary, expected_schema_version=version)
            os.replace(temporary, destination)
            if config_paths:
                config_directory = root / f"{stem}.config"
                config_directory.mkdir()
                for path in config_paths:
                    resolved = Path(path).expanduser().resolve()
                    if not resolved.is_file():
                        raise FileNotFoundError(f"configuration snapshot is missing: {resolved}")
                    shutil.copy2(resolved, config_directory / resolved.name)
            created_at = (now or datetime.now(BEIJING)).astimezone(BEIJING).isoformat()
            payload = {
                "database": destination.name,
                "schema_version": version,
                "created_at": created_at,
                "config_directory": None if config_directory is None else config_directory.name,
            }
            temporary_metadata.write_text(
                json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                encoding="utf-8",
            )
            os.replace(temporary_metadata, metadata)
        except BaseException:
            target.close()
            temporary.unlink(missing_ok=True)
            destination.unlink(missing_ok=True)
            temporary_metadata.unlink(missing_ok=True)
            metadata.unlink(missing_ok=True)
            if config_directory is not None:
                shutil.rmtree(config_directory, ignore_errors=True)
            raise
        return BackupResult(destination, metadata, config_directory, version)

    @staticmethod
    def verify(path: str | Path, *, expected_schema_version: int | None = None) -> None:
        database_path = Path(path).expanduser().resolve()
        uri = f"file:{database_path}?mode=ro"
        connection = sqlite3.connect(uri, uri=True)
        try:
            rows = connection.execute("PRAGMA quick_check").fetchall()
            if rows != [("ok",)]:
                raise RuntimeError(f"backup quick_check failed: {rows}")
            if expected_schema_version is not None:
                row = connection.execute("SELECT max(version) FROM schema_migrations").fetchone()
                actual = int(row[0] or 0)
                if actual != expected_schema_version:
                    raise RuntimeError(
                        f"backup schema is {actual}, expected {expected_schema_version}"
                    )
        finally:
            connection.close()

    @staticmethod
    def prune(backup_directory: str | Path, *, keep: int) -> list[Path]:
        if keep < 1:
            raise ValueError("keep must be positive")
        root = Path(backup_directory).expanduser().resolve()
        backups = sorted(root.glob("app-*.sqlite3"), key=lambda path: path.stat().st_mtime)
        removed: list[Path] = []
        for database_path in backups[:-keep]:
            stem = database_path.with_suffix("")
            metadata = database_path.with_suffix(".json")
            config_directory = root / f"{stem.name}.config"
            database_path.unlink()
            metadata.unlink(missing_ok=True)
            if config_directory.exists():
                shutil.rmtree(config_directory)
            removed.append(database_path)
        return removed
