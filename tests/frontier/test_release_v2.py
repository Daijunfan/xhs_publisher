"""Release failure gates against real temporary files/SQLite, with no live services."""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import sqlite3
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "frontier_release_under_test", Path(__file__).resolve().parents[2] / "ops/frontier_release.py"
)
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)
ARCHIVE_SPEC = importlib.util.spec_from_file_location(
    "frontier_archive_under_test", Path(__file__).resolve().parents[2] / "ops/frontier_archive.py"
)
archive = importlib.util.module_from_spec(ARCHIVE_SPEC)
ARCHIVE_SPEC.loader.exec_module(archive)


class ReleaseV2Tests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="frontier-release-v2-")
        self.addCleanup(self.temporary.cleanup)
        # macOS temp directories can be /var -> /private/var symlinks.
        # Release code canonicalizes the root; fixture expectations must too.
        self.root = Path(self.temporary.name).resolve()
        self.candidate = self.root / "runtime/candidate"
        self.database = self.root / "runtime/frontier/events.sqlite3"
        self.database.parent.mkdir(parents=True)
        with sqlite3.connect(self.database) as c:
            c.execute("CREATE TABLE fixture(value TEXT)")
            c.execute("INSERT INTO fixture VALUES('before')")
        self.existing = self.root / "src/changed.py"
        self.existing.parent.mkdir()
        self.existing.write_text("before = True\n")
        self.static = self.root / "src/xhs_local/frontier/static/index.html"
        self.static.parent.mkdir(parents=True)
        self.static.write_text("old frontend")
        candidate_static = self.candidate / "src/xhs_local/frontier/static/index.html"
        candidate_static.parent.mkdir(parents=True)
        candidate_static.write_text("reviewed frontend")
        self.manifest = self.root / "reviewed-manifest.json"
        self.files = {
            "src/changed.py": {"content": "after = True\n", "old_sha256": hashlib.sha256(self.existing.read_bytes()).hexdigest()},
            "src/added.py": {"content": "new_file = True\n", "old_sha256": None},
        }
        for entry in self.files.values():
            entry["sha256"] = hashlib.sha256(entry["content"].encode()).hexdigest()
        self.manifest.write_text(json.dumps({"version": 2, "files": self.files}))
        self.args = SimpleNamespace(root=self.root, candidate=self.candidate, manifest=self.manifest)
        self.units = {name: True for name in release.UNITS}
        self.calls = []
        self.stop_failures = 0

    def run_command(self, command, *, check=False, **_kwargs):
        self.calls.append(command)
        if command[0] == "systemctl":
            action = command[2]
            if action == "stop":
                self.units[release.UNITS[0]] = False
                if self.stop_failures:
                    self.stop_failures -= 1
                    if check:
                        raise subprocess.CalledProcessError(1, command)
                    return SimpleNamespace(returncode=1)
                self.units[release.UNITS[1]] = False
            elif action == "start":
                self.units = {name: True for name in release.UNITS}
            return SimpleNamespace(returncode=0)
        with sqlite3.connect(self.database) as c:
            c.execute("UPDATE fixture SET value='after migration'")
        return SimpleNamespace(returncode=0)

    def database_value(self, path=None):
        with sqlite3.connect(path or self.database) as c:
            return c.execute("SELECT value FROM fixture").fetchone()[0]

    def test_unreviewed_file_at_new_path_blocks_before_stopping_any_unit(self):
        (self.root / "src/added.py").write_text("a concurrent developer's file\n")
        with patch.object(release.subprocess, "run", side_effect=self.run_command), self.assertRaises(RuntimeError):
            release.deploy(self.args)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.existing.read_text(), "before = True\n")
        self.assertEqual(self.database_value(), "before")

    def test_partial_stop_failure_restarts_both_original_units(self):
        self.stop_failures = 1
        with patch.object(release.subprocess, "run", side_effect=self.run_command), self.assertRaises(subprocess.CalledProcessError):
            release.deploy(self.args)
        self.assertTrue(all(self.units.values()))
        self.assertEqual(self.existing.read_text(), "before = True\n")
        self.assertEqual(self.static.read_text(), "old frontend")
        self.assertEqual(self.database_value(), "before")

    def time_plan_args(self, database):
        plan = self.root / "runtime/reviewed-time-plan.json"
        plan.write_text(json.dumps({"version": "event-time-week-precision-v1", "database": str(database),
                                   "generated_at": "2026-10-18T08:00:00.000+00:00", "records": []}))
        self.args.time_plan = plan
        self.args.time_plan_sha256 = hashlib.sha256(plan.read_bytes()).hexdigest()

    def test_candidate_time_plan_cannot_be_substituted_for_production(self):
        self.time_plan_args(self.candidate / "data/events.sqlite3")
        with patch.object(release.subprocess, "run", side_effect=self.run_command), \
                self.assertRaisesRegex(RuntimeError, "separate reviewed time plan"):
            release.deploy(self.args)
        self.assertEqual(self.calls, [])
        self.assertTrue(all(self.units.values()))

    def test_time_repair_failure_recovers_the_entire_release_checkpoint(self):
        self.time_plan_args(self.database)

        def fail_repair(command, **kwargs):
            if "time-repair" in command:
                raise subprocess.CalledProcessError(1, command)
            return self.run_command(command, **kwargs)

        with patch.object(release.subprocess, "run", side_effect=fail_repair), \
                patch.object(release, "wait_health", return_value={"ready": True, "version": "previous"}), \
                redirect_stdout(io.StringIO()), self.assertRaises(subprocess.CalledProcessError):
            release.deploy(self.args)
        self.assertTrue(all(self.units.values()))
        self.assertEqual(self.existing.read_text(), "before = True\n")
        self.assertEqual(self.static.read_text(), "old frontend")
        self.assertFalse((self.root / "src/added.py").exists())
        self.assertEqual(self.database_value(), "before")

    def test_failed_post_deployment_health_restores_code_and_database(self):
        health = [RuntimeError("forced readiness failure"), {"ready": True, "version": "previous"}]
        with patch.object(release.subprocess, "run", side_effect=self.run_command), \
                patch.object(release, "wait_health", side_effect=health) as gate, redirect_stdout(io.StringIO()), \
                self.assertRaisesRegex(RuntimeError, "forced readiness failure"):
            release.deploy(self.args)
        self.assertEqual(gate.call_count, 2)
        self.assertTrue(all(self.units.values()))
        self.assertEqual(self.existing.read_text(), "before = True\n")
        self.assertFalse((self.root / "src/added.py").exists())
        self.assertEqual(self.static.read_text(), "old frontend")
        self.assertEqual(self.database_value(), "before")

    def test_successful_deployment_retains_verified_original_checkpoint(self):
        with patch.object(release.subprocess, "run", side_effect=self.run_command), \
                patch.object(release, "wait_health", return_value={"ready": True, "version": "2.0.0"}) as gate, \
                redirect_stdout(io.StringIO()):
            release.deploy(self.args)
        gate.assert_called_once_with(self.root, version="2.0.0")
        self.assertTrue(all(self.units.values()))
        self.assertEqual(self.existing.read_text(), self.files["src/changed.py"]["content"])
        self.assertEqual(self.database_value(), "after migration")
        checkpoint = next((self.root / "runtime/frontier/releases").iterdir())
        self.assertEqual(self.database_value(checkpoint / "events-before.sqlite3"), "before")
        self.assertTrue((checkpoint / "deployed.json").is_file())

    def test_manual_rollback_preserves_state_written_since_deployment(self):
        with patch.object(release.subprocess, "run", side_effect=self.run_command), \
                patch.object(release, "wait_health", return_value={"ready": True, "version": "2.0.0"}), \
                redirect_stdout(io.StringIO()):
            release.deploy(self.args)
            checkpoint = next((self.root / "runtime/frontier/releases").iterdir())
            with sqlite3.connect(self.database) as c:
                c.execute("UPDATE fixture SET value='new user state after release'")
            release.rollback(SimpleNamespace(root=self.root, release=checkpoint))
        self.assertEqual(self.database_value(), "before")
        preserved = next(checkpoint.glob("before-manual-rollback-*"))
        self.assertEqual(self.database_value(preserved / "events.sqlite3"), "new user state after release")
        self.assertTrue((preserved / "source.tar.gz").is_file())
        self.assertTrue(all(self.units.values()))


class ArchiveV2Tests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="frontier-git-v2-")
        self.addCleanup(self.temporary.cleanup)
        self.work = Path(self.temporary.name)
        self.repo = self.work / "repository"
        self.repo.mkdir()
        subprocess.run(["git", "init", "--quiet", "-b", "review-branch", str(self.repo)], check=True)
        archive.git(self.repo, "config", "user.name", "Local release fixture")
        archive.git(self.repo, "config", "user.email", "release-fixture@example.invalid")
        initial = {"src/core.py": "before = True\n", "frontend/src/main.js": "old frontend source",
                   "src/xhs_local/frontier/static/index.html": "old bundle", ".gitignore": "runtime/\n",
                   "unrelated.txt": "before unrelated staged edit", "notes.txt": "before unstaged edit"}
        for name, content in initial.items():
            path = self.repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        archive.git(self.repo, "add", ".")
        archive.git(self.repo, "commit", "--quiet", "-m", "Isolated fixture baseline")
        head = archive.git(self.repo, "rev-parse", "HEAD").stdout.decode().strip()
        (self.repo / "unrelated.txt").write_text("a pre-existing staged user change")
        archive.git(self.repo, "add", "unrelated.txt")
        (self.repo / "notes.txt").write_text("a pre-existing unstaged user change")
        self.backend_manifest = self.work / "backend.json"
        data = "after = True\n".encode()
        self.backend_manifest.write_text(json.dumps({"files": {"src/core.py": {"content": data.decode(), "sha256": hashlib.sha256(data).hexdigest()}}}))
        frontend_manifest = self.work / "frontend.json"
        frontend_manifest.write_text(json.dumps({"src/main.js": "reviewed frontend source"}))
        static = self.work / "reviewed-static"
        static.mkdir()
        (static / "index.html").write_text("reviewed bundle")
        self.args = SimpleNamespace(repo=self.repo, expected_head=head, expected_branch="review-branch",
                                    backend_manifest=self.backend_manifest, frontend_manifest=frontend_manifest,
                                    static=static, plan=self.work / "plan.json")

    def test_scoped_commit_preserves_unrelated_staged_and_unstaged_changes(self):
        with redirect_stdout(io.StringIO()):
            archive.sync_xhs(self.args)
            archive.commit(SimpleNamespace(plan=self.args.plan, message="Review scope fixture\n\nOnly the three reviewed source paths."))
        changed = archive.git(self.repo, "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD").stdout.decode().splitlines()
        self.assertEqual(set(changed), {"src/core.py", "frontend/src/main.js", "src/xhs_local/frontier/static/index.html"})
        staged = archive.git(self.repo, "diff", "--cached", "--name-only").stdout.decode().splitlines()
        self.assertEqual(staged, ["unrelated.txt"])
        self.assertEqual(archive.blob(self.repo, "", "unrelated.txt"), b"a pre-existing staged user change")
        self.assertEqual((self.repo / "notes.txt").read_text(), "a pre-existing unstaged user change")
        self.assertEqual(archive.git(self.repo, "symbolic-ref", "--short", "HEAD").stdout.decode().strip(), "review-branch")

    def test_unrelated_change_inside_source_scope_blocks_before_any_sync_write(self):
        (self.repo / "src/core.py").write_text("a concurrent source edit")
        with self.assertRaisesRegex(RuntimeError, "unrelated local changes"):
            archive.sync_xhs(self.args)
        self.assertEqual((self.repo / "src/core.py").read_text(), "a concurrent source edit")
        self.assertEqual((self.repo / "frontend/src/main.js").read_text(), "old frontend source")
        self.assertFalse(self.args.plan.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
