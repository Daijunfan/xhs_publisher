#!/usr/bin/env python3
"""Prepare an isolated candidate or install a reviewed Frontier manifest.

No collector or model is started by the candidate. Source databases are opened
read-only. Production installation retains a code/data rollback checkpoint.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import shutil
import signal
import sqlite3
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
from contextlib import contextmanager, suppress
from datetime import UTC, datetime
from functools import wraps
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import HTTPCookieProcessor, ProxyHandler, Request, build_opener

UNITS = ["frontier-web.service", "frontier-collector.service"]
STATIC_REL = Path("src/xhs_local/frontier/static")
WRITER_LOCK_REL = Path("runtime/frontier/daily-dispatch/writer.lock")
WRITER_LOCK_ENV = "FRONTIER_WRITER_LOCK_FD"
# Daily production release is authorized by the owner's existing delivery
# delegation; no invented third-party signing key is a prerequisite.


@contextmanager
def production_writer_lock(root: Path):
    """Serialize direct deploy/rollback/time-repair with the V99 daily writer.

    A dispatcher child inherits exactly its parent's locked open-file description
    via pass_fds plus FRONTIER_WRITER_LOCK_FD. Never explicitly LOCK_UN: after
    SIGKILL, an inherited surviving process must still protect production.
    """
    root = Path(root)
    if root.is_symlink():
        raise RuntimeError("Writer lock: project root must not be a symlink")
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise RuntimeError("Writer lock: production root is not a directory")
    directory = root
    for part in WRITER_LOCK_REL.parent.parts:
        directory = directory / part
        if directory.is_symlink():
            raise RuntimeError("Writer lock: symlink in lock directory path")
        if not directory.exists():
            if root == Path(__file__).resolve().parents[1]:
                raise RuntimeError("Writer lock: production inode must be provisioned")
            directory.mkdir(mode=0o700, exist_ok=True)
        if not directory.is_dir():
            raise RuntimeError("Writer lock: directory component is not a directory")
    if stat.S_IMODE(directory.stat().st_mode) != 0o700:
        raise RuntimeError("Writer lock: daily-dispatch directory must be 0700")
    path = root / WRITER_LOCK_REL
    if path.is_symlink():
        raise RuntimeError("Writer lock: inode path must not be a symlink")
    inherited = os.environ.get(WRITER_LOCK_ENV)
    if inherited is not None:
        if not inherited.isdecimal() or int(inherited) < 3:
            raise RuntimeError("Writer lock: malformed inherited descriptor")
        fd = int(inherited)
        try:
            opened = os.fstat(fd)
        except OSError as exc:
            raise RuntimeError("Writer lock: inherited descriptor invalid") from exc
    else:
        if root == Path(__file__).resolve().parents[1] and not path.exists():
            raise RuntimeError("Writer lock: production lock not provisioned")
        fd = os.open(
            path,
            os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0),
            0o600,
        )
        opened = os.fstat(fd)
    try:
        try:
            named = path.lstat()
        except FileNotFoundError as exc:
            raise RuntimeError("Writer lock: named inode disappeared") from exc
        if (
            not stat.S_ISREG(opened.st_mode)
            or not stat.S_ISREG(named.st_mode)
            or (opened.st_dev, opened.st_ino) != (named.st_dev, named.st_ino)
            or opened.st_uid != os.geteuid()
            or opened.st_nlink != 1
            or stat.S_IMODE(opened.st_mode) != 0o600
        ):
            raise RuntimeError("Writer lock: inode, ownership or mode mismatch")
        if inherited is not None:
            # BEFORE acquiring, prove the inherited OFD was already locked.
            # An unlocked forged FD must not self-grant a delegation token.
            probe = os.open(path, os.O_RDWR | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0))
            try:
                try:
                    fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    pass
                else:
                    fcntl.flock(probe, fcntl.LOCK_UN)
                    raise RuntimeError("Writer lock: inherited descriptor was not held")
            finally:
                os.close(probe)
        try:
            # With inheritance this succeeds ONLY on the SAME OFD as parent;
            # with a fresh FD this is the lock acquisition itself.
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Writer lock: another production writer is active") from exc
        final = path.lstat()
        if (final.st_dev, final.st_ino) != (opened.st_dev, opened.st_ino):
            raise RuntimeError("Writer lock: named inode replaced while acquiring")
        yield fd
    finally:
        # Close only. LOCK_UN here would release the same inherited OFD lock
        # even while a separate dispatcher/publisher subprocess is still alive.
        os.close(fd)


def writer_transaction(function):
    """Enforce flock even for Python callers importing publisher functions."""
    @wraps(function)
    def locked(args):
        with production_writer_lock(args.root) as fd:
            args._writer_fd = fd
            return function(args)
    return locked


def reject_replayed_release(root: Path, reviewed_sha: str):
    """A prior completed checkpoint means identical manifest is not a new deploy."""
    release_dir = root / "runtime/frontier/releases"
    if not release_dir.is_dir():
        return
    for receipt in release_dir.glob("v3-*/manifest.json"):
        if receipt.is_symlink() or not receipt.is_file():
            continue
        try:
            data = json.loads(receipt.read_bytes())
        except (OSError, ValueError):
            continue
        if (
            data.get("integrity", {}).get("manifest_sha256") == reviewed_sha
            and (receipt.parent / "deployed.json").is_file()
        ):
            raise RuntimeError("Identical reviewed manifest already deployed; no replay")


def stamp():
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")


def safe_scope(name):
    path = Path(name)
    return (
        not path.is_absolute()
        and ".." not in path.parts
        and (
            name.startswith(("src/", "tests/", "ops/"))
            or name in {"pyproject.toml", "uv.lock", "FRONTIER_V2.md"}
        )
    )


def backup_readonly(source: Path, target: Path):
    target.parent.mkdir(parents=True, exist_ok=True)
    original = sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True)
    destination = sqlite3.connect(target)
    try:
        original.backup(destination)
        if destination.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("Database backup failed integrity check")
    finally:
        original.close()
        destination.close()
    target.chmod(0o600)


def read_manifest(path: Path, *, pinned_bytes: bytes | None = None):
    # Deploy pins one immutable-in-memory manifest: never re-read mutable
    # on-disk JSON after computing an optionally supplied review SHA256.
    manifest = json.loads(pinned_bytes if pinned_bytes is not None else path.read_bytes())
    for name, entry in manifest["files"].items():
        if not safe_scope(name):
            raise RuntimeError("Manifest path is outside the release scope")
        if hashlib.sha256(entry["content"].encode()).hexdigest() != entry["sha256"]:
            raise RuntimeError("Manifest checksum mismatch")
    if manifest.get("version", 2) >= 3:
        if manifest.get("release_version") != "3.0.0":
            raise RuntimeError("V3 release must declare the reviewed 3.0.0 runtime version")
        if "static_files" not in manifest:
            raise RuntimeError("V3 release requires a reviewed frontend asset inventory")
        # Keep the V3 runtime version source and deploy implementation in scope.
        for name in ("src/xhs_local/frontier/__init__.py", "ops/frontier_release.py"):
            if name not in manifest["files"]:
                raise RuntimeError("V3 release must include its version and release gate: " + name)
    return manifest


def checked_candidate(root: Path, candidate: Path, manifest: dict) -> Path:
    """Require an independent runtime QA tree, never production or a checkpoint."""
    runtime = (root.resolve() / "runtime").resolve()
    candidate = candidate.resolve()
    if (
        not candidate.is_relative_to(runtime)
        or candidate == runtime
        or candidate.is_relative_to(runtime / "frontier")
        or (
            manifest.get("version", 2) >= 3
            and not candidate.name.startswith("frontier-v3-candidate-")
        )
    ):
        raise RuntimeError("V3 release candidate must be the named QA clone below runtime")
    return candidate


def validate_static_assets(static: Path, manifest: dict) -> dict:
    """Verify the entire frontend tree, not only backend hashes or index.html."""
    if manifest.get("version", 2) < 3:
        return {}
    expected = manifest.get("static_files")
    if (
        not isinstance(expected, dict)
        or "index.html" not in expected
        or not 2 <= len(expected) <= 64
        or not static.is_dir()
        or static.is_symlink()
    ):
        raise RuntimeError("Reviewed V3 static asset inventory is missing")
    actual = {}
    for path in static.rglob("*"):
        if path.is_symlink() or not path.resolve().is_relative_to(static.resolve()):
            raise RuntimeError("Candidate static contains a symlink or an escaped asset")
        if not path.is_file():
            continue
        name = path.relative_to(static).as_posix()
        if (
            name.startswith(".")
            or ".." in Path(name).parts
            or path.stat().st_size > 12 * 1024 * 1024
            or name not in expected
        ):
            raise RuntimeError(
                "Candidate static contains an unreviewed or oversized asset: " + name
            )
        actual[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    if set(actual) != set(expected):
        raise RuntimeError("Static inventory differs from the reviewed V3 manifest")
    if any(
        not isinstance(value, str) or len(value) != 64 or actual[name] != value
        for name, value in expected.items()
    ):
        raise RuntimeError("Frontend static SHA256 differs from the reviewed V3 manifest")
    return actual


def activate_reviewed_static(root: Path, candidate: Path, manifest: dict, tag: str) -> Path | None:
    """Stage bytes on the same volume and swap the whole tree while services are stopped."""
    current = root / STATIC_REL
    if manifest.get("version", 2) < 3:
        shutil.copytree(candidate / STATIC_REL, current, dirs_exist_ok=True)
        return None
    stage = current.parent / (".frontier-static-staging-" + tag)
    retired = current.parent / (".frontier-static-before-" + tag)
    if stage.exists() or retired.exists() or current.is_symlink():
        raise RuntimeError("Static release staging path is occupied or is a symlink")
    shutil.copytree(candidate / STATIC_REL, stage, symlinks=False)
    try:
        validate_static_assets(stage, manifest)
        current.rename(retired)
        try:
            stage.rename(current)
        except BaseException:
            retired.rename(current)
            raise
        return retired
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def verify_v3_service(
    root: Path, manifest: dict, *, port: int = 8088, static_root: Path | None = None
) -> dict:
    """Authenticated, read-only V3 API and served-index release gate.

    Authorization creates a short-lived session and then logs it out; it never
    creates radar topics, marks reads, modifies subscriptions, or calls AI.
    """
    if manifest.get("version", 2) < 3:
        return {"v3_checked": False}
    validate_static_assets(static_root or root / STATIC_REL, manifest)
    opener = build_opener(ProxyHandler({}))
    base = "http://127.0.0.1:" + str(port) + "/"
    for name, expected_sha in manifest["static_files"].items():
        # All V3 assets must be served, not just the root HTML. Disk-only SHA
        # would miss stale HTTP bundles behind a still-active web process.
        url = base + ("" if name == "index.html" else quote(name, safe="/"))
        with opener.open(url, timeout=10) as response:
            content = response.read(12 * 1024 * 1024 + 1)
        if len(content) > 12 * 1024 * 1024 or hashlib.sha256(content).hexdigest() != expected_sha:
            raise RuntimeError("Live HTTP frontend asset SHA256 mismatch: " + name)
    client = OwnerClient(root, port)
    try:
        version = client.request("GET", "/api/version")
        radar = client.request("GET", "/api/radar")
        plans = client.request("GET", "/api/plans")
        events = client.request("GET", "/api/events?scope=all&read=all&limit=1")
        sources = client.request("GET", "/api/sources?include_deleted=1")
        if (
            version.get("version") != manifest["release_version"]
            or not isinstance(radar.get("topics"), list)
            or radar.get("plan", {}).get("id") not in {"free", "pro", "analyst"}
            or plans.get("billing_enabled") is not False
            or not isinstance(events.get("items"), list)
            or not isinstance(sources.get("items"), list)
        ):
            raise RuntimeError("Authenticated V3 API/product contract release gate failed")
        return {
            "v3_checked": True,
            "version": version["version"],
            "topics": len(radar["topics"]),
            "sources": len(sources["items"]),
            "billing_enabled": False,
            "static_files_verified": len(manifest["static_files"]),
        }
    finally:
        client.close()


def write_manifest(root: Path, manifest):
    for name, entry in manifest["files"].items():
        path = root / name
        if not path.resolve().is_relative_to(root.resolve()):
            raise RuntimeError("Manifest destination escapes the project root")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(entry["content"])


def validate_production(root, manifest):
    for name, entry in manifest["files"].items():
        actual = _source_digest(root, name)
        expected = entry.get("old_sha256")
        if expected is not None and actual != expected:
            raise RuntimeError("Production file changed since review: " + name)
        if expected is None and actual is not None and actual != entry["sha256"]:
            raise RuntimeError("An unreviewed production file now occupies the new path: " + name)


def archive_source(root, target, names):
    with tarfile.open(target, "w:gz") as archive:
        for name in names:
            if not safe_scope(name):
                raise RuntimeError("Source archive path is outside the release scope")
            if (root / name).exists():
                archive.add(root / name, arcname=name)
        static = root / "src/xhs_local/frontier/static"
        if static.is_dir():
            archive.add(static, arcname="src/xhs_local/frontier/static")
    target.chmod(0o600)


def restore_checkpoint(root, release, existed):
    source_archive = release / "source-before.tar.gz"
    database = release / "events-before.sqlite3"
    if not source_archive.is_file() or not database.is_file():
        raise RuntimeError("The release checkpoint is incomplete; no restore attempted")
    with sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True) as c:
        if c.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("The rollback database failed integrity verification")
    with tarfile.open(source_archive) as archive:
        if any(not safe_scope(member.name) for member in archive.getmembers()):
            raise RuntimeError("Rollback archive contains an unexpected path")
        # Replace, never merge, bundled assets; otherwise failed V3 hashes
        # silently linger next to the restored V2 bundle.
        active_static = root / STATIC_REL
        if active_static.is_dir() and not active_static.is_symlink():
            shutil.rmtree(active_static)
        archive.extractall(root, filter="data")
    for name, previous in existed.items():
        if not safe_scope(name):
            raise RuntimeError("Rollback metadata contains an unexpected path")
        if not previous:
            (root / name).unlink(missing_ok=True)
    original_db = root / "runtime/frontier/events.sqlite3"
    for suffix in ("-wal", "-shm"):
        Path(str(original_db) + suffix).unlink(missing_ok=True)
    incoming = original_db.with_suffix(".restore.sqlite3")
    shutil.copy2(database, incoming)
    incoming.chmod(0o600)
    incoming.replace(original_db)


def wait_health(root, *, version=None, timeout=45):
    opener = build_opener(ProxyHandler({}))
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        active = subprocess.run(
            ["systemctl", "--user", "is-active", "--quiet", *UNITS], check=False
        )
        if active.returncode == 0:
            try:
                with opener.open("http://127.0.0.1:8088/health/ready", timeout=3) as response:
                    health = json.load(response)
                if health.get("ready") is True and (
                    version is None or health.get("version") == version
                ):
                    return health
            except (URLError, TimeoutError, ValueError, OSError):
                pass
        time.sleep(1)
    raise RuntimeError("The web and collector units did not pass the active/HTTP readiness gate")


def prepare(args):
    candidate = args.candidate.resolve()
    root = args.root.resolve()
    if not candidate.is_relative_to(root / "runtime") or candidate == root / "runtime":
        raise RuntimeError("Candidate must be a dedicated directory below the project runtime")
    manifest = read_manifest(args.manifest)
    candidate.mkdir(parents=True, exist_ok=True)
    for name in ("src", "tests", "ops", "tools"):
        if (root / name).is_dir():
            shutil.copytree(
                root / name,
                candidate / name,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "node_modules", "*.jpg"),
            )
    for name in (".gitignore", "pyproject.toml", "uv.lock", "README.md", "FRONTIER.md"):
        if (root / name).is_file():
            shutil.copy2(root / name, candidate / name)
    config = candidate / "config"
    if not config.exists():
        config.symlink_to(root / "config", target_is_directory=True)
    write_manifest(candidate, manifest)
    database = candidate / "data/events.sqlite3"
    if not database.exists() or args.reset:
        if database.exists():
            backup_readonly(database, candidate / "data/previous-candidate.sqlite3")
            for suffix in ("", "-wal", "-shm"):
                Path(str(database) + suffix).unlink(missing_ok=True)
        backup_readonly(root / "runtime/frontier/events.sqlite3", database)
    print(
        json.dumps(
            {
                "candidate": str(candidate),
                "files": len(manifest["files"]),
                "enrichment": False,
                "collector": False,
                "source_database": "read-only",
            }
        )
    )


def refresh(args):
    """Update candidate code only; retain its database and separately built frontend."""
    root, candidate = args.root.resolve(), args.candidate.resolve()
    if not candidate.is_relative_to(root / "runtime"):
        raise RuntimeError("Candidate must remain below runtime")
    manifest = read_manifest(args.manifest)
    write_manifest(candidate, manifest)
    shutil.copy2(root / ".gitignore", candidate / ".gitignore")
    print(json.dumps({"refreshed": True, "files": len(manifest["files"]), "database_reset": False}))


def serve(args):
    candidate, root = args.candidate.resolve(), args.root.resolve()
    sys.path.insert(0, str(candidate / "src"))
    from aiohttp import web

    from xhs_local.frontier.store import Store
    from xhs_local.frontier.subscriptions import Subscriptions
    from xhs_local.frontier.web import Settings, create_app

    store = Store(candidate / "data/events.sqlite3")
    store.import_records(root / "runtime/app.sqlite3")
    Subscriptions(store, root).ensure_seeded()
    settings = Settings(
        root=root,
        database=store.path,
        source_database=root / "runtime/app.sqlite3",
        static_dir=candidate / "src/xhs_local/frontier/static",
        enrich=False,
        port=args.port,
    )
    web.run_app(
        create_app(settings, store, background=False),
        host="127.0.0.1",
        port=args.port,
        access_log=None,
        print=lambda _: print("Isolated Frontier candidate is ready", flush=True),
    )


def warm(args):
    """Cache at most the requested number of allowlisted public source images."""
    import asyncio

    import aiohttp

    candidate, root = args.candidate.resolve(), args.root.resolve()
    sys.path.insert(0, str(candidate / "src"))
    from xhs_local.frontier.media import MediaCache
    from xhs_local.frontier.store import Store

    store = Store(candidate / "data/events.sqlite3")
    store.import_records(root / "runtime/app.sqlite3")
    namespace = (candidate / "media").relative_to(root / "runtime").as_posix()
    cache = MediaCache(store, root / "runtime", cache_namespace=namespace)

    async def run():
        processed = 0
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=20),
            trust_env=True,
            connector=aiohttp.TCPConnector(limit=3),
        ) as session:
            while processed < args.maximum:
                pending = await asyncio.to_thread(cache._pending, args.platform)
                if not pending:
                    break
                pending = pending[: min(args.maximum - processed, 8)]
                for start in range(0, len(pending), 3):
                    await asyncio.gather(
                        *(cache.fetch(session, row) for row in pending[start : start + 3])
                    )
                processed += len(pending)
        with store.connect() as c:
            counts = [
                dict(row)
                for row in c.execute(
                    "SELECT platform,state,count(*) count FROM media_assets GROUP BY platform,state"
                )
            ]
        print(
            json.dumps(
                {"attempted": processed, "media": counts, "collector": False, "enrichment": False}
            )
        )

    asyncio.run(run())


def time_context(args):
    """Limit precision repair tools to the selected derived event databases."""
    root = args.root.resolve()
    candidate = args.candidate.resolve() if args.candidate else None
    if candidate and (
        not candidate.is_relative_to(root / "runtime") or candidate == root / "runtime"
    ):
        raise RuntimeError("Time repair code must use the reviewed isolated candidate")
    production = root / "runtime/frontier/events.sqlite3"
    choices = {production.resolve()}
    if candidate:
        choices.add((candidate / "data/events.sqlite3").resolve())
    database = (
        args.database.resolve()
        if args.database
        else (candidate / "data/events.sqlite3" if candidate else production).resolve()
    )
    if (
        database not in choices
        or not database.is_relative_to(root / "runtime")
        or database == (root / "runtime/app.sqlite3").resolve()
    ):
        raise RuntimeError(
            "Time tools only accept the production or selected candidate derived event database"
        )
    if not database.is_file():
        raise RuntimeError("The selected derived database does not exist")
    sys.path.insert(0, str((candidate or root) / "src"))
    return root, database


def time_plan(args):
    root, database = time_context(args)
    from xhs_local.frontier.time_quality import plan_week_repairs

    plan_path = args.plan.resolve()
    if (
        not plan_path.is_relative_to(root / "runtime")
        or plan_path.suffix != ".json"
        or plan_path.exists()
    ):
        raise RuntimeError("Write each reviewed plan to a new .json file below runtime")
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as connection:
        plan = plan_week_repairs(connection)
    plan["database"] = str(database)
    content = json.dumps(plan, ensure_ascii=False, indent=2).encode()
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    with plan_path.open("xb") as output:
        output.write(content)
    plan_path.chmod(0o600)
    print(
        json.dumps(
            {
                "planned": len(plan["records"]),
                "readonly": True,
                "version": plan["version"],
                "database": str(database),
                "plan": str(plan_path),
                "sha256": hashlib.sha256(content).hexdigest(),
                "event_ids": [entry["event_id"] for entry in plan["records"]],
                "unmatched_evidence_skipped": plan["unmatched_evidence_skipped"],
            }
        ),
        flush=True,
    )


def reviewed_time_plan(path, expected_sha256, database):
    if not isinstance(expected_sha256, str) or len(expected_sha256) != 64:
        raise RuntimeError("The exact reviewed time-plan SHA256 is required")
    content = path.read_bytes()
    actual = hashlib.sha256(content).hexdigest()
    if actual != expected_sha256:
        raise RuntimeError("Time repair plan has changed since review")
    plan = json.loads(content)
    if plan.get("database") != str(database.resolve()):
        raise RuntimeError("Generate a separate reviewed time plan for this derived database")
    return plan


@writer_transaction
def time_repair(args):
    _root, database = time_context(args)
    from xhs_local.frontier.time_quality import apply_week_repairs

    plan = reviewed_time_plan(args.plan, args.expected_plan_sha256, database)
    checkpoint = database.parent / "time-repairs" / stamp()
    checkpoint.mkdir(parents=True, mode=0o700)
    backup = checkpoint / "events-before.sqlite3"
    # This SQLite snapshot finishes and passes integrity verification before any
    # repair transaction opens. It never reads or writes the original source DB.
    backup_readonly(database, backup)
    shutil.copy2(args.plan, checkpoint / "reviewed-plan.json")
    with sqlite3.connect(database.as_uri() + "?mode=rw", uri=True, timeout=15) as connection:
        result = apply_week_repairs(connection, plan, plan_sha256=args.expected_plan_sha256)
    result.update(
        database=str(database),
        backup=str(backup),
        backup_sha256=hashlib.sha256(backup.read_bytes()).hexdigest(),
        plan_sha256=args.expected_plan_sha256,
    )
    (checkpoint / "applied.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result), flush=True)


def veto_explicit_non_deployable_manifest(manifest):
    """Reject an artifact explicitly marked as not releasable, not an extra GO process."""
    reviewed = manifest.get("reviewed_for")
    if not isinstance(reviewed, dict):
        return
    status = str(reviewed.get("status") or "").upper()
    release_name = str(reviewed.get("product_release") or "").upper()
    review_stage = str(reviewed.get("review_stage") or "").upper()
    blocked_markers = (
        "DRAFT",
        "NOT_DEPLOYABLE",
        "NOT_APPROVED",
        "NEEDS_SIGNED",
        "NEEDS_NATIVE_ROTATION",
    )
    if (
        reviewed.get("must_not_use_as_published_review")
        or reviewed.get("formal_go_requires_main_pm_new_cloud_and_native_receipt")
        or any(
            marker in value
            for value in (status, release_name, review_stage)
            for marker in blocked_markers
        )
    ):
        raise RuntimeError(
            "Release manifest is explicitly DRAFT / not deployable; "
            "generate a current deployable manifest from the authorized release candidate"
        )



def reviewed_manifest_digest(raw_manifest: bytes, pin: str | None) -> str:
    """Optional out-of-band SHA pin is a byte-integrity check, NOT a new GO."""
    digest = hashlib.sha256(raw_manifest).hexdigest()
    if pin is not None and (
        not isinstance(pin, str)
        or len(pin) != 64
        or any(char not in "0123456789abcdef" for char in pin)
        or pin != digest
    ):
        raise RuntimeError("Manifest raw-byte SHA256 differs from supplied review pin")
    return digest


def _source_digest(root: Path, name: str) -> str | None:
    """Read the current named regular inode, rejecting redirected source paths."""
    if not safe_scope(name):
        raise RuntimeError("Production source path is outside the release scope")
    path = root
    for part in Path(name).parts:
        path = path / part
        if path.is_symlink():
            raise RuntimeError("Production source has a symlink component: " + name)
    if not path.exists():
        return None
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    with os.fdopen(descriptor, "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise RuntimeError("Production source is not a regular file: " + name)
        content = stream.read()
        after = os.fstat(stream.fileno())
    named = path.lstat()
    if (
        (before.st_dev, before.st_ino) != (named.st_dev, named.st_ino)
        or (before.st_size, before.st_mtime_ns, before.st_ctime_ns)
        != (after.st_size, after.st_mtime_ns, after.st_ctime_ns)
    ):
        raise RuntimeError("Production source changed during guarded read: " + name)
    return hashlib.sha256(content).hexdigest()


def checkpoint_source_digests(archive_path: Path, manifest: dict, existed: dict) -> dict:
    """Prove rollback's archived source matches the reviewed old bytes."""
    snapshots = {}
    with tarfile.open(archive_path, "r:gz") as archive:
        for name, entry in manifest["files"].items():
            old_sha = entry.get("old_sha256")
            expected = old_sha if old_sha is not None else entry["sha256"]
            if existed[name]:
                try:
                    member = archive.getmember(name)
                except KeyError as error:
                    raise RuntimeError(
                        "Rollback checkpoint omitted a production source: " + name
                    ) from error
                if not member.isfile():
                    raise RuntimeError("Rollback checkpoint source is not a regular file: " + name)
                stream = archive.extractfile(member)
                if stream is None:
                    raise RuntimeError("Rollback checkpoint source is unreadable: " + name)
                with stream:
                    digest = hashlib.sha256(stream.read()).hexdigest()
                if digest != expected:
                    raise RuntimeError("Rollback checkpoint old SHA256 mismatch: " + name)
                snapshots[name] = digest
            else:
                try:
                    archive.getmember(name)
                except KeyError:
                    snapshots[name] = None
                else:
                    raise RuntimeError(
                        "Rollback checkpoint contains a previously absent source: " + name
                    )
    return snapshots


def publish_guarded_sources(root: Path, manifest: dict, checkpoint: dict, state: dict):
    """Stage exact new bytes; guard archived old inodes immediately before atomic replaces.

    Services are stopped and bytes checked against the recovery snapshot.
    Independent uncooperative writers still require production filesystem
    permissions/operational exclusion: no Python SHA check
    can perform a multi-file kernel compare-and-swap.
    """
    staged = []
    try:
        for name, entry in manifest["files"].items():
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            # The deployment only introduces private staging paths until all
            # old-source and rollback checkpoint checks have passed.
            _source_digest(root, name)
            fd, temporary = tempfile.mkstemp(prefix=".frontier-release-stage-", dir=target.parent)
            stage = Path(temporary)
            staged.append((name, target, stage))
            try:
                mode = stat.S_IMODE(target.stat().st_mode) if target.exists() else 0o644
                with os.fdopen(fd, "wb") as output:
                    os.fchmod(output.fileno(), mode)
                    output.write(entry["content"].encode())
                    output.flush()
                    os.fsync(output.fileno())
            except BaseException:
                # fdopen may fail before accepting ownership of the descriptor.
                with suppress(OSError):
                    os.close(fd)
                raise
            if hashlib.sha256(stage.read_bytes()).hexdigest() != entry["sha256"]:
                raise RuntimeError("Staged source SHA256 mismatch: " + name)
        validate_production(root, manifest)
        # One last whole-manifest comparison before the first source replacement
        # prevents a late edit to a later-listed file from forcing a partial
        # publish before its per-file check runs.
        for name in manifest["files"]:
            if _source_digest(root, name) != checkpoint[name]:
                raise RuntimeError("Production source changed after rollback checkpoint: " + name)
        for name, target, stage in staged:
            # This guard follows ALL checkpoint I/O and stage I/O. A concurrent
            # edit after the earlier oldSHA check must not silently be overwritten.
            if _source_digest(root, name) != checkpoint[name]:
                raise RuntimeError("Production source changed after rollback checkpoint: " + name)
            state["source_write_started"] = True
            os.replace(stage, target)  # same-directory atomic individual file swap
            if _source_digest(root, name) != manifest["files"][name]["sha256"]:
                raise RuntimeError("Published source SHA256 mismatch: " + name)
        for name, entry in manifest["files"].items():
            if _source_digest(root, name) != entry["sha256"]:
                raise RuntimeError("Post-publish source SHA256 mismatch: " + name)
    finally:
        for _name, _target, stage in staged:
            stage.unlink(missing_ok=True)


@writer_transaction
def deploy(args):
    root = args.root.resolve()
    raw_manifest = args.manifest.read_bytes()
    manifest = read_manifest(args.manifest, pinned_bytes=raw_manifest)
    veto_explicit_non_deployable_manifest(manifest)
    manifest_sha256 = reviewed_manifest_digest(raw_manifest, getattr(args, "review_sha256", None))
    reject_replayed_release(root, manifest_sha256)
    candidate = checked_candidate(root, args.candidate, manifest)
    validate_production(root, manifest)
    validate_static_assets(candidate / STATIC_REL, manifest)
    time_plan_path = getattr(args, "time_plan", None)
    if time_plan_path:
        reviewed_time_plan(
            time_plan_path, args.time_plan_sha256, root / "runtime/frontier/events.sqlite3"
        )
    if not (candidate / "src/xhs_local/frontier/static/index.html").is_file():
        raise RuntimeError("Built candidate frontend is missing")
    created = stamp()
    release = (
        root
        / "runtime/frontier/releases"
        / (("v3-" if manifest.get("version", 2) >= 3 else "v2-") + created)
    )
    release.mkdir(parents=True)
    release.chmod(0o700)
    existed = {name: (root / name).exists() for name in manifest["files"]}
    original_db = root / "runtime/frontier/events.sqlite3"
    checkpoint_ready = False
    commit_state = {"source_write_started": False}
    retired_static = None
    try:
        # A partial stop failure is included in recovery: both original units are
        # restarted even if systemctl stopped only one of them before returning nonzero.
        subprocess.run(["systemctl", "--user", "stop", *UNITS], check=True)
        # Repeat the guard after the units stop, before any production file is written.
        validate_production(root, manifest)
        backup_readonly(original_db, release / "events-before.sqlite3")
        archive_source(root, release / "source-before.tar.gz", manifest["files"])
        snapshots = checkpoint_source_digests(
            release / "source-before.tar.gz", manifest, existed
        )
        (release / "checkpoint.json").write_text(
            json.dumps({"created_at": created, "existed": existed}, indent=2)
        )
        checkpoint_ready = True
        publish_guarded_sources(root, manifest, snapshots, commit_state)
        retired_static = activate_reviewed_static(root, candidate, manifest, created)
        if time_plan_path:
            # Apply the separately reviewed production plan before the additive
            # schema migration; the release backup above covers both operations.
            # Nested time-repair is a second CLI process, not a second writer.
            # It inherits the parent's already locked open file description.
            parent_fd = os.environ.get(WRITER_LOCK_ENV)
            if parent_fd is None:
                parent_fd = getattr(args, "_writer_fd", None)
            parent_fd = int(parent_fd) if parent_fd is not None else None
            nested_lock = (
                {"pass_fds": (parent_fd,), "env": {**os.environ, WRITER_LOCK_ENV: str(parent_fd)}}
                if parent_fd is not None else {}
            )
            subprocess.run(
                [
                    str(root / ".venv/bin/python"),
                    str(root / "ops/frontier_release.py"),
                    "time-repair",
                    "--root",
                    str(root),
                    "--database",
                    str(original_db),
                    "--plan",
                    str(time_plan_path),
                    "--expected-plan-sha256",
                    args.time_plan_sha256,
                ],
                cwd=root,
                check=True,
                **nested_lock,
            )
        code = (
            "from pathlib import Path; from xhs_local.frontier.store import Store; "
            "from xhs_local.frontier.subscriptions import Subscriptions; "
            "r=Path.cwd(); s=Store(r/'runtime/frontier/events.sqlite3'); "
            "s.import_records(r/'runtime/app.sqlite3'); Subscriptions(s,r).ensure_seeded(); "
            "print('Frontier schema, media and subscriptions migrated')"
        )
        env = {**os.environ, "PYTHONPATH": str(root / "src")}
        subprocess.run([str(root / ".venv/bin/python"), "-c", code], cwd=root, env=env, check=True)
        # The migration must not have modified the reviewed source/static bytes.
        for name, entry in manifest["files"].items():
            if _source_digest(root, name) != entry["sha256"]:
                raise RuntimeError("Source changed after migration: " + name)
        validate_static_assets(root / STATIC_REL, manifest)
        (release / "manifest.json").write_text(
            json.dumps(
                {
                    "created_at": created,
                    "version": manifest.get("release_version", "2.0.0"),
                    "files": {k: v["sha256"] for k, v in manifest["files"].items()},
                    "static_files": manifest.get("static_files", {}),
                    "integrity": {
                        "manifest_sha256": manifest_sha256,
                        "review_pin_supplied": getattr(args, "review_sha256", None) is not None,
                        "source_sha256_verified": len(manifest["files"]),
                        "static_sha256_verified": len(manifest.get("static_files", {})),
                    },
                },
                indent=2,
            )
        )
        subprocess.run(["systemctl", "--user", "start", *UNITS], check=True)
        health = wait_health(root, version=manifest.get("release_version", "2.0.0"))
        product = verify_v3_service(root, manifest)
        (release / "deployed.json").write_text(
            json.dumps({"healthy_at": stamp(), "health": health, "product": product})
        )
        if retired_static and retired_static.is_dir():
            shutil.rmtree(retired_static)
        print(
            json.dumps(
                {
                    "deployed": True,
                    "release": str(release),
                    "rollback_backup": True,
                    "health_verified": True,
                    "v3_verified": product["v3_checked"],
                    "version": health["version"],
                    "static_assets": product.get("static_files_verified", 0),
                }
            ),
            flush=True,
        )
    except BaseException:
        # Pre-commit conflict: *never* restore the earlier checkpoint over a
        # third-party old-source edit that caused our last guard to fail.
        if not commit_state["source_write_started"]:
            (release / "aborted-before-publish.json").write_text(
                json.dumps({"at": stamp(), "source_write_started": False})
            )
            subprocess.run(["systemctl", "--user", "start", *UNITS], check=False)
            raise
        # After a partial publish retain a sidecar of the failed source state,
        # then recover from the independently checked pre-release checkpoint.
        with suppress(Exception):
            archive_source(root, release / "source-failed-upgrade.tar.gz", manifest["files"])
        # Never replace a live SQLite database during recovery.
        stop = subprocess.run(["systemctl", "--user", "stop", *UNITS], check=False)
        if checkpoint_ready and stop.returncode == 0:
            try:
                # If V3 briefly accepted a user action before a gate failed,
                # preserve the modified database, never silently discard it.
                if original_db.is_file():
                    backup_readonly(original_db, release / "events-failed-upgrade.sqlite3")
                restore_checkpoint(root, release, existed)
                if retired_static and retired_static.is_dir():
                    shutil.rmtree(retired_static)
            finally:
                subprocess.run(["systemctl", "--user", "start", *UNITS], check=False)
            wait_health(root)
            print(
                json.dumps({"rolled_back": True, "release": str(release), "health_verified": True}),
                flush=True,
            )
        else:
            subprocess.run(["systemctl", "--user", "start", *UNITS], check=False)
            if checkpoint_ready:
                print(
                    json.dumps(
                        {
                            "rollback_blocked": True,
                            "reason": "Could not stop both units safely",
                            "checkpoint": str(release),
                        }
                    ),
                    flush=True,
                )
        raise


@writer_transaction
def rollback(args):
    root, release = args.root.resolve(), args.release.resolve()
    if not release.is_relative_to(
        root / "runtime/frontier/releases"
    ) or not release.name.startswith(("v2-", "v3-")):
        raise RuntimeError("Rollback must use an existing Frontier release checkpoint")
    if release.name.startswith("v3-") and not getattr(args, "allow_data_rewind", False):
        raise RuntimeError(
            "V3 manual rollback moves newer user edits into a preserved sidecar; "
            "provide --allow-data-rewind only after reviewing the recovery plan"
        )
    checkpoint = json.loads((release / "checkpoint.json").read_text())
    existed = checkpoint["existed"]
    if not isinstance(existed, dict) or any(not safe_scope(name) for name in existed):
        raise RuntimeError("Invalid rollback checkpoint scope")
    current = release / ("before-manual-rollback-" + stamp())
    current.mkdir(mode=0o700)
    try:
        subprocess.run(["systemctl", "--user", "stop", *UNITS], check=True)
        # Preserve all reading/settings/source changes since deployment before the
        # reviewed earlier database is restored. This checkpoint is never discarded.
        backup_readonly(root / "runtime/frontier/events.sqlite3", current / "events.sqlite3")
        archive_source(root, current / "source.tar.gz", existed)
        restore_checkpoint(root, release, existed)
    finally:
        subprocess.run(["systemctl", "--user", "start", *UNITS], check=False)
    wait_health(root)
    print(
        json.dumps(
            {
                "rolled_back": True,
                "release": str(release),
                "preserved_current": str(current),
                "health_verified": True,
            }
        ),
        flush=True,
    )


class OwnerClient:
    """Loopback-only API client; access code and CSRF token never enter output."""

    def __init__(self, root, port):
        self.base = "http://127.0.0.1:" + str(port)
        self.opener = build_opener(ProxyHandler({}), HTTPCookieProcessor(CookieJar()))
        self.csrf = None
        token = (root / "runtime/secrets/frontier-access.token").read_text().strip()
        self.csrf = self.request("POST", "/api/auth/session", {"token": token})["csrf_token"]

    def request(self, method, path, data=None, *, binary=False):
        if not path.startswith("/") or path.startswith("//"):
            raise RuntimeError("Only same-origin API paths are permitted")
        headers = {"Origin": self.base}
        if self.csrf:
            headers["X-CSRF-Token"] = self.csrf
        if data is not None:
            headers["Content-Type"] = "application/json"
        request = Request(
            self.base + path,
            data=json.dumps(data).encode() if data is not None else None,
            headers=headers,
            method=method,
        )
        try:
            with self.opener.open(request, timeout=20) as response:
                if binary:
                    payload = response.read(8 * 1024 * 1024 + 1)
                    if len(payload) > 8 * 1024 * 1024:
                        raise RuntimeError("Media exceeds the verified image limit")
                    return payload, response.headers.get_content_type()
                return json.load(response)
        except HTTPError as error:
            # Do not print request headers, response bodies, or credential values.
            raise RuntimeError(
                f"API {method} {path.split('?')[0]} returned HTTP {error.code}"
            ) from None

    def close(self):
        with suppress(Exception):
            self.request("POST", "/api/auth/logout", {})


def smoke(args):
    """Read existing source data and decode one real image per platform."""
    import io

    from PIL import Image

    root = args.root.resolve()
    client = OwnerClient(root, args.port)
    report = {"collector_started": False, "model_called": False, "sources_modified": False}
    try:
        report["version"] = client.request("GET", "/api/version")["version"]
        report["settings_version"] = client.request("GET", "/api/settings")["version"]
        sources = client.request("GET", "/api/sources?include_deleted=1")
        report["subscriptions"] = {
            platform: sum(
                item["platform"] == platform and not item["deleted_at"] for item in sources["items"]
            )
            for platform in ("telegram", "x", "youtube")
        }
        report["subscription_sync"] = sources["sync"]["state"]
        report["revision"] = sources["revision"]
        report["applied_revision"] = sources["applied_revision"]
        report["media"] = []
        for platform in ("telegram", "x", "youtube"):
            query = urlencode({"source": platform, "scope": "all", "read": "all", "limit": 100})
            start = time.monotonic()
            inbox = client.request("GET", "/api/inbox?" + query)
            elapsed = round((time.monotonic() - start) * 1000, 1)
            chosen = next((item for item in inbox["items"] if item["images"]), None)
            if chosen is None:
                raise RuntimeError("No ready original image is available for " + platform)
            url = chosen["images"][0]
            if not url.startswith("/api/media/"):
                raise RuntimeError("Media URL is not the same-origin image endpoint")
            payload, mime = client.request("GET", url, binary=True)
            with Image.open(io.BytesIO(payload)) as decoded:
                dimensions = [decoded.width, decoded.height]
                actual = Image.MIME.get(decoded.format)
                decoded.verify()
            if mime != actual:
                raise RuntimeError("Image MIME and decoded content disagree")
            report["media"].append(
                {
                    "platform": platform,
                    "records": inbox["total"],
                    "inbox_ms": elapsed,
                    "mime": mime,
                    "bytes": len(payload),
                    "dimensions": dimensions,
                    "sha256": hashlib.sha256(payload).hexdigest(),
                }
            )
        report["source_health"] = client.request("GET", "/api/status")["sources"]
        print(json.dumps(report, ensure_ascii=False), flush=True)
    finally:
        client.close()


def observe_sources(args):
    """Observe exact QA IDs; never create, mutate, fetch, or remove subscriptions."""
    root = args.root.resolve()
    identities = list(args.ids or [])
    if args.journal:
        journal = json.loads(args.journal.read_text())
        for entry in journal.get("mutations", []):
            if (
                entry.get("method") == "POST"
                and entry.get("path") == "/api/sources"
                and 200 <= (entry.get("status") or 0) < 300
            ):
                identities.append(entry["response"]["id"])
    identities = sorted(set(identities))
    if (
        not identities
        or len(identities) > 20
        or any(not isinstance(value, str) or not 1 <= len(value) <= 150 for value in identities)
    ):
        raise RuntimeError("Provide 1–20 exact QA source IDs or the successful mutation journal")
    path = (
        args.candidate / "data/events.sqlite3"
        if args.candidate
        else root / "runtime/frontier/events.sqlite3"
    )
    with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True) as c:
        c.row_factory = sqlite3.Row
        state = dict(
            c.execute(
                "SELECT revision,applied_revision FROM subscription_state WHERE id=1"
            ).fetchone()
        )
        subscriptions = {}
        for identity in identities:
            row = c.execute(
                "SELECT id,platform,enabled,deleted_at,version FROM subscriptions WHERE id=?",
                (identity,),
            ).fetchone()
            subscriptions[identity] = dict(row) if row else None
    collector = json.loads((root / "runtime/frontier/collector-status.json").read_text())
    updated = datetime.fromisoformat(collector["updated_at"])
    fresh = time.time() - updated.timestamp() < 120 and collector.get("ready") is True
    targets = collector.get("source_targets", {})
    configured = {
        identity for values in collector.get("platform_targets", {}).values() for identity in values
    }
    report = {
        "observed_at": stamp(),
        "readonly": True,
        "collector_fresh": fresh,
        **state,
        "collector_revision": collector.get("subscription_revision"),
        "items": [],
    }
    with sqlite3.connect(
        (root / "runtime/app.sqlite3").resolve().as_uri() + "?mode=ro", uri=True
    ) as source:
        for identity, subscription in subscriptions.items():
            scheduled = identity in configured and identity in targets
            expected = bool(
                subscription and subscription["enabled"] and not subscription["deleted_at"]
            )
            target = targets.get(identity, {})
            count = source.execute(
                "SELECT count(*) FROM records WHERE target_id=?", (identity,)
            ).fetchone()[0]
            report["items"].append(
                {
                    "id": identity,
                    "subscription_exists": subscription is not None,
                    "expected_scheduled": expected,
                    "in_actual_scheduler": scheduled,
                    "membership_matches": expected == scheduled,
                    "original_records": count,
                    "last_success_at": target.get("last_success_at"),
                    "last_failure_at": target.get("last_failure_at"),
                    "next_run_at": target.get("next_run_at"),
                    "has_collection_error": bool(target.get("last_error")),
                }
            )
    report["applied_verified"] = bool(
        fresh
        and state["revision"] == state["applied_revision"] == collector.get("subscription_revision")
        and all(item["membership_matches"] for item in report["items"])
    )
    print(json.dumps(report), flush=True)
    if args.expect_applied and not report["applied_verified"]:
        raise RuntimeError(
            "The requested QA subscription state is not yet reflected by the actual collector"
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action",
        choices=[
            "prepare",
            "refresh",
            "serve",
            "warm",
            "deploy",
            "rollback",
            "smoke",
            "observe-sources",
            "time-plan",
            "time-repair",
        ],
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--review-sha256")
    parser.add_argument("--release", type=Path)
    parser.add_argument("--journal", type=Path)
    parser.add_argument("--database", type=Path)
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--expected-plan-sha256")
    parser.add_argument("--time-plan", type=Path)
    parser.add_argument("--time-plan-sha256")
    parser.add_argument("--ids", nargs="+")
    parser.add_argument("--expect-applied", action="store_true")
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--allow-data-rewind", action="store_true")
    parser.add_argument("--port", type=int, default=8089)
    parser.add_argument("--maximum", type=int, default=24)
    parser.add_argument("--platform", choices=["x", "youtube"])
    args = parser.parse_args()
    if args.action in {"prepare", "refresh", "deploy"} and args.manifest is None:
        parser.error("--manifest is required")
    if args.action in {"prepare", "refresh", "serve", "warm", "deploy"} and args.candidate is None:
        parser.error("--candidate is required")
    if args.action == "rollback" and args.release is None:
        parser.error("--release is required")
    if args.action != "deploy" and args.review_sha256 is not None:
        parser.error("--review-sha256 is only valid for deploy")
    if args.action in {"time-plan", "time-repair"} and args.plan is None:
        parser.error("--plan is required")
    if args.action == "time-repair" and args.expected_plan_sha256 is None:
        parser.error("--expected-plan-sha256 is required")
    if args.time_plan and (args.action != "deploy" or not args.time_plan_sha256):
        parser.error("--time-plan is only valid for deploy and requires --time-plan-sha256")
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    if not 1 <= args.maximum <= 100:
        parser.error("--maximum must be between 1 and 100")
    if args.action in {"deploy", "rollback"}:

        def interrupted(_signal, _frame):
            raise InterruptedError("Release interrupted; restoring service availability")

        signal.signal(signal.SIGTERM, interrupted)
    operation = {
        "prepare": prepare,
        "refresh": refresh,
        "serve": serve,
        "warm": warm,
        "deploy": deploy,
        "rollback": rollback,
        "smoke": smoke,
        "observe-sources": observe_sources,
        "time-plan": time_plan,
        "time-repair": time_repair,
    }[args.action]
    # Each write-capable function self-guards even if imported by another
    # Python caller. The CLI must not acquire a second FD and self-deadlock.
    operation(args)


if __name__ == "__main__":
    main()
