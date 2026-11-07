"""V3 topic radar acceptance checks on disposable SQLite, no collector/AI/real data.

Run: PYTHONPATH=src .venv/bin/python -m unittest tests/frontier/test_radar_v3.py -v
HTTP uses aiohttp's in-process TestServer(background=False), not a desktop window.
"""

from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

import aiohttp
from aiohttp.test_utils import TestClient, TestServer

from xhs_local.frontier.preferences import ProductError
from xhs_local.frontier.radar import Radar
from xhs_local.frontier.store import Store
from xhs_local.frontier.web import Settings, create_app


def timestamp(days: int = 0) -> str:
    return (datetime.now(UTC) - timedelta(days=days)).isoformat(timespec="milliseconds")


def add_event(
    store: Store,
    key: str,
    *,
    title="chip programme",
    text="satellite engineering",
    age_days=0,
    importance=75,
    platform="telegram",
    occurred=None,
    located=False,
    source_count=1,
    completed=True,
    with_source=True,
):
    """Synthetic *derived* evidence in the disposable test DB; no raw collector write."""
    ingestion = timestamp(age_days)
    with store.connect() as c:
        c.execute(
            "INSERT INTO events(id,title,summary,category,importance,event_time_start,"
            "location_status,data,created_at,updated_at,first_ingested_at)"
            "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (
                key,
                title,
                "synthetic research summary",
                "science",
                importance,
                occurred,
                "located" if located else "unknown",
                json.dumps({"fixture": key}),
                ingestion,
                ingestion,
                ingestion,
            ),
        )
        if with_source:
            for n in range(source_count):
                record_id = f"{key}-raw-{n}"
                c.execute(
                    "INSERT INTO raw_records(record_id,fingerprint,content_hash,plugin_id,"
                    "source_name,source_url,title,text,ingested_at,first_ingested_at,"
                    "state,event_id,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        record_id,
                        record_id,
                        record_id,
                        platform,
                        "Fixture source",
                        f"https://example.test/{record_id}",
                        title,
                        text,
                        ingestion,
                        ingestion,
                        "completed" if completed else "pending",
                        key,
                        ingestion,
                    ),
                )


class RadarMigrationTests(unittest.TestCase):
    def test_v2_reopen_creates_sidecar_without_changing_existing_data_or_schema_number(self):
        with tempfile.TemporaryDirectory(prefix="frontier-radar-migrate-") as folder:
            database = Path(folder) / "events.sqlite3"
            store = Store(database)
            with store.connect() as c:
                c.execute(
                    "INSERT INTO metadata(key,value) VALUES('preserve',?)", ('"do not change"',)
                )
                self.assertEqual(c.execute("SELECT version FROM schema_version").fetchone()[0], 2)
                # Simulate a previously initialized V2 database without the radar sidecar.
                c.execute("DROP TABLE radar_topics")
            reopened = Store(database)
            with reopened.connect() as c:
                self.assertEqual(c.execute("SELECT version FROM schema_version").fetchone()[0], 2)
                self.assertEqual(
                    c.execute("SELECT value FROM metadata WHERE key='preserve'").fetchone()[0],
                    '"do not change"',
                )
                self.assertIn(
                    "radar_topics",
                    {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")},
                )
            Radar(reopened).create("owner", {"name": "存续主题", "query": "research"})
            Store(database)  # Second startup is idempotent, preserves existing topic.
            self.assertEqual(len(Radar(Store(database)).overview("owner")["topics"]), 1)

    def test_upgrade_existing_radar_sidecar_without_version_preserves_topics(self):
        with tempfile.TemporaryDirectory(prefix="frontier-radar-sidecar-") as folder:
            database = Path(folder) / "db.sqlite3"
            store = Store(database)
            with store.connect() as c:
                c.execute("DROP TABLE radar_decisions")
                c.execute("DROP TABLE radar_topics")
                c.execute(
                    "CREATE TABLE radar_topics("
                    "id TEXT PRIMARY KEY,owner TEXT NOT NULL,name TEXT NOT NULL,"
                    "query TEXT NOT NULL,platforms TEXT NOT NULL,min_importance INTEGER,"
                    "created_at TEXT,updated_at TEXT,last_reviewed_at TEXT)"
                )
                c.execute(
                    "INSERT INTO radar_topics VALUES(?,?,?,?,?,?,?,?,?)",
                    (
                        "legacy",
                        "owner",
                        "Existing radar",
                        "chip",
                        '["x"]',
                        0,
                        "2026-10-19T00:00:00+00:00",
                        "2026-10-19T00:00:00+00:00",
                        None,
                    ),
                )
            restored = Store(database)
            radar = Radar(restored)
            topic = radar.overview("owner")["topics"][0]
            self.assertEqual((topic["id"], topic["version"]), ("legacy", 1))
            updated = radar.update("owner", "legacy", {"version": 1, "name": "Still here"})
            self.assertEqual(updated["topic"]["version"], 2)
            Store(database)
            self.assertEqual(Radar(Store(database)).overview("owner")["topics"][0]["version"], 2)

    def test_owner_scoped_crud_transaction_audit_and_plan_limits(self):
        with tempfile.TemporaryDirectory(prefix="frontier-radar-crud-") as folder:
            store = Store(Path(folder) / "derived.sqlite3")
            free = Radar(store, "free")
            a = free.create(
                "alice", {"name": "A", "query": "chip", "platforms": ["x"], "min_importance": 20}
            )["topic"]
            self.assertIsNone(a["last_reviewed_at"])
            with self.assertRaises(ProductError) as context:
                free.create("alice", {"name": "B", "query": "satellite"})
            self.assertEqual(
                (context.exception.code, context.exception.status), ("radar_topic_limit", 403)
            )
            self.assertEqual(len(free.overview("bob")["topics"]), 0)
            with self.assertRaises(ProductError) as context:
                free.update("bob", a["id"], {"version": a["version"], "name": "sneaky"})
            self.assertEqual(context.exception.status, 404)
            with self.assertRaises(ProductError) as context:
                free.review("bob", a["id"], {"version": a["version"]})
            self.assertEqual(context.exception.status, 404)
            with self.assertRaises(ProductError):
                free.delete("bob", a["id"], {"version": a["version"]})
            with store.connect() as c:
                before = c.execute("SELECT count(*) FROM audit").fetchone()[0]
            with self.assertRaises(ProductError):
                free.update("alice", a["id"], {"version": a["version"], "query": "x " * 9})
            with store.connect() as c:
                self.assertEqual(c.execute("SELECT count(*) FROM audit").fetchone()[0], before)
            self.assertFalse(
                free.update("alice", a["id"], {"version": a["version"], "name": "A"})["updated"]
            )
            with store.connect() as c:
                self.assertEqual(c.execute("SELECT count(*) FROM audit").fetchone()[0], before)
            stamp = free.review("alice", a["id"], {"version": a["version"]})["last_reviewed_at"]
            updated = free.update(
                "alice", a["id"], {"version": a["version"] + 1, "query": "chip satellite"}
            )["topic"]
            self.assertEqual(updated["last_reviewed_at"], stamp)
            self.assertTrue(
                free.delete("alice", a["id"], {"version": updated["version"]})["deleted"]
            )
            self.assertEqual(len(free.overview("alice")["topics"]), 0)
            with store.connect() as c:
                actions = [r[0] for r in c.execute("SELECT action FROM audit ORDER BY id")]
                self.assertTrue(all(action.startswith("radar.") for action in actions))
            for plan, max_topics in (("pro", 10), ("analyst", 30)):
                radar = Radar(store, plan)
                for index in range(max_topics):
                    radar.create("owner-" + plan, {"name": f"Topic {index}", "query": "chip"})
                with self.assertRaises(ProductError) as context:
                    radar.create("owner-" + plan, {"name": "Extra", "query": "chip"})
                self.assertEqual(context.exception.status, 403)


class RadarEntitlementAndUniquenessTests(unittest.TestCase):
    def test_downgrade_retains_topics_but_enforces_analytics_permissions(self):
        with tempfile.TemporaryDirectory(prefix="frontier-plan-downgrade-") as directory:
            store = Store(Path(directory) / "derived.sqlite3")
            add_event(store, "evidence", title="quantum funding", text="quantum")
            analyst = Radar(store, "analyst")
            first = analyst.create("owner", {"name": "量子", "query": "quantum"})["topic"]
            second = analyst.create("owner", {"name": "其他关注", "query": "quantum"})["topic"]
            analyst.decide("owner", second["id"], {"event_id": "evidence", "decision": "research"})
            downgraded = Radar(store, "free")
            overview = downgraded.overview("owner")
            self.assertEqual(len(overview["topics"]), 2)
            self.assertFalse(overview["topics"][0]["suspended"])
            self.assertTrue(overview["topics"][1]["suspended"])
            self.assertIsNone(overview["topics"][1]["metrics"])
            self.assertEqual(overview["topics"][1]["highlights"], [])
            self.assertEqual(overview["topics"][0]["metrics"]["total"], 1)
            with self.assertRaises(ProductError) as error:
                downgraded.review("owner", second["id"], {"version": second["version"]})
            self.assertEqual(error.exception.status, 403)
            with self.assertRaises(ProductError) as error:
                downgraded.decide("owner", second["id"], {"event_id": "evidence", "decision": None})
            self.assertEqual(error.exception.status, 403)
            with self.assertRaises(ProductError) as error:
                downgraded.create("owner", {"name": "不可新建", "query": "quantum"})
            self.assertEqual(error.exception.status, 403)
            # Existing triage survives downgrades and can be restored by
            # changing only the server-assigned tier, never by an API query.
            restored = analyst.overview("owner")["topics"][1]
            self.assertEqual(restored["metrics"]["decided"]["research"], 1)
            self.assertEqual(restored["highlights"][0]["decision"], "research")
            downgraded.delete("owner", first["id"], {"version": first["version"]})
            self.assertEqual(len(downgraded.overview("owner")["topics"]), 1)

    def test_server_duplicate_name_is_409_across_client_and_unicode_variants(self):
        with tempfile.TemporaryDirectory(prefix="frontier-topic-names-") as directory:
            store = Store(Path(directory) / "derived.sqlite3")
            radar = Radar(store, "analyst")
            first = radar.create("owner", {"name": "AI 研究", "query": "AI"})["topic"]
            second = radar.create("owner", {"name": "Other", "query": "AI"})["topic"]
            with self.assertRaises(ProductError) as err:
                radar.create("owner", {"name": "ＡＩ 研究", "query": "AI"})
            self.assertEqual(
                (err.exception.code, err.exception.status), ("radar_topic_duplicate", 409)
            )
            with self.assertRaises(ProductError) as err:
                radar.update(
                    "owner", second["id"], {"version": second["version"], "name": "ai 研究"}
                )
            self.assertEqual(err.exception.status, 409)
            self.assertEqual(len(radar.overview("owner")["topics"]), 2)
            self.assertTrue(
                radar.update(
                    "owner", first["id"], {"version": first["version"], "query": "AI 核验"}
                )["updated"]
            )


class RadarVersionConflictTests(unittest.TestCase):
    def test_two_client_compare_and_swap_update_review_delete(self):
        with tempfile.TemporaryDirectory(prefix="frontier-radar-cas-") as folder:
            store = Store(Path(folder) / "db.sqlite3")
            radar = Radar(store)
            topic = radar.create("owner", {"name": "Quantum", "query": "chip"})["topic"]
            ident = topic["id"]
            self.assertEqual(topic["version"], 1)
            with self.assertRaises(ProductError) as error:
                radar.update("owner", ident, {"name": "stale"})
            self.assertEqual(error.exception.status, 422)
            with self.assertRaises(ProductError) as error:
                radar.update("owner", ident, {"version": True, "name": "stale"})
            self.assertEqual(error.exception.status, 422)
            a = radar.update("owner", ident, {"version": 1, "name": "First client"})
            self.assertEqual(a["topic"]["version"], 2)
            with self.assertRaises(ProductError) as error:
                radar.update("owner", ident, {"version": 1, "query": "lost-update"})
            self.assertEqual(
                (error.exception.code, error.exception.status), ("radar_topic_conflict", 409)
            )
            with self.assertRaises(ProductError) as error:
                radar.review("owner", ident, {"version": 1})
            self.assertEqual(error.exception.status, 409)
            self.assertEqual(
                (
                    radar.overview("owner")["topics"][0]["name"],
                    radar.overview("owner")["topics"][0]["query"],
                ),
                ("First client", "chip"),
            )
            b = radar.review("owner", ident, {"version": 2})
            self.assertEqual(b["version"], 3)
            with self.assertRaises(ProductError) as error:
                radar.delete("owner", ident, {"version": 2})
            self.assertEqual(error.exception.status, 409)
            with self.assertRaises(ProductError) as error:
                radar.delete("owner", ident, {"version": "3"})
            self.assertEqual(error.exception.status, 422)
            self.assertEqual(len(radar.overview("owner")["topics"]), 1)
            self.assertTrue(radar.delete("owner", ident, {"version": 3})["deleted"])
            self.assertEqual(len(radar.overview("owner")["topics"]), 0)
            with store.connect() as c:
                actions = [
                    r[0]
                    for r in c.execute(
                        "SELECT action FROM audit WHERE action LIKE 'radar.%' ORDER BY id"
                    )
                ]
            self.assertEqual(
                actions,
                [
                    "radar.topic.created",
                    "radar.topic.updated",
                    "radar.topic.reviewed",
                    "radar.topic.deleted",
                ],
            )


class RadarPlanWindowTests(unittest.TestCase):
    def test_history_window_trend_window_and_importance_are_server_side(self):
        with tempfile.TemporaryDirectory(prefix="frontier-radar-windows-") as folder:
            store = Store(Path(folder) / "derived.sqlite3")
            for age in (0, 6, 10, 29, 31, 80, 95):
                add_event(store, f"age-{age}", age_days=age, importance=75)
            for plan, count, trend_days, trend_count in (
                ("free", 2, 7, 2),
                ("pro", 4, 30, 4),
                ("analyst", 6, 30, 4),
            ):
                radar = Radar(store, plan)
                radar.create(
                    "owner", {"name": "Selected", "query": "chip satellite", "min_importance": 70}
                )
                topic = radar.overview("owner")["topics"][0]
                self.assertEqual(topic["metrics"]["total"], count)
                self.assertEqual(len(topic["metrics"]["trend"]), trend_days)
                self.assertEqual(
                    sum(day["count"] for day in topic["metrics"]["trend"]), trend_count
                )
                radar.delete("owner", topic["id"], {"version": topic["version"]})
            selected = Radar(store, "analyst").create(
                "owner", {"name": "Strict", "query": "chip", "min_importance": 90}
            )
            self.assertEqual(
                Radar(store, "analyst").overview("owner")["topics"][0]["metrics"]["total"], 0
            )
            self.assertEqual(selected["topic"]["min_importance"], 90)

    def test_radar_highlights_explain_current_archive_window_without_deleting_history(self):
        from xhs_local.frontier.preferences import Preferences

        with tempfile.TemporaryDirectory(prefix="frontier-radar-archive-") as folder:
            store = Store(Path(folder) / "db.sqlite3")
            add_event(store, "recent", age_days=0)
            add_event(store, "historic", age_days=20)
            radar = Radar(store, "analyst")
            radar.create("owner", {"name": "Archive semantics", "query": "chip"})

            def flags():
                topic = radar.overview("owner")["topics"][0]
                return {item["id"]: item for item in topic["highlights"]}

            first = flags()
            self.assertFalse(first["recent"]["archived"])
            self.assertTrue(first["historic"]["archived"])
            self.assertEqual(first["historic"]["retention_at"][:10], timestamp(20)[:10])
            with store.connect() as c:
                c.execute(
                    "INSERT INTO bookmarks(owner,event_id,created_at) VALUES(?,?,?)",
                    ("owner", "historic", timestamp()),
                )
                c.execute(
                    "UPDATE raw_records SET source_published_at=? WHERE event_id='recent'",
                    (timestamp(20),),
                )
            self.assertFalse(flags()["historic"]["archived"])  # Bookmarks stay in active view.
            settings = Preferences(store).update(
                "owner", {"retention_basis": "published", "retain_bookmarks": False}, 1
            )
            self.assertEqual(settings["version"], 2)
            published = flags()
            self.assertTrue(published["historic"]["archived"])
            self.assertTrue(published["recent"]["archived"])
            self.assertEqual(published["recent"]["source_published_at"][:10], timestamp(20)[:10])
            # The radar does not delete or hide older evidence, unlike an active-only view.
            with store.connect() as c:
                self.assertEqual(c.execute("SELECT count(*) FROM events").fetchone()[0], 2)

    def test_query_terms_are_and_substrings_and_never_sql_syntax(self):
        with tempfile.TemporaryDirectory(prefix="frontier-radar-keywords-") as folder:
            store = Store(Path(folder) / "derived.sqlite3")
            add_event(store, "mixed-fields", title="Chip", text="satellite")
            add_event(store, "raw-only", title="independent fixture", text="chip satellite")
            add_event(store, "only-chip", title="chip", text="different")
            add_event(store, "only-satellite", title="satellite", text="different")
            radar = Radar(store)
            name = radar.create("owner", {"name": "Keyword match", "query": "CHIP satellite"})
            snapshot = radar.overview("owner")["topics"][0]
            self.assertEqual(snapshot["metrics"]["total"], 2)
            self.assertEqual(
                {event["id"] for event in snapshot["highlights"]}, {"mixed-fields", "raw-only"}
            )
            radar.update(
                "owner",
                name["topic"]["id"],
                {"version": name["topic"]["version"], "query": "' OR 1=1 --"},
            )
            self.assertEqual(radar.overview("owner")["topics"][0]["metrics"]["total"], 0)


class RadarDecisionTests(unittest.TestCase):
    def test_explicit_triage_is_idempotent_owner_scoped_reversible_and_keeps_v2_state(self):
        with tempfile.TemporaryDirectory(prefix="frontier-radar-triage-") as directory:
            store = Store(Path(directory) / "db.sqlite3")
            add_event(store, "matching", title="chip innovation", text="satellite")
            add_event(store, "unmatched", title="other research", text="different")
            radar = Radar(store)
            topic = radar.create("owner", {"name": "Topic", "query": "chip satellite"})["topic"]
            eid, tid = "matching", topic["id"]
            original = radar.overview("owner")["topics"][0]
            self.assertEqual(
                original["metrics"]["decided"], {"dismiss": 0, "watch": 0, "research": 0}
            )
            self.assertIsNone(original["highlights"][0]["decision"])
            with self.assertRaises(ProductError) as error:
                radar.decide("another-owner", tid, {"event_id": eid, "decision": "watch"})
            self.assertEqual(error.exception.status, 404)
            with self.assertRaises(ProductError) as error:
                radar.decide("owner", tid, {"event_id": "unmatched", "decision": "watch"})
            self.assertEqual(error.exception.status, 409)
            for invalid in ("watching", "WATCH", False, 0, 1, [], {}):
                with self.assertRaises(ProductError):
                    radar.decide("owner", tid, {"event_id": eid, "decision": invalid})
            first = radar.decide("owner", tid, {"event_id": eid, "decision": "watch"})
            self.assertTrue(first["updated"])
            self.assertEqual(first["decision"], "watch")
            second = radar.decide("owner", tid, {"event_id": eid, "decision": "watch"})
            self.assertFalse(second["updated"])
            self.assertEqual(second["decided_at"], first["decided_at"])
            result = radar.overview("owner")["topics"][0]
            self.assertEqual(result["metrics"]["decided"]["watch"], 1)
            self.assertEqual(result["highlights"][0]["decision"], "watch")
            self.assertEqual(result["metrics"]["unread"], original["metrics"]["unread"])
            radar.decide("owner", tid, {"event_id": eid, "decision": "research"})
            result = radar.overview("owner")["topics"][0]
            self.assertEqual(result["metrics"]["decided"]["research"], 1)
            self.assertEqual(result["metrics"]["decided"]["watch"], 0)
            restored = radar.decide("owner", tid, {"event_id": eid, "decision": None})
            self.assertTrue(restored["updated"])
            self.assertIsNone(restored["decision"])
            self.assertFalse(
                radar.decide("owner", tid, {"event_id": eid, "decision": None})["updated"]
            )
            with store.connect() as c:
                self.assertEqual(c.execute("SELECT count(*) FROM event_reads").fetchone()[0], 0)
                self.assertEqual(c.execute("SELECT count(*) FROM bookmarks").fetchone()[0], 0)
                self.assertEqual(c.execute("SELECT count(*) FROM radar_decisions").fetchone()[0], 0)
                self.assertEqual(
                    c.execute(
                        "SELECT count(*) FROM audit WHERE action='radar.event.decided'"
                    ).fetchone()[0],
                    3,
                )
            radar.decide("owner", tid, {"event_id": eid, "decision": "dismiss"})
            radar.delete("owner", tid, {"version": topic["version"]})
            with store.connect() as c:
                self.assertEqual(c.execute("SELECT count(*) FROM radar_decisions").fetchone()[0], 0)
                self.assertEqual(c.execute("SELECT count(*) FROM events").fetchone()[0], 2)
            # Migration is repeatable and does not restore deleted user decisions.
            Store(store.path)
            self.assertEqual(radar.overview("owner")["topics"], [])


class RadarApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="frontier-radar-http-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        secrets = self.root / "runtime/secrets"
        secrets.mkdir(parents=True)
        self.access_token = "synthetic-radar-access-token-not-an-account-secret"
        (secrets / "frontier-access.token").write_text(self.access_token)
        self.store = Store(self.root / "derived.sqlite3")
        self.client = TestClient(
            TestServer(
                create_app(
                    Settings(
                        root=self.root, database=self.store.path, enrich=False, plan="analyst"
                    ),
                    self.store,
                    background=False,
                )
            )
        )
        await self.client.start_server()
        response = await self.client.post("/api/auth/session", json={"token": self.access_token})
        self.assertEqual(response.status, 200, await response.text())
        self.csrf = (await response.json())["csrf_token"]
        self.client.session.headers.update({"X-CSRF-Token": self.csrf})
        self.addAsyncCleanup(self.client.close)

    async def _get(self, path):
        response = await self.client.get(path)
        self.assertEqual(response.status, 200, await response.text())
        return await response.json()

    async def _create(self, **overrides):
        payload = {
            "name": "Chip research",
            "query": "chip satellite",
            "platforms": ["telegram", "x"],
            "min_importance": 40,
        }
        payload.update(overrides)
        response = await self.client.post("/api/radar/topics", json=payload)
        self.assertEqual(response.status, 201, await response.text())
        return (await response.json())["topic"]

    async def test_http_shape_evidence_filters_sources_trend_review_and_v2_state(self):
        add_event(
            self.store,
            "recent",
            importance=97,
            occurred=timestamp(400),
            located=True,
            source_count=14,
        )
        add_event(self.store, "other-platform", platform="youtube", importance=99)
        add_event(self.store, "no-satellite", text="no matching second term", importance=99)
        add_event(self.store, "old", age_days=50, importance=99, occurred=timestamp())
        add_event(self.store, "unprocessed", completed=False, importance=99)
        add_event(self.store, "unlinked", with_source=False, importance=99)
        add_event(self.store, "future", age_days=-2, importance=99)
        topic = await self._create()
        self.assertEqual(
            set(topic),
            {
                "id",
                "name",
                "query",
                "platforms",
                "min_importance",
                "created_at",
                "updated_at",
                "last_reviewed_at",
                "version",
            },
        )
        overview = await self._get("/api/radar?plan=free&days=9999")
        self.assertEqual(set(overview), {"plan", "topics", "generated_at"})
        self.assertEqual(overview["plan"]["id"], "analyst")  # Query cannot elevate/override plan.
        self.assertEqual(overview["plan"]["limits"]["history_days"], 90)
        self.assertEqual(len(overview["topics"]), 1)
        t = overview["topics"][0]
        self.assertEqual(t["metrics"]["total"], 2)  # Recent + old (50d); unlinked excluded.
        self.assertEqual(t["metrics"]["unread"], 2)
        self.assertEqual(t["metrics"]["new_since_review"], 2)
        self.assertEqual(t["metrics"]["with_event_time"], 2)
        self.assertEqual(t["metrics"]["with_location"], 1)
        self.assertEqual(len(t["metrics"]["trend"]), 30)
        self.assertEqual(t["metrics"]["trend"][-1]["count"], 1)
        self.assertEqual(t["metrics"]["trend"][-1]["day"], datetime.now(UTC).date().isoformat())
        best = t["highlights"][0]
        self.assertEqual(best["id"], "old")  # Higher score wins for equal unread/review rank.
        recent_best = next(event for event in t["highlights"] if event["id"] == "recent")
        self.assertEqual(recent_best["source_count"], 14)
        self.assertEqual(len(recent_best["sources"]), 12)
        self.assertTrue(recent_best["sources_truncated"])
        self.assertTrue(all(set(s) == {"name", "platform", "url"} for s in recent_best["sources"]))
        self.assertIn("未进行交叉核实", recent_best["why"])
        self.assertIn("重要性评分", recent_best["why"])
        self.assertLess(recent_best["event_time_start"], recent_best["first_ingested_at"])
        self.assertEqual(recent_best["location_status"], "located")

        response = await self.client.put("/api/events/recent/read", json={"read": True})
        self.assertEqual(response.status, 200, await response.text())
        response = await self.client.put("/api/events/recent/bookmark", json={"bookmarked": True})
        self.assertEqual(response.status, 200, await response.text())
        t = (await self._get("/api/radar"))["topics"][0]
        self.assertEqual(t["metrics"]["unread"], 1)
        self.assertTrue(next(e for e in t["highlights"] if e["id"] == "recent")["bookmarked"])
        self.assertTrue(next(e for e in t["highlights"] if e["id"] == "recent")["read"])

        response = await self.client.post(
            f"/api/radar/topics/{topic['id']}/review", json={"version": topic["version"]}
        )
        self.assertEqual(response.status, 200, await response.text())
        reviewed_response = await response.json()
        reviewed = reviewed_response["last_reviewed_at"]
        t = (await self._get("/api/radar"))["topics"][0]
        self.assertEqual(t["metrics"]["new_since_review"], 0)
        self.assertEqual(t["last_reviewed_at"], reviewed)
        response = await self.client.patch(
            f"/api/radar/topics/{topic['id']}",
            json={"name": "Renamed chip monitor", "version": reviewed_response["version"]},
        )
        self.assertEqual(response.status, 200, await response.text())
        self.assertTrue((await response.json())["updated"])
        self.assertEqual((await self._get("/api/radar"))["topics"][0]["last_reviewed_at"], reviewed)
        await asyncio.sleep(0.02)
        add_event(self.store, "after-review", importance=80, located=False)
        updated = (await self._get("/api/radar"))["topics"][0]["metrics"]
        self.assertEqual(updated["new_since_review"], 1)
        self.assertEqual(updated["total"], 3)

    async def test_plan_boundaries_filters_keyword_semantics_and_priority(self):
        for i in range(11):
            add_event(
                self.store, f"matched-{i}", importance=50 + i, age_days=5, platform="telegram"
            )
        add_event(self.store, "nonmatch", title="chip", text="no second term", importance=99)
        topic = await self._create(platforms=["telegram"])
        results = (await self._get("/api/radar"))["topics"][0]
        self.assertEqual(results["metrics"]["total"], 11)
        self.assertEqual(len(results["highlights"]), 8)
        self.assertEqual(results["highlights"][0]["importance"], 60)
        self.assertEqual(sum(row["count"] for row in results["metrics"]["trend"]), 11)
        # Read/highlight ordering is owner specific, not sourced from caller payload.
        response = await self.client.put("/api/events/matched-10/read", json={"read": True})
        self.assertEqual(response.status, 200)
        ids = [r["id"] for r in (await self._get("/api/radar"))["topics"][0]["highlights"]]
        self.assertNotEqual(ids[0], "matched-10")
        self.assertEqual(ids[0], "matched-9")
        response = await self.client.patch(
            f"/api/radar/topics/{topic['id']}",
            json={"platforms": ["youtube"], "version": topic["version"]},
        )
        self.assertEqual(response.status, 200)
        self.assertEqual((await self._get("/api/radar"))["topics"][0]["metrics"]["total"], 0)
        response = await self.client.delete(
            f"/api/radar/topics/{topic['id']}", json={"version": topic["version"] + 1}
        )
        self.assertEqual(response.status, 200)
        self.assertEqual(await response.json(), {"id": topic["id"], "deleted": True})

    async def test_http_owner_isolation_not_only_in_store_methods(self):
        topic = await self._create()
        self.store.create_session(
            "isolated-bob-session-token",
            "bob-csrf-token",
            datetime.now(UTC).timestamp() + 3600,
            owner="bob",
        )
        # Use a separate cookie jar: the default TestClient is logged in as
        # owner and automatically overrides a supplied Cookie request header.
        async with aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True)) as other:

            async def bob(method, path, **kwargs):
                async with other.request(
                    method,
                    self.client.make_url(path),
                    cookies={"frontier_session": "isolated-bob-session-token"},
                    headers={"X-CSRF-Token": "bob-csrf-token"},
                    **kwargs,
                ) as response:
                    return response.status, await response.json()

            code, data = await bob("GET", "/api/radar")
            self.assertEqual(code, 200)
            self.assertEqual(data["topics"], [])
            code, _ = await bob(
                "PATCH",
                f"/api/radar/topics/{topic['id']}",
                json={"name": "not owned", "version": topic["version"]},
            )
            self.assertEqual(code, 404)
            code, _ = await bob(
                "POST",
                f"/api/radar/topics/{topic['id']}/review",
                json={"version": topic["version"]},
            )
            self.assertEqual(code, 404)
            code, _ = await bob(
                "DELETE", f"/api/radar/topics/{topic['id']}", json={"version": topic["version"]}
            )
            self.assertEqual(code, 404)
        self.assertEqual(len((await self._get("/api/radar"))["topics"]), 1)

    async def test_http_triage_csrf_validation_and_evidence_linkage(self):
        add_event(self.store, "decision-evidence", title="chip satellite breakthrough")
        topic = await self._create()
        route = f"/api/radar/topics/{topic['id']}/decisions"
        self.client.session.headers.pop("X-CSRF-Token")
        response = await self.client.post(
            route, json={"event_id": "decision-evidence", "decision": "watch"}
        )
        self.assertEqual(response.status, 403)
        self.client.session.headers["X-CSRF-Token"] = self.csrf
        for wrong in (
            {"event_id": "decision-evidence", "decision": "unverified"},
            {"event_id": "decision-evidence", "decision": 2},
            {"event_id": "decision-evidence", "decision": "watch", "plan": "analyst"},
            {"decision": "watch"},
        ):
            response = await self.client.post(route, json=wrong)
            self.assertEqual(response.status, 422, await response.text())
        response = await self.client.post(route, json={"event_id": "absent", "decision": "watch"})
        self.assertEqual(response.status, 409)
        response = await self.client.post(
            route, json={"event_id": "decision-evidence", "decision": "watch"}
        )
        self.assertEqual(response.status, 200, await response.text())
        self.assertTrue((await response.json())["updated"])
        snapshot = (await self._get("/api/radar"))["topics"][0]
        self.assertEqual(snapshot["metrics"]["decided"]["watch"], 1)
        self.assertEqual(snapshot["highlights"][0]["decision"], "watch")
        self.assertFalse(snapshot["highlights"][0]["read"])
        self.assertFalse(snapshot["highlights"][0]["bookmarked"])
        response = await self.client.post(
            route, json={"event_id": "decision-evidence", "decision": None}
        )
        self.assertEqual(response.status, 200, await response.text())
        self.assertEqual(
            (await self._get("/api/radar"))["topics"][0]["metrics"]["decided"]["watch"], 0
        )

    async def test_auth_csrf_json_validation_and_no_fake_billing(self):
        response = await self.client.get("/api/plans")
        comparison = await response.json()
        self.assertEqual(response.status, 200)
        self.assertEqual(comparison["current_plan_id"], "analyst")
        self.assertFalse(comparison["billing_enabled"])
        self.assertIn("未开通", comparison["pricing_disclaimer"])
        self.assertEqual([p["limits"]["max_topics"] for p in comparison["plans"]], [1, 10, 30])
        self.assertEqual([p["limits"]["history_days"] for p in comparison["plans"]], [7, 30, 90])
        self.assertTrue(all(not p["pricing"]["billing_active"] for p in comparison["plans"]))

        self.client.session.headers.pop("X-CSRF-Token")
        response = await self.client.post("/api/radar/topics", json={"name": "a", "query": "b"})
        self.assertEqual(response.status, 403)
        self.assertEqual((await response.json())["error"]["code"], "csrf_rejected")
        self.client.session.headers.update({"X-CSRF-Token": self.csrf})
        for payload in (
            {"name": "a" * 49, "query": "term"},
            {"name": "title", "query": "x" * 161},
            {"name": "title", "query": "1 2 3 4 5 6 7 8 9"},
            {"name": "title", "query": "term", "platforms": ["x", "x"]},
            {"name": "title", "query": "term", "platforms": ["invalid"]},
            {"name": "title", "query": "term", "min_importance": True},
            {"name": "title", "query": "term", "min_importance": 101},
            {"name": "title", "query": "term", "plan": "analyst"},
        ):
            response = await self.client.post("/api/radar/topics", json=payload)
            self.assertEqual(response.status, 422, (payload, await response.text()))
            self.assertIn("message", (await response.json())["error"])
        response = await self.client.post(
            "/api/radar/topics", data="{oops", headers={"Content-Type": "application/json"}
        )
        self.assertEqual(response.status, 400)
        self.assertEqual((await response.json())["error"]["code"], "invalid_json")
        response = await self.client.post(
            "/api/radar/topics", data="name=x", headers={"Content-Type": "text/plain"}
        )
        self.assertEqual(response.status, 415)

        topic = await self._create()
        response = await self.client.post(
            f"/api/radar/topics/{topic['id']}/review", json={"unexpected": True}
        )
        self.assertEqual(response.status, 422)
        response = await self.client.patch(
            f"/api/radar/topics/{topic['id']}",
            json={"min_importance": "10", "version": topic["version"]},
        )
        self.assertEqual(response.status, 422)
        self.assertIsNone((await self._get("/api/radar"))["topics"][0]["last_reviewed_at"])


if __name__ == "__main__":
    unittest.main()
