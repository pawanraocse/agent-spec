-- DEC-17 (PI-001): local project-intelligence index for dashboard and agent questions.
-- Derived data like every other table (DEC-04): `ingest --what index` rebuilds it from the
-- working tree, .agent-spec/ artifacts, request traces and reviews. Nothing here leaves the machine.
--
-- index_sources: one row per indexed source (a file, a trace, a review) with the stamp
--   (mtime:size, or a trace's end:span_count) and content hash seen at index time, so an
--   incremental pass re-reads only what changed and drops what disappeared.
-- chunks: retrievable passages with citation metadata (line range, session, timestamp).
-- chunks_fts: BM25 keyword index over title, body and split identifiers (external content).
-- chunk_vectors: optional embeddings, one per chunk and embedding model, written only when a
--   local embedding provider is configured (AGENT_SPEC_EMBED).
CREATE TABLE index_sources (
    kind        TEXT NOT NULL,
    source      TEXT NOT NULL,
    stamp       TEXT NOT NULL,
    sha         TEXT NOT NULL,
    chunks      INTEGER NOT NULL DEFAULT 0,
    indexed_at  TEXT NOT NULL,
    PRIMARY KEY (kind, source)
);

CREATE TABLE chunks (
    chunk_id    INTEGER PRIMARY KEY,
    kind        TEXT NOT NULL,
    source      TEXT NOT NULL,
    ref         TEXT NOT NULL,
    title       TEXT NOT NULL DEFAULT '',
    start_line  INTEGER,
    end_line    INTEGER,
    session_id  TEXT,
    ts          TEXT,
    body        TEXT NOT NULL,
    terms       TEXT NOT NULL DEFAULT ''
);
CREATE INDEX idx_chunks_source ON chunks(kind, source);
CREATE INDEX idx_chunks_ts ON chunks(ts);

CREATE VIRTUAL TABLE chunks_fts USING fts5(
    title, body, terms, content = 'chunks', content_rowid = 'chunk_id', tokenize = 'porter unicode61'
);
CREATE TRIGGER chunks_ai AFTER INSERT ON chunks BEGIN
    INSERT INTO chunks_fts(rowid, title, body, terms) VALUES (new.chunk_id, new.title, new.body, new.terms);
END;
CREATE TRIGGER chunks_ad AFTER DELETE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, title, body, terms) VALUES ('delete', old.chunk_id, old.title, old.body, old.terms);
END;

CREATE TABLE chunk_vectors (
    chunk_id    INTEGER NOT NULL REFERENCES chunks(chunk_id) ON DELETE CASCADE,
    model       TEXT NOT NULL,
    dim         INTEGER NOT NULL,
    vec         BLOB NOT NULL,
    PRIMARY KEY (chunk_id, model)
);
