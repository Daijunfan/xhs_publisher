CREATE TABLE dead_letters (
    dead_letter_id TEXT PRIMARY KEY,
    work_id TEXT NOT NULL REFERENCES work_items(work_id) ON DELETE RESTRICT,
    topic TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    error_class TEXT,
    error_code TEXT,
    error_summary TEXT NOT NULL,
    attempt INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    replayed_at TEXT,
    replay_actor TEXT,
    replay_reason TEXT,
    UNIQUE(work_id, created_at)
);

CREATE INDEX idx_dead_letters_open ON dead_letters(replayed_at, created_at);

CREATE TABLE config_revisions (
    revision TEXT PRIMARY KEY,
    snapshot_json TEXT NOT NULL,
    diff_json TEXT,
    preflight_json TEXT,
    source TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    activated_at TEXT
);

CREATE INDEX idx_config_revisions_status
    ON config_revisions(status, created_at DESC);

CREATE TABLE maintenance_runs (
    run_id TEXT PRIMARY KEY,
    operation TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL,
    detail_json TEXT
);

CREATE TABLE legacy_imports (
    import_kind TEXT NOT NULL,
    source_path TEXT NOT NULL,
    source_fingerprint TEXT NOT NULL,
    source_counts_json TEXT NOT NULL,
    imported_at TEXT NOT NULL,
    PRIMARY KEY(import_kind, source_path)
);

CREATE TABLE legacy_record_map (
    channel_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    record_id TEXT NOT NULL REFERENCES records(record_id) ON DELETE CASCADE,
    PRIMARY KEY(channel_id, message_id),
    UNIQUE(record_id)
);

CREATE TABLE published (
    channel_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    record_id TEXT,
    published_at TEXT NOT NULL,
    status TEXT NOT NULL,
    PRIMARY KEY(channel_id, message_id)
);

CREATE INDEX idx_legacy_published_record ON published(record_id);

CREATE TABLE publish_slots (
    slot_start TEXT NOT NULL,
    slot_end TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    publish_invoked_at TEXT,
    title TEXT,
    item_count INTEGER NOT NULL DEFAULT 0,
    details TEXT,
    error TEXT,
    PRIMARY KEY(slot_start, slot_end)
);

CREATE TABLE legacy_sync_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE resource_jobs (
    folder_name TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    pdf_names TEXT NOT NULL,
    status TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    started_at TEXT,
    share_link TEXT,
    share_code TEXT,
    publish_invoked_at TEXT,
    completed_at TEXT,
    error TEXT,
    PRIMARY KEY(folder_name, fingerprint)
);

CREATE INDEX idx_resource_jobs_status
    ON resource_jobs(status, observed_at);
