"""Occurrence precision regression gates; no models, collectors or network calls."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from xhs_local.frontier.models import validate_analysis
from xhs_local.frontier.store import Store
from xhs_local.frontier.time_quality import apply_week_repairs, plan_week_repairs, week_point_without_day

SPEC = importlib.util.spec_from_file_location(
    "frontier_time_release_under_test", Path(__file__).resolve().parents[2] / "ops/frontier_release.py"
)
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


def proposed(evidence, *, start="2026-10-10T00:00:00.000+00:00", end=None, precision="day"):
    return {"is_event": True, "title": "A concrete conference event", "summary": "Evidence fixture.",
            "category": "science", "tags": [], "score_components": {
                "impact": 60, "scope": 40, "novelty": 50, "urgency": 30},
            "score_reason": "Test evidence explains the score.", "locations": [], "location_status": "global",
            "event_time_start": start, "event_time_end": end, "event_time_precision": precision,
            "event_time_status": "inferred", "event_time_evidence": evidence, "event_timezone": "UTC"}


class TimeEvidenceV2Tests(unittest.TestCase):
    def validated(self, evidence, **kwargs):
        return validate_analysis(proposed(evidence, **kwargs), {"title": "", "text": evidence})

    def test_month_abbreviations_are_supported_only_as_real_quoted_date_tokens(self):
        for evidence, date, end_date in (
            ("Oct 16", "2026-10-16", None), ("Oct. 16", "2026-10-16", None),
            ("16 Oct", "2026-10-16", None), ("16th Oct.", "2026-10-16", None),
            ("Nov. 2–5", "2026-11-02", "2026-11-05"),
            ("Sept 9", "2026-09-09", None), ("Sep. 9", "2026-09-09", None),
        ):
            with self.subTest(evidence=evidence):
                start = date + "T00:00:00.000+00:00"
                end = end_date + "T00:00:00.000+00:00" if end_date else None
                self.assertEqual(self.validated(evidence, start=start, end=end)["event_time_start"], start)
        for evidence in ("Octopus 16", "Marathon 16", "archive Oct", "Oct 123"):
            with self.subTest(evidence=evidence):
                self.assertIsNone(self.validated(evidence)["event_time_start"])
        unsupported = validate_analysis(proposed("Oct 16"), {"title": "", "text": "The date was not reported."})
        self.assertIsNone(unsupported["event_time_start"], "A proposed date cannot supply its own missing evidence")

    def test_week_only_point_with_or_without_equal_end_is_unknown_and_retains_quote(self):
        evidence = "at this week's LPC2026 conference in Prague"
        for end in (None, "2026-10-10T00:00:00.000+00:00"):
            for precision in ("day", "exact", "range"):
                with self.subTest(end=end, precision=precision):
                    result = self.validated(evidence, end=end, precision=precision)
                    self.assertIsNone(result["event_time_start"])
                    self.assertIsNone(result["event_time_end"])
                    self.assertIsNone(result["event_timezone"])
                    self.assertEqual(result["event_time_precision"], "unknown")
                    self.assertEqual(result["event_time_status"], "unknown")
                    self.assertEqual(result["event_time_evidence"], evidence)
                    self.assertIn("具体日期", result["event_time_note"])

    def test_real_intervals_and_week_with_explicit_day_are_preserved(self):
        examples = [
            ("this week, on Oct 16", "2026-10-16T00:00:00.000+00:00", None),
            ("this week, on Friday", "2026-10-16T00:00:00.000+00:00", None),
            ("this week from October 12 to October 18", "2026-10-12T00:00:00.000+00:00", "2026-10-18T00:00:00.000+00:00"),
            ("2026 年上半年", "2026-01-01T00:00:00.000+00:00", "2026-06-30T00:00:00.000+00:00"),
            ("政策自 2026 年 10 月 12 日生效，至 2027 年 12 月 31 日截止", "2026-10-12T00:00:00.000+00:00", "2027-12-31T00:00:00.000+00:00"),
            ("Nov 2-5", "2026-11-02T00:00:00.000+00:00", "2026-11-05T00:00:00.000+00:00"),
            ("The week runs October 16-25", "2026-10-16T00:00:00.000+00:00", "2026-10-25T00:00:00.000+00:00"),
        ]
        for evidence, start, end in examples:
            with self.subTest(evidence=evidence):
                result = self.validated(evidence, start=start, end=end)
                self.assertEqual(result["event_time_start"], start)
                self.assertEqual(result["event_time_end"], end)
                self.assertEqual(result["event_time_precision"], "day")
                self.assertNotIn("event_time_note", result)
        # A non-point interval is outside this specifically approved withdrawal rule.
        self.assertFalse(week_point_without_day(proposed("this week's conference", end="2026-10-16T00:00:00.000+00:00")))


class TimeRepairV2Tests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="frontier-time-v2-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.candidate = self.root / "runtime/candidate"
        self.store = Store(self.candidate / "data/events.sqlite3")
        self.at = datetime.now(UTC).isoformat(timespec="milliseconds")
        self.put("a-week", "at this week's LPC2026 conference in Prague", end="2026-10-10T00:00:00.000+00:00")
        self.put("b-week-no-end", "this week's second conference")
        self.put("c-half", "2026 年上半年", start="2026-01-01T00:00:00.000+00:00", end="2026-06-30T00:00:00.000+00:00")
        self.put("d-day", "October 10", end="2026-10-10T00:00:00.000+00:00")
        self.put("e-unknown", "Oct 16", start=None, precision="unknown")
        with self.store.connect() as c:
            c.execute("INSERT INTO bookmarks VALUES('owner','a-week',?)", (self.at,))
            c.execute("INSERT INTO event_reads VALUES('owner','a-week',?)", (self.at,))
            c.execute("INSERT INTO raw_reads VALUES('owner','raw-a-week',?)", (self.at,))
            c.execute("INSERT INTO usage VALUES('2026-10-18',1998,333,644939,289831)")

    def put(self, identity, evidence, **kwargs):
        data = proposed(evidence, **kwargs)
        data.update(id=identity, title=identity, importance=50, enrichment_status="completed", analysed_at=self.at)
        data.pop("is_event")
        if not data["event_time_start"]:
            data["event_time_status"] = "unknown"
        with self.store.connect() as c:
            c.execute(
                "INSERT INTO events VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (identity, identity, data["summary"], "science", 50, data["event_time_start"], "global",
                 json.dumps(data, ensure_ascii=False), self.at, self.at, self.at),
            )
            c.execute(
                "INSERT INTO raw_records(record_id,fingerprint,content_hash,plugin_id,source_name,title,text,"
                "source_published_at,ingested_at,state,event_id,updated_at,first_ingested_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                ("raw-" + identity, identity, identity, "telegram", "Fixture source", "", evidence,
                 "2026-10-12T08:00:00.000+00:00", self.at, "completed", identity, self.at, self.at),
            )

    def plan(self):
        with sqlite3.connect(self.store.path.as_uri() + "?mode=ro", uri=True) as c:
            return plan_week_repairs(c)

    def apply(self, plan):
        digest = hashlib.sha256(json.dumps(plan).encode()).hexdigest()
        with sqlite3.connect(self.store.path) as c:
            return apply_week_repairs(c, plan, plan_sha256=digest)

    def snapshot(self):
        with self.store.connect() as c:
            return {table: [tuple(row) for row in c.execute("SELECT * FROM " + table + " ORDER BY 1")]
                    for table in ("raw_records", "bookmarks", "event_reads", "raw_reads", "usage")}

    def test_repair_preserves_all_other_state_and_occurrence_indexes_match_json(self):
        untouched = self.snapshot()
        before = {identity: self.store.get_event(identity) for identity in ("c-half", "d-day", "e-unknown")}
        plan = self.plan()
        self.assertEqual([item["event_id"] for item in plan["records"]], ["a-week", "b-week-no-end"])
        self.assertEqual(self.apply(plan)["changed"], 2)
        self.assertEqual(self.snapshot(), untouched)
        with self.store.connect() as c:
            for identity in ("a-week", "b-week-no-end"):
                row = c.execute("SELECT data,event_time_start FROM events WHERE id=?", (identity,)).fetchone()
                data = json.loads(row["data"])
                self.assertIsNone(row["event_time_start"])
                self.assertIsNone(data["event_time_start"])
                self.assertIn("此前", data["event_time_note"])
                self.assertEqual(data["id"], identity)
            journal = c.execute("SELECT * FROM event_time_repairs WHERE event_id='a-week'").fetchone()
            self.assertEqual(json.loads(journal["before_row"]), plan["records"][0]["before"])
            self.assertEqual(json.loads(journal["after_row"]), plan["records"][0]["after"])
        for identity, previous in before.items():
            self.assertEqual(self.store.get_event(identity), previous)
        ordered = self.store.list_events({"scope": "all", "sort": "event_time", "read": "all"})["items"]
        self.assertEqual([item["id"] for item in ordered[:2]], ["d-day", "c-half"])
        filtered = self.store.list_events({"scope": "all", "after": "2026-10-01", "read": "all"})["items"]
        self.assertEqual([item["id"] for item in filtered], ["d-day"])

    def test_reapply_is_a_noop_and_journal_is_immutable_after_additive_migration(self):
        plan = self.plan()
        self.apply(plan)
        with self.store.connect() as c:
            c.execute("ALTER TABLE events ADD COLUMN future_additive_column TEXT")
        result = self.apply(plan)
        self.assertEqual(result["changed"], 0)
        self.assertEqual(result["already_applied"], 2)
        self.assertEqual(self.plan()["records"], [])
        with self.store.connect() as c:
            self.assertEqual(c.execute("SELECT count(*) FROM event_time_repairs").fetchone()[0], 2)
            for query in ("UPDATE event_time_repairs SET applied_at='modified'", "DELETE FROM event_time_repairs"):
                with self.assertRaisesRegex(sqlite3.IntegrityError, "immutable"):
                    c.execute(query)

    def test_stale_plan_or_changed_quote_rejects_every_repair_before_journal_creation(self):
        plan = self.plan()
        with self.store.connect() as c:
            c.execute("UPDATE events SET summary='A concurrent correction' WHERE id='b-week-no-end'")
        with self.assertRaisesRegex(RuntimeError, "changed"):
            self.apply(plan)
        self.assertIsNotNone(self.store.get_event("a-week")["event_time_start"])
        plan = self.plan()
        with self.store.connect() as c:
            c.execute("UPDATE raw_records SET text='The original quote changed' WHERE record_id='raw-b-week-no-end'")
        with self.assertRaisesRegex(RuntimeError, "quote context changed"):
            self.apply(plan)
        self.assertIsNotNone(self.store.get_event("a-week")["event_time_start"])
        with self.store.connect() as c:
            self.assertIsNone(c.execute("SELECT 1 FROM sqlite_master WHERE name='event_time_repairs'").fetchone())

    def test_cli_plan_requires_correct_database_digest_and_creates_verified_backup_before_apply(self):
        args = SimpleNamespace(root=self.root, candidate=self.candidate, database=self.store.path,
                               plan=self.root / "runtime/qa-time-plan.json")
        before = self.snapshot()
        with redirect_stdout(io.StringIO()) as output:
            release.time_plan(args)
        report = json.loads(output.getvalue())
        self.assertEqual(report["planned"], 2)
        self.assertEqual(self.snapshot(), before)
        args.expected_plan_sha256 = "0" * 64
        with self.assertRaisesRegex(RuntimeError, "changed since review"):
            release.time_repair(args)
        args.expected_plan_sha256 = report["sha256"]
        with redirect_stdout(io.StringIO()) as output:
            release.time_repair(args)
        applied = json.loads(output.getvalue())
        self.assertEqual(applied["changed"], 2)
        backup = Path(applied["backup"])
        self.assertEqual(hashlib.sha256(backup.read_bytes()).hexdigest(), applied["backup_sha256"])
        with sqlite3.connect(backup.as_uri() + "?mode=ro", uri=True) as c:
            self.assertEqual(c.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertIsNotNone(c.execute("SELECT event_time_start FROM events WHERE id='a-week'").fetchone()[0])
        self.assertEqual(self.snapshot(), before)
        args.database = self.root / "runtime/frontier/events.sqlite3"
        Store(args.database)
        with self.assertRaisesRegex(RuntimeError, "separate reviewed time plan"):
            release.time_repair(args)
        args.database = self.root / "runtime/app.sqlite3"
        args.database.touch()
        with self.assertRaisesRegex(RuntimeError, "derived event database"):
            release.time_repair(args)

    def test_mid_transaction_failure_rolls_back_both_event_changes_and_new_journal(self):
        plan = self.plan()
        with self.store.connect() as c:
            c.execute(
                "CREATE TRIGGER fixture_second_row_failure BEFORE UPDATE ON events "
                "WHEN OLD.id='b-week-no-end' BEGIN SELECT RAISE(ABORT,'injected storage failure'); END"
            )
        with self.assertRaisesRegex(sqlite3.IntegrityError, "injected storage failure"):
            self.apply(plan)
        self.assertIsNotNone(self.store.get_event("a-week")["event_time_start"])
        self.assertIsNotNone(self.store.get_event("b-week-no-end")["event_time_start"])
        with self.store.connect() as c:
            self.assertIsNone(c.execute("SELECT 1 FROM sqlite_master WHERE name='event_time_repairs'").fetchone())


if __name__ == "__main__":
    unittest.main(verbosity=2)
