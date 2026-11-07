"""Runtime integration tests with real scheduler/database and in-memory source clients."""
from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from xhs_local.configuration.loader import load_snapshot
from xhs_local.core.contracts import CollectBatch, SourceRecord
from xhs_local.frontier.collector import FrontierCollector, FrontierScheduler, apply_subscription_revision
from xhs_local.frontier.preferences import Preferences, ProductError
from xhs_local.frontier.store import Store
from xhs_local.frontier.subscriptions import Subscriptions
from xhs_local.plugins.contracts import PluginTarget
from xhs_local.storage.checkpoints import CheckpointRepository
from xhs_local.storage.records import RecordsRepository
from xhs_local.storage.schema import open_database


class FakeRegistry:
    def __init__(self):
        self.calls = []

    def prepare(self, source, **_kwargs):
        return SimpleNamespace(
            source=source, context=SimpleNamespace(source_id=source.id, options=source.options),
            targets=tuple(PluginTarget(t.id, t.locator, t.name, t.options) for t in source.targets if t.enabled),
        )

    def create(self, prepared):
        calls = self.calls

        class FakePlugin:
            async def collect(self, request):
                calls.append((request.source_id, request.target.id, request.target.locator))
                # An old publication newly collected must not be discarded by a hard-coded 7-day gate.
                record = SourceRecord(
                    record_id="raw-" + request.target.id,
                    source_id=request.source_id, target_id=request.target.id, plugin_id=prepared.source.plugin,
                    external_id=request.target.id, content_type="tech_news",
                    occurred_at=datetime.now(UTC) - timedelta(days=40), observed_at=datetime.now(UTC),
                    title="Synthetic source story", text="This is a deterministic test record.",
                    source_name=request.target.name,
                )
                return CollectBatch(request.source_id, request.target.id, (record,), {})

            async def close(self):
                return None

        return FakePlugin()


class FrontierRuntimeV2Tests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="frontier-runtime-v2-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        config = self.root / "config"
        config.mkdir()
        values = {
            "app": {"version": 1, "runtime_root": "../runtime", "database_path": "../runtime/app.sqlite3",
                    "queues": {}, "status": {}, "sqlite": {}, "retention": {}, "backup": {}},
            "sources": {"version": 1, "sources": [{"id": "source-x", "plugin": "x", "enabled": True,
                         "poll_seconds": 3600, "options": {"kept_private": "fixture-only"},
                         "targets": [{"id": "base-x", "locator": "base_fixture", "name": "Base", "enabled": True}]}]},
            "publishing": {"version": 1, "filters": {}, "routes": [], "news": {
                "publish_interval_minutes": 30, "night_publish_interval_minutes": 60,
                "night_start_hour": 23, "night_end_hour": 7, "new_post_threshold": 1,
                "max_news_per_note": 10, "first_review_model": "deepseek-v4-pro",
                "second_review_model": "deepseek-v4-flash", "deepseek_key_path": "missing-key",
                "codex_fallback_enabled": False},
                "sinks": {"xiaohongshu": {"enabled": False, "account_id": "fixture", "mode": "mac_safari"}},
                "retry": {"editorial_attempts": 1, "editorial_base_delay_seconds": 1,
                          "transient_attempts": 1, "transient_base_delay_seconds": 1}},
        }
        for name, data in values.items():
            (config / (name + ".yaml")).write_text(json.dumps(data))
        self.store = Store(self.root / "runtime/frontier/events.sqlite3")
        self.manager = Subscriptions(self.store, self.root)

    def test_persisted_source_changes_reach_actual_scheduler_and_preserve_originals(self):
        async def scenario():
            original = load_snapshot(self.root / "config")
            snapshot, revision = self.manager.overlay(original)
            database = open_database(self.root / "runtime/app.sqlite3", apply_migrations=True)
            records = RecordsRepository(database, self.root / "runtime")
            collector = FrontierCollector(records)
            collector.set_sources(snapshot)
            registry = FakeRegistry()

            async def on_batch(*_args):
                return None

            scheduler = FrontierScheduler(snapshot, registry, CheckpointRepository(database), collector, on_batch)

            async def await_collected(target):
                async with asyncio.timeout(2):
                    while not scheduler.status.get(target, {}).get("last_success_at"):
                        await asyncio.sleep(0.005)

            try:
                await scheduler.start()
                self.manager.mark_applied(revision)
                await await_collected("base-x")
                self.assertIsNotNone(records.get("raw-base-x"), "First-ingest retention must not discard old publication dates")
                created = self.manager.create("owner", {"platform": "x", "locator": "new_fixture", "name": "Added"})
                self.assertNotIn(created["id"], scheduler.tasks, "Saving alone must not pretend scheduler has already applied")
                applied = await apply_subscription_revision(self.manager, scheduler, collector, original)
                self.assertEqual(applied, created["revision"])
                await await_collected(created["id"])
                self.assertIsNotNone(records.get("raw-" + created["id"]))
                changed = self.manager.update(created["id"], "owner", {"enabled": False}, created["version"])
                await apply_subscription_revision(self.manager, scheduler, collector, original)
                self.assertNotIn(created["id"], scheduler.tasks)
                self.assertNotIn(("source-x", created["id"]), collector.targets)
                self.assertIsNotNone(records.get("raw-" + created["id"]), "Disabling a source deleted a collected original")
                deleted = self.manager.delete_or_restore(created["id"], "owner", changed["version"])
                await apply_subscription_revision(self.manager, scheduler, collector, original)
                restored = self.manager.delete_or_restore(created["id"], "owner", deleted["version"], restore=True)
                # Restore preserves the previous disabled state; explicitly enabling resumes collection.
                self.manager.update(created["id"], "owner", {"enabled": True}, restored["version"])
                final_revision = await apply_subscription_revision(self.manager, scheduler, collector, original)
                self.assertIn(created["id"], scheduler.tasks)
                self.assertEqual(scheduler.snapshot.sources.sources[0].options, original.sources.sources[0].options)
                with self.store.connect() as c:
                    self.assertEqual(c.execute("SELECT applied_revision FROM subscription_state").fetchone()[0], final_revision)
            finally:
                await scheduler.stop()
                database.close()
        asyncio.run(scenario())

    def test_concurrent_settings_writers_cannot_silently_overwrite_each_other(self):
        barrier = threading.Barrier(2)

        def update(days):
            preferences = Preferences(Store(self.store.path))
            barrier.wait()
            try:
                return preferences.update("owner", {"retention_days": days}, 1)["version"]
            except ProductError as error:
                return error.status

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(update, (2, 30)))
        self.assertEqual(sorted(results), [2, 409])
        self.assertIn(Preferences(self.store).get()["settings"]["retention_days"], {2, 30})

    def test_concurrent_source_creation_keeps_a_single_subscription(self):
        self.manager.ensure_seeded()
        barrier = threading.Barrier(2)

        def create(_value):
            manager = Subscriptions(Store(self.store.path), self.root)
            barrier.wait()
            try:
                return manager.create("owner", {"platform": "x", "locator": "race_fixture"})["id"]
            except ProductError as error:
                return error.status

        with ThreadPoolExecutor(max_workers=2) as pool:
            values = list(pool.map(create, (0, 1)))
        self.assertEqual(values.count(409), 1)
        with self.store.connect() as c:
            self.assertEqual(c.execute("SELECT count(*) FROM subscriptions WHERE canonical_key='race_fixture'").fetchone()[0], 1)

    def test_editing_locator_allows_resubscribing_to_the_previous_locator(self):
        original = self.manager.create("owner", {"platform": "x", "locator": "old_fixture"})
        changed = self.manager.update(original["id"], "owner", {"locator": "new_fixture"}, original["version"])
        replacement = self.manager.create("owner", {"platform": "x", "locator": "old_fixture"})
        self.assertEqual(changed["id"], original["id"])
        self.assertNotEqual(replacement["id"], original["id"])
        rows = {row["id"]: row for row in self.manager.list(initialize=False)["items"]}
        self.assertEqual(rows[original["id"]]["locator"], "new_fixture")
        self.assertEqual(rows[replacement["id"]]["locator"], "old_fixture")

    def test_restore_respects_capacity_without_mutating_the_deleted_source(self):
        original = self.manager.create("owner", {"platform": "x", "locator": "restore_fixture"})
        deleted = self.manager.delete_or_restore(original["id"], "owner", original["version"])
        with self.store.connect() as c:
            c.executemany(
                "INSERT INTO subscriptions(id,parent_id,platform,locator,canonical_key,name,poll_seconds,created_at,updated_at) "
                "SELECT ?,parent_id,platform,locator,canonical_key,name,poll_seconds,created_at,updated_at "
                "FROM subscriptions WHERE id='base-x'",
                [("capacity-" + str(index),) for index in range(999)],
            )
        with self.assertRaises(ProductError) as raised:
            self.manager.delete_or_restore(original["id"], "owner", deleted["version"], restore=True)
        self.assertEqual((raised.exception.status, raised.exception.code), (409, "source_limit"))
        self.assertEqual(self.manager.revision(), deleted["revision"])
        with self.store.connect() as c:
            self.assertIsNotNone(c.execute("SELECT deleted_at FROM subscriptions WHERE id=?", (original["id"],)).fetchone()[0])


class MediaIntegrityV2Tests(unittest.TestCase):
    def test_large_gallery_keeps_every_source_image_and_repairs_previously_truncated_rows(self):
        with tempfile.TemporaryDirectory(prefix="frontier-gallery-v2-") as temporary:
            runtime = Path(temporary)
            source_path = runtime / "app.sqlite3"
            stamp = datetime.now(UTC).isoformat()
            with sqlite3.connect(source_path) as c:
                c.executescript(
                    "CREATE TABLE records(record_id TEXT PRIMARY KEY,content_hash TEXT,plugin_id TEXT,source_name TEXT,"
                    "source_url TEXT,title TEXT,text TEXT,occurred_at TEXT,observed_at TEXT,created_at TEXT,updated_at TEXT,"
                    "payload_json TEXT,content_type TEXT,target_id TEXT,source_id TEXT,external_id TEXT,group_id TEXT);"
                    "CREATE TABLE attachments(record_id TEXT,attachment_id TEXT PRIMARY KEY,attachment_index INTEGER,"
                    "mime_type TEXT,relative_path TEXT,sha256 TEXT);"
                )
                c.execute("INSERT INTO records VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                    "gallery", "fixture-hash", "telegram", "Fixture", None, "Synthetic gallery", "Gallery transport fixture",
                    stamp, stamp, stamp, stamp, "{}", "tech_news", "fixture-target", "fixture-source", "1", None,
                ))
                expected_hashes = []
                for index in range(12):
                    path = runtime / (str(index) + ".png")
                    Image.new("RGB", (1, 1), (index, index * 10, 200)).save(path)
                    digest = hashlib.sha256(path.read_bytes()).hexdigest()
                    expected_hashes.append(digest)
                    c.execute("INSERT INTO attachments VALUES(?,?,?,?,?,?)", (
                        "gallery", "gallery-" + str(index), index, "image/png", path.name, digest,
                    ))
            store = Store(runtime / "derived/events.sqlite3")
            store.import_records(source_path)
            self.assertEqual(len(store.get_raw("gallery")["images"]), 12)
            with store.connect() as c:
                hashes = [row[0] for row in c.execute("SELECT sha256 FROM media_assets ORDER BY position")]
                self.assertEqual(hashes, expected_hashes)
                c.execute("DELETE FROM media_assets WHERE position>=8")
            # Upgrading an already imported candidate must repair the old truncation
            # even if the original record's updated_at has not changed.
            store.set_meta("collector_media_revision", 1)
            self.assertEqual(len(store.get_raw("gallery")["images"]), 8)
            store.import_records(source_path)
            self.assertEqual(len(store.get_raw("gallery")["images"]), 12)


if __name__ == "__main__":
    unittest.main(verbosity=2)
