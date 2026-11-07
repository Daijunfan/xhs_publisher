"""Independent fault-injection gates for the narrow approved time repair.

Only temporary SQLite databases are used. No browser, socket, collector, model,
production credential, or real project database is accessed.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import io
import json
import sqlite3
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from xhs_local.frontier import time_quality

BACKEND = Path(time_quality.__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location(
    "time_repair_fixture_for_independent_audit",
    BACKEND / "tests/frontier/test_time_quality_v2.py",
)
fixture_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixture_module)


class IndependentTimeRepairChecks(unittest.TestCase):
    def setUp(self):
        # Reuse only the temporary fixture setup. Do not inherit or duplicate its
        # seven test methods; these checks target three additional failure modes.
        self.fixture = fixture_module.TimeRepairV2Tests(methodName="runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def complete_snapshot(self):
        with self.fixture.store.connect() as c:
            events = [tuple(row) for row in c.execute("SELECT * FROM events ORDER BY id")]
            schema = [tuple(row) for row in c.execute(
                "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name"
            )]
        return {"events": events, "schema": schema, "other": self.fixture.snapshot()}

    def test_failure_during_second_update_rolls_back_first_update_and_journal_schema(self):
        plan = self.fixture.plan()
        self.assertEqual(len(plan["records"]), 2)
        with self.fixture.store.connect() as c:
            c.execute(
                "CREATE TRIGGER audit_fail_second BEFORE UPDATE ON events "
                "WHEN OLD.id='b-week-no-end' "
                "BEGIN SELECT RAISE(ABORT,'audit_injected_second_write_failure'); END"
            )
        before = self.complete_snapshot()
        with self.assertRaisesRegex(sqlite3.IntegrityError, "second_write_failure"):
            self.fixture.apply(plan)
        self.assertEqual(self.complete_snapshot(), before,
                         "A mid-transaction failure left a partial event or schema repair")

    def test_rehashed_plan_with_unrelated_change_is_rejected_without_mutation(self):
        plan = copy.deepcopy(self.fixture.plan())
        before = self.complete_snapshot()
        plan["records"][0]["after"]["summary"] = "An unrelated field must not change"
        plan["records"][0]["after_sha256"] = hashlib.sha256(
            json.dumps(plan["records"][0]["after"], ensure_ascii=False,
                       sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        with self.assertRaisesRegex(ValueError, "out-of-scope"):
            self.fixture.apply(plan)
        self.assertEqual(self.complete_snapshot(), before)

    def test_failed_full_database_backup_prevents_any_repair(self):
        args = SimpleNamespace(
            root=self.fixture.root, candidate=self.fixture.candidate,
            database=self.fixture.store.path,
            plan=self.fixture.root / "runtime/independent-reviewed-time-plan.json",
        )
        with redirect_stdout(io.StringIO()) as output:
            fixture_module.release.time_plan(args)
        args.expected_plan_sha256 = json.loads(output.getvalue())["sha256"]
        before = self.complete_snapshot()
        with patch.object(fixture_module.release, "backup_readonly",
                          side_effect=RuntimeError("audit_injected_backup_failure")):
            with self.assertRaisesRegex(RuntimeError, "backup_failure"):
                fixture_module.release.time_repair(args)
        self.assertEqual(self.complete_snapshot(), before)
        self.assertEqual(list(self.fixture.store.path.parent.glob("time-repairs/*/applied.json")), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
