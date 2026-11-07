#!/usr/bin/env python3
"""V99 single-writer, date-pinned Frontier cloud daily release dispatcher.

This is a production-capable wrapper of the EXISTING ops/frontier_release.py,
not a second publisher. Write-capable modes are the normal --scheduled real
Beijing 20:00-20:14 window or an expressly owner-authorized --immediate using
the real current clock, always on the known Linux production root. Both need
a new immutable date-bound QA candidate handoff; old releases never qualify.
--dry-run performs no writes or service changes, including on cloud.
All cooperative deploy entrypoints must hold the SAME inode. The V103
publisher CLI has a native lock with inherited-FD handoff. The existing daily
timer and a manual immediate call share the SAME installed writer and lock;
an already COMMITTED real Beijing date safely returns ALREADY_COMMITTED_TODAY.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import platform
import re
import shutil
import sqlite3
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
from contextlib import closing, contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
from zoneinfo import ZoneInfo

BJ = ZoneInfo("Asia/Shanghai")
PRODUCTION_ROOT = Path(__file__).resolve().parents[1]
STATIC = Path("src/xhs_local/frontier/static")
STATE = Path("runtime/frontier/daily-dispatch")
HANDOFF = Path("runtime/frontier/daily-handoff")
MARKER = ".frontier-v99-disposable-fixture"
SHA = re.compile(r"[0-9a-f]{64}\Z")
DATE = re.compile(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}\Z")
SOURCE_REQUIRED = {"ops/frontier_release.py", "src/xhs_local/frontier/__init__.py"}
# Exact V132 baseline; only evidence_change.py is an admissible ninth source.
SOURCE8 = frozenset({
    "ops/frontier_release.py", "src/xhs_local/frontier/__init__.py",
    "src/xhs_local/frontier/dossier.py", "src/xhs_local/frontier/migrations.py",
    "src/xhs_local/frontier/models.py", "src/xhs_local/frontier/radar.py",
    "src/xhs_local/frontier/time_quality.py", "src/xhs_local/frontier/web.py",
})
NINTH_SOURCE = "src/xhs_local/frontier/evidence_change.py"
SOURCE9 = SOURCE8 | {NINTH_SOURCE}
FIRST_NINE_DATE = "2026-10-25"
UNITS = ("frontier-web.service", "frontier-collector.service")
MAX_JSON = 2_000_000
MAX_ASSET = 12 * 1024 * 1024
_ACTIVE_WRITER_FD: ContextVar[int | None] = ContextVar("frontier_v99_writer_fd", default=None)


class Hold(Exception):
    def __init__(self, code: str, reason: str):
        super().__init__(reason)
        self.code = code


def check(ok: bool, code: str, why: str) -> None:
    if not ok:
        raise Hold(code, why)


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def digest_ok(s: object) -> bool:
    return isinstance(s, str) and SHA.fullmatch(s) is not None


def path_name(name: object, *, scope: str) -> bool:
    if not isinstance(name, str) or not name or "\\" in name:
        return False
    parts = name.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        return False
    if scope == "source":
        return name.startswith(("ops/", "src/")) and not name.startswith("src/xhs_local/frontier/static/")
    if scope == "static":
        return not name.startswith(".") and not Path(name).is_absolute()
    return False


def scoped(root: Path, rel: str | Path, *, must_exist: bool = True) -> Path:
    """Lexical containment plus lstat every existing component: no link traversal."""
    rel = Path(rel)
    check(not rel.is_absolute() and all(x not in {".", "..", ""} for x in rel.parts),
          "HOLD_SCOPE", "Absolute, parent or empty release path")
    target = root / rel
    check(target.is_relative_to(root), "HOLD_SCOPE", "Path escapes root")
    node = root
    for part in rel.parts:
        node = node / part
        try:
            info = node.lstat()
        except FileNotFoundError:
            if must_exist:
                raise Hold("HOLD_MISSING_FILE", "Required pinned input is missing")
            continue
        check(not stat.S_ISLNK(info.st_mode), "HOLD_SYMLINK", "Symlink in release input")
    return target


def regular_bytes(path: Path, *, max_size: int, immutable: bool = False) -> bytes:
    try:
        before = path.lstat()
        check(stat.S_ISREG(before.st_mode) and 0 < before.st_size <= max_size,
              "HOLD_FILE", "Input is not a bounded regular file")
        if immutable:
            check((before.st_mode & 0o222) == 0, "HOLD_NOT_FROZEN",
                  "Handoff, reviewed manifest, receipt and candidate must be read-only")
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(fd, "rb") as stream:
            opened = os.fstat(stream.fileno())
            content = stream.read(max_size + 1)
            after = os.fstat(stream.fileno())
        named = path.lstat()
        identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        check(identity(before) == identity(opened) == identity(after) == identity(named),
              "HOLD_MUTABLE_INPUT", "Pinned inode changed during read")
        check(len(content) <= max_size, "HOLD_FILE", "Input exceeds byte limit")
        return content
    except Hold:
        raise
    except (OSError, ValueError) as exc:
        raise Hold("HOLD_INPUT_IO", "Pinned regular data could not be read") from exc


def json_input(root: Path, rel: str | Path, *, immutable: bool = False) -> tuple[dict, bytes, str]:
    path = scoped(root, rel)
    raw = regular_bytes(path, max_size=MAX_JSON, immutable=immutable)
    try:
        obj = json.loads(raw)
    except (UnicodeError, ValueError) as exc:
        raise Hold("HOLD_JSON", "Pinned JSON cannot be decoded") from exc
    check(isinstance(obj, dict), "HOLD_JSON", "Pinned JSON is not an object")
    return obj, raw, sha256(raw)


def hash_map(obj: object, *, scope: str) -> dict[str, str]:
    check(isinstance(obj, dict), "HOLD_INVENTORY", "SHA inventory must be an object")
    if scope == "source":
        check(set(obj) in (SOURCE8, SOURCE9), "HOLD_INVENTORY",
              "Baseline must be exactly 8 or 9 reviewed sources")
    else:
        check(len(obj) == 7 and "index.html" in obj,
              "HOLD_INVENTORY", "Static scope must be exactly seven reviewed assets")
    for name, value in obj.items():
        check(path_name(name, scope=scope) and digest_ok(value),
              "HOLD_INVENTORY", "Inventory path/SHA is invalid")
    return obj


def file_hash(root: Path, rel: str | Path, *, frozen: bool = False) -> str:
    path = scoped(root, rel)
    return sha256(regular_bytes(path, max_size=MAX_ASSET, immutable=frozen))


def tree_hashes(root: Path, rel: Path, *, frozen: bool = False) -> dict[str, str]:
    parent = scoped(root, rel)
    check(parent.is_dir(), "HOLD_STATIC", "Static tree missing")
    if frozen:
        check(not (parent.stat().st_mode & 0o222), "HOLD_NOT_FROZEN", "Candidate static directory is writable")
    result = {}
    try:
        for item in parent.rglob("*"):
            scoped(root, item.relative_to(root))
            mode = item.lstat().st_mode
            check(stat.S_ISREG(mode) or stat.S_ISDIR(mode),
                  "HOLD_STATIC", "Non-regular item in asset inventory")
            if frozen:
                check(not (mode & 0o222), "HOLD_NOT_FROZEN",
                      "Frozen candidate static tree contains writable data")
            if item.is_file():
                name = item.relative_to(parent).as_posix()
                check(path_name(name, scope="static") and len(result) < 65,
                      "HOLD_STATIC", "Extra or invalid static asset")
                result[name] = file_hash(root, item.relative_to(root), frozen=frozen)
    except OSError as exc:
        raise Hold("HOLD_STATIC", "Static tree could not be read") from exc
    return result


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise Hold("HOLD_HTTP", "HTTP redirect is not a pinned asset")


def http_verify(base: str, assets: dict[str, str]) -> dict:
    url = urlsplit(base)
    check(url.scheme == "http" and url.hostname in {"127.0.0.1", "::1", "localhost"}
          and url.path in {"", "/"} and not url.query and not url.fragment
          and not url.username and not url.password,
          "HOLD_HTTP_SCOPE", "Only a bare loopback HTTP origin is allowed")
    opener = build_opener(ProxyHandler({}), NoRedirect())
    result = {}
    try:
        for name, expected in assets.items():
            suffix = "/" if name == "index.html" else "/" + quote(name, safe="/")
            with opener.open(Request(base.rstrip("/") + suffix, method="GET"), timeout=5) as response:
                raw = response.read(MAX_ASSET + 1)
                check(response.status == 200 and len(raw) <= MAX_ASSET
                      and sha256(raw) == expected, "HOLD_HTTP",
                      "Live served asset differs from pinned SHA")
                result[name] = sha256(raw)
        for path in ("/health/ready", "/api/version"):
            with opener.open(Request(base.rstrip("/") + path, method="GET"), timeout=5) as response:
                check(response.status == 200, "HOLD_HTTP", "Live health or version status is not HTTP 200")
                payload = json.loads(response.read(16385))
                check(isinstance(payload, dict) and payload.get("version") == "3.0.0",
                      "HOLD_HTTP", "Live service version drift")
                if path == "/health/ready":
                    check(payload.get("ready") is True, "HOLD_HTTP", "Live readiness is false")
    except Hold:
        raise
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, UnicodeError) as exc:
        raise Hold("HOLD_HTTP", "Loopback HTTP probe failed") from exc
    return {"http_static_count": len(result), "http_static_sha256": result,
            "health_ready": True, "api_version": "3.0.0"}


def sqlite_readonly(path: Path) -> None:
    check(path.is_file() and not path.is_symlink(), "HOLD_ROLLBACK", "SQLite snapshot missing")
    try:
        with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
            db.execute("PRAGMA query_only=ON")
            check(db.execute("PRAGMA quick_check").fetchone()[0] == "ok"
                  and db.total_changes == 0,
                  "HOLD_ROLLBACK", "Read-only SQLite quick_check failed")
    except sqlite3.DatabaseError as exc:
        raise Hold("HOLD_ROLLBACK", "Read-only SQLite check could not finish") from exc


def active_units(root: Path, *, fixture: bool) -> dict[str, str]:
    if fixture:
        record, _, _ = json_input(root, "runtime/frontier/fake-units.json")
        states = record
    else:
        try:
            run = subprocess.run(["systemctl", "--user", "is-active", *UNITS],
                                 capture_output=True, text=True, timeout=8, check=False)
            states = dict(zip(UNITS, run.stdout.splitlines()))
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise Hold("HOLD_UNITS", "Cannot read cloud user service states") from exc
        check(run.returncode == 0, "HOLD_UNITS", "Cloud service is not active")
    check(all(states.get(unit) == "active" for unit in UNITS),
          "HOLD_UNITS", "Both Frontier systemd user services must be active")
    return {unit: states[unit] for unit in UNITS}


def rollback_checkpoint(root: Path, rel: str, old_files: dict, old_static: dict,
                        *, manifest_sha: str | None = None) -> dict:
    check(isinstance(rel, str) and re.fullmatch(
        r"runtime/frontier/releases/v3-[0-9]{8}T[0-9]{6}[0-9]{0,8}Z", rel),
        "HOLD_ROLLBACK", "Baseline must pin a V3 checkpoint name")
    directory = scoped(root, rel)
    check(directory.is_dir(), "HOLD_ROLLBACK", "Pinned checkpoint directory unavailable")
    releases = scoped(root, "runtime/frontier/releases")
    latest = sorted(p.name for p in releases.iterdir()
                    if p.name.startswith("v3-") and p.is_dir() and not p.is_symlink())
    check(latest and directory.name == latest[-1],
          "HOLD_BASELINE_CHANGED", "A newer or different production checkpoint exists")
    previous, _, frozen_sha = json_input(root, Path(rel) / "manifest.json")
    if manifest_sha:
        check(digest_ok(manifest_sha) and frozen_sha == manifest_sha,
              "HOLD_ROLLBACK", "Baseline checkpoint manifest SHA pin mismatch")
    check(previous.get("version") == "3.0.0"
          and previous.get("files") == old_files
          and previous.get("static_files") == old_static,
          "HOLD_ROLLBACK", "Pinned old SHA disagrees with deployed checkpoint")
    deployed, _, _ = json_input(root, Path(rel) / "deployed.json")
    check(deployed.get("health", {}).get("ready") is True
          and deployed.get("health", {}).get("version") == "3.0.0"
          and deployed.get("product", {}).get("v3_checked") is True
          and deployed.get("product", {}).get("static_files_verified") == 7,
          "HOLD_ROLLBACK", "Baseline health/product acceptance absent")
    check(scoped(root, Path(rel) / "checkpoint.json").is_file(),
          "HOLD_ROLLBACK", "Rollback existed-files checkpoint missing")
    archive = scoped(root, Path(rel) / "source-before.tar.gz", must_exist=False)
    check(archive.is_file() and archive.stat().st_size > 0, "HOLD_ROLLBACK", "Rollback tar missing")
    try:
        with tarfile.open(archive, "r:gz") as tar:
            members = tar.getmembers()
            check(bool(members) and all(
                not m.name.startswith("/") and ".." not in Path(m.name).parts
                and not m.issym() and not m.islnk() for m in members),
                "HOLD_ROLLBACK", "Rollback source archive unsafe/empty")
            archived_sources = {m.name for m in members if m.isfile()}
            check(SOURCE_REQUIRED <= archived_sources,
                  "HOLD_ROLLBACK", "Rollback archive lacks required release source")
    except (OSError, tarfile.TarError) as exc:
        raise Hold("HOLD_ROLLBACK", "Rollback source tar could not be inspected") from exc
    sqlite_readonly(scoped(root, Path(rel) / "events-before.sqlite3"))
    return {"checkpoint": rel, "checkpoint_manifest_sha256": frozen_sha,
            "rollback_tar_readable": True, "rollback_database_readonly_quick_check": "ok"}


def parse_today(value: object, today: str, *, now: datetime) -> None:
    check(isinstance(value, str), "HOLD_DATE", "Date-bound timestamp required")
    try:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
        check(instant.utcoffset() is not None, "HOLD_DATE", "Timestamp must include offset")
        beijing = instant.astimezone(BJ)
        check(beijing.date().isoformat() == today and instant <= now,
              "HOLD_DATE", "Handoff/QA timestamp must be from this Beijing day, not future")
    except ValueError as exc:
        raise Hold("HOLD_DATE", "Date-bound timestamp cannot be decoded") from exc


def preflight(root: Path, *, day: str, now: datetime, http_base: str, fixture: bool) -> dict:
    check(day >= FIRST_NINE_DATE, "HOLD_NINE_DATE",
          "Nine-source daily release cannot run before 2026-10-25 Beijing time")
    handoff_rel = HANDOFF / (day + ".json")
    handoff_file = scoped(root, handoff_rel, must_exist=False)
    check(handoff_file.is_file(), "HOLD_NO_NEW_CANDIDATE",
          "No new dated frozen handoff; keep current production unchanged")
    h, handoff_raw, handoff_sha = json_input(root, handoff_rel, immutable=True)
    check(h.get("schema") == "frontier.cloud.daily.handoff.v1"
          and h.get("beijing_date") == day and DATE.fullmatch(day) is not None,
          "HOLD_HANDOFF", "Missing matching date-scoped handoff")
    parse_today(h.get("created_at"), day, now=now)
    product = h.get("product_release")
    compact_date = day.replace("-", "")
    check(isinstance(product, str) and compact_date in product
          and product.startswith("Frontier-"), "HOLD_REPLAY",
          "Old product release cannot be re-labelled as today's release")
    old_source = hash_map(h.get("old_source_sha256"), scope="source")
    old_static = hash_map(h.get("old_static_sha256"), scope="static")
    if set(old_source) == SOURCE8:
        # Native V103 rollback deletes this previously absent source.
        new_path = scoped(root, NINTH_SOURCE, must_exist=False)
        check(not new_path.exists() and not new_path.is_symlink(),
              "HOLD_ADDITION_OCCUPIED", "Ninth source occupied before 8-to-9")
    checkpoint = h.get("baseline_checkpoint")
    old_receipt = rollback_checkpoint(
        root, checkpoint, old_source, old_static,
        manifest_sha=h.get("baseline_manifest_sha256"))
    source_actual = {name: file_hash(root, name) for name in old_source}
    check(source_actual == old_source, "HOLD_OLD_SOURCE", "Cloud oldSHA changed")
    static_actual = tree_hashes(root, STATIC)
    check(static_actual == old_static, "HOLD_OLD_STATIC", "Cloud old static tree changed")
    http_old = http_verify(http_base, old_static)
    units = active_units(root, fixture=fixture)
    sqlite_readonly(scoped(root, "runtime/frontier/events.sqlite3"))
    manifest_rel = h.get("manifest_path")
    qa_rel = h.get("qa_receipt_path")
    candidate_rel = h.get("candidate_path")
    check(all(isinstance(x, str) for x in (manifest_rel, qa_rel, candidate_rel)),
          "HOLD_HANDOFF", "Manifest/QA/candidate pinned paths are absent")
    expected_prefix = "runtime/frontier-daily-candidates/" + day + "-"
    check(manifest_rel.startswith(expected_prefix)
          and qa_rel.startswith(expected_prefix)
          and manifest_rel.endswith("/manifest.json")
          and qa_rel.endswith("/qa.json"),
          "HOLD_REPLAY", "A fresh date-named immutable manifest/QA package is required")
    candidate = Path(candidate_rel)
    check(candidate_rel.startswith("runtime/frontier-v3-candidate-")
          and compact_date in candidate.name
          and candidate.parent == Path("runtime"),
          "HOLD_REPLAY", "Cannot replay an old or non-isolated candidate")
    candidate_dir = scoped(root, candidate_rel)
    check(candidate_dir.is_dir() and not (candidate_dir.stat().st_mode & 0o222),
          "HOLD_NOT_FROZEN", "Candidate directory must be frozen after QA")
    manifest, raw, manifest_sha = json_input(root, manifest_rel, immutable=True)
    check(digest_ok(h.get("manifest_sha256")) and manifest_sha == h["manifest_sha256"],
          "HOLD_MANIFEST_PIN", "Frozen manifest raw-byte SHA pin differs")
    check(manifest.get("version") == 3 and manifest.get("release_version") == "3.0.0"
          and manifest.get("product_release") == product,
          "HOLD_MANIFEST", "Reviewed V3 manifest/product-release mismatch")
    entries = manifest.get("files")
    check(isinstance(entries, dict) and set(entries) == SOURCE9,
          "HOLD_MANIFEST", "New source manifest must contain exactly the reviewed nine paths")
    new_source = {}
    for name, item in entries.items():
        check(path_name(name, scope="source") and isinstance(item, dict)
              and isinstance(item.get("content"), str) and digest_ok(item.get("sha256"))
              and sha256(item["content"].encode()) == item["sha256"],
              "HOLD_MANIFEST", "New source manifest content/SHA invalid")
        check("old_sha256" in item and item["old_sha256"] == old_source.get(name),
              "HOLD_OLD_PIN", "Old SHA must be exact (only new ninth may be explicit null)")
        new_source[name] = item["sha256"]
    new_static = hash_map(manifest.get("static_files"), scope="static")
    check(new_source != old_source or new_static != old_static,
          "HOLD_NO_CHANGE", "Identical old/new bytes are not a new daily delivery")
    for name, expected in new_source.items():
        check(file_hash(root, candidate / name, frozen=True) == expected,
              "HOLD_CANDIDATE_SOURCE", "Frozen candidate source disagrees with new SHA")
    candidate_static = tree_hashes(root, candidate / STATIC, frozen=True)
    check(candidate_static == new_static, "HOLD_CANDIDATE_STATIC",
          "Frozen candidate 7-asset inventory differs from pinned manifest")
    qa, qa_raw, qa_sha = json_input(root, qa_rel, immutable=True)
    check(digest_ok(h.get("qa_receipt_sha256")) and qa_sha == h["qa_receipt_sha256"],
          "HOLD_QA_PIN", "QA receipt raw-byte pin mismatch")
    check(qa.get("schema") == "frontier.cloud.daily.qa.v1"
          and qa.get("beijing_date") == day and qa.get("product_release") == product
          and qa.get("candidate_path") == candidate_rel
          and qa.get("manifest_sha256") == manifest_sha
          and qa.get("baseline_checkpoint") == checkpoint
          and qa.get("independent_preprod_passed") is True
          and qa.get("rollback_fixture_passed") is True
          and qa.get("http_static_verified") == 7
          and qa.get("source_sha256_verified") == 9
          and qa.get("static_sha256_verified") == 7,
          "HOLD_QA", "Independent candidate QA evidence is not consistent/passed")
    parse_today(qa.get("finished_at"), day, now=now)
    fingerprint = sha256(json.dumps(
        [day, handoff_sha, manifest_sha, qa_sha, candidate_rel],
        separators=(",", ":"), ensure_ascii=False).encode())
    return {
        "beijing_date": day, "product_release": product, "handoff_sha256": handoff_sha,
        "manifest_sha256": manifest_sha, "qa_receipt_sha256": qa_sha,
        "candidate_path": candidate_rel, "manifest_path": manifest_rel,
        "baseline_checkpoint": checkpoint, "baseline_manifest_sha256": old_receipt["checkpoint_manifest_sha256"],
        "old_source_sha256": old_source, "old_static_sha256": old_static,
        "new_source_sha256": new_source, "new_static_sha256": new_static,
        "source_transition": f"{len(old_source)}-to-9",
        "old_http_static_verified": http_old["http_static_count"],
        "new_candidate_static_verified": len(candidate_static),
        "rollback_database_readonly_quick_check": "ok",
        "live_database_readonly_quick_check": "ok",
        "rollback_tar_readable": True, "services": units, "fingerprint": fingerprint,
        "_manifest_bytes": raw,
    }


@contextmanager
def only_writer(root: Path, *, dry_run: bool):
    """One flock covers preflight, deploy, final verification and daily ledger."""
    state = scoped(root, STATE, must_exist=dry_run)
    if dry_run:
        check(state.is_dir(), "HOLD_LOCK_NOT_PROVISIONED", "Dry-run requires pre-existing writer-lock directory")
    else:
        state.mkdir(parents=True, mode=0o700, exist_ok=True)
        check(not state.is_symlink(), "HOLD_SYMLINK", "State directory is symlink")
        os.chmod(state, 0o700)
    lock = scoped(root, STATE / "writer.lock", must_exist=dry_run)
    if dry_run:
        check(lock.is_file(), "HOLD_LOCK_NOT_PROVISIONED", "Writer lock does not exist")
        descriptor = os.open(lock, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    else:
        descriptor = os.open(lock, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0),
                             0o600)
    try:
        check(stat.S_ISREG(os.fstat(descriptor).st_mode),
              "HOLD_LOCK", "Writer lock is not a regular inode")
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise Hold("HOLD_LOCK_BUSY", "Another cooperative production writer owns flock") from exc
        token = _ACTIVE_WRITER_FD.set(descriptor)
        try:
            yield state
        finally:
            _ACTIVE_WRITER_FD.reset(token)
    finally:
        # Never explicit LOCK_UN on a shared open-file-description: if the
        # dispatcher dies while its publisher child continues, that child must
        # retain the exclusive lock until publication/recovery exits.
        os.close(descriptor)


def ledger_read(root: Path, day: str) -> dict | None:
    path = scoped(root, STATE / (day + ".json"), must_exist=False)
    if not path.exists():
        return None
    rec, _, _ = json_input(root, STATE / (day + ".json"))
    check(rec.get("schema") == "frontier.cloud.daily.transaction.v1"
          and rec.get("beijing_date") == day,
          "HOLD_LEDGER", "Existing daily receipt schema/date malformed")
    return rec


def ledger_write(state: Path, day: str, record: dict) -> None:
    payload = json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2).encode() + b"\n"
    destination = state / (day + ".json")
    temp = state / (day + ".tmp-" + str(os.getpid()) + "-" + str(time.time_ns()))
    descriptor = os.open(temp, os.O_WRONLY | os.O_EXCL | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0),
                         0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, destination)
        directory = os.open(state, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temp.unlink(missing_ok=True)


def pin_manifest(state: Path, day: str, raw: bytes, sha: str) -> Path:
    target = state / (day + "-manifest-" + sha + ".json")
    if target.exists():
        check(not target.is_symlink() and sha256(regular_bytes(target, max_size=MAX_JSON)) == sha,
              "HOLD_PIN_RACE", "Previously pinned manifest changed")
        return target
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o400)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    return target


@contextmanager
def reversible_static_bridge(root: Path, manifest: Path, prepared: dict):
    """Post-V99-gate, lock-scoped *disposable* candidate for V103 copytree.

    The QA candidate remains frozen 0555 and is NEVER altered. V103 copies
    directory modes, so only this transient copy has 0755 static directories.
    The existing V103 writer and its manifest/source SHA pins remain unchanged.
    Must run inside only_writer; all cleanup is before COMMITTED ledger write.
    """
    check(_ACTIVE_WRITER_FD.get() is not None, "HOLD_LOCK",
          "Publisher bridge requires the existing locked writer inode")
    candidate_rel = Path(prepared["candidate_path"])
    check(candidate_rel.parent == Path("runtime")
          and candidate_rel.name.startswith("frontier-v3-candidate-"),
          "HOLD_SCOPE", "Reviewed candidate is not a date-pinned runtime child")
    source = scoped(root, candidate_rel)
    check(source.is_dir() and not (source.stat().st_mode & 0o222),
          "HOLD_NOT_FROZEN", "Reviewed candidate root is no longer immutable")
    old_static = hash_map(prepared["old_static_sha256"], scope="static")
    new_static = hash_map(prepared["new_static_sha256"], scope="static")
    new_source = hash_map(prepared["new_source_sha256"], scope="source")
    check(sha256(regular_bytes(manifest, max_size=MAX_JSON, immutable=True))
          == prepared["manifest_sha256"],
          "HOLD_MANIFEST_PIN", "Pinned publisher manifest drifted before stage")
    check(tree_hashes(root, STATIC) == old_static,
          "HOLD_OLD_STATIC", "Production old static bytes changed before staging")
    check(tree_hashes(root, candidate_rel / STATIC, frozen=True) == new_static,
          "HOLD_CANDIDATE_STATIC", "Frozen reviewed static SHA/mode drift")
    for name, expected in new_source.items():
        check(file_hash(root, candidate_rel / name, frozen=True) == expected,
              "HOLD_CANDIDATE_SOURCE", "Frozen reviewed source SHA/mode drift")
    # Both V103 restore_checkpoint(rmtree(active)) and success cleanup
    # (rmtree(retired)) require writer-owned + writable/executable dirs.
    current = scoped(root, STATIC)
    folders = [scoped(root, STATIC.parent), current]
    folders.extend(item for item in current.rglob("*") if item.is_dir())
    for folder in folders:
        scoped(root, folder.relative_to(root))
        st = folder.lstat()
        check(stat.S_ISDIR(st.st_mode) and st.st_uid == os.geteuid()
              and (st.st_mode & 0o300) == 0o300,
              "HOLD_OLD_STATIC_PERMISSIONS",
              "Existing active/parent static directories cannot be retired/removed")
    runtime = scoped(root, "runtime")
    check(runtime.is_dir(), "HOLD_SCOPE", "Runtime staging parent missing")
    temp = None
    try:
        temp = Path(tempfile.mkdtemp(prefix="frontier-v3-candidate-dispatch-bridge-",
                                     dir=runtime))
        static = temp / STATIC
        # Create all directories ourselves: copytree(..., copystat) would
        # propagate frozen 0555 and recreate the original rollback failure.
        directories = {static}
        directories.update((static / name).parent for name in new_static)
        for folder in sorted(directories, key=lambda value: len(value.parts)):
            folder.mkdir(parents=True, exist_ok=True)
            folder.chmod(0o755)
        for name, expected in sorted(new_static.items()):
            original = scoped(root, candidate_rel / STATIC / name)
            payload = regular_bytes(original, max_size=MAX_ASSET, immutable=True)
            check(sha256(payload) == expected,
                  "HOLD_CANDIDATE_STATIC", "Frozen asset changed during copy")
            dest = static / name
            fd = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                         getattr(os, "O_NOFOLLOW", 0), 0o600)
            with os.fdopen(fd, "wb") as output:
                output.write(payload)
                output.flush()
                os.fchmod(output.fileno(), 0o444)
                os.fsync(output.fileno())
        check(tree_hashes(root, temp.relative_to(root) / STATIC) == new_static,
              "HOLD_BRIDGE_HASH", "Disposable publisher bridge differs from pinned 7SHA")
        check(all((folder.stat().st_mode & 0o300) == 0o300
                  for folder in directories),
              "HOLD_BRIDGE_MODE", "Bridge static directories must be removable")
        # Fail closed on a second source/manifest/frozen-static read immediately
        # before giving the old publisher this new temporary candidate path.
        check(sha256(regular_bytes(manifest, max_size=MAX_JSON, immutable=True))
              == prepared["manifest_sha256"] and
              tree_hashes(root, candidate_rel / STATIC, frozen=True) == new_static and
              all(file_hash(root, candidate_rel / name, frozen=True) == digest
                  for name, digest in new_source.items()),
              "HOLD_INPUT_DRIFT", "Frozen reviewed input drifted before publisher")
        yield temp
    finally:
        if temp is not None:
            check(temp.parent == runtime and
                  temp.name.startswith("frontier-v3-candidate-dispatch-bridge-")
                  and not temp.is_symlink(),
                  "HOLD_STAGE_SCOPE", "Refusing cleanup of unexpected staging path")
            try:
                shutil.rmtree(temp)
            except OSError as exc:
                raise Hold("HOLD_STAGE_CLEANUP",
                           "Publisher bridge could not be fully removed") from exc


def run_deploy(root: Path, manifest: Path, prepared: dict, *, bridge: Path) -> dict:
    """Only the existing byte-identical V103 guarded publisher writes production."""
    check(bridge.parent == root / "runtime" and
          bridge.name.startswith("frontier-v3-candidate-dispatch-bridge-")
          and bridge.is_dir() and not bridge.is_symlink(),
          "HOLD_STAGE_SCOPE", "Publisher must use only the verified bridge")
    cmd = [str(root / ".venv/bin/python"), "-B",
           str(root / "ops/frontier_release.py"), "deploy",
           "--root", str(root), "--manifest", str(manifest),
           "--candidate", str(bridge),
           "--review-sha256", prepared["manifest_sha256"]]
    fd = _ACTIVE_WRITER_FD.get()
    inheritance = (
        {"pass_fds": (fd,), "env": {**os.environ, "FRONTIER_WRITER_LOCK_FD": str(fd)}}
        if fd is not None else {}
    )
    try:
        run = subprocess.run(cmd, cwd=root, capture_output=True, text=True,
                             timeout=900, check=False, **inheritance)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise Hold("HOLD_DEPLOY_UNCERTAIN", "Publisher failed/timeout; inspect recovery journal") from exc
    check(run.returncode == 0, "HOLD_DEPLOY_UNCERTAIN",
          "Existing guarded publisher exited nonzero; manual recovery check required")
    try:
        lines = [line.strip() for line in run.stdout.splitlines() if line.strip()]
        result = json.loads(lines[-1])
    except (ValueError, IndexError) as exc:
        raise Hold("HOLD_DEPLOY_UNCERTAIN", "Publisher success receipt missing") from exc
    check(result.get("deployed") is True and result.get("rollback_backup") is True
          and result.get("health_verified") is True and result.get("v3_verified") is True
          and result.get("static_assets") == 7,
          "HOLD_DEPLOY_UNCERTAIN", "Publisher did not report validated V3 success")
    return result


def postverify(root: Path, prepared: dict, deployed: dict, *, http_base: str, fixture: bool) -> dict:
    new_source, new_static = prepared["new_source_sha256"], prepared["new_static_sha256"]
    check({name: file_hash(root, name) for name in new_source} == new_source,
          "HOLD_POSTVERIFY", "Postpublish backend 9-file SHA drift")
    check(tree_hashes(root, STATIC) == new_static, "HOLD_POSTVERIFY",
          "Postpublish frontend 7-file SHA drift")
    http_result = http_verify(http_base, new_static)
    active_units(root, fixture=fixture)
    sqlite_readonly(scoped(root, "runtime/frontier/events.sqlite3"))
    release_path = Path(deployed.get("release", ""))
    check(release_path.is_absolute() and release_path.parent == root / "runtime/frontier/releases"
          and release_path.name.startswith("v3-"), "HOLD_POSTVERIFY", "New checkpoint path invalid")
    rel = release_path.relative_to(root).as_posix()
    check(rel != prepared["baseline_checkpoint"], "HOLD_POSTVERIFY", "No new checkpoint created")
    checkpoint = rollback_checkpoint(
        root, rel, new_source, new_static)
    committed, _, _ = json_input(root, Path(rel) / "manifest.json")
    check(committed.get("integrity", {}).get("manifest_sha256") == prepared["manifest_sha256"]
          and committed.get("integrity", {}).get("review_pin_supplied") is True
          and committed.get("integrity", {}).get("source_sha256_verified") == 9
          and committed.get("integrity", {}).get("static_sha256_verified") == 7,
          "HOLD_POSTVERIFY", "Committed manifest pin/9+7 release evidence mismatch")
    return {"checkpoint": rel, "checkpoint_manifest_sha256": checkpoint["checkpoint_manifest_sha256"],
            "http_static_verified": http_result["http_static_count"], "sources_verified": 9,
            "static_verified": 7, "services_active": True, "db_quick_check": "ok",
            "rollback_snapshot_readable": True}


def _hold(code: str, message: str, *, base: dict) -> dict:
    return {**base, "status": "HOLD", "hold_code": code, "reason": message,
            "cloud_deploy_executed": False}


def _record(day: str, status: str, **extra: object) -> dict:
    return {"schema": "frontier.cloud.daily.transaction.v1", "beijing_date": day,
            "status": status, "recorded_at": datetime.now(UTC).isoformat(), **extra}


def _real_execution_context(root: Path) -> None:
    check(platform.system() == "Linux" and root == PRODUCTION_ROOT
          and Path(__file__).resolve() == root / "ops/frontier_cloud_daily_dispatcher.py"
          and not (root / MARKER).exists(),
          "HOLD_EXECUTION_SCOPE", "Live scheduling requires installed reviewed production dispatcher")


def _fixture(root: Path) -> bool:
    marker = root / MARKER
    if not marker.exists():
        return False
    check(not marker.is_symlink() and marker.is_file()
          and marker.read_text().strip() == "V99_DISPOSABLE_TEST_ONLY",
          "HOLD_FIXTURE", "Fixture marker invalid")
    return True


def dispatch(root: Path, *, scheduled: bool, now: datetime,
             http_base: str, immediate: bool=False) -> tuple[dict, int]:
    fixture = _fixture(root)
    live = scheduled or immediate
    base = {"schema": "frontier.cloud.daily.dispatch.v1",
            "mode": ("IMMEDIATE_LIVE" if immediate else "SCHEDULED_LIVE"
                     if scheduled else "INDEPENDENT_READONLY_DRY_RUN"),
            "beijing_time": now.astimezone(BJ).isoformat(),
            "cloud_deploy_executed": False, "app_launched": False,
            "fixture_root": fixture}
    local = now.astimezone(BJ)
    day = local.date().isoformat()
    base["beijing_date"] = day
    if not immediate and not (local.hour == 20 and 0 <= local.minute <= 14):
        return {**base, "status": "SKIPPED_OUTSIDE_BEIJING_WINDOW"}, 0
    if live:
        _real_execution_context(root)
    with only_writer(root, dry_run=not live) as state:
        ledger = ledger_read(root, day)
        if ledger and ledger.get("status") == "COMMITTED":
            return {**base, "status": "ALREADY_COMMITTED_TODAY",
                    "checkpoint": ledger.get("checkpoint"),
                    "fingerprint": ledger.get("fingerprint")}, 0
        if ledger and ledger.get("status") in {"DEPLOYING", "HOLD_AFTER_ATTEMPT"}:
            return {**base, "status": "HOLD",
                    "hold_code": "HOLD_DAY_ALREADY_ATTEMPTED",
                    "reason": "Prior deploy attempt pending/manual recovery; never auto-retry",
                    "prior_cloud_deploy_attempted": True}, 2
        try:
            prepared = preflight(root, day=day, now=now, http_base=http_base,
                                 fixture=fixture)
        except Hold as exc:
            if live:
                ledger_write(state, day, _record(day, "HOLD", hold_code=exc.code,
                                                cloud_deploy_executed=False,
                                                reason=str(exc)))
            raise
        raw = prepared.pop("_manifest_bytes")
        public = {**base, **prepared}
        if not live:
            return {**public, "status": "READY_DRY_RUN_NOT_DEPLOYED",
                    "ledger_written": False}, 0
        # Release must use the ACTUAL current clock and the same frozen handoff;
        # --immediate is explicitly owner-authorized, not a synthetic timestamp.
        fresh = datetime.now(UTC).astimezone(BJ)
        check(fresh.date().isoformat() == day and
              (immediate or (fresh.hour == 20 and fresh.minute <= 14)),
              "HOLD_WINDOW_EXPIRED", "Release preflight exceeded today's authorized window")
        immutable_manifest = pin_manifest(state, day, raw, prepared["manifest_sha256"])
        check(sha256(regular_bytes(immutable_manifest, max_size=MAX_JSON))
              == prepared["manifest_sha256"], "HOLD_PIN_RACE",
              "Frozen manifest changed before publisher launch")
        # Stage before DEPLOYING: a permission/SHA drift is a zero-attempt
        # HOLD, not an irreversible attempted deployment on this Beijing date.
        attempted = False
        try:
            with reversible_static_bridge(root, immutable_manifest, prepared) as bridge:
                fresh = datetime.now(UTC).astimezone(BJ)
                check(fresh.date().isoformat() == day and
                      (immediate or (fresh.hour == 20 and fresh.minute <= 14)),
                      "HOLD_WINDOW_EXPIRED", "Bridge exceeded the authorized launch window")
                ledger_write(state, day, _record(day, "DEPLOYING",
                            fingerprint=prepared["fingerprint"],
                            manifest_sha256=prepared["manifest_sha256"],
                            candidate_path=prepared["candidate_path"],
                            baseline_checkpoint=prepared["baseline_checkpoint"],
                            cloud_deploy_executed=False))
                attempted = True
                publisher = run_deploy(root, immutable_manifest, prepared, bridge=bridge)
                verified = postverify(root, prepared, publisher, http_base=http_base,
                                      fixture=fixture)
                # Context exits HERE: stage is gone before any COMMITTED receipt.
        except BaseException as exc:
            code = exc.code if isinstance(exc, Hold) else (
                "HOLD_DEPLOY_UNCERTAIN" if attempted else "HOLD_STAGE_IO")
            if not attempted:
                ledger_write(state, day, _record(day, "HOLD",
                             fingerprint=prepared["fingerprint"], hold_code=code,
                             reason="Publisher was never invoked; bridge preflight failed",
                             cloud_deploy_executed=False))
                if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                    raise
                return {**public, "status": "HOLD", "hold_code": code,
                        "reason": "Bridge preflight failed before deploy; production untouched",
                        "cloud_deploy_executed": False, "ledger_written": True}, 2
            ledger_write(state, day, _record(day, "HOLD_AFTER_ATTEMPT",
                         fingerprint=prepared["fingerprint"], hold_code=code,
                         reason="A deployment was attempted; manual service/DB/checkpoint inspection required",
                         cloud_deploy_executed=True))
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            return {**public, "status": "HOLD_AFTER_ATTEMPT", "hold_code": code,
                    "reason": "Publisher attempted; check real service/DB/checkpoint and manual rollback evidence",
                    "cloud_deploy_executed": True, "ledger_written": True}, 2
        ledger_write(state, day, _record(day, "COMMITTED",
                        fingerprint=prepared["fingerprint"],
                        product_release=prepared["product_release"],
                        manifest_sha256=prepared["manifest_sha256"],
                        checkpoint=verified["checkpoint"],
                        postverify=verified, cloud_deploy_executed=True))
        return {**public, **verified, "status": "COMMITTED",
                "cloud_deploy_executed": True, "ledger_written": True}, 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--scheduled", action="store_true")
    mode.add_argument("--immediate", action="store_true",
                      help="Owner-authorized, real-clock, same-day immediate cloud delivery")
    p.add_argument("--root", type=Path, default=Path(__file__).absolute().parents[1])
    p.add_argument("--http-base", default="http://127.0.0.1:8088")
    p.add_argument("--at", help="Offset-aware test instant; supported ONLY in --dry-run")
    args = p.parse_args(argv)
    if (args.scheduled or args.immediate) and args.at:
        p.error("--at cannot spoof real production live time")
    result: dict
    code = 0
    try:
        check(not args.root.is_symlink() and args.root.is_dir(),
              "HOLD_ROOT", "Root must be a real directory, not a symlink")
        root = args.root.resolve()
        if args.at:
            try:
                now = datetime.fromisoformat(args.at.replace("Z", "+00:00"))
            except ValueError as exc:
                raise Hold("HOLD_TIME", "Invalid offset-aware test time") from exc
            check(now.utcoffset() is not None, "HOLD_TIME", "Test time requires timezone offset")
        else:
            now = datetime.now(UTC)
        result, code = dispatch(root, scheduled=args.scheduled, now=now,
                                http_base=args.http_base, immediate=args.immediate)
    except Hold as exc:
        code = 2
        result = {"schema": "frontier.cloud.daily.dispatch.v1",
                  "mode": ("IMMEDIATE_LIVE" if args.immediate else "SCHEDULED_LIVE"
                           if args.scheduled else "INDEPENDENT_READONLY_DRY_RUN"),
                  "status": "HOLD", "hold_code": exc.code, "reason": str(exc),
                  "cloud_deploy_executed": False, "app_launched": False}
    except (OSError, RuntimeError, sqlite3.DatabaseError, tarfile.TarError) as exc:
        code = 2
        result = {"schema": "frontier.cloud.daily.dispatch.v1",
                  "mode": ("IMMEDIATE_LIVE" if args.immediate else "SCHEDULED_LIVE"
                           if args.scheduled else "INDEPENDENT_READONLY_DRY_RUN"),
                  "status": "HOLD", "hold_code": "HOLD_UNEXPECTED_IO",
                  "reason": "Read-only gate or scheduled I/O failed (" + type(exc).__name__ + ")",
                  "cloud_deploy_executed": False, "app_launched": False}
    result["exit_code"] = code
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return code


if __name__ == "__main__":
    sys.exit(main())
