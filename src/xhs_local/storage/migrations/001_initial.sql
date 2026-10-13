CREATE TABLE records (
    record_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    plugin_id TEXT NOT NULL,
    external_id TEXT NOT NULL,
    content_type TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    text TEXT NOT NULL DEFAULT '',
    source_name TEXT NOT NULL DEFAULT '',
    source_url TEXT,
    group_id TEXT,
    payload_json TEXT NOT NULL DEFAULT '{}',
    content_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(source_id, target_id, external_id)
);

CREATE INDEX idx_records_target_occurred
    ON records(target_id, occurred_at DESC, record_id);
CREATE INDEX idx_records_content_type_occurred
    ON records(content_type, occurred_at DESC, record_id);
CREATE INDEX idx_records_group
    ON records(source_id, target_id, group_id, occurred_at);

CREATE TABLE record_versions (
    version_id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id TEXT NOT NULL REFERENCES records(record_id) ON DELETE CASCADE,
    content_hash TEXT NOT NULL,
    snapshot_json TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    UNIQUE(record_id, content_hash)
);

CREATE TABLE attachments (
    attachment_id TEXT PRIMARY KEY,
    record_id TEXT NOT NULL REFERENCES records(record_id) ON DELETE CASCADE,
    attachment_index INTEGER NOT NULL CHECK(attachment_index >= 0),
    mime_type TEXT NOT NULL,
    file_name TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    byte_size INTEGER NOT NULL CHECK(byte_size > 0),
    sha256 TEXT NOT NULL CHECK(length(sha256) = 64),
    width INTEGER,
    height INTEGER,
    created_at TEXT NOT NULL,
    UNIQUE(record_id, attachment_index)
);

CREATE INDEX idx_attachments_sha256 ON attachments(sha256);

CREATE TABLE checkpoints (
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    checkpoint_json TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(source_id, target_id)
);

CREATE TABLE publication_marks (
    record_id TEXT NOT NULL REFERENCES records(record_id) ON DELETE CASCADE,
    sink TEXT NOT NULL,
    account_id TEXT NOT NULL,
    status TEXT NOT NULL,
    marked_at TEXT NOT NULL,
    detail_json TEXT,
    PRIMARY KEY(record_id, sink, account_id)
);

CREATE INDEX idx_publication_marks_status
    ON publication_marks(sink, account_id, status, marked_at);

CREATE TABLE quarantined_records (
    quarantine_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    external_id TEXT,
    error_class TEXT NOT NULL,
    error_summary TEXT NOT NULL,
    raw_metadata_json TEXT,
    created_at TEXT NOT NULL
);
