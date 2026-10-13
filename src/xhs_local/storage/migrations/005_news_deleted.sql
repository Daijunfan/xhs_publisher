-- No foreign key: remember explicit deletions after the original record is gone.
CREATE TABLE news_deleted (
    record_id TEXT PRIMARY KEY,
    deleted_at TEXT NOT NULL
);
