#!/usr/bin/env python3
"""Reclaim Frontier's collected news caches; dry-run unless --apply is explicit.

Only the source/derived news databases and the named runtime cache directories
are in scope. User research, publication/task histories, credentials, release
archives, sessions, checkpoints and source files are never removed.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import sqlite3
import stat
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path


HEX64 = re.compile(r"^[a-f0-9]{64}$")
SOURCE_PROTECTION = ("work_items", "publication_marks", "legacy_record_map", "news_favorites")
RESEARCH_PROTECTION = ("bookmarks", "radar_decisions", "dossier_revisions", "radar_usefulness")
DAYS = 7


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in connection.execute("PRAGMA table_info(" + table + ")")}


def require_columns(connection: sqlite3.Connection, table: str, required: set[str]):
    if not required <= columns(connection, table):
        raise RuntimeError("Unexpected Frontier database schema: " + table)


def protections(connection: sqlite3.Connection, tables: tuple[str, ...], column: str, key: str) -> str:
    parts = []
    for table in tables:
        present = columns(connection, table)
        if not present:
            continue
        if column not in present:
            raise RuntimeError("Cannot safely inspect protected references: " + table)
        parts.append("EXISTS(SELECT 1 FROM " + table + " p WHERE p." + column + "=" + key + ")")
    return "(" + " OR ".join(parts) + ")" if parts else "0"


@contextmanager
def database(path: Path, apply: bool):
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("Frontier database is missing or is not a regular file")
    connection = sqlite3.connect(path.as_uri() + ("?mode=rw" if apply else "?mode=ro"), uri=True, timeout=8)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA busy_timeout=8000")
    if not apply:
        connection.execute("PRAGMA query_only=ON")
    try:
        yield connection
    finally:
        connection.close()


def count(connection: sqlite3.Connection, sql: str, args=()) -> int:
    return int(connection.execute(sql, args).fetchone()[0])


def runtime_path(value: object) -> str | None:
    """Accept normalized runtime-relative references only, without traversal."""
    if not isinstance(value, str) or not value or "\\" in value:
        return None
    path = Path(value)
    if path.is_absolute() or any(part in ("..", ".") for part in path.parts):
        return None
    return path.as_posix()


def referenced_record_paths(row: sqlite3.Row) -> set[str]:
    references = {"generated/website/" + hashlib.sha256(str(row["record_id"]).encode()).hexdigest()}
    if row["plugin_id"] and row["external_id"]:
        references.add("videos/" + hashlib.sha256((str(row["plugin_id"]) + ":" + str(row["external_id"])).encode()).hexdigest())
    try:
        payload = json.loads(row["payload_json"] or "{}")
    except (TypeError, ValueError):
        return references
    if not isinstance(payload, dict):
        return references
    # videos/<hash> is an explicit retained artifact reference; the video hash
    # can differ from record_id. It must therefore participate in protection.
    values = [payload.get("artifacts_path")]
    return references | {cleaned for value in values if (cleaned := runtime_path(value)) is not None}


def reclaim_source(connection: sqlite3.Connection, cutoff: str, apply: bool, report: dict) -> tuple[set[str], set[str], set[str]]:
    require_columns(connection, "records", {"record_id", "plugin_id", "external_id", "content_type", "created_at", "observed_at", "payload_json"})
    require_columns(connection, "attachments", {"record_id", "relative_path", "sha256"})
    protected = protections(connection, SOURCE_PROTECTION, "record_id", "r.record_id")
    age = "r.plugin_id IN ('telegram','x','youtube') AND r.content_type IN ('tech_news','video_pending') AND julianday(COALESCE(NULLIF(r.created_at,''),r.observed_at))<julianday(?)"
    candidate = "(" + age + " AND NOT " + protected + ")"
    connection.execute("BEGIN IMMEDIATE" if apply else "BEGIN")
    try:
        report["sourceExpiredRecords"] = count(connection, "SELECT COUNT(*) FROM records r WHERE " + age, (cutoff,))
        report["sourceProtectedRecords"] = count(connection, "SELECT COUNT(*) FROM records r WHERE " + age + " AND " + protected, (cutoff,))
        report["sourceDeletedRecords"] = count(connection, "SELECT COUNT(*) FROM records r WHERE " + candidate, (cutoff,))
        report["sourceDeletedAttachments"] = count(connection, "SELECT COUNT(*) FROM attachments a JOIN records r ON r.record_id=a.record_id WHERE " + candidate, (cutoff,))
        if apply:
            connection.execute("DELETE FROM records WHERE record_id IN (SELECT r.record_id FROM records r WHERE " + candidate + ")", (cutoff,))
            # Foreign keys own attachment/version cascading. Refuse a malformed
            # schema instead of pretending that only metadata was reclaimed.
            if count(connection, "SELECT COUNT(*) FROM attachments a WHERE NOT EXISTS(SELECT 1 FROM records r WHERE r.record_id=a.record_id)"):
                raise RuntimeError("Orphan attachment rows remain; inspect Frontier foreign keys")
            retain_sql, retain_args = "1", ()
        else:
            retain_sql, retain_args = "NOT " + candidate, (cutoff,)
        retained_ids: set[str] = set()
        retained_directories: set[str] = set()
        for row in connection.execute("SELECT r.record_id,r.plugin_id,r.external_id,r.payload_json FROM records r WHERE " + retain_sql, retain_args):
            retained_ids.add(row["record_id"])
            retained_directories.update(referenced_record_paths(row))
        paths, hashes = set(), set()
        for row in connection.execute("SELECT a.relative_path,a.sha256 FROM attachments a JOIN records r ON r.record_id=a.record_id WHERE " + retain_sql, retain_args):
            if cleaned := runtime_path(row["relative_path"]):
                paths.add(cleaned)
            if isinstance(row["sha256"], str) and HEX64.fullmatch(row["sha256"]):
                hashes.add(row["sha256"])
        connection.commit()
        report["sourceRetainedRecords"] = len(retained_ids)
        return retained_ids, retained_directories, paths | {"@sha256/" + value for value in hashes}
    except Exception:
        connection.rollback()
        raise


def reclaim_derived(connection: sqlite3.Connection, cutoff: str, apply: bool, report: dict) -> set[str]:
    require_columns(connection, "raw_records", {"record_id", "event_id", "ingested_at"})
    require_columns(connection, "events", {"id", "created_at"})
    require_columns(connection, "media_assets", {"record_id", "relative_path"})
    protected_raw = protections(connection, RESEARCH_PROTECTION, "event_id", "r.event_id")
    protected_event = protections(connection, RESEARCH_PROTECTION, "event_id", "e.id")
    raw_candidate = "(julianday(r.ingested_at)<julianday(?) AND NOT " + protected_raw + ")"
    connection.execute("BEGIN IMMEDIATE" if apply else "BEGIN")
    try:
        report["derivedDeletedRecords"] = count(connection, "SELECT COUNT(*) FROM raw_records r WHERE " + raw_candidate, (cutoff,))
        report["derivedProtectedRecords"] = count(connection, "SELECT COUNT(*) FROM raw_records r WHERE julianday(r.ingested_at)<julianday(?) AND " + protected_raw, (cutoff,))
        report["derivedDeletedMediaRows"] = count(connection, "SELECT COUNT(*) FROM media_assets m JOIN raw_records r ON r.record_id=m.record_id WHERE " + raw_candidate, (cutoff,))
        if apply:
            connection.execute("DELETE FROM raw_records WHERE record_id IN (SELECT r.record_id FROM raw_records r WHERE " + raw_candidate + ")", (cutoff,))
            event_where = "julianday(e.created_at)<julianday(?) AND NOT " + protected_event + " AND NOT EXISTS(SELECT 1 FROM raw_records r WHERE r.event_id=e.id)"
            event_args = (cutoff,)
            retain_raw, retain_args = "1", ()
        else:
            event_where = "julianday(e.created_at)<julianday(?) AND NOT " + protected_event + " AND NOT EXISTS(SELECT 1 FROM raw_records r WHERE r.event_id=e.id AND NOT " + raw_candidate + ")"
            event_args = (cutoff, cutoff)
            retain_raw, retain_args = "NOT " + raw_candidate, (cutoff,)
        report["derivedDeletedEvents"] = count(connection, "SELECT COUNT(*) FROM events e WHERE " + event_where, event_args)
        if apply:
            connection.execute("DELETE FROM events WHERE id IN (SELECT e.id FROM events e WHERE " + event_where + ")", event_args)
        references = set()
        for row in connection.execute("SELECT m.relative_path FROM media_assets m JOIN raw_records r ON r.record_id=m.record_id WHERE " + retain_raw, retain_args):
            if cleaned := runtime_path(row["relative_path"]):
                references.add(cleaned)
        connection.commit()
        return references
    except Exception:
        connection.rollback()
        raise


def regular_files(directory: Path):
    if not directory.exists() or directory.is_symlink() or not directory.is_dir():
        return
    for parent, folders, files in os.walk(directory, followlinks=False):
        base = Path(parent)
        folders[:] = [name for name in folders if not (base / name).is_symlink()]
        for name in files:
            file = base / name
            try:
                info = file.lstat()
            except FileNotFoundError:
                continue
            if stat.S_ISREG(info.st_mode):
                yield file, info


def retained_video_dirs(retained_ids: set[str], directory_refs: set[str], file_refs: set[str]) -> set[str]:
    keep = set(retained_ids)
    for reference in directory_refs | file_refs:
        parts = reference.split("/")
        if len(parts) >= 2 and parts[0] == "videos" and HEX64.fullmatch(parts[1]):
            keep.add(parts[1])
        if len(parts) >= 3 and parts[:2] == ["generated", "website"] and HEX64.fullmatch(parts[2]):
            keep.add(parts[2])
    return keep


def cache_candidates(runtime: Path, cutoff_epoch: float, retained_ids: set[str], directory_refs: set[str], references: set[str]):
    media = runtime / "media/sha256"
    for file, info in regular_files(media) or ():
        relative = file.relative_to(runtime).as_posix()
        if (len(file.relative_to(media).parts) == 2 and HEX64.fullmatch(file.name)
                and file.parent.name == file.name[:2] and info.st_mtime < cutoff_epoch
                and relative not in references and "@sha256/" + file.name not in references):
            yield "sourceMedia", file, info
    for file, info in regular_files(runtime / "frontier/media") or ():
        if info.st_mtime < cutoff_epoch and file.relative_to(runtime).as_posix() not in references:
            yield "derivedMedia", file, info
    keep = retained_video_dirs(retained_ids, directory_refs, references)
    for group, directory in (("video", runtime / "videos"), ("poster", runtime / "generated/website")):
        if not directory.is_dir() or directory.is_symlink():
            continue
        for child in directory.iterdir():
            if not HEX64.fullmatch(child.name) or child.name in keep or child.is_symlink() or not child.is_dir():
                continue
            safe = True
            children = []
            try:
                if child.stat().st_mtime >= cutoff_epoch:
                    continue
                for parent, folders, files in os.walk(child, followlinks=False):
                    for name in [*folders, *files]:
                        path = Path(parent) / name
                        info = path.lstat()
                        if stat.S_ISLNK(info.st_mode) or info.st_mtime >= cutoff_epoch or not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
                            safe = False
                            break
                        if stat.S_ISREG(info.st_mode):
                            children.append((path, info))
                    if not safe:
                        break
            except FileNotFoundError:
                safe = False
            if safe:
                for path, info in children:
                    yield group, path, info
    for file, info in regular_files(runtime / "tmp") or ():
        if info.st_mtime < cutoff_epoch:
            yield "temporary", file, info


def live_referenced(source: sqlite3.Connection, derived: sqlite3.Connection, runtime: Path, file: Path, record_cache: dict) -> bool:
    """Recheck current references immediately before unlinking an old file."""
    relative = file.relative_to(runtime).as_posix()
    if source.execute("SELECT 1 FROM attachments WHERE relative_path=? OR sha256=? LIMIT 1", (relative, file.name)).fetchone():
        return True
    parts = relative.split("/")
    artifact = "/".join(parts[:2]) if parts[0] == "videos" and len(parts) >= 3 else "/".join(parts[:3]) if parts[:2] == ["generated", "website"] and len(parts) >= 4 else None
    if artifact:
        identity = artifact.split("/")[-1]
        version = count(source, "PRAGMA data_version")
        if record_cache.get("version") != version:
            current_ids, current_paths = set(), set()
            for row in source.execute("SELECT record_id,plugin_id,external_id,payload_json FROM records"):
                current_ids.add(row["record_id"])
                current_paths.update(referenced_record_paths(row))
            record_cache.update(version=version, ids=current_ids, paths=current_paths)
        if identity in record_cache["ids"] or artifact in record_cache["paths"]:
            return True
    return bool(derived.execute("SELECT 1 FROM media_assets WHERE relative_path=? LIMIT 1", (relative,)).fetchone())


def clean_empty_hash_dirs(runtime: Path, retained: set[str], cutoff_epoch: float):
    # Only remove the explicitly owned, now-empty hash subdirectories. Never
    # remove broad runtime roots or chase a symlink during cleanup.
    for directory in (runtime / "videos", runtime / "generated/website"):
        if directory.is_symlink() or not directory.is_dir():
            continue
        for child in directory.iterdir():
            if not HEX64.fullmatch(child.name) or child.name in retained or child.is_symlink() or not child.is_dir() or child.stat().st_mtime >= cutoff_epoch:
                continue
            for parent, folders, files in os.walk(child, topdown=False, followlinks=False):
                base = Path(parent)
                for name in folders:
                    folder = base / name
                    if not folder.is_symlink():
                        try:
                            folder.rmdir()
                        except OSError:
                            pass
                try:
                    base.rmdir()
                except OSError:
                    pass


def checkpoint(connection: sqlite3.Connection, report: dict, label: str):
    values = connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
    report[label + "CheckpointBusy"] = int(values[0])
    report[label + "ReusableDatabaseBytes"] = count(connection, "PRAGMA freelist_count") * count(connection, "PRAGMA page_size")
    # Free pages are reused by the next collector writes. Avoid repeated VACUUM
    # of a small production database or large temporary copies during cleanup.


def save_status(frontier: Path, report: dict):
    if frontier.is_symlink() or not frontier.is_dir():
        raise RuntimeError("Unsafe Frontier status directory")
    destination = frontier / "retention-status.json"
    if destination.is_symlink():
        raise RuntimeError("Unsafe Frontier retention status file")
    temporary = frontier / (".retention-status-" + str(os.getpid()) + ".tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(report, stream, separators=(",", ":"))
            stream.write("\n")
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def run(root: Path, apply: bool = False, *, now: datetime | None = None) -> dict:
    root = root.absolute()
    if root.is_symlink() or not root.is_dir():
        raise RuntimeError("Frontier root must be an existing real directory")
    root = root.resolve()
    runtime = root / "runtime"
    if runtime.is_symlink() or not runtime.is_dir() or runtime.resolve() != runtime:
        raise RuntimeError("Frontier runtime must be a real directory inside its project")
    for relative in ("frontier", "media", "media/sha256", "videos", "generated", "generated/website", "tmp"):
        path = runtime / relative
        if path.is_symlink() or (path.exists() and (not path.is_dir() or path.resolve() != path)):
            raise RuntimeError("Unsafe Frontier runtime cache directory")
    timestamp = now or datetime.now(timezone.utc)
    cutoff = timestamp - timedelta(days=DAYS)
    report = {"version": 1, "applied": int(apply), "runAt": round(timestamp.timestamp() * 1000), "retentionDays": DAYS}
    # The existing lock belongs only to this cleanup task, never the collector.
    # Read-only runs create no lock, status, temporary file, or database.
    lock = None
    try:
        if apply:
            lock_path = runtime / "frontier/channel-retention.lock"
            if lock_path.is_symlink():
                raise RuntimeError("Unsafe Frontier retention lock")
            lock = os.open(lock_path, os.O_WRONLY | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with database(runtime / "app.sqlite3", apply) as source, database(runtime / "frontier/events.sqlite3", apply) as derived:
            # Validate every protected schema before either database is mutated.
            for table in SOURCE_PROTECTION:
                if columns(source, table) and "record_id" not in columns(source, table):
                    raise RuntimeError("Unexpected protected source schema: " + table)
            for table in RESEARCH_PROTECTION:
                if columns(derived, table) and "event_id" not in columns(derived, table):
                    raise RuntimeError("Unexpected protected research schema: " + table)
            require_columns(derived, "media_assets", {"record_id", "relative_path"})
            require_columns(derived, "events", {"id", "created_at"})
            require_columns(derived, "raw_records", {"record_id", "event_id", "ingested_at"})
            ids, directories, source_refs = reclaim_source(source, iso(cutoff), apply, report)
            derived_refs = reclaim_derived(derived, iso(cutoff), apply, report)
            references = source_refs | derived_refs
            report["files"] = 0
            report["bytes"] = 0
            report["concurrentReferencesSkipped"] = 0
            live_record_cache: dict = {}
            for group, file, expected in cache_candidates(runtime, cutoff.timestamp(), ids, directories, references):
                if apply:
                    try:
                        current = file.lstat()
                    except FileNotFoundError:
                        continue
                    if (not stat.S_ISREG(current.st_mode) or current.st_ino != expected.st_ino
                            or current.st_dev != expected.st_dev or current.st_mtime >= cutoff.timestamp()
                            or current.st_size != expected.st_size or file.resolve() != file):
                        continue
                    if live_referenced(source, derived, runtime, file, live_record_cache):
                        report["concurrentReferencesSkipped"] += 1
                        continue
                    file.unlink()
                report["files"] += 1
                report["bytes"] += expected.st_size
                report[group + "Files"] = report.get(group + "Files", 0) + 1
                report[group + "Bytes"] = report.get(group + "Bytes", 0) + expected.st_size
            if apply:
                clean_empty_hash_dirs(runtime, retained_video_dirs(ids, directories, references), cutoff.timestamp())
                checkpoint(source, report, "source")
                checkpoint(derived, report, "derived")
        if apply:
            save_status(runtime / "frontier", report)
        return report
    finally:
        if lock is not None:
            os.close(lock)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Only calculate the cleanup; the default")
    mode.add_argument("--apply", action="store_true", help="Delete expired unprotected news and unreferenced old cache files")
    args = parser.parse_args()
    try:
        print(json.dumps(run(args.root, args.apply), separators=(",", ":")))
    except (RuntimeError, sqlite3.Error, OSError) as error:
        print("Frontier retention failed: " + str(error), file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
