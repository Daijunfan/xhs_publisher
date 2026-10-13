#!/usr/bin/env python3
"""Explicit, idempotent import of the pre-refactor SQLite databases.

The command never deletes or modifies a legacy database.  Telegram media BLOBs
are verified and copied into ``runtime/media/sha256`` before their metadata is
committed to the unified database.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from xhs_local.core.contracts import AttachmentInput, SourceRecord  # noqa: E402
from xhs_local.core.identifiers import stable_record_id  # noqa: E402
from xhs_local.storage.checkpoints import CheckpointRepository  # noqa: E402
from xhs_local.storage.database import Database  # noqa: E402
from xhs_local.storage.records import RecordsRepository  # noqa: E402
from xhs_local.storage.schema import migrate  # noqa: E402


@dataclass(frozen=True, slots=True)
class MigrationReport:
    legacy_posts: int = 0
    legacy_images: int = 0
    legacy_published: int = 0
    legacy_slots: int = 0
    legacy_resource_jobs: int = 0
    imported_records: int = 0
    imported_attachments: int = 0
    imported_published: int = 0
    imported_slots: int = 0
    imported_resource_jobs: int = 0


def _connect_read_only(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise FileNotFoundError(path)
    wal = path.with_name(f"{path.name}-wal")
    if wal.exists() and wal.stat().st_size > 0:
        raise RuntimeError(f"legacy database has a non-empty WAL; stop the old pipeline: {wal}")
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        is not None
    )


def _count(connection: sqlite3.Connection, table: str) -> int:
    return int(connection.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0])


def _parse_datetime(value: str | None) -> datetime:
    if not value:
        return datetime.now(UTC)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_target_names(path: Path | None) -> dict[str, str]:
    if path is None or not path.is_file():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    mapping: dict[str, str] = {}
    for source in raw.get("sources", []):
        if source.get("plugin") != "telegram":
            continue
        for target in source.get("targets", []):
            name = str(target.get("name", "")).strip()
            target_id = str(target.get("id", "")).strip()
            if name and target_id:
                mapping[name] = target_id
    return mapping


def _archive_counts(connection: sqlite3.Connection) -> dict[str, int]:
    required = ("posts", "post_images", "published", "publish_slots")
    missing = [table for table in required if not _table_exists(connection, table)]
    if missing:
        raise RuntimeError(f"legacy archive is missing tables: {', '.join(missing)}")
    return {table: _count(connection, table) for table in required}


def _import_archive(
    legacy: sqlite3.Connection,
    database: Database,
    records: RecordsRepository,
    *,
    target_names: dict[str, str],
    source_id: str,
) -> dict[str, int]:
    counts = _archive_counts(legacy)
    image_query = legacy.execute(
        """
        SELECT channel_id,message_id,image_index,mime_type,file_name,width,height,
               byte_size,sha256,data,downloaded_at
          FROM post_images ORDER BY channel_id,message_id,image_index
        """
    ).fetchall()
    images: dict[tuple[int, int], list[sqlite3.Row]] = {}
    for image in image_query:
        payload = bytes(image["data"])
        digest = hashlib.sha256(payload).hexdigest()
        if digest != image["sha256"] or len(payload) != int(image["byte_size"]):
            raise RuntimeError(
                f"legacy attachment failed checksum: {image['channel_id']}:{image['message_id']}"
            )
        images.setdefault((int(image["channel_id"]), int(image["message_id"])), []).append(image)

    maximums: dict[tuple[str, str], int] = {}
    for row in legacy.execute(
        "SELECT channel_id,message_id,channel_name,posted_at,text,grouped_id "
        "FROM posts ORDER BY channel_id,message_id"
    ):
        channel_id = int(row["channel_id"])
        message_id = int(row["message_id"])
        target_id = target_names.get(row["channel_name"], f"legacy-telegram-{channel_id}")
        record_id = stable_record_id(source_id, target_id, str(message_id))
        attachments = tuple(
            AttachmentInput(
                mime_type=image["mime_type"],
                file_name=image["file_name"],
                data=bytes(image["data"]),
                width=image["width"],
                height=image["height"],
            )
            for image in images.get((channel_id, message_id), [])
        )
        occurred_at = _parse_datetime(row["posted_at"])
        records.upsert(
            SourceRecord(
                record_id=record_id,
                source_id=source_id,
                target_id=target_id,
                plugin_id="telegram",
                external_id=str(message_id),
                content_type="tech_news",
                occurred_at=occurred_at,
                observed_at=occurred_at,
                text=row["text"] or "",
                source_name=row["channel_name"],
                group_id=None if row["grouped_id"] is None else str(row["grouped_id"]),
                payload={
                    "legacy_channel_id": channel_id,
                    "legacy_message_id": message_id,
                },
                attachments=attachments,
            )
        )
        with database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO legacy_record_map(channel_id,message_id,record_id) VALUES(?,?,?)
                ON CONFLICT(channel_id,message_id) DO UPDATE SET record_id=excluded.record_id
                """,
                (channel_id, message_id, record_id),
            )
        key = (source_id, target_id)
        maximums[key] = max(maximums.get(key, 0), message_id)

    checkpoints = CheckpointRepository(database)
    for (checkpoint_source, target_id), maximum_id in maximums.items():
        checkpoints.put(checkpoint_source, target_id, {"max_message_id": maximum_id})

    with database.transaction() as connection:
        for row in legacy.execute(
            "SELECT channel_id,message_id,published_at,status FROM published"
        ):
            mapped = connection.execute(
                "SELECT record_id FROM legacy_record_map WHERE channel_id=? AND message_id=?",
                (row["channel_id"], row["message_id"]),
            ).fetchone()
            record_id = None if mapped is None else mapped["record_id"]
            connection.execute(
                """
                INSERT INTO published(channel_id,message_id,record_id,published_at,status)
                VALUES(?,?,?,?,?)
                ON CONFLICT(channel_id,message_id) DO UPDATE SET
                    record_id=excluded.record_id,published_at=excluded.published_at,
                    status=excluded.status
                """,
                (
                    row["channel_id"],
                    row["message_id"],
                    record_id,
                    row["published_at"],
                    row["status"],
                ),
            )
            if record_id is not None:
                connection.execute(
                    """
                    INSERT INTO publication_marks(
                        record_id,sink,account_id,status,marked_at,detail_json
                    ) VALUES(?,'xiaohongshu','main',?,?,?)
                    ON CONFLICT(record_id,sink,account_id) DO UPDATE SET
                        status=excluded.status,marked_at=excluded.marked_at,
                        detail_json=excluded.detail_json
                    """,
                    (
                        record_id,
                        row["status"],
                        row["published_at"],
                        json.dumps({"legacy": True}, separators=(",", ":")),
                    ),
                )
        for row in legacy.execute("SELECT * FROM publish_slots"):
            connection.execute(
                """
                INSERT INTO publish_slots(
                    slot_start,slot_end,status,started_at,completed_at,publish_invoked_at,
                    title,item_count,details,error
                ) VALUES(?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(slot_start,slot_end) DO UPDATE SET
                    status=excluded.status,started_at=excluded.started_at,
                    completed_at=excluded.completed_at,
                    publish_invoked_at=excluded.publish_invoked_at,title=excluded.title,
                    item_count=excluded.item_count,details=excluded.details,error=excluded.error
                """,
                tuple(row),
            )
        if _table_exists(legacy, "sync_state"):
            connection.executemany(
                """
                INSERT INTO legacy_sync_state(key,value) VALUES(?,?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
                """,
                [tuple(row) for row in legacy.execute("SELECT key,value FROM sync_state")],
            )
    return counts


def _import_resources(legacy: sqlite3.Connection, database: Database) -> int:
    if not _table_exists(legacy, "resource_jobs"):
        raise RuntimeError("legacy resource database is missing resource_jobs")
    rows = legacy.execute("SELECT * FROM resource_jobs").fetchall()
    with database.transaction() as connection:
        for row in rows:
            connection.execute(
                """
                INSERT INTO resource_jobs(
                    folder_name,fingerprint,pdf_names,status,observed_at,started_at,
                    share_link,share_code,publish_invoked_at,completed_at,error
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(folder_name,fingerprint) DO UPDATE SET
                    pdf_names=excluded.pdf_names,status=excluded.status,
                    observed_at=excluded.observed_at,started_at=excluded.started_at,
                    share_link=excluded.share_link,share_code=excluded.share_code,
                    publish_invoked_at=excluded.publish_invoked_at,
                    completed_at=excluded.completed_at,error=excluded.error
                """,
                tuple(row),
            )
    return len(rows)


def migrate_legacy_data(
    *,
    archive_path: str | Path,
    destination_path: str | Path,
    runtime_root: str | Path,
    resources_path: str | Path | None = None,
    sources_config: str | Path | None = None,
    source_id: str = "telegram-main",
) -> MigrationReport:
    archive = Path(archive_path).expanduser().resolve()
    destination = Path(destination_path).expanduser().resolve()
    runtime = Path(runtime_root).expanduser().resolve()
    resource_database = (
        None if resources_path is None else Path(resources_path).expanduser().resolve()
    )
    if destination in {archive, resource_database}:
        raise ValueError("destination database must differ from every legacy database")
    target_names = load_target_names(
        None if sources_config is None else Path(sources_config).expanduser().resolve()
    )
    legacy_archive = _connect_read_only(archive)
    legacy_resources = None if resource_database is None else _connect_read_only(resource_database)
    try:
        with Database(destination) as database:
            migrate(database)
            archive_counts = _archive_counts(legacy_archive)
            resource_count = (
                0 if legacy_resources is None else _count(legacy_resources, "resource_jobs")
            )
            archive_fingerprint = _fingerprint(archive)
            resource_fingerprint = (
                None if resource_database is None else _fingerprint(resource_database)
            )
            with database.locked() as connection:
                archive_import = connection.execute(
                    """
                    SELECT source_fingerprint FROM legacy_imports
                     WHERE import_kind='archive' AND source_path=?
                    """,
                    (str(archive),),
                ).fetchone()
                resource_import = (
                    None
                    if resource_database is None
                    else connection.execute(
                        """
                        SELECT source_fingerprint FROM legacy_imports
                         WHERE import_kind='resources' AND source_path=?
                        """,
                        (str(resource_database),),
                    ).fetchone()
                )
            already_imported = (
                archive_import is not None
                and archive_import["source_fingerprint"] == archive_fingerprint
                and (
                    resource_database is None
                    or (
                        resource_import is not None
                        and resource_import["source_fingerprint"] == resource_fingerprint
                    )
                )
            )
            if already_imported:
                database.quick_check()
                return MigrationReport(
                    legacy_posts=archive_counts["posts"],
                    legacy_images=archive_counts["post_images"],
                    legacy_published=archive_counts["published"],
                    legacy_slots=archive_counts["publish_slots"],
                    legacy_resource_jobs=resource_count,
                    imported_records=archive_counts["posts"],
                    imported_attachments=archive_counts["post_images"],
                    imported_published=archive_counts["published"],
                    imported_slots=archive_counts["publish_slots"],
                    imported_resource_jobs=resource_count,
                )
            repository = RecordsRepository(database, runtime)
            imported_archive_counts = _import_archive(
                legacy_archive,
                database,
                repository,
                target_names=target_names,
                source_id=source_id,
            )
            imported_resource_count = (
                0 if legacy_resources is None else _import_resources(legacy_resources, database)
            )
            if (
                imported_archive_counts != archive_counts
                or imported_resource_count != resource_count
            ):
                raise RuntimeError("legacy source changed while it was being imported")
            database.quick_check()
            with database.locked() as connection:
                imported = {
                    "records": int(
                        connection.execute("SELECT count(*) FROM legacy_record_map").fetchone()[0]
                    ),
                    "attachments": int(
                        connection.execute(
                            """
                        SELECT count(*) FROM attachments a
                         JOIN legacy_record_map m ON m.record_id=a.record_id
                        """
                        ).fetchone()[0]
                    ),
                    "published": int(
                        connection.execute("SELECT count(*) FROM published").fetchone()[0]
                    ),
                    "slots": int(
                        connection.execute("SELECT count(*) FROM publish_slots").fetchone()[0]
                    ),
                    "resources": int(
                        connection.execute("SELECT count(*) FROM resource_jobs").fetchone()[0]
                    ),
                }
            expected = {
                "records": archive_counts["posts"],
                "attachments": archive_counts["post_images"],
                "published": archive_counts["published"],
                "slots": archive_counts["publish_slots"],
                "resources": resource_count,
            }
            if imported != expected:
                raise RuntimeError(
                    f"legacy reconciliation failed: expected={expected}, got={imported}"
                )
            imported_at = datetime.now(UTC).isoformat()
            with database.transaction() as connection:
                connection.execute(
                    """
                    INSERT INTO legacy_imports(
                        import_kind,source_path,source_fingerprint,source_counts_json,imported_at
                    ) VALUES('archive',?,?,?,?)
                    ON CONFLICT(import_kind,source_path) DO UPDATE SET
                        source_fingerprint=excluded.source_fingerprint,
                        source_counts_json=excluded.source_counts_json,
                        imported_at=excluded.imported_at
                    """,
                    (
                        str(archive),
                        archive_fingerprint,
                        json.dumps(archive_counts, sort_keys=True),
                        imported_at,
                    ),
                )
                if resource_database is not None:
                    connection.execute(
                        """
                        INSERT INTO legacy_imports(
                            import_kind,source_path,source_fingerprint,source_counts_json,imported_at
                        ) VALUES('resources',?,?,?,?)
                        ON CONFLICT(import_kind,source_path) DO UPDATE SET
                            source_fingerprint=excluded.source_fingerprint,
                            source_counts_json=excluded.source_counts_json,
                            imported_at=excluded.imported_at
                        """,
                        (
                            str(resource_database),
                            resource_fingerprint,
                            json.dumps({"resource_jobs": resource_count}),
                            imported_at,
                        ),
                    )
            return MigrationReport(
                legacy_posts=expected["records"],
                legacy_images=expected["attachments"],
                legacy_published=expected["published"],
                legacy_slots=expected["slots"],
                legacy_resource_jobs=expected["resources"],
                imported_records=imported["records"],
                imported_attachments=imported["attachments"],
                imported_published=imported["published"],
                imported_slots=imported["slots"],
                imported_resource_jobs=imported["resources"],
            )
    finally:
        legacy_archive.close()
        if legacy_resources is not None:
            legacy_resources.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--resources", type=Path)
    parser.add_argument("--destination", required=True, type=Path)
    parser.add_argument("--runtime-root", required=True, type=Path)
    parser.add_argument("--sources-config", type=Path)
    parser.add_argument("--source-id", default="telegram-main")
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = migrate_legacy_data(
        archive_path=arguments.archive,
        resources_path=arguments.resources,
        destination_path=arguments.destination,
        runtime_root=arguments.runtime_root,
        sources_config=arguments.sources_config,
        source_id=arguments.source_id,
    )
    print(json.dumps(asdict(report), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
