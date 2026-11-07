"""V3 release signoff: all tests use disposable SQLite/static and mocked systemd."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "release_v3_for_tests",
    Path(__file__).resolve().parents[2] / "ops/frontier_release.py",
)
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


def sha(data):
    return hashlib.sha256(data).hexdigest()


class SignedReleaseTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="frontier-v3-release-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.candidate = self.root / "runtime/frontier-v3-candidate-qa"
        self.database = self.root / "runtime/frontier/events.sqlite3"
        self.database.parent.mkdir(parents=True)
        with sqlite3.connect(self.database) as c:
            c.execute("CREATE TABLE fixture(value TEXT)")
            c.execute("INSERT INTO fixture VALUES('before')")
        self.old = self.root / "src/old.py"
        self.old.parent.mkdir(parents=True)
        self.old.write_text("old = True\n")
        self.current_static = self.root / release.STATIC_REL
        self.current_static.mkdir(parents=True)
        (self.current_static / "index.html").write_text("old index")
        (self.current_static / "assets").mkdir()
        (self.current_static / "assets/old.js").write_text("old js")
        self.new_static = self.candidate / release.STATIC_REL
        self.new_static.mkdir(parents=True)
        (self.new_static / "index.html").write_text("V3 bundled")
        (self.new_static / "assets").mkdir()
        (self.new_static / "assets/app.js").write_text("reviewed v3 js")
        files = {}
        for name, content in {
            "src/old.py": "old = False\n",
            "src/xhs_local/frontier/__init__.py": '__version__="3.0.0"\n',
            "ops/frontier_release.py": "# reviewed runtime gate\n",
        }.items():
            target = self.root / name
            files[name] = {
                "content": content,
                "old_sha256": sha(target.read_bytes()) if target.is_file() else None,
                "sha256": sha(content.encode()),
            }
        self.manifest_data = {
            "version": 3,
            "release_version": "3.0.0",
            "files": files,
            "static_files": {
                item.relative_to(self.new_static).as_posix(): sha(item.read_bytes())
                for item in self.new_static.rglob("*")
                if item.is_file()
            },
        }
        self.manifest = self.root / "manifest.json"
        self.save()
        self.args = SimpleNamespace(
            root=self.root, candidate=self.candidate, manifest=self.manifest
        )
        self.actions = []

    def save(self):
        self.manifest.write_text(json.dumps(self.manifest_data))

    def system(self, command, *, check=False, **_kwargs):
        if command[0] == "systemctl":
            self.actions.append(command[2])
        else:
            with sqlite3.connect(self.database) as c:
                c.execute("UPDATE fixture SET value='after'")
        return SimpleNamespace(returncode=0)

    def row(self):
        with sqlite3.connect(self.database) as c:
            return c.execute("SELECT value FROM fixture").fetchone()[0]

    def patched_deploy(self, probe=None, *, fail=False):
        product = probe if probe is not None else {"v3_checked": True, "static_files_verified": 2}
        with (
            patch.object(release.subprocess, "run", side_effect=self.system),
            patch.object(
                release,
                "wait_health",
                side_effect=([{"version": "3.0.0"}, {"version": "2.0.0"}] if fail else None),
                return_value={"version": "3.0.0"},
            ) as health,
            patch.object(
                release,
                "verify_v3_service",
                side_effect=(RuntimeError("intentional V3 smoke failure") if fail else None),
                return_value=product,
            ) as verified,
            redirect_stdout(io.StringIO()),
        ):
            release.deploy(self.args)
        health.assert_called_once_with(self.root, version="3.0.0")
        verified.assert_called_once()
        return next((self.root / "runtime/frontier/releases").iterdir())

    def test_tampered_static_rejected_before_service_stop(self):
        (self.new_static / "assets/app.js").write_text("tamper")
        with patch.object(release.subprocess, "run", side_effect=self.system):
            with self.assertRaisesRegex(RuntimeError, "SHA256"):
                release.deploy(self.args)
        self.assertEqual(self.actions, [])
        self.assertEqual(self.row(), "before")

    def test_unreviewed_file_and_symlink_rejected(self):
        extra = self.new_static / "assets/unreviewed.js"
        extra.write_text("evil")
        with self.assertRaisesRegex(RuntimeError, "unreviewed"):
            release.validate_static_assets(self.new_static, self.manifest_data)
        extra.unlink()
        extra.symlink_to(self.old)
        with self.assertRaisesRegex(RuntimeError, "symlink"):
            release.validate_static_assets(self.new_static, self.manifest_data)

    def test_invalid_manifest_and_candidate_scope_rejected_before_stop(self):
        saved = self.manifest_data.pop("static_files")
        self.save()
        with self.assertRaisesRegex(RuntimeError, "reviewed frontend"):
            release.deploy(self.args)
        self.manifest_data["static_files"] = saved
        self.save()
        self.args.candidate = self.root / "src"
        with self.assertRaisesRegex(RuntimeError, "QA clone"):
            release.deploy(self.args)
        self.assertEqual(self.actions, [])

    def test_signed_static_atomic_replacement_and_version_gate(self):
        checkpoint = self.patched_deploy()
        self.assertEqual(self.actions, ["stop", "start"])
        self.assertEqual(self.row(), "after")
        self.assertTrue(checkpoint.name.startswith("v3-"))
        self.assertEqual((self.current_static / "index.html").read_text(), "V3 bundled")
        self.assertTrue((self.current_static / "assets/app.js").is_file())
        self.assertFalse((self.current_static / "assets/old.js").exists())
        self.assertTrue((checkpoint / "events-before.sqlite3").is_file())
        self.assertTrue(
            json.loads((checkpoint / "deployed.json").read_text())["product"]["v3_checked"]
        )

    def test_failed_v3_smoke_restores_previous_code_static_and_db(self):
        with self.assertRaisesRegex(RuntimeError, "intentional V3 smoke failure"):
            self.patched_deploy(fail=True)
        self.assertEqual(self.row(), "before")
        self.assertEqual(self.old.read_text(), "old = True\n")
        self.assertEqual((self.current_static / "index.html").read_text(), "old index")
        self.assertFalse((self.current_static / "assets/app.js").exists())
        self.assertTrue((self.current_static / "assets/old.js").exists())
        checkpoint = next((self.root / "runtime/frontier/releases").iterdir())
        self.assertTrue((checkpoint / "events-failed-upgrade.sqlite3").is_file())
        self.assertEqual(self.actions, ["stop", "start", "stop", "start"])

    def test_manual_v3_rewind_requires_ack_and_saves_new_user_edits(self):
        checkpoint = self.patched_deploy()
        with sqlite3.connect(self.database) as c:
            c.execute("UPDATE fixture SET value='new user decision'")
        with self.assertRaisesRegex(RuntimeError, "--allow-data-rewind"):
            release.rollback(SimpleNamespace(root=self.root, release=checkpoint))
        self.assertEqual(self.row(), "new user decision")
        with (
            patch.object(release.subprocess, "run", side_effect=self.system),
            patch.object(release, "wait_health", return_value={"ready": True}),
            redirect_stdout(io.StringIO()),
        ):
            release.rollback(
                SimpleNamespace(root=self.root, release=checkpoint, allow_data_rewind=True)
            )
        self.assertEqual(self.row(), "before")
        backup = next(checkpoint.glob("before-manual-rollback-*"))
        with sqlite3.connect(backup / "events.sqlite3") as c:
            self.assertEqual(
                c.execute("SELECT value FROM fixture").fetchone()[0],
                "new user decision",
            )
        self.assertEqual((self.current_static / "index.html").read_text(), "old index")


if __name__ == "__main__":
    unittest.main()
