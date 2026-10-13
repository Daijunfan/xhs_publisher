"""Configuration revision audit and readable local snapshots."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import yaml

from xhs_local.core.clock import utc_iso
from xhs_local.storage.database import Database

from .loader import ConfigSnapshot, snapshot_data, snapshot_from_data


def _timestamp() -> str:
    return utc_iso()


class ConfigHistory:
    def __init__(self, database: Database, snapshot_directory: Path, config_root: Path) -> None:
        self.database = database
        self.snapshot_directory = snapshot_directory.resolve()
        self.config_root = config_root.resolve()

    def save_candidate(
        self,
        snapshot: ConfigSnapshot,
        *,
        source: str,
        diff: dict[str, Any] | None,
        preflight: dict[str, Any] | None,
    ) -> None:
        payload = snapshot_data(snapshot)
        now = _timestamp()
        with self.database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO config_revisions(
                    revision,snapshot_json,diff_json,preflight_json,source,status,created_at
                ) VALUES(?,?,?,?,?,'CANDIDATE',?)
                ON CONFLICT(revision) DO UPDATE SET
                    diff_json=excluded.diff_json,preflight_json=excluded.preflight_json,
                    source=excluded.source
                """,
                (
                    snapshot.revision,
                    json.dumps(payload, ensure_ascii=False, sort_keys=True),
                    None if diff is None else json.dumps(diff, ensure_ascii=False, sort_keys=True),
                    None
                    if preflight is None
                    else json.dumps(preflight, ensure_ascii=False, sort_keys=True),
                    source,
                    now,
                ),
            )
        self._write_files(snapshot)

    def activate(self, revision: str) -> None:
        now = _timestamp()
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT 1 FROM config_revisions WHERE revision=?", (revision,)
            ).fetchone()
            if row is None:
                raise KeyError(f"unknown configuration revision: {revision}")
            connection.execute(
                "UPDATE config_revisions SET status='SUPERSEDED' WHERE status='ACTIVE'"
            )
            connection.execute(
                "UPDATE config_revisions SET status='ACTIVE',activated_at=? WHERE revision=?",
                (now, revision),
            )

    def last_active(self) -> ConfigSnapshot | None:
        with self.database.locked() as connection:
            row = connection.execute(
                """
                SELECT snapshot_json FROM config_revisions WHERE status='ACTIVE'
                 ORDER BY activated_at DESC LIMIT 1
                """
            ).fetchone()
        if row is None:
            return None
        data = json.loads(row["snapshot_json"])
        return snapshot_from_data(self.config_root, data)

    def revisions(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.database.locked() as connection:
            rows = connection.execute(
                """
                SELECT revision,source,status,created_at,activated_at,diff_json
                  FROM config_revisions ORDER BY created_at DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get(self, revision: str) -> ConfigSnapshot:
        with self.database.locked() as connection:
            row = connection.execute(
                "SELECT snapshot_json FROM config_revisions WHERE revision=?", (revision,)
            ).fetchone()
        if row is None:
            raise KeyError(f"unknown configuration revision: {revision}")
        return snapshot_from_data(self.config_root, json.loads(row["snapshot_json"]))

    def rollback_files(self, revision: str) -> ConfigSnapshot:
        snapshot = self.get(revision)
        self._write_config_root(snapshot)
        return snapshot

    def _write_files(self, snapshot: ConfigSnapshot) -> None:
        directory = self.snapshot_directory / snapshot.revision
        directory.mkdir(parents=True, exist_ok=True)
        for name, value in snapshot_data(snapshot).items():
            path = directory / f"{name}.yaml"
            temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
            temporary.write_text(
                yaml.safe_dump(value, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            temporary.replace(path)

    def _write_config_root(self, snapshot: ConfigSnapshot) -> None:
        for name, value in snapshot_data(snapshot).items():
            path = self.config_root / f"{name}.yaml"
            temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
            temporary.write_text(
                yaml.safe_dump(value, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            temporary.replace(path)
