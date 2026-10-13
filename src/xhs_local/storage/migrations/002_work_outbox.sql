CREATE TABLE work_items (
    work_id TEXT PRIMARY KEY,
    topic TEXT NOT NULL,
    state TEXT NOT NULL,
    record_id TEXT REFERENCES records(record_id) ON DELETE SET NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    config_revision TEXT,
    trace_id TEXT NOT NULL,
    attempt INTEGER NOT NULL DEFAULT 0 CHECK(attempt >= 0),
    next_retry_at TEXT,
    started_at TEXT,
    completed_at TEXT,
    error_class TEXT,
    error_code TEXT,
    error_summary TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX idx_work_items_dispatch
    ON work_items(topic, state, next_retry_at, created_at);
CREATE INDEX idx_work_items_record ON work_items(record_id, topic, created_at);

CREATE TABLE outbox (
    event_id TEXT PRIMARY KEY,
    topic TEXT NOT NULL,
    work_id TEXT NOT NULL REFERENCES work_items(work_id) ON DELETE CASCADE,
    payload_json TEXT NOT NULL DEFAULT '{}',
    state TEXT NOT NULL DEFAULT 'NEW' CHECK(state IN ('NEW', 'DISPATCHED')),
    created_at TEXT NOT NULL,
    dispatched_at TEXT
);

CREATE INDEX idx_outbox_pending ON outbox(topic, state, created_at);

CREATE TABLE remote_operations (
    operation_id TEXT PRIMARY KEY,
    work_id TEXT NOT NULL REFERENCES work_items(work_id) ON DELETE RESTRICT,
    sink TEXT NOT NULL,
    account_id TEXT NOT NULL,
    operation TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    state TEXT NOT NULL,
    attempt INTEGER NOT NULL CHECK(attempt >= 1),
    request_json TEXT,
    result_json TEXT,
    error_summary TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(sink, account_id, idempotency_key)
);

CREATE INDEX idx_remote_operations_work ON remote_operations(work_id, created_at);
