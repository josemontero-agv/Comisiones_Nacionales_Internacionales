PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS bronze_snapshot (
    snapshot_id TEXT PRIMARY KEY,
    channel TEXT NOT NULL,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    source_path TEXT NOT NULL,
    source_sha256 TEXT NOT NULL,
    loaded_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('open', 'closed'))
);

CREATE TABLE IF NOT EXISTS bronze_record (
    snapshot_id TEXT NOT NULL REFERENCES bronze_snapshot(snapshot_id),
    source_model TEXT NOT NULL,
    source_key TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL,
    PRIMARY KEY (snapshot_id, source_model, source_key)
);

CREATE TABLE IF NOT EXISTS silver_record (
    snapshot_id TEXT NOT NULL REFERENCES bronze_snapshot(snapshot_id),
    entity_type TEXT NOT NULL,
    entity_key TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    PRIMARY KEY (snapshot_id, entity_type, entity_key)
);

CREATE TABLE IF NOT EXISTS gold_run (
    run_id TEXT PRIMARY KEY,
    snapshot_id TEXT NOT NULL REFERENCES bronze_snapshot(snapshot_id),
    channel TEXT NOT NULL,
    status TEXT NOT NULL,
    manifest_json TEXT NOT NULL,
    completed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS gold_commission_line (
    run_id TEXT NOT NULL REFERENCES gold_run(run_id),
    row_key TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    PRIMARY KEY (run_id, row_key)
);

CREATE TABLE IF NOT EXISTS gold_difference (
    run_id TEXT NOT NULL REFERENCES gold_run(run_id),
    difference_key TEXT NOT NULL,
    classification TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    PRIMARY KEY (run_id, difference_key, classification)
);

CREATE TABLE IF NOT EXISTS gold_exception (
    run_id TEXT NOT NULL REFERENCES gold_run(run_id),
    exception_key TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    PRIMARY KEY (run_id, exception_key)
);

CREATE INDEX IF NOT EXISTS idx_gold_run_channel ON gold_run(channel, completed_at);
