"""Normalized records, versions, and content-addressed attachment files."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from xhs_local.core.clock import utc_iso
from xhs_local.core.contracts import (
    AttachmentInput,
    CollectBatch,
    NewsCandidate,
    SourceRecord,
    StoredAttachment,
)
from xhs_local.core.identifiers import content_hash, new_id, stable_record_id
from xhs_local.core.states import WorkTopic

from .checkpoints import CheckpointRepository
from .database import Database
from .outbox import OutboxRepository
from .work_items import WorkItemRepository


def _timestamp(value: datetime | None = None) -> str:
    return utc_iso(value)


def _datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _attachment_id(record_id: str, index: int, sha256: str) -> str:
    return hashlib.sha256(f"{record_id}\0{index}\0{sha256}".encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class StoredRecord:
    record: SourceRecord
    attachments: tuple[StoredAttachment, ...]
    content_hash: str


@dataclass(frozen=True, slots=True)
class CommitResult:
    inserted_record_ids: tuple[str, ...]
    updated_record_ids: tuple[str, ...]
    work_ids: tuple[str, ...]


class MediaStore:
    """Write immutable media by digest below ``runtime/media/sha256``."""

    def __init__(self, runtime_root: str | Path) -> None:
        self.runtime_root = Path(runtime_root).expanduser().resolve()
        self.root = self.runtime_root / "media" / "sha256"

    def put(self, data: bytes | Path) -> tuple[str, int, str]:
        if isinstance(data, Path):
            if not data.is_file() or not data.stat().st_size:
                raise ValueError("attachment file must be non-empty")
            with data.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            destination = self.root / digest[:2] / digest
            destination.parent.mkdir(parents=True, exist_ok=True)
            if not destination.exists():
                temporary = destination.with_name(f".{digest}.{os.getpid()}.{new_id()}.tmp")
                try:
                    with data.open("rb") as source, temporary.open("xb") as target:
                        shutil.copyfileobj(source, target, 256 * 1024)
                        target.flush()
                        os.fsync(target.fileno())
                    os.replace(temporary, destination)
                finally:
                    temporary.unlink(missing_ok=True)
            return (
                digest,
                destination.stat().st_size,
                destination.relative_to(self.runtime_root).as_posix(),
            )
        if not isinstance(data, bytes) or not data:
            raise ValueError("attachment data must be non-empty bytes")
        digest = hashlib.sha256(data).hexdigest()
        destination = self.root / digest[:2] / digest
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            existing = destination.read_bytes()
            if len(existing) != len(data) or hashlib.sha256(existing).hexdigest() != digest:
                raise RuntimeError(f"media digest collision or corruption: {destination}")
        else:
            temporary = destination.with_name(f".{digest}.{os.getpid()}.{new_id()}.tmp")
            try:
                with temporary.open("xb") as stream:
                    stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, destination)
            finally:
                temporary.unlink(missing_ok=True)
        relative = destination.relative_to(self.runtime_root).as_posix()
        return digest, len(data), relative

    def resolve(self, relative_path: str) -> Path:
        path = (self.runtime_root / relative_path).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("media path escapes the content-addressed store")
        return path


class RecordsRepository:
    def __init__(self, database: Database, runtime_root: str | Path) -> None:
        self.database = database
        self.media = MediaStore(runtime_root)

    def news_feed(
        self,
        *,
        source: str = "",
        query: str = "",
        favorites: bool = False,
        page: int = 1,
        page_size: int = 30,
    ) -> dict:
        """Public fields only; committed news needs no review or publication mark."""
        where = "content_type IN ('tech_news','video_pending')"
        parameters: list[object] = []
        if favorites:
            where += " AND record_id IN (SELECT record_id FROM news_favorites)"
        if source:
            where += " AND plugin_id=?"
            parameters.append(source)
        if query:
            where += " AND (instr(lower(title || ' ' || text || ' ' || source_name),lower(?))>0)"
            parameters.append(query)
        with self.database.locked() as connection:
            counts = {
                row["plugin_id"]: row["total"]
                for row in connection.execute(
                    "SELECT plugin_id,count(*) AS total FROM records "
                    "WHERE content_type IN ('tech_news','video_pending') GROUP BY plugin_id"
                )
            }
            total = connection.execute(
                f"SELECT count(*) FROM records WHERE {where}", parameters
            ).fetchone()[0]
            favorite_count = connection.execute("SELECT count(*) FROM news_favorites").fetchone()[0]
            rows = connection.execute(
                f"""
                SELECT record_id,source_id,target_id,plugin_id,title,text,source_name,source_url,
                       occurred_at,
                       content_hash,observed_at,json_extract(payload_json,'$.avatar_attachment_index')
                         AS avatar_index,
                       record_id IN (SELECT record_id FROM news_favorites) AS favorite
                  FROM records WHERE {where}
                 ORDER BY occurred_at DESC,record_id DESC LIMIT ? OFFSET ?
                """,
                (*parameters, page_size, (page - 1) * page_size),
            ).fetchall()
            attachments = self._attachments_in(connection, [row["record_id"] for row in rows])
        items = []
        for row in rows:
            item = dict(row)
            item["favorite"] = bool(item["favorite"])
            avatar_index = item.pop("avatar_index")
            item["images"] = []
            item["avatar"] = None
            for attachment in attachments.get(row["record_id"], ()):
                if attachment.mime_type not in {
                    "image/jpeg",
                    "image/png",
                    "image/webp",
                    "image/gif",
                }:
                    continue
                url = f"/media/{attachment.attachment_id}"
                if attachment.index == avatar_index:
                    item["avatar"] = url
                else:
                    item["images"].append(url)
            items.append(item)
        return {
            "items": items,
            "total": total,
            "counts": counts,
            "favorite_count": favorite_count,
            "page": page,
            "page_size": page_size,
        }

    def set_news_favorite(self, record_id: str, favorite: bool) -> bool:
        with self.database.transaction() as connection:
            exists = connection.execute(
                "SELECT 1 FROM records WHERE record_id=? "
                "AND content_type IN ('tech_news','video_pending')",
                (record_id,),
            ).fetchone()
            if exists is None:
                return False
            if favorite:
                connection.execute(
                    "INSERT OR IGNORE INTO news_favorites(record_id,created_at) VALUES(?,?)",
                    (record_id, _timestamp()),
                )
            else:
                connection.execute("DELETE FROM news_favorites WHERE record_id=?", (record_id,))
        return True

    def deleted_news_ids(self, record_ids: tuple[str, ...]) -> set[str]:
        if not record_ids:
            return set()
        placeholders = ",".join("?" for _ in record_ids)
        with self.database.locked() as connection:
            return {
                row["record_id"]
                for row in connection.execute(
                    f"SELECT record_id FROM news_deleted WHERE record_id IN ({placeholders})",
                    record_ids,
                )
            }

    def delete_news(self, record_id: str) -> None:
        with self.database.transaction() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO news_deleted(record_id,deleted_at) "
                "SELECT record_id,? FROM records WHERE record_id=? "
                "AND content_type IN ('tech_news','video_pending')",
                (_timestamp(), record_id),
            )
            connection.execute(
                "DELETE FROM records WHERE record_id=? "
                "AND record_id IN (SELECT record_id FROM news_deleted)",
                (record_id,),
            )

    def remove_source_news(self, source_id: str, target_id: str) -> int:
        """Unfollowing removes ordinary posts while preserving saved favorites."""
        with self.database.transaction() as connection:
            return connection.execute(
                "DELETE FROM records WHERE source_id=? AND target_id=? "
                "AND content_type IN ('tech_news','video_pending') "
                "AND record_id NOT IN (SELECT record_id FROM news_favorites)",
                (source_id, target_id),
            ).rowcount

    def news_image(self, attachment_id: str) -> tuple[Path, str] | None:
        with self.database.locked() as connection:
            row = connection.execute(
                """
                SELECT a.relative_path,a.mime_type FROM attachments a
                  JOIN records r ON r.record_id=a.record_id
                 WHERE a.attachment_id=? AND r.content_type IN ('tech_news','video_pending')
                   AND a.mime_type IN ('image/jpeg','image/png','image/webp','image/gif')
                """,
                (attachment_id,),
            ).fetchone()
        if row is None:
            return None
        path = self.media.resolve(row["relative_path"])
        return (path, row["mime_type"]) if path.is_file() else None

    def _materialize(
        self, record: SourceRecord
    ) -> tuple[tuple[StoredAttachment, ...], list[dict[str, object]]]:
        stored: list[StoredAttachment] = []
        hashes: list[dict[str, object]] = []
        for index, attachment in enumerate(record.attachments):
            digest, byte_size, relative_path = self.media.put(attachment.data)
            if isinstance(attachment.data, Path) and attachment.data.is_relative_to(
                self.media.runtime_root / "cache" / "source_media"
            ):
                attachment.data.unlink(missing_ok=True)
            stored_attachment = StoredAttachment(
                attachment_id=_attachment_id(record.record_id, index, digest),
                record_id=record.record_id,
                index=index,
                mime_type=attachment.mime_type,
                file_name=attachment.file_name,
                relative_path=relative_path,
                byte_size=byte_size,
                sha256=digest,
                width=attachment.width,
                height=attachment.height,
            )
            stored.append(stored_attachment)
            hashes.append(
                {
                    "index": index,
                    "mime_type": attachment.mime_type,
                    "file_name": attachment.file_name,
                    "sha256": digest,
                    "byte_size": byte_size,
                    "width": attachment.width,
                    "height": attachment.height,
                }
            )
        return tuple(stored), hashes

    @staticmethod
    def _snapshot(record: SourceRecord, attachment_hashes: list[dict[str, object]]) -> dict:
        return {
            "record_id": record.record_id,
            "source_id": record.source_id,
            "target_id": record.target_id,
            "plugin_id": record.plugin_id,
            "external_id": record.external_id,
            "content_type": record.content_type,
            "occurred_at": _timestamp(record.occurred_at),
            "observed_at": _timestamp(record.observed_at),
            "title": record.title,
            "text": record.text,
            "source_name": record.source_name,
            "source_url": record.source_url,
            "group_id": record.group_id,
            "payload": record.payload,
            "attachments": attachment_hashes,
        }

    @staticmethod
    def _upsert_in(
        connection: sqlite3.Connection,
        record: SourceRecord,
        attachments: tuple[StoredAttachment, ...],
        attachment_hashes: list[dict[str, object]],
        *,
        now: datetime | None = None,
    ) -> tuple[bool, bool]:
        snapshot = RecordsRepository._snapshot(record, attachment_hashes)
        digest = content_hash(
            {key: value for key, value in snapshot.items() if key != "observed_at"}
        )
        existing = connection.execute(
            "SELECT content_hash FROM records WHERE record_id=?", (record.record_id,)
        ).fetchone()
        inserted = existing is None
        changed = inserted or existing["content_hash"] != digest
        changed_at = _timestamp(now)
        connection.execute(
            """
            INSERT INTO records(
                record_id,source_id,target_id,plugin_id,external_id,content_type,
                occurred_at,observed_at,title,text,source_name,source_url,group_id,
                payload_json,content_hash,created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(record_id) DO UPDATE SET
                source_id=excluded.source_id,target_id=excluded.target_id,
                plugin_id=excluded.plugin_id,external_id=excluded.external_id,
                content_type=excluded.content_type,occurred_at=excluded.occurred_at,
                observed_at=excluded.observed_at,title=excluded.title,text=excluded.text,
                source_name=excluded.source_name,source_url=excluded.source_url,
                group_id=excluded.group_id,payload_json=excluded.payload_json,
                content_hash=excluded.content_hash,updated_at=excluded.updated_at
            """,
            (
                record.record_id,
                record.source_id,
                record.target_id,
                record.plugin_id,
                record.external_id,
                record.content_type,
                _timestamp(record.occurred_at),
                _timestamp(record.observed_at),
                record.title,
                record.text,
                record.source_name,
                record.source_url,
                record.group_id,
                _json(record.payload),
                digest,
                changed_at,
                changed_at,
            ),
        )
        if changed:
            connection.execute(
                """
                INSERT OR IGNORE INTO record_versions(
                    record_id,content_hash,snapshot_json,observed_at
                ) VALUES(?,?,?,?)
                """,
                (record.record_id, digest, _json(snapshot), _timestamp(record.observed_at)),
            )
            connection.execute("DELETE FROM attachments WHERE record_id=?", (record.record_id,))
            connection.executemany(
                """
                INSERT INTO attachments(
                    attachment_id,record_id,attachment_index,mime_type,file_name,
                    relative_path,byte_size,sha256,width,height,created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                """,
                [
                    (
                        attachment.attachment_id,
                        attachment.record_id,
                        attachment.index,
                        attachment.mime_type,
                        attachment.file_name,
                        attachment.relative_path,
                        attachment.byte_size,
                        attachment.sha256,
                        attachment.width,
                        attachment.height,
                        changed_at,
                    )
                    for attachment in attachments
                ],
            )
        return inserted, changed

    def upsert(self, record: SourceRecord) -> tuple[bool, bool]:
        attachments, hashes = self._materialize(record)
        with self.database.transaction() as connection:
            return self._upsert_in(connection, record, attachments, hashes)

    def commit_batch(
        self,
        batch: CollectBatch,
        *,
        work_topic: WorkTopic | str = WorkTopic.RECORD_COLLECTED,
        config_revision: str | None = None,
        create_work: bool = True,
    ) -> CommitResult:
        """Commit records, checkpoint, work, and outbox in one DB transaction."""

        if batch.source_id == "" or batch.target_id == "":
            raise ValueError("batch source_id and target_id are required")
        materialized = [(record, *self._materialize(record)) for record in batch.records]
        inserted_ids: list[str] = []
        updated_ids: list[str] = []
        work_ids: list[str] = []
        with self.database.transaction() as connection:
            for record, attachments, hashes in materialized:
                if record.source_id != batch.source_id or record.target_id != batch.target_id:
                    raise ValueError("every batch record must match the batch source and target")
                if (
                    batch.preserve_existing
                    and connection.execute(
                        "SELECT 1 FROM records WHERE record_id=?", (record.record_id,)
                    ).fetchone()
                ):
                    continue
                inserted, changed = self._upsert_in(connection, record, attachments, hashes)
                if inserted:
                    inserted_ids.append(record.record_id)
                elif changed:
                    updated_ids.append(record.record_id)
                if create_work and inserted:
                    work_id = WorkItemRepository.create_in(
                        connection,
                        work_topic,
                        record_id=record.record_id,
                        payload={"record_id": record.record_id},
                        config_revision=config_revision,
                    )
                    OutboxRepository.add_in(
                        connection,
                        work_topic,
                        work_id,
                        payload={"record_id": record.record_id},
                    )
                    work_ids.append(work_id)
            CheckpointRepository.put_in(
                connection,
                batch.source_id,
                batch.target_id,
                batch.checkpoint,
            )
        return CommitResult(tuple(inserted_ids), tuple(updated_ids), tuple(work_ids))

    @staticmethod
    def _attachments_in(
        connection: sqlite3.Connection, record_ids: tuple[str, ...] | list[str]
    ) -> dict[str, tuple[StoredAttachment, ...]]:
        if not record_ids:
            return {}
        placeholders = ",".join("?" for _record_id in record_ids)
        rows = connection.execute(
            f"""
            SELECT * FROM attachments WHERE record_id IN ({placeholders})
             ORDER BY record_id,attachment_index
            """,
            tuple(record_ids),
        ).fetchall()
        grouped: dict[str, list[StoredAttachment]] = {}
        for row in rows:
            grouped.setdefault(row["record_id"], []).append(
                StoredAttachment(
                    attachment_id=row["attachment_id"],
                    record_id=row["record_id"],
                    index=int(row["attachment_index"]),
                    mime_type=row["mime_type"],
                    file_name=row["file_name"],
                    relative_path=row["relative_path"],
                    byte_size=int(row["byte_size"]),
                    sha256=row["sha256"],
                    width=row["width"],
                    height=row["height"],
                )
            )
        return {key: tuple(value) for key, value in grouped.items()}

    @staticmethod
    def _latest_avatar_in(
        connection: sqlite3.Connection,
        source_id: str,
        target_id: str,
    ) -> StoredAttachment | None:
        row = connection.execute(
            """
            SELECT r.record_id,
                   cast(json_extract(r.payload_json,'$.avatar_attachment_index') AS integer)
                     AS avatar_index
              FROM records r
             WHERE r.source_id=? AND r.target_id=?
               AND json_type(r.payload_json,'$.avatar_attachment_index') IS NOT NULL
               AND EXISTS(
                   SELECT 1 FROM attachments a
                    WHERE a.record_id=r.record_id
                      AND a.attachment_index=cast(
                          json_extract(r.payload_json,'$.avatar_attachment_index') AS integer
                      )
               )
             ORDER BY r.observed_at DESC,r.occurred_at DESC LIMIT 1
            """,
            (source_id, target_id),
        ).fetchone()
        if row is None:
            return None
        attachments = RecordsRepository._attachments_in(connection, [row["record_id"]])
        return next(
            (
                attachment
                for attachment in attachments.get(row["record_id"], ())
                if attachment.index == int(row["avatar_index"])
            ),
            None,
        )

    def get(self, record_id: str) -> StoredRecord | None:
        with self.database.locked() as connection:
            row = connection.execute(
                "SELECT * FROM records WHERE record_id=?", (record_id,)
            ).fetchone()
            attachments = self._attachments_in(connection, [record_id])
        if row is None:
            return None
        record = SourceRecord(
            record_id=row["record_id"],
            source_id=row["source_id"],
            target_id=row["target_id"],
            plugin_id=row["plugin_id"],
            external_id=row["external_id"],
            content_type=row["content_type"],
            occurred_at=_datetime(row["occurred_at"]),
            observed_at=_datetime(row["observed_at"]),
            title=row["title"],
            text=row["text"],
            source_name=row["source_name"],
            source_url=row["source_url"],
            group_id=row["group_id"],
            payload=json.loads(row["payload_json"]),
            attachments=(),
        )
        return StoredRecord(record, attachments.get(record_id, ()), row["content_hash"])

    def enqueue_pending_videos(
        self, targets: set[tuple[str, str]], since: datetime, *, config_revision: str
    ) -> int:
        """Backfill and newly discovered video jobs share the existing atomic outbox."""
        count = 0
        with self.database.transaction() as connection:
            rows = connection.execute(
                "SELECT record_id,source_id,target_id FROM records r "
                "WHERE plugin_id='youtube' AND content_type='video_pending' AND occurred_at>=? "
                "AND NOT EXISTS(SELECT 1 FROM work_items w WHERE w.record_id=r.record_id "
                "AND w.topic=?) "
                "AND NOT EXISTS(SELECT 1 FROM publication_marks p WHERE p.record_id=r.record_id "
                "AND p.sink='agents-company' AND p.status IN ('deleted','expired')) "
                "ORDER BY occurred_at,record_id",
                (_timestamp(since), WorkTopic.VIDEO_PREPARE.value),
            ).fetchall()
            for row in rows:
                if (row["source_id"], row["target_id"]) not in targets:
                    continue
                work_id = WorkItemRepository.create_in(
                    connection, WorkTopic.VIDEO_PREPARE,
                    record_id=row["record_id"], config_revision=config_revision,
                )
                OutboxRepository.add_in(connection, WorkTopic.VIDEO_PREPARE, work_id)
                count += 1
        return count

    def pending_agents_news(
        self,
        sources: dict[tuple[str, str], str],
        since: datetime,
        *,
        limit: int = 50,
        document_since: datetime | None = None,
    ) -> list[tuple[str, str]]:
        """Current retained content not yet confirmed by its Core subscription."""
        with self.database.locked() as connection:
            rows = connection.execute(
                "SELECT record_id,plugin_id,target_id,content_hash FROM records "
                "WHERE content_type='tech_news' AND (occurred_at>=? OR "
                "(json_extract(payload_json,'$.cloud_document_channel')=1 AND occurred_at>=?)) "
                "ORDER BY occurred_at,record_id",
                (_timestamp(since), _timestamp(document_since or since)),
            ).fetchall()
            marks = {
                (row["record_id"], row["account_id"]): row
                for row in connection.execute(
                    "SELECT record_id,account_id,status,detail_json FROM publication_marks "
                    "WHERE sink='agents-company'"
                )
            }
        pending = []
        for row in rows:
            account = sources.get((row["plugin_id"], row["target_id"]))
            if account is None:
                continue
            mark = marks.get((row["record_id"], account))
            if mark and (
                mark["status"] in {"deleted", "expired"}
                or json.loads(mark["detail_json"] or "{}").get("contentHash") == row["content_hash"]
            ):
                continue
            pending.append((row["record_id"], account))
            if len(pending) == limit:
                break
        return pending

    def mark_agents_news(
        self, record_id: str, source_id: str, digest: str, status: str
    ) -> None:
        # Retention may remove a record while its HTTP request is in flight.
        with self.database.transaction() as connection:
            connection.execute(
                "INSERT INTO publication_marks("
                "record_id,sink,account_id,status,marked_at,detail_json) "
                "SELECT record_id,'agents-company',?,?,?,? FROM records WHERE record_id=? "
                "ON CONFLICT(record_id,sink,account_id) DO UPDATE SET "
                "status=excluded.status,marked_at=excluded.marked_at,detail_json=excluded.detail_json",
                (source_id, status, _timestamp(), _json({"contentHash": digest}), record_id),
            )

    def count(self) -> int:
        with self.database.locked() as connection:
            return int(connection.execute("SELECT count(*) FROM records").fetchone()[0])

    def published_counts_by_plugin(
        self,
        since: datetime,
        *,
        sink: str,
        account_id: str,
        plugin_ids: tuple[str, ...],
    ) -> dict[str, int]:
        """Count recent published news items for platform-level exposure balancing."""

        counts = dict.fromkeys(plugin_ids, 0)
        if not counts:
            return counts
        placeholders = ",".join("?" for _plugin_id in plugin_ids)
        with self.database.locked() as connection:
            rows = connection.execute(
                f"""
                SELECT r.plugin_id,count(*) AS item_count
                  FROM publication_marks p
                  JOIN records r ON r.record_id=p.record_id
                 WHERE p.sink=? AND p.account_id=? AND p.status='published'
                   AND p.marked_at>=? AND r.content_type='tech_news'
                   AND r.plugin_id IN ({placeholders})
                 GROUP BY r.plugin_id
                """,
                (sink, account_id, _timestamp(since), *plugin_ids),
            ).fetchall()
        counts.update({row["plugin_id"]: int(row["item_count"]) for row in rows})
        return counts

    def news_candidates(
        self,
        start: datetime,
        end: datetime,
        *,
        limit: int = 12,
        exclude_marked: bool = True,
        sink: str,
        account_id: str,
        descending: bool = False,
        minimum_text_characters: int = 20,
        plugin_ids: tuple[str, ...] | None = None,
    ) -> list[NewsCandidate]:
        """Preserve the legacy album grouping and 20-character candidate rule."""

        if limit < 1:
            raise ValueError("limit must be positive")
        if minimum_text_characters < 1:
            raise ValueError("minimum_text_characters must be positive")
        if plugin_ids is not None and any(not plugin_id for plugin_id in plugin_ids):
            raise ValueError("plugin_ids must contain non-empty identifiers")
        with self.database.locked() as connection:
            plugin_clause = ""
            parameters: list[object] = [_timestamp(start), _timestamp(end)]
            if plugin_ids:
                placeholders = ",".join("?" for _plugin_id in plugin_ids)
                plugin_clause = f" AND plugin_id IN ({placeholders})"
                parameters.extend(plugin_ids)
            rows = connection.execute(
                f"""
                SELECT * FROM records r
                 WHERE content_type='tech_news'
                   AND coalesce(json_extract(payload_json,'$.ready_at'),occurred_at)>=?
                   AND coalesce(json_extract(payload_json,'$.ready_at'),occurred_at)<?
                 {plugin_clause}
                """,
                parameters,
            ).fetchall()
            rows = sorted(
                rows,
                key=lambda row: (
                    row["occurred_at"],
                    (0, int(row["external_id"]))
                    if str(row["external_id"]).isdecimal()
                    else (1, str(row["external_id"])),
                    row["record_id"],
                ),
                reverse=descending,
            )
            groups: dict[tuple[str, str, str], list[sqlite3.Row]] = {}
            for row in rows:
                group = row["group_id"] or f"record:{row['record_id']}"
                key = (row["source_id"], row["target_id"], group)
                groups.setdefault(key, []).append(row)
            candidates: list[NewsCandidate] = []
            for grouped_rows in groups.values():
                texts: list[str] = []
                for row in grouped_rows:
                    value = row["text"].strip()
                    if value and value not in texts:
                        texts.append(value)
                text = "\n\n".join(texts)
                if len(text) < minimum_text_characters:
                    continue
                record_ids = tuple(row["record_id"] for row in grouped_rows)
                if exclude_marked:
                    placeholders = ",".join("?" for _record_id in record_ids)
                    already_marked = connection.execute(
                        f"""
                        SELECT 1 FROM publication_marks WHERE record_id IN ({placeholders})
                         AND sink=? AND account_id=? LIMIT 1
                        """,
                        (*record_ids, sink, account_id),
                    ).fetchone()
                    if already_marked is not None:
                        continue
                attachment_map = self._attachments_in(connection, list(record_ids))
                attachment_rows = sorted(
                    grouped_rows,
                    key=lambda row: (
                        row["occurred_at"],
                        (0, int(row["external_id"]))
                        if str(row["external_id"]).isdecimal()
                        else (1, str(row["external_id"])),
                        row["record_id"],
                    ),
                )
                avatar = None
                content_attachments: list[StoredAttachment] = []
                for row in attachment_rows:
                    payload = json.loads(row["payload_json"])
                    avatar_index = payload.get("avatar_attachment_index")
                    for attachment in attachment_map.get(row["record_id"], ()):
                        if attachment.index == avatar_index and avatar is None:
                            avatar = attachment
                        else:
                            content_attachments.append(attachment)
                newest = max(grouped_rows, key=lambda row: row["occurred_at"])
                if avatar is None:
                    avatar = self._latest_avatar_in(
                        connection,
                        newest["source_id"],
                        newest["target_id"],
                    )
                candidate_id = (
                    record_ids[0]
                    if newest["group_id"] is None
                    else stable_record_id(
                        newest["source_id"],
                        newest["target_id"],
                        f"group:{newest['group_id']}",
                    )
                )
                candidates.append(
                    NewsCandidate(
                        record_id=candidate_id,
                        source_name=newest["source_name"],
                        occurred_at=_datetime(newest["occurred_at"]),
                        text=text,
                        group_record_ids=record_ids,
                        attachments=tuple(content_attachments),
                        avatar=avatar,
                        plugin_id=newest["plugin_id"],
                        title=newest["title"],
                    )
                )
                if len(candidates) >= limit:
                    break
        return candidates


def attachment_input(
    *,
    mime_type: str,
    file_name: str,
    data: bytes,
    width: int | None = None,
    height: int | None = None,
) -> AttachmentInput:
    """Named constructor kept for migration code and fixture readability."""

    return AttachmentInput(mime_type, file_name, data, width, height)
