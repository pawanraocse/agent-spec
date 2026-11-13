-- DV-010 (DEC-16 §14.3): a request is a trace, every step a span.
-- Field names follow OpenTelemetry/OpenInference so a Langfuse or Phoenix export is a mapping.
-- source: 'hook' (Cursor hook events, measured), 'cursor_store' (Cursor local store, unofficial,
-- durations estimated from message timestamps), 'run' (hub-runner workflow), 'demo_seed'.
CREATE TABLE traces (
    trace_id         TEXT PRIMARY KEY,
    session_id       TEXT NOT NULL,
    source           TEXT NOT NULL,
    workspace        TEXT,
    prompt           TEXT,
    model            TEXT,
    cursor_version   TEXT,
    start            TEXT,
    end              TEXT,
    duration_ms      INTEGER,
    status           TEXT NOT NULL DEFAULT 'running',
    span_count       INTEGER NOT NULL DEFAULT 0,
    tool_count       INTEGER NOT NULL DEFAULT 0,
    subagent_count   INTEGER NOT NULL DEFAULT 0,
    error_count      INTEGER NOT NULL DEFAULT 0,
    guard_count      INTEGER NOT NULL DEFAULT 0,
    edit_count       INTEGER NOT NULL DEFAULT 0,
    skills           TEXT NOT NULL DEFAULT '[]',
    transcript_path  TEXT,
    provenance       TEXT NOT NULL DEFAULT 'measured'
);
CREATE INDEX idx_traces_session ON traces(session_id, start);
CREATE INDEX idx_traces_start ON traces(start);

CREATE TABLE spans (
    span_id          TEXT PRIMARY KEY,
    trace_id         TEXT NOT NULL REFERENCES traces(trace_id) ON DELETE CASCADE,
    parent_span_id   TEXT,
    kind             TEXT NOT NULL,
    name             TEXT,
    start            TEXT,
    end              TEXT,
    duration_ms      INTEGER,
    status           TEXT,
    seq              INTEGER NOT NULL DEFAULT 0,
    attributes       TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX idx_spans_trace ON spans(trace_id, seq);
CREATE INDEX idx_spans_kind ON spans(kind);
