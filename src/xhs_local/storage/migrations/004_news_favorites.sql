CREATE TABLE news_favorites (
    record_id TEXT PRIMARY KEY REFERENCES records(record_id) ON DELETE CASCADE,
    created_at TEXT NOT NULL
);
