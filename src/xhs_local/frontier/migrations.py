"""Additive Frontier v2 migration; original collector tables are never modified."""

from __future__ import annotations

SCHEMA_V2 = """
CREATE TABLE IF NOT EXISTS preferences(
 owner TEXT PRIMARY KEY,data TEXT NOT NULL,version INTEGER NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS event_reads(
 owner TEXT NOT NULL,event_id TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
 read_at TEXT NOT NULL,PRIMARY KEY(owner,event_id));
CREATE TABLE IF NOT EXISTS raw_reads(
 owner TEXT NOT NULL,record_id TEXT NOT NULL REFERENCES raw_records(record_id) ON DELETE CASCADE,
 read_at TEXT NOT NULL,PRIMARY KEY(owner,record_id));
CREATE TABLE IF NOT EXISTS subscriptions(
 id TEXT PRIMARY KEY,parent_id TEXT NOT NULL,platform TEXT NOT NULL,locator TEXT NOT NULL,
 canonical_key TEXT NOT NULL,name TEXT NOT NULL,poll_seconds INTEGER NOT NULL,
 enabled INTEGER NOT NULL DEFAULT 1,deleted_at TEXT,restore_enabled INTEGER NOT NULL DEFAULT 1,
 target_options TEXT NOT NULL DEFAULT '{}',version INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS subscriptions_key ON subscriptions(platform,canonical_key);
CREATE TABLE IF NOT EXISTS subscription_state(
 id INTEGER PRIMARY KEY CHECK(id=1),revision INTEGER NOT NULL DEFAULT 1,
 applied_revision INTEGER NOT NULL DEFAULT 0,applied_at TEXT,error TEXT,updated_at TEXT);
INSERT OR IGNORE INTO subscription_state(id) VALUES(1);
CREATE TABLE IF NOT EXISTS media_assets(
 id TEXT PRIMARY KEY,record_id TEXT NOT NULL REFERENCES raw_records(record_id) ON DELETE CASCADE,
 attachment_id TEXT,origin_url TEXT,relative_path TEXT,mime_type TEXT,
 sha256 TEXT,kind TEXT NOT NULL,
 origin TEXT NOT NULL,platform TEXT NOT NULL,state TEXT NOT NULL,
 position INTEGER NOT NULL DEFAULT 0,
 attempts INTEGER NOT NULL DEFAULT 0,
 next_attempt REAL NOT NULL DEFAULT 0,error TEXT,updated_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS media_record ON media_assets(record_id);
CREATE INDEX IF NOT EXISTS media_pending ON media_assets(state,next_attempt);
CREATE INDEX IF NOT EXISTS events_first_ingested ON events(first_ingested_at DESC,id);
CREATE INDEX IF NOT EXISTS raw_target ON raw_records(target_id,event_id);
CREATE INDEX IF NOT EXISTS raw_first_ingested ON raw_records(first_ingested_at DESC,record_id);
"""


# Sidecar feature migration: do not bump schema_version (V2 readers still expect 2).
# Additive DDL runs for BOTH version 1 (after V2) and already-migrated version 2.
SCHEMA_RADAR = """
CREATE TABLE IF NOT EXISTS radar_topics(
 id TEXT PRIMARY KEY,owner TEXT NOT NULL,name TEXT NOT NULL CHECK(length(name) BETWEEN 1 AND 48),
 query TEXT NOT NULL CHECK(length(query) BETWEEN 1 AND 160),platforms TEXT NOT NULL,
 min_importance INTEGER NOT NULL CHECK(min_importance BETWEEN 0 AND 100),
 created_at TEXT NOT NULL,updated_at TEXT NOT NULL,last_reviewed_at TEXT,
 version INTEGER NOT NULL DEFAULT 1 CHECK(version>=1));
CREATE INDEX IF NOT EXISTS radar_topics_owner_created
 ON radar_topics(owner,created_at,id);
CREATE INDEX IF NOT EXISTS radar_events_ingested
 ON events(coalesce(first_ingested_at,created_at),importance DESC,id);
CREATE INDEX IF NOT EXISTS radar_source_event_platform
 ON raw_records(event_id,plugin_id,state);
CREATE TABLE IF NOT EXISTS radar_decisions(
 owner TEXT NOT NULL,topic_id TEXT NOT NULL REFERENCES radar_topics(id) ON DELETE CASCADE,
 event_id TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
 decision TEXT NOT NULL CHECK(decision IN ('dismiss','watch','research')),
 decided_at TEXT NOT NULL,PRIMARY KEY(owner,topic_id,event_id));
CREATE INDEX IF NOT EXISTS radar_decisions_topic
 ON radar_decisions(owner,topic_id,decision);
-- Snapshots freeze a reviewed radar round and cascade on topic deletion.
CREATE TABLE IF NOT EXISTS radar_briefs(
 id TEXT PRIMARY KEY,
 owner TEXT NOT NULL,
 topic_id TEXT NOT NULL REFERENCES radar_topics(id) ON DELETE CASCADE,
 generated_at TEXT NOT NULL,
 topic_version INTEGER NOT NULL,
 data TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS radar_briefs_recent
 ON radar_briefs(owner,topic_id,generated_at DESC,id DESC);
"""


# V4.4 additive value feedback. This sidecar never updates V2/triage/raw
# tables or stored review briefs. The composite topic FK prevents writing a
# feedback row under an owner different from its parent topic, even by SQL.
SCHEMA_RADAR_USEFULNESS = """
CREATE INDEX IF NOT EXISTS audit_owner_revision
 ON audit(owner,id DESC);
CREATE UNIQUE INDEX IF NOT EXISTS radar_topics_id_owner_fk
 ON radar_topics(id,owner);
CREATE TABLE IF NOT EXISTS radar_usefulness(
 owner TEXT NOT NULL,
 topic_id TEXT NOT NULL,
 event_id TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
 value TEXT NOT NULL CHECK(value IN ('useful','noise')),
 rated_at TEXT NOT NULL,
 PRIMARY KEY(owner,topic_id,event_id),
 FOREIGN KEY(topic_id,owner) REFERENCES radar_topics(id,owner) ON DELETE CASCADE);
CREATE INDEX IF NOT EXISTS radar_usefulness_owner_rated
 ON radar_usefulness(owner,rated_at);
"""


# V144 review-only, owner-scoped opt-in manual numbers. Additive sidecar:
# never update events, collector, radar decisions, audit or production ledger.
# No individual activity timestamps, URLs, keywords, credentials or notes.
SCHEMA_OWNER_PILOT = """
CREATE TABLE IF NOT EXISTS owner_pilot_sessions(
 owner TEXT NOT NULL CHECK(length(owner) BETWEEN 1 AND 128),
 session_ref TEXT NOT NULL CHECK(length(session_ref) BETWEEN 1 AND 64),
 day TEXT NOT NULL CHECK(length(day)=10),
 old_seconds INTEGER NOT NULL CHECK(old_seconds BETWEEN 1 AND 86400),
 frontier_seconds INTEGER NOT NULL CHECK(frontier_seconds BETWEEN 1 AND 86400),
 reviewed_items INTEGER NOT NULL CHECK(reviewed_items BETWEEN 0 AND 20000),
 noise_items INTEGER NOT NULL CHECK(noise_items BETWEEN 0 AND reviewed_items),
 explicit_page_actions INTEGER NOT NULL CHECK(explicit_page_actions BETWEEN 0 AND 20000),
 owner_confirmed_original_opened INTEGER NOT NULL CHECK(owner_confirmed_original_opened IN (0,1)),
 owner_confirmed_decision_saved INTEGER NOT NULL CHECK(owner_confirmed_decision_saved IN (0,1)),
 owner_confirmed_no_prompt INTEGER NOT NULL CHECK(owner_confirmed_no_prompt IN (0,1)),
 owner_confirmed_comparable_task INTEGER NOT NULL CHECK(owner_confirmed_comparable_task IN (0,1)),
 key_miss INTEGER NOT NULL CHECK(key_miss IN (0,1)),
 claimed_independence_without_check INTEGER NOT NULL CHECK(claimed_independence_without_check IN (0,1)),
 fabricated_occurrence_time INTEGER NOT NULL CHECK(fabricated_occurrence_time IN (0,1)),
 PRIMARY KEY(owner,session_ref));
CREATE INDEX IF NOT EXISTS owner_pilot_sessions_owner_day
 ON owner_pilot_sessions(owner,day);
"""


def migrate(c):
    c.execute("BEGIN IMMEDIATE")
    version = c.execute("SELECT version FROM schema_version").fetchone()[0]
    if version not in (1, 2):
        raise RuntimeError("Unsupported Frontier database version")
    if version == 1:
        additions = {
            "events": {"first_ingested_at": "TEXT"},
            "raw_records": {
                "first_ingested_at": "TEXT",
                "target_id": "TEXT NOT NULL DEFAULT ''",
                "content_type": "TEXT NOT NULL DEFAULT 'tech_news'",
            },
        }
        for table, fields in additions.items():
            existing = {row[1] for row in c.execute("PRAGMA table_info(" + table + ")")}
            for name, definition in fields.items():
                if name not in existing:
                    c.execute("ALTER TABLE " + table + " ADD COLUMN " + name + " " + definition)
        for statement in SCHEMA_V2.split(";"):
            if statement.strip():
                c.execute(statement)
        c.execute(
            "UPDATE raw_records SET first_ingested_at=ingested_at WHERE first_ingested_at IS NULL"
        )
        c.execute(
            "UPDATE events SET first_ingested_at=coalesce((SELECT min(first_ingested_at) "
            "FROM raw_records r WHERE r.event_id=events.id),created_at) "
            "WHERE first_ingested_at IS NULL"
        )
        c.execute("UPDATE schema_version SET version=2")
    for statement in SCHEMA_RADAR.split(";"):
        if statement.strip():
            c.execute(statement)
    # Idempotently upgrade early V3 candidates without rewriting their topics.
    columns = {row[1] for row in c.execute("PRAGMA table_info(radar_topics)")}
    if "version" not in columns:
        c.execute("ALTER TABLE radar_topics ADD COLUMN version INTEGER NOT NULL DEFAULT 1")
    for statement in SCHEMA_RADAR_USEFULNESS.split(";"):
        if statement.strip():
            c.execute(statement)
    for statement in SCHEMA_OWNER_PILOT.split(";"):
        if statement.strip():
            c.execute(statement)
