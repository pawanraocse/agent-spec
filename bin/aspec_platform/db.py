"""SQLite access for the platform extra (D-001).

`connect()` returns a WAL connection with foreign keys on; `migrate()` applies ordered
migrations tracked by `PRAGMA user_version`. The database is derived data (DEC-04): corrupt or
stale -> `agent-spec-platform.py ingest --rebuild`.
"""
from __future__ import annotations

import os
import sqlite3
import time

from .common import agent_spec_dir

HERE = os.path.dirname(os.path.abspath(__file__))
# Append-only. SCHEMA_VERSION == len(MIGRATIONS); never edit a shipped migration.
MIGRATIONS = ["schema.sql", "schema_v2_demo_seed.sql", "schema_v3_traces.sql", "schema_v4_retrieval.sql"]
SCHEMA_VERSION = len(MIGRATIONS)
BUSY_TIMEOUT_MS = 5000


class SchemaError(RuntimeError):
    """The database cannot be used with this version of the harness."""


def db_path(project=None) -> str:
    """`AGENT_SPEC_DB` wins; otherwise `<project>/.agent-spec/platform/platform.db`."""
    override = os.environ.get("AGENT_SPEC_DB")
    if override:
        return override
    return os.path.join(agent_spec_dir(project or os.getcwd()), "platform", "platform.db")


def connect(path=None, readonly: bool = False) -> sqlite3.Connection:
    """Open the database (creating parent directories) with WAL, FK and a busy timeout."""
    path = path or db_path()
    if readonly:
        conn = sqlite3.connect("file:%s?mode=ro" % path, uri=True, timeout=BUSY_TIMEOUT_MS / 1000,
                               check_same_thread=False)
    else:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        conn = sqlite3.connect(path, timeout=BUSY_TIMEOUT_MS / 1000, check_same_thread=False)
        _wal(conn)
        conn.execute("PRAGMA synchronous=NORMAL")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=%d" % BUSY_TIMEOUT_MS)
    return conn


def _wal(conn: sqlite3.Connection) -> None:
    """Switch to WAL. SQLite answers a contended switch with SQLITE_BUSY at once instead of calling
    the busy handler, so two writers opening a fresh database need a retry here."""
    deadline = time.monotonic() + BUSY_TIMEOUT_MS / 1000
    while True:
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            return
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc) or time.monotonic() > deadline:
                raise
            time.sleep(0.02)


def schema_version(conn: sqlite3.Connection) -> int:
    return conn.execute("PRAGMA user_version").fetchone()[0]


def migrate(conn: sqlite3.Connection) -> int:
    """Apply pending migrations; each runs in one transaction. Returns the resulting version."""
    current = schema_version(conn)
    if current > SCHEMA_VERSION:
        raise SchemaError("database schema v%d is newer than this harness (v%d); upgrade agent-spec"
                          % (current, SCHEMA_VERSION))
    # Two writers can both read the old version before either migrates (the dashboard and a hook
    # ingest on a fresh database). So each step takes the write lock first and re-reads the version
    # under it; the loser skips. executescript() would commit the lock away, hence per statement.
    previous, conn.isolation_level = conn.isolation_level, None
    try:
        for index in range(current, SCHEMA_VERSION):
            with open(os.path.join(HERE, MIGRATIONS[index]), encoding="utf-8") as fh:
                script = fh.read()
            conn.execute("BEGIN IMMEDIATE")
            try:
                if schema_version(conn) <= index:
                    for statement in _statements(script):
                        conn.execute(statement)
                    conn.execute("PRAGMA user_version = %d" % (index + 1))
                conn.execute("COMMIT")
            except sqlite3.Error:
                conn.execute("ROLLBACK")
                raise
    finally:
        conn.isolation_level = previous
    return schema_version(conn)


def _statements(script: str):
    """Split a migration into single statements; complete_statement() keeps trigger bodies whole."""
    buf = ""
    for line in script.splitlines(keepends=True):
        buf += line
        if sqlite3.complete_statement(buf):
            yield buf
            buf = ""
    if any(l.strip() and not l.strip().startswith("--") for l in buf.splitlines()):
        raise SchemaError("migration ends mid-statement: %r" % buf.strip()[:80])


def open_ready(path=None, readonly: bool = False) -> sqlite3.Connection:
    """connect() + migrate() for writers; readers get a read-only handle on an existing DB."""
    if readonly:
        return connect(path, readonly=True)
    conn = connect(path)
    migrate(conn)
    return conn
