"""Small-batch database and runtime-file retention."""

from __future__ import annotations

import hashlib
import re
import shutil
from contextlib import suppress
from datetime import datetime
from pathlib import Path

from xhs_local.core.clock import utc_iso
from xhs_local.core.states import TERMINAL_WORK_STATES

from .database import Database


def _timestamp(value: datetime) -> str:
    return utc_iso(value)


class RetentionService:
    def __init__(self, database: Database, runtime_root: str | Path) -> None:
        self.database = database
        self.runtime_root = Path(runtime_root).expanduser().resolve()

    @staticmethod
    def _limit(value: int) -> int:
        if value < 1:
            raise ValueError("batch_size must be positive")
        return value

    def purge_news(
        self, before: datetime, *, batch_size: int = 500, documents_before: datetime | None = None
    ) -> int:
        """Delete expired local records, including favorites, to bound disk use."""
        with self.database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT record_id FROM records
                 WHERE content_type IN ('tech_news','video_pending')
                   AND ((COALESCE(json_extract(payload_json,'$.cloud_document_channel'),0)=0
                         AND occurred_at<?)
                        OR (json_extract(payload_json,'$.cloud_document_channel')=1
                            AND occurred_at<?))
                 ORDER BY occurred_at LIMIT ?
                """,
                (
                    _timestamp(before),
                    _timestamp(documents_before or before),
                    self._limit(batch_size),
                ),
            ).fetchall()
            connection.executemany(
                "DELETE FROM records WHERE record_id=?", [(row["record_id"],) for row in rows]
            )
        return len(rows)

    def purge_news_posters(self) -> None:
        root = self.runtime_root / "generated" / "website"
        with self.database.locked() as connection:
            retained = {
                hashlib.sha256(row["record_id"].encode()).hexdigest()
                for row in connection.execute("SELECT record_id FROM records")
            }
            for directory in root.glob("*"):
                if directory.name not in retained and directory.is_dir():
                    shutil.rmtree(directory)

            videos = self.runtime_root / "videos"
            if videos.is_symlink():
                return
            retained_videos = {
                hashlib.sha256(f"{row['plugin_id']}:{row['external_id']}".encode()).hexdigest()
                for row in connection.execute("SELECT plugin_id,external_id FROM records")
            }
            for directory in videos.glob("*"):
                if (
                    re.fullmatch(r"[0-9a-f]{64}", directory.name)
                    and directory.name not in retained_videos
                    and directory.is_dir()
                    and not directory.is_symlink()
                ):
                    shutil.rmtree(directory)

    def purge_dispatched_outbox(self, before: datetime, *, batch_size: int = 500) -> int:
        with self.database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT event_id FROM outbox WHERE state='DISPATCHED' AND dispatched_at<?
                 ORDER BY dispatched_at LIMIT ?
                """,
                (_timestamp(before), self._limit(batch_size)),
            ).fetchall()
            connection.executemany(
                "DELETE FROM outbox WHERE event_id=?", [(row["event_id"],) for row in rows]
            )
        return len(rows)

    def purge_terminal_work(self, before: datetime, *, batch_size: int = 500) -> int:
        states = tuple(state.value for state in TERMINAL_WORK_STATES)
        placeholders = ",".join("?" for _state in states)
        with self.database.transaction() as connection:
            rows = connection.execute(
                f"""
                SELECT work_id FROM work_items
                 WHERE state IN ({placeholders}) AND completed_at<?
                   AND NOT EXISTS(
                       SELECT 1 FROM remote_operations r WHERE r.work_id=work_items.work_id
                   )
                   AND NOT EXISTS(
                       SELECT 1 FROM dead_letters d WHERE d.work_id=work_items.work_id
                   )
                 ORDER BY completed_at LIMIT ?
                """,
                (*states, _timestamp(before), self._limit(batch_size)),
            ).fetchall()
            connection.executemany(
                "DELETE FROM work_items WHERE work_id=?", [(row["work_id"],) for row in rows]
            )
        return len(rows)

    def purge_completed_remote_operations(self, before: datetime) -> None:
        with self.database.transaction() as connection:
            connection.execute(
                "DELETE FROM remote_operations WHERE updated_at<? "
                "AND state IN ('SUCCEEDED','REJECTED','NOT_SUBMITTED')",
                (_timestamp(before),),
            )

    def purge_unreferenced_records(self, before: datetime, *, batch_size: int = 500) -> int:
        with self.database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT record_id FROM records WHERE updated_at<?
                  AND NOT EXISTS(
                      SELECT 1 FROM work_items w WHERE w.record_id=records.record_id
                  )
                  AND NOT EXISTS(
                      SELECT 1 FROM publication_marks p WHERE p.record_id=records.record_id
                  )
                  AND NOT EXISTS(
                      SELECT 1 FROM legacy_record_map l WHERE l.record_id=records.record_id
                  )
                 ORDER BY updated_at LIMIT ?
                """,
                (_timestamp(before), self._limit(batch_size)),
            ).fetchall()
            connection.executemany(
                "DELETE FROM records WHERE record_id=?", [(row["record_id"],) for row in rows]
            )
        return len(rows)

    def purge_orphan_media(self, before: datetime, *, batch_size: int = 500) -> int:
        media_root = self.runtime_root / "media" / "sha256"
        if not media_root.exists():
            return 0
        with self.database.locked() as connection:
            referenced = {
                row["relative_path"]
                for row in connection.execute("SELECT DISTINCT relative_path FROM attachments")
            }
        cutoff = before.timestamp()
        removed = 0
        for path in sorted(media_root.rglob("*")):
            if removed >= self._limit(batch_size) or not path.is_file():
                continue
            resolved = path.resolve()
            if not resolved.is_relative_to(media_root.resolve()):
                continue
            relative = resolved.relative_to(self.runtime_root).as_posix()
            if relative in referenced or path.stat().st_mtime >= cutoff:
                continue
            path.unlink()
            removed += 1
        for directory in sorted(media_root.rglob("*"), reverse=True):
            if directory.is_dir():
                with suppress(OSError):
                    directory.rmdir()
        return removed

    def purge_directory(
        self,
        relative_directory: str,
        before: datetime,
        *,
        batch_size: int = 500,
    ) -> int:
        root = (self.runtime_root / relative_directory).resolve()
        if root == self.runtime_root or not root.is_relative_to(self.runtime_root):
            raise ValueError("retention directory must be a child of runtime_root")
        if not root.exists():
            return 0
        cutoff = before.timestamp()
        removed = 0
        for path in sorted(root.rglob("*")):
            if removed >= self._limit(batch_size) or not path.is_file():
                continue
            if path.is_symlink() or not path.resolve().is_relative_to(root):
                continue
            if path.stat().st_mtime < cutoff:
                path.unlink()
                removed += 1
        for directory in sorted(root.rglob("*"), reverse=True):
            if directory.is_dir() and not directory.is_symlink():
                with suppress(OSError):
                    directory.rmdir()
        return removed

    def database_bytes(self) -> int:
        return self.database.path.stat().st_size if self.database.path.exists() else 0

    def vacuum_if_worthwhile(
        self,
        *,
        minimum_free_ratio: float = 0.25,
        backup_completed: bool,
        maintenance_window: bool,
    ) -> bool:
        if not 0 < minimum_free_ratio <= 1:
            raise ValueError("minimum_free_ratio must be in (0, 1]")
        if not backup_completed or not maintenance_window:
            return False
        with self.database.locked() as connection:
            page_count = int(connection.execute("PRAGMA page_count").fetchone()[0])
            free_count = int(connection.execute("PRAGMA freelist_count").fetchone()[0])
            if page_count == 0 or free_count / page_count < minimum_free_ratio:
                return False
            connection.execute("VACUUM")
        return True

    def ensure_capacity(self, maximum_bytes: int) -> None:
        if maximum_bytes < 1:
            raise ValueError("maximum_bytes must be positive")
        size = self.database_bytes()
        if size >= maximum_bytes:
            raise RuntimeError(f"SQLite capacity reached: {size} >= {maximum_bytes}")
