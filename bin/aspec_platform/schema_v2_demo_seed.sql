-- schema v2: allow demo_seed on requests (DEC-14 / CP-005)
PRAGMA foreign_keys=OFF;
CREATE TABLE requests_v2 (
    request_id        TEXT PRIMARY KEY,
    run_id            TEXT,
    session_id        TEXT,
    parent_request_id TEXT,
    source            TEXT NOT NULL DEFAULT 'ide' CHECK (source IN ('ide', 'headless', 'demo_seed')),
    ordinal           INTEGER NOT NULL DEFAULT 0,
    prompt_redacted   TEXT,
    interpreted_json  TEXT,
    status            TEXT NOT NULL DEFAULT 'success',
    started           TEXT,
    finished          TEXT,
    tokens_input      INTEGER NOT NULL DEFAULT 0,
    tokens_output     INTEGER NOT NULL DEFAULT 0,
    tokens_cache_read INTEGER NOT NULL DEFAULT 0,
    tokens_estimated  INTEGER NOT NULL DEFAULT 1,
    cost_usd          REAL NOT NULL DEFAULT 0,
    workflow_id       TEXT,
    workflow_version  TEXT,
    strategy          TEXT,
    transcript_path   TEXT
);
INSERT INTO requests_v2 SELECT * FROM requests;
DROP TABLE requests;
ALTER TABLE requests_v2 RENAME TO requests;
CREATE INDEX IF NOT EXISTS idx_requests_started ON requests(started);
CREATE INDEX IF NOT EXISTS idx_requests_session ON requests(session_id, ordinal);
CREATE INDEX IF NOT EXISTS idx_requests_run ON requests(run_id);
CREATE INDEX IF NOT EXISTS idx_requests_parent ON requests(parent_request_id);
PRAGMA foreign_keys=ON;
