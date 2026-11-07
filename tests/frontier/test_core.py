"""Independent release checks for Frontier's observable data and security contract.

Run with the project's interpreter: python -m unittest discover -s tests/frontier -v
All records, tokens, files and HTTP requests are temporary synthetic fixtures.
No background collector, model request, or publishing integration is started.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import aiohttp
from aiohttp.test_utils import TestClient, TestServer

from xhs_local.frontier.models import event_key, raw_fingerprint, validate_analysis
from xhs_local.frontier.store import Store
from xhs_local.frontier.web import Settings, create_app
from xhs_local.frontier.worker import EnrichmentWorker, ModelError


class FakeModelResponse:
    """An in-memory provider response, including chunked delivery."""

    status = 200

    def __init__(self, results):
        self.body = json.dumps(
            {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": json.dumps({"results": results}),
                        },
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 20},
            }
        ).encode()
        self.content = self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def iter_chunked(self, _chunk_size):
        for offset in range(0, len(self.body), 17):
            yield self.body[offset : offset + 17]


class FakeModelClient:
    def __init__(self, results):
        self.results = results
        self.request = None

    def post(self, _url, **kwargs):
        self.request = kwargs["json"]
        return FakeModelResponse(self.results)


class FrontierCoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="frontier-contract-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "source.sqlite3"
        self.store = Store(self.root / "events.sqlite3")
        with sqlite3.connect(self.source) as connection:
            connection.executescript(
                """
                CREATE TABLE records(
                    record_id TEXT PRIMARY KEY, content_hash TEXT, plugin_id TEXT,
                    source_name TEXT, source_url TEXT, title TEXT, text TEXT,
                    occurred_at TEXT, observed_at TEXT, payload_json TEXT,
                    content_type TEXT);
                CREATE TABLE attachments(
                    record_id TEXT, attachment_id TEXT PRIMARY KEY, mime_type TEXT,
                    relative_path TEXT);
                """
            )

    def add_source(
        self,
        record_id,
        *,
        title=None,
        text=None,
        platform="telegram",
        published_at="2026-10-18T08:00:00+00:00",
        observed_at="2026-10-18T09:00:00+00:00",
    ):
        title = title or "A research event " + record_id
        text = text or "The team reported a new instrument result."
        content_hash = hashlib.sha256((title + "\n" + text).encode()).hexdigest()
        with sqlite3.connect(self.source) as connection:
            connection.execute(
                "INSERT INTO records VALUES(?,?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(record_id) DO UPDATE SET "
                "title=excluded.title,text=excluded.text,content_hash=excluded.content_hash,"
                "occurred_at=excluded.occurred_at,observed_at=excluded.observed_at",
                (
                    record_id,
                    content_hash,
                    platform,
                    "Fixture source",
                    "https://example.org/report/" + record_id,
                    title,
                    text,
                    published_at,
                    observed_at,
                    "{}",
                    "tech_news",
                ),
            )

    @staticmethod
    def model_output(title="A supported research event", score=60, event_day=None):
        result = {
            "is_event": True,
            "title": title,
            "summary": "The source reports an instrument result; no additional facts are asserted.",
            "category": "science",
            "tags": ["research"],
            "score_components": {key: score for key in ("impact", "scope", "novelty", "urgency")},
            "score_reason": "Fixture editorial score used to verify ordering.",
            "event_time_start": None,
            "event_time_end": None,
            "event_time_precision": "unknown",
            "event_time_status": "unknown",
            "event_time_evidence": "",
            "event_timezone": None,
            "locations": [],
            "location_status": "unknown",
        }
        if event_day:
            result.update(
                event_time_start=event_day + "T00:00:00+00:00",
                event_time_precision="day",
                event_time_status="explicit",
                event_time_evidence="recorded on " + event_day,
            )
        return result

    def make_event(
        self,
        record_id="fixture",
        *,
        score=60,
        event_day=None,
        published_at="2026-10-18T08:00:00+00:00",
    ):
        title = "Research event " + record_id
        text = "The team reported a new instrument result."
        if event_day:
            text += " The event was recorded on " + event_day + "."
        self.add_source(record_id, title=title, text=text, published_at=published_at)
        self.store.import_records(self.source)
        rows = self.store.claim(200)
        raw = next(row for row in rows if row["record_id"] == record_id)
        self.assertEqual(len(rows), 1, "The fixture must not silently abandon other claims")
        analysis = validate_analysis(self.model_output(title, score, event_day), raw)
        self.store.complete(raw, analysis)
        with self.store.connect() as connection:
            event_id = connection.execute(
                "SELECT event_id FROM raw_records WHERE record_id=?", (record_id,)
            ).fetchone()[0]
        return event_id

    def test_unknown_event_time_is_not_publication_time_and_requires_evidence(self):
        raw = {
            "title": "An instrument result",
            "text": "The team reports a new result, with no event date or location.",
            "source_published_at": "2026-10-18T08:00:00+00:00",
            "ingested_at": "2026-10-18T09:00:00+00:00",
        }
        for evidence in ("", "reported on 2026-10-18", "The team reports a new result"):
            with self.subTest(evidence=evidence):
                output = self.model_output()
                output.update(
                    event_time_start="2026-10-18T08:00:00+00:00",
                    event_time_precision="exact",
                    event_time_status="explicit",
                    event_time_evidence=evidence,
                )
                result = validate_analysis(output, raw)
                self.assertIsNone(result["event_time_start"])
                self.assertIsNone(result["event_time_end"])
                self.assertEqual(result["event_time_precision"], "unknown")
                self.assertEqual(result["event_time_status"], "unknown")
        event = self.store.get_event(self.make_event("unknown"))
        self.assertIsNone(event["event_time_start"])
        self.assertTrue(event["source_published_at"].startswith("2026-10-18"))
        self.assertEqual(event["locations"], [])

        # Same headline/day can describe distinct launches at different exact times.
        precise_raw = {
            "title": "Launch complete",
            "text": "Launches happened on 2026-10-10 at 08:00 UTC and 18:00 UTC.",
        }
        identities = []
        for hour in ("08", "18"):
            output = self.model_output("Launch complete")
            output.update(
                event_time_start="2026-10-10T" + hour + ":00:00+00:00",
                event_time_precision="exact",
                event_time_status="explicit",
                event_time_evidence=precise_raw["text"],
            )
            identities.append(event_key(validate_analysis(output, precise_raw), "unused"))
        self.assertNotEqual(
            *identities, "Distinct precise occurrence times must not overwrite each other"
        )

    def test_sorting_uses_occurrence_time_and_numeric_importance_with_stable_pages(self):
        old_high = self.make_event("old-high", score=100, event_day="2026-10-10")
        new_low = self.make_event(
            "new-low", score=9, event_day="2026-10-12", published_at="2026-10-17T08:00:00+00:00"
        )
        unknown = self.make_event(
            "unknown-high", score=80, published_at="2026-10-19T08:00:00+00:00"
        )
        middle = self.make_event("middle-high", score=80, event_day="2026-10-11")
        for sort, expected in (
            ("importance", [old_high, middle, unknown, new_low]),
            ("event_time", [new_low, middle, old_high, unknown]),
        ):
            with self.subTest(sort=sort):
                full = self.store.list_events({"sort": sort})
                self.assertEqual(full["total"], 4)
                self.assertEqual([item["id"] for item in full["items"]], expected)
                pages = [
                    self.store.list_events({"sort": sort, "limit": 2, "offset": offset})
                    for offset in (0, 2)
                ]
                ids = [item["id"] for page in pages for item in page["items"]]
                self.assertEqual(ids, expected)
                self.assertEqual(len(set(ids)), 4)
        window = self.store.list_events(
            {"sort": "event_time", "after": "2026-10-11", "before": "2026-10-13"}
        )
        self.assertEqual([item["id"] for item in window["items"]], [new_low, middle])

    def test_import_is_read_only_idempotent_and_stale_analysis_cannot_overwrite_edit(self):
        title, text = "An identical source report", "An instrument test has been completed."
        self.add_source("original", title=title, text=text)
        source_before = hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.assertEqual(self.store.import_records(self.source), 1)
        raw = self.store.claim()[0]
        original_analysis = validate_analysis(self.model_output(title), raw)
        self.store.complete(raw, original_analysis)
        self.assertEqual(self.store.import_records(self.source), 0)
        self.assertEqual(self.store.claim(), [])
        self.assertEqual(self.store.list_events()["total"], 1)
        self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(), source_before)

        self.add_source("copied", title=title, text=text, platform="x")
        self.assertEqual(self.store.import_records(self.source), 1)
        self.assertEqual(
            self.store.claim(), [], "Exact duplicate content must not need another model call"
        )
        event = self.store.list_events()["items"][0]
        self.assertEqual(event["source_count"], 2)
        self.assertEqual(
            event["confidence"], "single_source", "Reposts do not prove independent verification"
        )

        self.add_source("original", title="Corrected report", text="A corrected instrument result.")
        self.assertEqual(self.store.import_records(self.source), 1)
        self.store.complete(raw, original_analysis)
        with self.store.connect() as connection:
            state, event_id = connection.execute(
                "SELECT state,event_id FROM raw_records WHERE record_id='original'"
            ).fetchone()
        self.assertEqual(state, "pending")
        self.assertIsNone(
            event_id, "An obsolete model response must not attach a changed raw record"
        )
        corrected = self.store.claim()[0]
        self.assertEqual(corrected["record_id"], "original")
        self.store.complete(
            corrected, validate_analysis(self.model_output("Corrected report"), corrected)
        )
        self.assertEqual(self.store.import_records(self.source), 0)
        self.assertEqual(self.store.claim(), [])
        events = self.store.list_events()["items"]
        self.assertEqual(len(events), 2)
        self.assertEqual({item["title"] for item in events}, {title, "Corrected report"})
        self.assertTrue(all(item["source_count"] == 1 for item in events))

        # A corrected publication/observation timestamp is provenance, even if text is unchanged.
        self.add_source(
            "original",
            title="Corrected report",
            text="A corrected instrument result.",
            published_at="2026-10-17T08:00:00+00:00",
            observed_at="2026-10-19T09:00:00+00:00",
        )
        self.assertEqual(self.store.import_records(self.source), 1)
        self.assertEqual(self.store.claim(), [], "Non-relative metadata edits need no model call")
        with self.store.connect() as connection:
            provenance = connection.execute(
                "SELECT source_published_at,ingested_at FROM raw_records WHERE record_id='original'"
            ).fetchone()
        self.assertTrue(provenance["source_published_at"].startswith("2026-10-17"))
        self.assertTrue(provenance["ingested_at"].startswith("2026-10-19"))

        # Repeated 'today' wording must use its own source-time context.
        relative_title, relative_text = "Daily launch", "The launch happened today."
        relative_rows = []
        for record_id, day in (("daily-first", "15"), ("daily-second", "16")):
            self.add_source(
                record_id,
                title=relative_title,
                text=relative_text,
                published_at="2026-10-" + day + "T08:00:00+00:00",
            )
            self.assertEqual(self.store.import_records(self.source), 1)
            claimed = self.store.claim()
            self.assertEqual(
                len(claimed), 1, "Cross-day relative reports must not reuse prior analysis"
            )
            relative_rows.append(claimed[0])
            self.store.complete(
                claimed[0], validate_analysis(self.model_output(relative_title), claimed[0])
            )
        self.assertNotEqual(raw_fingerprint(relative_rows[0]), raw_fingerprint(relative_rows[1]))
        self.assertNotEqual(relative_rows[0]["fingerprint"], relative_rows[1]["fingerprint"])

        # The same article's corrected relative-date context invalidates in-flight analysis.
        self.add_source(
            "daily-first",
            title=relative_title,
            text=relative_text,
            published_at="2026-10-17T08:00:00+00:00",
        )
        self.assertEqual(self.store.import_records(self.source), 1)
        self.store.complete(
            relative_rows[0], validate_analysis(self.model_output(relative_title), relative_rows[0])
        )
        with self.store.connect() as connection:
            row = connection.execute(
                "SELECT state,event_id FROM raw_records WHERE record_id='daily-first'"
            ).fetchone()
        self.assertEqual(row["state"], "pending")
        self.assertIsNone(row["event_id"])
        changed = self.store.claim()[0]
        self.store.complete(changed, validate_analysis(self.model_output(relative_title), changed))

        # A provider account/balance outage must preserve the source article's retry allowance.
        self.add_source("provider-blocked")
        self.assertEqual(self.store.import_records(self.source), 1)
        key_file = self.root / "synthetic-model.key"
        key_file.write_text("synthetic-test-key-no-network")

        async def blocked_provider():
            worker = EnrichmentWorker(self.store, self.source, key_file)
            processed = []

            async def process(_session, rows):
                processed.extend(row["record_id"] for row in rows)
                worker.stop.set()
                raise ModelError("deepseek_auth_or_balance_402", blocking=True)

            async def inline_store_call(function, *args, **kwargs):
                # This regression checks retry policy, independently of thread scheduling.
                return function(*args, **kwargs)

            with (
                patch.object(worker, "process", process),
                patch("xhs_local.frontier.worker.asyncio.to_thread", inline_store_call),
            ):
                try:
                    await asyncio.wait_for(worker.run(), timeout=3)
                except TimeoutError:
                    self.fail("Blocked-provider fixture did not finish: " + repr(worker.status))
            self.assertEqual(processed, ["provider-blocked"])

        asyncio.run(blocked_provider())
        with self.store.connect() as connection:
            pending = connection.execute(
                "SELECT state,attempts,lease_until FROM raw_records "
                "WHERE record_id='provider-blocked'"
            ).fetchone()
        self.assertEqual(dict(pending), {"state": "pending", "attempts": 0, "lease_until": 0.0})
        self.store.complete(self.store.claim()[0], {"is_event": False})
        self.assert_short_batch_identifiers(key_file)

    def assert_short_batch_identifiers(self, key_file):
        raw_ids = ("5a" * 32, "e3" * 32)
        self.add_source(raw_ids[0], title="Alpha source", text="An alpha experiment completed.")
        self.add_source(raw_ids[1], title="Beta source", text="A beta experiment completed.")
        self.assertEqual(self.store.import_records(self.source), 2)
        rows = self.store.claim()
        self.assertEqual(len(rows), 2)
        first = self.model_output("Analysis for first input") | {"id": "a1"}
        second = self.model_output("Analysis for second input") | {"id": "a2"}
        worker = EnrichmentWorker(self.store, self.source, key_file)
        baseline = self.store.list_events()["total"]

        async def inline_store_call(function, *args, **kwargs):
            return function(*args, **kwargs)

        async def check_responses():
            cases = (
                ("unknown", [first, second | {"id": "a9"}], "deepseek_result_identity_mismatch"),
                ("duplicate", [first, first], "deepseek_invalid_json"),
                ("missing", [first], "deepseek_result_identity_mismatch"),
                (
                    "extra",
                    [first, second, second | {"id": "a3"}],
                    "deepseek_result_identity_mismatch",
                ),
                (
                    "long_id",
                    [first | {"id": rows[0]["record_id"]}, second],
                    "deepseek_result_identity_mismatch",
                ),
            )
            with patch("xhs_local.frontier.worker.asyncio.to_thread", inline_store_call):
                for case, results, error in cases:
                    with self.subTest(batch_identity=case):
                        with self.assertRaises(ModelError) as raised:
                            await worker.process(FakeModelClient(results), rows)
                        self.assertEqual(raised.exception.code, error)
                        self.assertEqual(self.store.list_events()["total"], baseline)
                        with self.store.connect() as connection:
                            pending = connection.execute(
                                "SELECT state,event_id FROM raw_records WHERE record_id IN (?,?)",
                                raw_ids,
                            ).fetchall()
                        self.assertTrue(
                            all(
                                row["state"] == "processing" and row["event_id"] is None
                                for row in pending
                            )
                        )

                # A valid response may arrive in any order; IDs alone determine the mapping.
                client = FakeModelClient([second, first])
                await worker.process(client, rows)
                articles = json.loads(client.request["messages"][1]["content"])["articles"]
                self.assertEqual([article["id"] for article in articles], ["a1", "a2"])
                self.assertEqual(
                    [article["title"] for article in articles], [row["title"] for row in rows]
                )
                self.assertTrue(
                    all(
                        raw_id not in client.request["messages"][1]["content"] for raw_id in raw_ids
                    )
                )

        asyncio.run(check_responses())
        with self.store.connect() as connection:
            assigned = connection.execute(
                "SELECT r.record_id,r.state,e.title FROM raw_records r "
                "JOIN events e ON r.event_id=e.id WHERE r.record_id IN (?,?)",
                raw_ids,
            ).fetchall()
        self.assertEqual(
            {row["record_id"]: row["title"] for row in assigned},
            {
                rows[0]["record_id"]: first["title"],
                rows[1]["record_id"]: second["title"],
            },
        )
        self.assertTrue(all(row["state"] == "completed" for row in assigned))
        self.assertEqual(self.store.list_events()["total"], baseline + 2)

    def test_private_authentication_csrf_origin_and_logout(self):
        event_id = self.make_event("authenticated")
        token = "frontier-synthetic-test-token-" + "a" * 32
        token_file = self.root / "test-access.token"
        token_file.write_text(token)
        settings = Settings(
            root=self.root,
            database=self.store.path,
            source_database=self.source,
            access_token_file=token_file,
            static_dir=self.root / "static",
            enrich=False,
        )

        async def scenario():
            client = TestClient(
                TestServer(create_app(settings, self.store, background=False)),
                cookie_jar=aiohttp.CookieJar(unsafe=True),
            )
            try:
                await client.start_server()
                response = await client.get("/api/events")
                self.assertEqual(response.status, 401)
                self.assertEqual(response.headers.get("Cache-Control"), "no-store")
                self.assertEqual(response.headers.get("X-Content-Type-Options"), "nosniff")
                self.assertIn(
                    "frame-ancestors 'none'", response.headers.get("Content-Security-Policy", "")
                )
                self.assertEqual((await client.get("/api/version")).status, 200)
                self.assertEqual(
                    (await client.post("/api/auth/session", json={"token": "wrong"})).status, 401
                )
                response = await client.post("/api/auth/session", json={"token": token})
                self.assertEqual(response.status, 200)
                csrf = (await response.json())["csrf_token"]
                cookie = response.cookies["frontier_session"]
                self.assertTrue(cookie["httponly"])
                self.assertEqual(cookie["samesite"], "Strict")
                response = await client.get("/api/auth/me")
                self.assertEqual(response.status, 200)
                self.assertEqual((await response.json())["csrf_token"], csrf)
                endpoint = "/api/events/" + event_id + "/bookmark"
                response = await client.put(endpoint, json={"bookmarked": True})
                self.assertEqual(response.status, 403)
                self.assertEqual(response.headers.get("Cache-Control"), "no-store")
                self.assertEqual(response.headers.get("X-Frame-Options"), "DENY")
                self.assertFalse(self.store.get_event(event_id)["bookmarked"])
                response = await client.put(
                    endpoint,
                    json={"bookmarked": True},
                    headers={"X-CSRF-Token": csrf, "Origin": "https://elsewhere.invalid"},
                )
                self.assertEqual(response.status, 403)
                self.assertFalse(self.store.get_event(event_id)["bookmarked"])
                response = await client.put(
                    endpoint, json={"bookmarked": True}, headers={"X-CSRF-Token": csrf}
                )
                self.assertEqual(response.status, 200)
                self.assertTrue(self.store.get_event(event_id)["bookmarked"])
                response = await client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf})
                self.assertEqual(response.status, 200)
                self.assertEqual((await client.get("/api/events")).status, 401)
            finally:
                await client.close()

        asyncio.run(scenario())

    def test_backup_is_readable_consistent_and_retains_events_and_bookmarks(self):
        event_id = self.make_event("backup", event_day="2026-10-10")
        self.assertTrue(self.store.bookmark(event_id, "owner", True))
        destination = self.root / "backups" / "snapshot.sqlite3"
        result = self.store.backup(destination)
        self.assertEqual(result["integrity"], "ok")
        self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o600)
        with sqlite3.connect(destination.as_uri() + "?mode=ro", uri=True) as backup:
            self.assertEqual(backup.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(backup.execute("PRAGMA foreign_key_check").fetchall(), [])
            self.assertEqual(backup.execute("SELECT count(*) FROM events").fetchone()[0], 1)
            self.assertEqual(
                backup.execute(
                    "SELECT count(*) FROM raw_records WHERE state='completed'"
                ).fetchone()[0],
                1,
            )
            self.assertEqual(
                backup.execute("SELECT event_id FROM bookmarks").fetchone()[0], event_id
            )
            data = json.loads(backup.execute("SELECT data FROM events").fetchone()[0])
            self.assertTrue(data["event_time_start"].startswith("2026-10-10"))
        self.store.bookmark(event_id, "owner", False)
        restored = Store(destination)
        self.assertTrue(restored.get_event(event_id)["bookmarked"])
        self.assertEqual(restored.list_events()["total"], 1)
        self.assertEqual(restored.get_event(event_id)["sources"][0]["id"], "backup")


if __name__ == "__main__":
    unittest.main()
