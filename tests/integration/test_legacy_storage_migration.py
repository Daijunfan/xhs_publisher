from __future__ import annotations

import hashlib
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.migrate_legacy_data import migrate_legacy_data  # noqa: E402
from xhs_local.core.identifiers import stable_record_id
from xhs_local.storage.checkpoints import CheckpointRepository
from xhs_local.storage.database import Database
from xhs_local.storage.records import RecordsRepository
from xhs_local.storage.schema import assert_current


def _legacy_archive(path: Path) -> bytes:
    image = b"GIF89a-preserve-exact-bytes"
    database = sqlite3.connect(path)
    database.executescript(
        """
        CREATE TABLE posts (
            channel_id INTEGER NOT NULL, message_id INTEGER NOT NULL,
            channel_name TEXT NOT NULL, posted_at TEXT NOT NULL,
            text TEXT, grouped_id INTEGER,
            PRIMARY KEY(channel_id,message_id)
        );
        CREATE TABLE post_images (
            channel_id INTEGER NOT NULL, message_id INTEGER NOT NULL,
            image_index INTEGER NOT NULL, mime_type TEXT NOT NULL,
            file_name TEXT NOT NULL, width INTEGER, height INTEGER,
            byte_size INTEGER NOT NULL, sha256 TEXT NOT NULL,
            data BLOB NOT NULL, downloaded_at TEXT NOT NULL,
            PRIMARY KEY(channel_id,message_id,image_index)
        );
        CREATE TABLE published (
            channel_id INTEGER NOT NULL, message_id INTEGER NOT NULL,
            published_at TEXT NOT NULL, status TEXT NOT NULL,
            PRIMARY KEY(channel_id,message_id)
        );
        CREATE TABLE publish_slots (
            slot_start TEXT NOT NULL, slot_end TEXT NOT NULL, status TEXT NOT NULL,
            started_at TEXT NOT NULL, completed_at TEXT, publish_invoked_at TEXT,
            title TEXT, item_count INTEGER NOT NULL DEFAULT 0,
            details TEXT, error TEXT, PRIMARY KEY(slot_start,slot_end)
        );
        CREATE TABLE sync_state(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        """
    )
    album = 14_294_722_741_258_525
    database.executemany(
        "INSERT INTO posts VALUES(?,?,?,?,?,?)",
        [
            (
                -1001,
                10,
                "Mapped Channel",
                "2026-08-19T01:00:00+00:00",
                "A detailed legacy technology album caption for migration.",
                album,
            ),
            (
                -1001,
                11,
                "Mapped Channel",
                "2026-08-19T01:00:01+00:00",
                "",
                album,
            ),
        ],
    )
    database.execute(
        "INSERT INTO post_images VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (
            -1001,
            11,
            0,
            "image/gif",
            "motion.gif",
            640,
            480,
            len(image),
            hashlib.sha256(image).hexdigest(),
            image,
            "2026-08-19T01:00:02Z",
        ),
    )
    database.execute(
        "INSERT INTO published VALUES(?,?,?,?)",
        (-1001, 10, "2026-08-19T02:00:00Z", "published"),
    )
    database.execute(
        "INSERT INTO publish_slots VALUES(?,?,?,?,?,?,?,?,?,?)",
        (
            "2026-08-19T00:45:00.000Z",
            "2026-08-19T01:00:00.000Z",
            "published",
            "2026-08-19T01:00:00Z",
            "2026-08-19T01:01:00Z",
            "2026-08-19T01:00:30Z",
            "科技快讯",
            1,
            '{"imageCount":1}',
            None,
        ),
    )
    database.execute("INSERT INTO sync_state VALUES('legacy','proof')")
    database.commit()
    database.close()
    return image


def _legacy_resources(path: Path) -> None:
    database = sqlite3.connect(path)
    database.executescript(
        """
        CREATE TABLE resource_jobs (
            folder_name TEXT NOT NULL, fingerprint TEXT NOT NULL,
            pdf_names TEXT NOT NULL, status TEXT NOT NULL,
            observed_at TEXT NOT NULL, started_at TEXT,
            share_link TEXT, share_code TEXT, publish_invoked_at TEXT,
            completed_at TEXT, error TEXT,
            PRIMARY KEY(folder_name,fingerprint)
        );
        """
    )
    database.execute(
        "INSERT INTO resource_jobs VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (
            "books",
            "f" * 64,
            '["Book.pdf","Book.epub"]',
            "published",
            "2026-08-19T01:00:00Z",
            "2026-08-19T01:01:00Z",
            "https://pan.baidu.com/s/example",
            "a1b2",
            "2026-08-19T01:02:00Z",
            "2026-08-19T01:03:00Z",
            None,
        ),
    )
    database.commit()
    database.close()


def test_legacy_import_is_idempotent_externalizes_media_and_reconciles_every_row(
    tmp_path: Path,
) -> None:
    archive = tmp_path / "archive.sqlite3"
    resources = tmp_path / "resources.sqlite3"
    destination = tmp_path / "runtime" / "app.sqlite3"
    runtime = tmp_path / "runtime"
    sources_config = tmp_path / "sources.yaml"
    image = _legacy_archive(archive)
    _legacy_resources(resources)
    sources_config.write_text(
        """version: 1
sources:
  - id: telegram-main
    plugin: telegram
    targets:
      - id: telegram-mapped
        name: Mapped Channel
""",
        encoding="utf-8",
    )
    archive_before = hashlib.sha256(archive.read_bytes()).hexdigest()
    resources_before = hashlib.sha256(resources.read_bytes()).hexdigest()

    first = migrate_legacy_data(
        archive_path=archive,
        resources_path=resources,
        destination_path=destination,
        runtime_root=runtime,
        sources_config=sources_config,
    )
    second = migrate_legacy_data(
        archive_path=archive,
        resources_path=resources,
        destination_path=destination,
        runtime_root=runtime,
        sources_config=sources_config,
    )

    assert first == second
    assert first.legacy_posts == first.imported_records == 2
    assert first.legacy_images == first.imported_attachments == 1
    assert first.legacy_published == first.imported_published == 1
    assert first.legacy_slots == first.imported_slots == 1
    assert first.legacy_resource_jobs == first.imported_resource_jobs == 1
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == archive_before
    assert hashlib.sha256(resources.read_bytes()).hexdigest() == resources_before

    with Database(destination) as database:
        assert assert_current(database) == 5
        repository = RecordsRepository(database, runtime)
        first_id = stable_record_id("telegram-main", "telegram-mapped", "10")
        second_id = stable_record_id("telegram-main", "telegram-mapped", "11")
        assert repository.get(first_id).record.group_id == "14294722741258525"
        media = repository.get(second_id).attachments[0]
        assert media.absolute_path(runtime).read_bytes() == image
        assert media.relative_path.startswith("media/sha256/")
        assert CheckpointRepository(database).get("telegram-main", "telegram-mapped") == {
            "max_message_id": 11
        }
        with database.locked() as connection:
            assert connection.execute("SELECT count(*) FROM work_items").fetchone()[0] == 0
            assert connection.execute("SELECT count(*) FROM outbox").fetchone()[0] == 0
            assert (
                connection.execute(
                    "SELECT status FROM publication_marks WHERE record_id=?", (first_id,)
                ).fetchone()[0]
                == "published"
            )
            assert (
                connection.execute("SELECT status FROM publish_slots").fetchone()[0] == "published"
            )
            resource = connection.execute(
                "SELECT status,share_link,share_code FROM resource_jobs"
            ).fetchone()
            assert tuple(resource) == (
                "published",
                "https://pan.baidu.com/s/example",
                "a1b2",
            )
            assert (
                connection.execute(
                    "SELECT value FROM legacy_sync_state WHERE key='legacy'"
                ).fetchone()[0]
                == "proof"
            )
