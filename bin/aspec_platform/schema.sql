-- algosec-agent-spec platform database, schema v1 (IMPLEMENTATION-GUIDE §4.4).
-- The database is DERIVED from files (DEC-04) and rebuildable with
--   agent-spec-platform.py ingest --rebuild
-- Single writer: the ingestor (DEC-09). Timestamps are ISO-8601 UTC strings.

CREATE TABLE requests (
    request_id        TEXT PRIMARY KEY,
    run_id            TEXT,
    session_id        TEXT,
    parent_request_id TEXT,
    source            TEXT NOT NULL DEFAULT 'ide' CHECK (source IN ('ide', 'headless')),
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
CREATE INDEX idx_requests_started ON requests(started);
CREATE INDEX idx_requests_session ON requests(session_id, ordinal);
CREATE INDEX idx_requests_run ON requests(run_id);
CREATE INDEX idx_requests_parent ON requests(parent_request_id);

CREATE TABLE steps (
    step_id           TEXT PRIMARY KEY,
    request_id        TEXT NOT NULL REFERENCES requests(request_id) ON DELETE CASCADE,
    ordinal           INTEGER NOT NULL,
    kind              TEXT NOT NULL CHECK (kind IN ('tool', 'skill', 'subagent', 'gate', 'ai', 'run', 'message')),
    name              TEXT NOT NULL DEFAULT '',
    status            TEXT NOT NULL DEFAULT 'success',
    started           TEXT,
    duration_ms       INTEGER NOT NULL DEFAULT 0,
    tokens_input      INTEGER NOT NULL DEFAULT 0,
    tokens_output     INTEGER NOT NULL DEFAULT 0,
    tokens_cache_read INTEGER NOT NULL DEFAULT 0,
    bytes_in          INTEGER NOT NULL DEFAULT 0,
    whole_file        INTEGER NOT NULL DEFAULT 0,
    detail_json       TEXT
);
CREATE INDEX idx_steps_request ON steps(request_id, ordinal);
CREATE INDEX idx_steps_kind ON steps(kind, name);

CREATE TABLE subagent_runs (
    id                TEXT PRIMARY KEY,
    parent_request_id TEXT NOT NULL,
    child_request_id  TEXT,
    parent_step_id    TEXT,
    agent             TEXT NOT NULL DEFAULT '',
    model             TEXT,
    status            TEXT NOT NULL DEFAULT 'success',
    latency_ms        INTEGER NOT NULL DEFAULT 0,
    error             TEXT,
    started           TEXT,
    compacted         INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_subagent_parent ON subagent_runs(parent_request_id);
CREATE INDEX idx_subagent_agent ON subagent_runs(agent);

CREATE TABLE events (
    event_id          TEXT PRIMARY KEY,
    run_id            TEXT NOT NULL,
    trace_id          TEXT,
    span_id           TEXT,
    parent_span_id    TEXT,
    ts                TEXT NOT NULL,
    seq               INTEGER NOT NULL DEFAULT 0,
    source            TEXT NOT NULL DEFAULT 'headless',
    type              TEXT NOT NULL,
    step_id           TEXT,
    actor_json        TEXT,
    payload_json      TEXT,
    tokens_input      INTEGER NOT NULL DEFAULT 0,
    tokens_output     INTEGER NOT NULL DEFAULT 0,
    tokens_cache_read INTEGER NOT NULL DEFAULT 0,
    tokens_estimated  INTEGER NOT NULL DEFAULT 1,
    cost_usd          REAL NOT NULL DEFAULT 0,
    duration_ms       INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_events_run ON events(run_id, ts, seq);
CREATE INDEX idx_events_type ON events(type);

CREATE TABLE gate_events (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    feature           TEXT NOT NULL,
    gate              INTEGER NOT NULL,
    gate_name         TEXT NOT NULL DEFAULT '',
    ts                TEXT NOT NULL,
    artifact          TEXT NOT NULL DEFAULT '',
    session_id        TEXT,
    UNIQUE (feature, gate, ts, artifact)
);
CREATE INDEX idx_gate_events_ts ON gate_events(ts);

CREATE TABLE tasks (
    task_id           TEXT PRIMARY KEY,
    slice             TEXT,
    p_number          TEXT,
    title             TEXT NOT NULL DEFAULT '',
    status            TEXT NOT NULL DEFAULT 'open',
    acceptance        TEXT,
    effort            TEXT,
    deps_json         TEXT NOT NULL DEFAULT '[]',
    evidence_json     TEXT NOT NULL DEFAULT '[]',
    updated           TEXT
);
CREATE INDEX idx_tasks_status ON tasks(status);

CREATE TABLE memory_facts (
    fact_id           TEXT PRIMARY KEY,
    type              TEXT NOT NULL DEFAULT '',
    subject           TEXT NOT NULL DEFAULT '',
    bytes             INTEGER NOT NULL DEFAULT 0,
    confidence        TEXT,
    status            TEXT NOT NULL DEFAULT 'active',
    expires           TEXT,
    scope             TEXT NOT NULL DEFAULT 'local' CHECK (scope IN ('local', 'team')),
    source_path       TEXT,
    updated           TEXT
);

CREATE TABLE fact_injections (
    fact_id           TEXT NOT NULL,
    request_id        TEXT NOT NULL,
    PRIMARY KEY (fact_id, request_id)
);
CREATE INDEX idx_fact_injections_request ON fact_injections(request_id);

CREATE TABLE experiences (
    exp_id            TEXT PRIMARY KEY,
    signature         TEXT NOT NULL DEFAULT '',
    title             TEXT NOT NULL DEFAULT '',
    tier              TEXT NOT NULL DEFAULT 'candidate' CHECK (tier IN ('candidate', 'trusted', 'deprecated')),
    confidence        REAL NOT NULL DEFAULT 0,
    uses              INTEGER NOT NULL DEFAULT 0,
    successes         INTEGER NOT NULL DEFAULT 0,
    created           TEXT,
    expires           TEXT,
    run_id            TEXT,
    record_json       TEXT
);
CREATE INDEX idx_experiences_tier ON experiences(tier);

CREATE TABLE graph_stats (
    snapshot_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    ts                TEXT NOT NULL,
    files             INTEGER NOT NULL DEFAULT 0,
    edges             INTEGER NOT NULL DEFAULT 0,
    symbols           INTEGER NOT NULL DEFAULT 0,
    cycles            INTEGER NOT NULL DEFAULT 0,
    sha               TEXT,
    age_s             INTEGER NOT NULL DEFAULT 0,
    UNIQUE (ts, sha)
);

CREATE TABLE quarantine_events (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    ts                TEXT NOT NULL,
    tool              TEXT,
    pattern           TEXT,
    path_redacted     TEXT,
    session_id        TEXT,
    UNIQUE (ts, tool, pattern, path_redacted)
);

CREATE TABLE ingest_offsets (
    source_path       TEXT PRIMARY KEY,
    byte_offset       INTEGER NOT NULL DEFAULT 0,
    prefix_sha        TEXT,
    ingested_at       TEXT
);

CREATE TABLE meta (
    key               TEXT PRIMARY KEY,
    value             TEXT
);

-- Retrieval index (D-008). `fts_state` records what each document looked like when it was indexed,
-- so a re-index only touches documents whose content hash changed.
CREATE VIRTUAL TABLE fts_docs USING fts5(kind, ref, title, body, tokenize = 'porter unicode61');
CREATE TABLE fts_state (
    kind              TEXT NOT NULL,
    ref               TEXT NOT NULL,
    sha               TEXT NOT NULL,
    PRIMARY KEY (kind, ref)
);
