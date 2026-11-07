"""Independent V2 HTTP/data acceptance tests, using isolated synthetic records only.

Run with the server project's interpreter and PYTHONPATH=src. No production database,
credential, model, collector, publisher, or external service is touched.
These are observable contract tests; application modules are imported from the candidate.
"""
from __future__ import annotations

import base64
import hashlib
import json
import sqlite3
import tempfile
import unittest
import struct
import zlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

from aiohttp.test_utils import TestClient, TestServer

from xhs_local.frontier.models import validate_analysis
from xhs_local.frontier.store import Store
from xhs_local.frontier.web import Settings, create_app


# Valid 1x1 PNG, synthetic file for transport/path tests; never displayed as real news.
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a8O0AAAAASUVORK5CYII="
)


def fixture_png(seed):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    pixel = hashlib.sha256(seed.encode()).digest()[:3]
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(b"\0" + pixel)) + chunk(b"IEND", b"")


class V2Contract(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="frontier-v2-independent-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.runtime = self.root / "runtime"
        (self.runtime / "secrets").mkdir(parents=True)
        (self.runtime / "media").mkdir()
        self.token = "isolated-v2-access-token-not-a-real-credential"
        (self.runtime / "secrets/frontier-access.token").write_text(self.token)
        self.source = self.runtime / "app.sqlite3"
        self.database = self.runtime / "frontier/events.sqlite3"
        self.store = Store(self.database)
        self.asset_data = {}
        with sqlite3.connect(self.source) as connection:
            connection.executescript(
                """
                CREATE TABLE records(
                    record_id TEXT PRIMARY KEY,source_id TEXT,target_id TEXT,
                    content_hash TEXT,plugin_id TEXT,source_name TEXT,source_url TEXT,
                    title TEXT,text TEXT,occurred_at TEXT,observed_at TEXT,created_at TEXT,
                    payload_json TEXT,content_type TEXT,updated_at TEXT,external_id TEXT,group_id TEXT);
                CREATE TABLE attachments(
                    record_id TEXT,attachment_id TEXT PRIMARY KEY,attachment_index INTEGER,
                    mime_type TEXT,relative_path TEXT,width INTEGER,height INTEGER,sha256 TEXT);
                """
            )
        self.write_config()
        self.settings = Settings(root=self.root, enrich=False)
        self.client = TestClient(TestServer(create_app(self.settings, self.store, background=False)))
        self.addAsyncCleanup(self.client.close)
        await self.client.start_server()
        response = await self.client.post("/api/auth/session", json={"token": self.token})
        self.assertEqual(response.status, 200, await response.text())
        self.csrf = (await response.json())["csrf_token"]
        self.client.session.headers.update({"X-CSRF-Token": self.csrf})

    async def asyncTearDown(self):
        await self.client.close()
        self.temporary.cleanup()

    def write_config(self):
        config = self.root / "config"
        config.mkdir()
        values = {
            "app": {
                "version": 1, "runtime_root": "../runtime", "database_path": "../runtime/app.sqlite3",
                "queues": {}, "status": {}, "sqlite": {}, "retention": {}, "backup": {},
            },
            "sources": {
                "version": 1,
                "sources": [
                    {
                        "id": "audit-" + platform, "plugin": platform, "enabled": True,
                        "poll_seconds": 300,
                        "options": {"fixture_private_marker": "DO_NOT_RETURN_PRIVATE_OPTIONS"},
                        "targets": [{
                            "id": "audit-" + platform + "-existing", "locator": locator,
                            "name": platform + " existing fixture", "enabled": True,
                        }],
                    }
                    for platform, locator in [
                        ("telegram", "https://t.me/audit_existing"),
                        ("x", "audit_existing"),
                        ("youtube", "https://www.youtube.com/@audit_existing"),
                    ]
                ],
            },
            "publishing": {
                "version": 1, "filters": {}, "routes": [],
                "news": {
                    "publish_interval_minutes": 30, "night_publish_interval_minutes": 60,
                    "night_start_hour": 23, "night_end_hour": 7, "new_post_threshold": 1,
                    "max_news_per_note": 10, "first_review_model": "deepseek-v4-pro",
                    "second_review_model": "deepseek-v4-flash", "deepseek_key_path": "missing-key",
                    "codex_fallback_enabled": False,
                },
                "sinks": {"xiaohongshu": {"enabled": False, "account_id": "fixture", "mode": "mac_safari"}},
                "retry": {"editorial_attempts": 1, "editorial_base_delay_seconds": 1,
                          "transient_attempts": 1, "transient_base_delay_seconds": 1},
            },
        }
        # JSON is a strict subset of YAML, so no extra fixture YAML dependency is required.
        for name, value in values.items():
            (config / (name + ".yaml")).write_text(json.dumps(value))

    def event(self, key, *, age_hours=1, platform="telegram", publish_age_hours=None,
              observed_age_hours=None, score=60, image_count=0, avatar_index=None,
              finalize=True, content_type="tech_news"):
        now = datetime.now(UTC)
        created = (now - timedelta(hours=age_hours)).isoformat()
        published = (now - timedelta(hours=age_hours if publish_age_hours is None else publish_age_hours)).isoformat()
        observed = (now - timedelta(hours=age_hours if observed_age_hours is None else observed_age_hours)).isoformat()
        title = "Isolated audit event " + key
        text = "Synthetic independent audit record " + key + ". No event date is asserted."
        digest = hashlib.sha256((title + "\n" + text).encode()).hexdigest()
        payload = {} if avatar_index is None else {"avatar_attachment_index": avatar_index}
        with sqlite3.connect(self.source) as connection:
            connection.execute(
                "INSERT INTO records(record_id,source_id,target_id,content_hash,plugin_id,source_name,source_url,"
                "title,text,occurred_at,observed_at,created_at,payload_json,content_type,updated_at,external_id) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (key, "audit-" + platform, "audit-" + platform + "-existing", digest, platform,
                 "Independent fixture", "https://example.test/" + key, title, text,
                 published, observed, created, json.dumps(payload), content_type, now.isoformat(), key),
            )
            for index in range(image_count):
                attachment_id = (key + "-image-" + str(index)).replace("_", "-")
                relative = "media/" + attachment_id + ".png"
                data = fixture_png(key + ":" + str(index))
                self.asset_data.setdefault(key, []).append(data)
                (self.runtime / relative).write_bytes(data)
                connection.execute("INSERT INTO attachments VALUES(?,?,?,?,?,?,?,?)",
                                   (key, attachment_id, index, "image/png", relative, 1, 1, hashlib.sha256(data).hexdigest()))
        if not finalize:
            return key
        return self.complete(key, score=score)

    def complete(self, key, *, score=60):
        self.store.import_records(self.source)
        rows = self.store.claim(200)
        raw = next(row for row in rows if row["record_id"] == key)
        self.assertEqual(len(rows), 1, "Each fixture must leave no unrelated claimed record")
        title, text = raw["title"], raw["text"]
        analysis = validate_analysis({
            "is_event": True, "title": title, "summary": text, "category": "science", "tags": ["audit"],
            "score_components": {name: score for name in ("impact", "scope", "novelty", "urgency")},
            "score_reason": "Synthetic audit score.", "event_time_start": None, "event_time_end": None,
            "event_time_precision": "unknown", "event_time_status": "unknown", "event_time_evidence": "",
            "event_timezone": None, "locations": [], "location_status": "unknown",
        }, raw)
        self.store.complete(raw, analysis)
        with self.store.connect() as connection:
            event_id = connection.execute("SELECT event_id FROM raw_records WHERE record_id=?", (key,)).fetchone()[0]
        self.assertIsNotNone(event_id)
        return event_id

    async def get(self, route):
        response = await self.client.get(route)
        self.assertEqual(response.status, 200, await response.text())
        return await response.json()

    async def patch_settings(self, patch):
        current = await self.get("/api/settings")
        response = await self.client.put("/api/settings", json={"settings": patch, "version": current["version"]})
        self.assertEqual(response.status, 200, await response.text())
        return await response.json()

    async def ids(self, query=""):
        value = await self.get("/api/events?limit=200" + ("&" + query if query else ""))
        return {item["id"] for item in value["items"]}

    async def mark(self, event_id, value):
        response = await self.client.put("/api/events/" + event_id + "/read", json={"read": value})
        self.assertEqual(response.status, 200, await response.text())
        return await response.json()

    async def test_settings_reject_invalid_and_stale_writes_without_partial_changes(self):
        initial = await self.get("/api/settings")
        self.assertIn("settings", initial)
        for patch in ({"hide_read": "false"}, {"retention_days": -1}, {"retention_days": 2.5},
                      {"retention_days": True}, {"retention_days": 3651}, {"default_view": "made-up"},
                      {"density": "made-up"}, {"unrecognized_setting": True}):
            response = await self.client.put("/api/settings", json={"settings": patch, "version": initial["version"]})
            self.assertEqual(response.status, 422, (patch, await response.text()))
            self.assertEqual(await self.get("/api/settings"), initial, "Invalid patch modified values or version")
        changed = await self.patch_settings({"hide_read": True, "retention_days": 2, "auto_mark_read": False})
        self.assertEqual(changed["settings"]["retention_days"], 2)
        self.assertTrue(changed["settings"]["hide_read"])
        response = await self.client.put("/api/settings", json={"settings": {"retention_days": 30}, "version": initial["version"]})
        self.assertEqual(response.status, 409, await response.text())
        self.assertEqual((await self.get("/api/settings"))["settings"], changed["settings"])

    async def test_read_state_hidden_filter_explicit_override_and_batch_atomicity(self):
        one, two = self.event("read-one"), self.event("read-two", platform="x")
        self.assertFalse((await self.get("/api/events/" + one))["read"])
        await self.mark(one, True)
        first_read_at = (await self.get("/api/events/" + one))["read_at"]
        self.assertTrue(first_read_at)
        await self.mark(one, True)
        self.assertEqual((await self.get("/api/events/" + one))["read_at"], first_read_at, "Idempotent read resets original read time")
        await self.patch_settings({"hide_read": True})
        self.assertEqual(await self.ids(), {two})
        self.assertEqual(await self.ids("read=all"), {one, two})
        self.assertEqual(await self.ids("read=read"), {one})
        self.assertEqual(await self.ids("read=unread"), {two})
        response = await self.client.post("/api/events/read", json={"ids": [two, "missing-event-id"], "read": True})
        self.assertIn(response.status, {404, 422}, await response.text())
        self.assertFalse((await self.get("/api/events/" + two))["read"], "Batch partially wrote before discovering missing ID")
        response = await self.client.post("/api/events/read", json={"ids": [one, two], "read": False})
        self.assertEqual(response.status, 200, await response.text())
        self.assertEqual(await self.ids("read=unread"), {one, two})
        for item_id in (one, two):
            item = await self.get("/api/events/" + item_id)
            self.assertFalse(item["read"])
            self.assertIsNone(item["read_at"])
        for bad in ({"ids": [], "read": True}, {"ids": [one], "read": "false"},
                    {"ids": ["overflow-" + str(i) for i in range(201)], "read": True}):
            response = await self.client.post("/api/events/read", json=bad)
            self.assertIn(response.status, {400, 413, 422}, await response.text())

    async def test_read_and_settings_survive_new_http_session_and_store_reopen(self):
        event_id = self.event("persist")
        saved = await self.patch_settings({"hide_read": True, "auto_mark_read": False, "retention_days": 2})
        await self.mark(event_id, True)
        await self.client.close()
        self.store = Store(self.database)
        self.client = TestClient(TestServer(create_app(self.settings, self.store, background=False)))
        self.addAsyncCleanup(self.client.close)
        await self.client.start_server()
        response = await self.client.post("/api/auth/session", json={"token": self.token})
        self.assertEqual(response.status, 200)
        item = await self.get("/api/events/" + event_id)
        self.assertTrue(item["read"])
        reopened = await self.get("/api/settings")
        settings = reopened["settings"]
        self.assertEqual((settings["hide_read"], settings["auto_mark_read"], settings["retention_days"]), (True, False, 2))
        self.assertEqual(reopened["version"], saved["version"])
        self.assertEqual(await self.ids(), set())
        for endpoint in ("/api/events", "/api/inbox", "/api/export"):
            policy = (await self.get(endpoint + "?read=all"))["policy"]
            self.assertEqual(policy["settings_version"], saved["version"], endpoint)
            self.assertEqual(policy["retention_days"], 2, endpoint)
            self.assertTrue(policy["hide_read"], endpoint)
            self.assertEqual(policy["effective_read"], "all", endpoint)

    async def test_rolling_retention_uses_first_collection_and_is_not_refreshed_by_polling(self):
        inside = self.event("inside", age_hours=47.9, publish_age_hours=24 * 365)
        outside = self.event("outside", age_hours=48.1, observed_age_hours=0.1, publish_age_hours=1)
        ancient = self.event("ancient", age_hours=24 * 40, observed_age_hours=0.1)
        saved = await self.patch_settings({"retention_days": 2, "retention_basis": "first_ingested", "hide_read": False})
        self.assertEqual(await self.ids(), {inside}, "Retention is not a rolling first-ingest window")
        self.assertEqual(await self.ids("scope=archive"), {outside, ancient})
        self.assertEqual(await self.ids("scope=all"), {inside, outside, ancient})
        self.assertEqual(await self.ids("window_days=0"), {inside, outside, ancient})
        for endpoint in ("/api/events", "/api/inbox", "/api/export"):
            override = await self.get(endpoint + "?read=all&window_days=0")
            self.assertEqual(override["policy"]["retention_days"], 0, endpoint)
            self.assertEqual(override["policy"]["settings_version"], saved["version"], endpoint)
            self.assertEqual(await self.get("/api/settings"), saved, "Temporary window changed saved policy/version: " + endpoint)
            active = await self.get(endpoint + "?read=all")
            self.assertEqual(active["policy"]["retention_days"], 2, endpoint)
            self.assertEqual(active["policy"]["settings_version"], saved["version"], endpoint)
        for item_id in (inside, outside, ancient):
            item = await self.get("/api/events/" + item_id)
            self.assertIsNone(item["event_time_start"], "Unknown event date was fabricated for retention")
            self.assertTrue(item["first_ingested_at"])
            self.assertEqual(item["archived"], item_id != inside)
        previous = (await self.get("/api/events/" + outside))["first_ingested_at"]
        with sqlite3.connect(self.source) as connection:
            timestamp = datetime.now(UTC).isoformat()
            connection.execute("UPDATE records SET observed_at=?,updated_at=? WHERE record_id='outside'", (timestamp, timestamp))
        self.store.import_records(self.source)
        self.assertEqual((await self.get("/api/events/" + outside))["first_ingested_at"], previous)
        self.assertEqual(await self.ids(), {inside}, "A repeated observation resurfaced an archived old event")
        exported = await self.get("/api/export?scope=active&read=all")
        self.assertEqual({item["id"] for item in exported["items"]}, {inside}, "Export ignored the persisted window")

    async def test_publication_window_bookmark_exception_and_archive_are_explicit(self):
        recent_ingest_old_post = self.event("backfilled", age_hours=1, publish_age_hours=24 * 365)
        old_ingest_recent_post = self.event("corrected-post", age_hours=24 * 10, publish_age_hours=1)
        old_both = self.event("old-saved", age_hours=24 * 10, publish_age_hours=24 * 20)
        await self.patch_settings({"retention_days": 2, "retention_basis": "published", "retain_bookmarks": False, "hide_read": False})
        self.assertEqual(await self.ids(), {old_ingest_recent_post}, "Published window incorrectly includes newly backfilled old posts")
        self.assertEqual(await self.ids("scope=archive"), {recent_ingest_old_post, old_both})
        item = await self.get("/api/events/" + recent_ingest_old_post)
        self.assertEqual(item["retention_at"], item["source_published_at"])
        response = await self.client.put("/api/events/" + old_both + "/bookmark", json={"bookmarked": True})
        self.assertEqual(response.status, 200)
        self.assertNotIn(old_both, await self.ids(), "Disabled bookmark exception was ignored")
        self.assertIn(old_both, await self.ids("bookmarked=1&scope=all"), "Window removed the permanent bookmark")
        await self.patch_settings({"retain_bookmarks": True})
        self.assertEqual(await self.ids(), {old_ingest_recent_post, old_both})
        self.assertEqual(await self.ids("scope=archive"), {recent_ingest_old_post})
        await self.mark(old_both, True)
        self.assertEqual(await self.ids("bookmarked=1&read=unread&scope=all"), set(), "Explicit unread filter was ignored for bookmarks")

    async def test_inbox_fresh_raw_is_readable_while_model_budget_is_exhausted(self):
        self.assertTrue(self.store.reserve_budget(2000, 2000))
        self.assertFalse(self.store.reserve_budget(1, 2000))
        before = self.store.stats()["usage"]
        tg = self.event("inbox-tg", platform="telegram", image_count=2, finalize=False)
        x = self.event("inbox-x", platform="x", image_count=2, avatar_index=0, finalize=False)
        yt = self.event("inbox-yt", platform="youtube", image_count=1, finalize=False, content_type="video_pending")
        # No importer or model method was invoked after the collector writes these rows.
        value = await self.get("/api/inbox?limit=200&read=all")
        rows = {item["id"]: item for item in value["items"]}
        self.assertEqual(set(rows), {tg, x, yt}, "New raw records require model progress before becoming readable")
        for raw_id, platform in [(tg, "telegram"), (x, "x"), (yt, "youtube")]:
            item = rows[raw_id]
            self.assertEqual(item["kind"], "source_record")
            self.assertEqual(item["platform"], platform)
            self.assertTrue(item["source_published_at"])
            self.assertTrue(item["first_ingested_at"])
            self.assertTrue(item["images"])
            self.assertIsNone(item.get("event_id"))
            self.assertIsNone(item.get("importance"), "Pending raw record received an invented importance score")
            self.assertIsNone(item.get("event_time_start"), "Source publication date masquerades as event occurrence time")
            detail = await self.get("/api/inbox/" + raw_id)
            self.assertIn("Synthetic independent audit record", detail["text"])
            for url in detail["images"]:
                response = await self.client.get(url)
                self.assertEqual(response.status, 200)
                self.assertIn(await response.read(), self.asset_data[raw_id])
        self.assertEqual(len(rows[x]["images"]), 1, "Avatar was included in raw inbox content images")
        self.assertEqual(rows[yt]["state"], "video_processing", "Incomplete video presented as already transcribed news")
        filtered = await self.get("/api/inbox?source=x&q=inbox-x&read=all")
        self.assertEqual({item["id"] for item in filtered["items"]}, {x})
        self.assertEqual(self.store.stats()["usage"], before, "Reading the raw inbox consumed model budget")

    async def test_raw_read_state_survives_analysis_and_event_changes_sync_back(self):
        raw_id = self.event("inbox-read-transfer", finalize=False)
        original = await self.get("/api/inbox/" + raw_id)
        self.assertFalse(original["read"])
        response = await self.client.put("/api/inbox/" + raw_id + "/read", json={"read": True})
        self.assertEqual(response.status, 200, await response.text())
        raw_read = await self.get("/api/inbox/" + raw_id)
        self.assertTrue(raw_read["read"])
        self.assertTrue(raw_read["read_at"])
        event_id = self.complete(raw_id)
        event = await self.get("/api/events/" + event_id)
        self.assertTrue(event["read"], "Already-read raw content became unread when analysis finished")
        mapped = await self.get("/api/inbox/" + raw_id)
        self.assertEqual(mapped["event_id"], event_id)
        self.assertTrue(mapped["read"])
        await self.mark(event_id, False)
        self.assertFalse((await self.get("/api/inbox/" + raw_id))["read"], "Event unread did not propagate to linked original")
        response = await self.client.put("/api/inbox/" + raw_id + "/read", json={"read": True})
        self.assertEqual(response.status, 200)
        self.assertTrue((await self.get("/api/events/" + event_id))["read"])
        await self.patch_settings({"hide_read": True})
        self.assertEqual((await self.get("/api/inbox"))["total"], 0)
        self.assertEqual(await self.ids(), set())
        self.assertEqual((await self.get("/api/inbox?read=read"))["total"], 1)

    async def test_later_exact_duplicate_inherits_existing_event_read_state(self):
        event_id = self.event("already-read-original")
        await self.mark(event_id, True)
        with sqlite3.connect(self.source) as connection:
            connection.row_factory = sqlite3.Row
            data = dict(connection.execute("SELECT * FROM records WHERE record_id='already-read-original'").fetchone())
            data.update(record_id="later-copy", plugin_id="x", source_id="audit-x", target_id="audit-x-existing",
                        source_url="https://example.test/later-copy", updated_at=datetime.now(UTC).isoformat())
            columns = list(data)
            connection.execute("INSERT INTO records(" + ",".join(columns) + ") VALUES(" + ",".join("?" for _ in columns) + ")", [data[key] for key in columns])
        self.store.import_records(self.source)
        duplicate = await self.get("/api/inbox/later-copy")
        self.assertEqual(duplicate["event_id"], event_id, "Fixture did not exercise exact duplicate import")
        self.assertTrue(duplicate["read"], "A later copy of an already-read event reappeared as unread in the inbox")

    async def test_late_telegram_album_piece_updates_existing_first_message(self):
        first_id = self.event("album-first", image_count=1, finalize=False)
        with sqlite3.connect(self.source) as connection:
            connection.execute("UPDATE records SET group_id='album-42' WHERE record_id=?", (first_id,))
        first_event = self.complete(first_id)
        self.assertEqual(len((await self.get("/api/events/" + first_event))["images"]), 1)
        second_id = self.event("album-second", image_count=1, finalize=False)
        with sqlite3.connect(self.source) as connection:
            connection.execute("UPDATE records SET group_id='album-42' WHERE record_id=?", (second_id,))
        # The original first source row is intentionally untouched: album parts can arrive later.
        self.store.import_records(self.source)
        first_detail = await self.get("/api/events/" + first_event)
        self.assertEqual(len(first_detail["images"]), 2, "Late album image is visible only on its captionless companion, not the original news")
        # Same group id in a different target must never leak images across channels.
        unrelated = self.event("album-other-channel", image_count=1, finalize=False)
        with sqlite3.connect(self.source) as connection:
            connection.execute("UPDATE records SET group_id='album-42',target_id='other-channel' WHERE record_id=?", (unrelated,))
        self.store.import_records(self.source)
        self.assertEqual(len((await self.get("/api/events/" + first_event))["images"]), 2, "Telegram album grouped across distinct channels")

    async def test_unknown_dates_keep_membership_media_excludes_avatar_and_handles_late_attachment(self):
        event_id = self.event("media", image_count=3, avatar_index=0, platform="x")
        item = await self.get("/api/events/" + event_id)
        self.assertEqual(len(item["images"]), 2, "Profile avatar leaked into content media or real content was lost")
        delivered = []
        for url in item["images"]:
            self.assertTrue(url.startswith("/api/media/"), "Media must use the authenticated same-origin reader")
            response = await self.client.get(url)
            self.assertEqual(response.status, 200)
            self.assertEqual(response.headers.get("Content-Type"), "image/png")
            delivered.append(await response.read())
        self.assertCountEqual(delivered, self.asset_data["media"][1:])
        before = self.store.stats()["enrichment"]
        late_file = self.runtime / "media/late.png"
        late_png = fixture_png("late-content-image")
        late_file.write_bytes(late_png)
        with sqlite3.connect(self.source) as connection:
            connection.execute("INSERT INTO attachments VALUES(?,?,?,?,?,?,?,?)", ("media", "late-image", 3, "image/png", "media/late.png", 1, 1, hashlib.sha256(late_png).hexdigest()))
            connection.execute("UPDATE records SET updated_at=? WHERE record_id='media'", (datetime.now(UTC).isoformat(),))
        self.store.import_records(self.source)
        item = await self.get("/api/events/" + event_id)
        self.assertEqual(len(item["images"]), 3, "Late media was not attached to the already analysed event")
        self.assertEqual(self.store.stats()["enrichment"], before, "Media-only refresh enqueued a model reanalysis")
        self.assertIsNone(item["event_time_start"])
        self.assertEqual(item["event_time_status"], "unknown")

    async def test_source_image_order_preserves_original_attachment_sequence(self):
        event_id = self.event("ordered-images", image_count=4, avatar_index=0, platform="telegram")
        expected = self.asset_data["ordered-images"][1:]
        item = await self.get("/api/events/" + event_id)
        actual = []
        for url in item["images"]:
            response = await self.client.get(url)
            self.assertEqual(response.status, 200)
            actual.append(await response.read())
        self.assertEqual(actual, expected, "Content image sequence was reordered by hash/id rather than original source order")

    async def test_merged_sources_deduplicate_equal_image_bytes_across_distinct_paths(self):
        event_id = self.event("merge-primary", image_count=2)
        first_images = list(self.asset_data["merge-primary"])
        third = fixture_png("third-distinct-image")
        with sqlite3.connect(self.source) as connection:
            connection.row_factory = sqlite3.Row
            data = dict(connection.execute("SELECT * FROM records WHERE record_id='merge-primary'").fetchone())
            data.update(record_id="merge-secondary", plugin_id="x", source_id="audit-x", target_id="audit-x-existing",
                        source_url="https://example.test/merge-secondary", occurred_at=datetime.now(UTC).isoformat(), updated_at=datetime.now(UTC).isoformat())
            columns = list(data)
            connection.execute("INSERT INTO records(" + ",".join(columns) + ") VALUES(" + ",".join("?" for _ in columns) + ")", [data[key] for key in columns])
            for index, content in enumerate([first_images[0], third]):
                relative = f"media/other-source-{index}.png"
                (self.runtime / relative).write_bytes(content)
                connection.execute("INSERT INTO attachments VALUES(?,?,?,?,?,?,?,?)", ("merge-secondary", f"secondary-image-{index}", index, "image/png", relative, 1, 1, hashlib.sha256(content).hexdigest()))
        self.store.import_records(self.source)
        merged = await self.get("/api/events/" + event_id)
        self.assertEqual(len(merged["sources"]), 2, "Fixture did not exercise multiple linked sources")
        self.assertEqual(len(merged["images"]), 3, "Byte-identical source images at different file paths were shown repeatedly")
        actual = []
        for url in merged["images"]:
            response = await self.client.get(url)
            self.assertEqual(response.status, 200)
            actual.append(await response.read())
        self.assertEqual(actual, first_images + [third], "Merged gallery changed primary source image order")

    async def test_source_crud_normalization_versions_and_private_options(self):
        initial = await self.get("/api/sources?include_deleted=1")
        self.assertEqual(len(initial["items"]), 3)
        self.assertEqual({row["platform"] for row in initial["items"]}, {"telegram", "x", "youtube"})
        self.assertNotIn("DO_NOT_RETURN_PRIVATE_OPTIONS", json.dumps(initial))
        self.assertTrue(all("options" not in row for row in initial["items"]))
        for platform, locator, duplicate in [
            ("telegram", "https://t.me/Audit_New", "@audit_new"),
            ("x", "https://twitter.com/Audit_New", "@audit_new"),
            ("youtube", "https://www.youtube.com/@Audit_New/videos", "@audit_new"),
        ]:
            response = await self.client.post("/api/sources", json={"platform": platform, "locator": locator, "enabled": False, "poll_seconds": 7200})
            self.assertIn(response.status, {200, 201}, await response.text())
            created = await response.json()
            source_id = created["id"]
            rows = (await self.get("/api/sources?include_deleted=1"))["items"]
            row = next(item for item in rows if item["id"] == source_id)
            self.assertFalse(row["enabled"])
            self.assertTrue(row["name"], "Omitted optional source name was not derived")
            duplicate_response = await self.client.post("/api/sources", json={"platform": platform, "locator": duplicate, "enabled": False, "poll_seconds": 7200})
            self.assertEqual(duplicate_response.status, 409, await duplicate_response.text())
            response = await self.client.patch("/api/sources/" + source_id, json={"name": "Updated audit name", "enabled": True, "version": row["version"]})
            self.assertEqual(response.status, 200, await response.text())
            changed = await response.json()
            response = await self.client.patch("/api/sources/" + source_id, json={"name": "Stale write", "version": row["version"]})
            self.assertEqual(response.status, 409)
            response = await self.client.delete("/api/sources/" + source_id, json={"version": changed["version"]})
            self.assertEqual(response.status, 200, await response.text())
            deleted = await response.json()
            self.assertNotIn(source_id, {item["id"] for item in (await self.get("/api/sources"))["items"]})
            row = next(item for item in (await self.get("/api/sources?include_deleted=1"))["items"] if item["id"] == source_id)
            self.assertTrue(row["deleted_at"])
            self.assertFalse(row["enabled"])
            response = await self.client.post("/api/sources/" + source_id + "/restore", json={"version": deleted["version"]})
            self.assertEqual(response.status, 200, await response.text())
            restored = next(item for item in (await self.get("/api/sources"))["items"] if item["id"] == source_id)
            self.assertTrue(restored["enabled"])
            self.assertEqual(restored["name"], "Updated audit name")
        final = await self.get("/api/sources")
        self.assertEqual(len(final["items"]), 6)
        self.assertGreater(final["revision"], final["applied_revision"], "Unapplied config falsely reports live collection")
        self.assertNotIn("DO_NOT_RETURN_PRIVATE_OPTIONS", json.dumps(final))

    async def test_source_seed_preserves_legacy_duplicates_and_rejects_unsafe_inputs(self):
        file = self.root / "config/sources.yaml"
        content = json.loads(file.read_text())
        x = next(row for row in content["sources"] if row["plugin"] == "x")
        x["targets"].append({**x["targets"][0], "id": "audit-x-existing-alias", "name": "Existing alias must survive"})
        file.write_text(json.dumps(content))
        existing = await self.get("/api/sources")
        self.assertEqual(len(existing["items"]), 4, "Migration collapsed an existing user target with a shared canonical account")
        before = existing["revision"]
        for platform, locator in [
            ("x", "https://x.com.evil.example/account"),
            ("x", "https://x.com/account/status/123"),
            ("x", "file:///etc/passwd"),
            ("x", "https://user:pass@x.com/account"),
            ("youtube", "https://youtube.com/watch?v=abcdefghijk"),
            ("telegram", "https://t.me/example/123"),
            ("telegram", "https://t.me/+invite-secret"),
            ("mastodon", "https://example.com/user"),
        ]:
            response = await self.client.post("/api/sources", json={"platform": platform, "locator": locator, "enabled": False})
            self.assertEqual(response.status, 422, (platform, locator, await response.text()))
        for bad in ({"enabled": "false"}, {"poll_seconds": True}, {"poll_seconds": -5}, {"poll_seconds": 86401}, {"options": {"api_key": "should-not-be-accepted"}}):
            response = await self.client.post("/api/sources", json={"platform": "x", "locator": "new_audit", **bad})
            self.assertEqual(response.status, 422, await response.text())
        self.assertEqual((await self.get("/api/sources"))["revision"], before)

    async def test_media_traversal_and_new_mutations_require_authentication_and_csrf(self):
        event_id = self.event("protected")
        outside = self.root / "outside.png"
        outside.write_bytes(PNG)
        with sqlite3.connect(self.source) as connection:
            connection.execute("INSERT INTO attachments VALUES(?,?,?,?,?,?,?,?)", ("protected", "outside-image", 0, "image/png", "../outside.png", 1, 1, hashlib.sha256(PNG).hexdigest()))
        response = await self.client.get("/api/media/outside-image")
        self.assertIn(response.status, {403, 404})
        current = await self.get("/api/settings")
        self.client.session.headers.pop("X-CSRF-Token", None)
        for route, body, method in [
            ("/api/settings", {"settings": {"hide_read": True}, "version": current["version"]}, "put"),
            ("/api/events/" + event_id + "/read", {"read": True}, "put"),
            ("/api/events/read", {"ids": [event_id], "read": True}, "post"),
        ]:
            response = await getattr(self.client, method)(route, json=body)
            self.assertEqual(response.status, 403, (route, await response.text()))
        self.assertFalse((await self.get("/api/events/" + event_id))["read"])
        self.assertEqual(await self.get("/api/settings"), current)
        self.client.session.headers.update({"X-CSRF-Token": self.csrf, "Origin": "https://evil.example"})
        response = await self.client.put("/api/events/" + event_id + "/read", json={"read": True})
        self.assertEqual(response.status, 403)
        self.client.session.headers.pop("Origin", None)

    async def test_media_volume_does_not_starve_control_api_and_private_cache_keeps_auth(self):
        event_id = self.event("media-burst", image_count=1)
        event = await self.get("/api/events/" + event_id)
        image = event["images"][0]
        first = await self.client.get(image)
        self.assertEqual(first.status, 200, await first.text() if first.status != 200 else "")
        self.assertEqual(await first.read(), self.asset_data["media-burst"][0])
        cache = first.headers.get("Cache-Control", "")
        self.assertIn("private", cache)
        self.assertIn("max-age=", cache)
        self.assertNotIn("no-store", cache)
        self.assertIn("cookie", first.headers.get("Vary", "").lower())
        etag = first.headers.get("ETag")
        self.assertTrue(etag, "Hash-addressed media should have conditional-cache validation")
        for index in range(605):
            response = await self.client.get(image)
            self.assertEqual(response.status, 200, (index, await response.text() if response.status != 200 else ""))
            await response.read()
        self.assertIn("settings", await self.get("/api/settings"))
        self.assertEqual(len((await self.get("/api/sources"))["items"]), 3)
        write = await self.client.put("/api/events/" + event_id + "/read", json={"read": True})
        self.assertEqual(write.status, 200, await write.text())
        self.assertTrue((await self.get("/api/events/" + event_id))["read"])
        conditional = await self.client.get(image, headers={"If-None-Match": etag})
        self.assertEqual(conditional.status, 304)
        self.assertEqual(await conditional.read(), b"")
        self.assertIn("private", conditional.headers.get("Cache-Control", ""))
        self.assertIn("cookie", conditional.headers.get("Vary", "").lower())
        logout = await self.client.post("/api/auth/logout")
        self.assertEqual(logout.status, 200)
        # A previous ETag cannot turn an unauthenticated request into a 304 bypass.
        denied = await self.client.get(image, headers={"If-None-Match": etag})
        self.assertEqual(denied.status, 401, await denied.text())
        self.assertIn("no-store", denied.headers.get("Cache-Control", ""))

    async def test_control_api_retains_own_limit_and_retry_after_without_blocking_media_or_write(self):
        event_id = self.event("read-bucket", image_count=1)
        image = (await self.get("/api/events/" + event_id))["images"][0]
        # A fresh genuine session gives an exact API-read counter, no monkeypatch.
        login = await self.client.post("/api/auth/session", json={"token": self.token})
        self.assertEqual(login.status, 200)
        self.csrf = (await login.json())["csrf_token"]
        self.client.session.headers.update({"X-CSRF-Token": self.csrf})
        for index in range(600):
            response = await self.client.get("/api/settings")
            self.assertEqual(response.status, 200, (index, await response.text() if response.status != 200 else ""))
            await response.read()
        limited = await self.client.get("/api/settings")
        self.assertEqual(limited.status, 429, await limited.text())
        self.assertTrue(1 <= int(limited.headers.get("Retry-After", "0")) <= 60)
        self.assertIn("no-store", limited.headers.get("Cache-Control", ""))
        response = await self.client.get(image)
        self.assertEqual(response.status, 200)
        self.assertEqual(await response.read(), self.asset_data["read-bucket"][0])
        write = await self.client.put("/api/events/" + event_id + "/read", json={"read": True})
        self.assertEqual(write.status, 200, await write.text())


if __name__ == "__main__":
    unittest.main(verbosity=2)
