"""SQLite access for the platform extra (D-001).

`connect()` returns a WAL connection with foreign keys on; `migrate()` applies ordered
migrations tracked by `PRAGMA user_version`. The database is derived data (DEC-04): corrupt or
stale -> `agent-spec-platform.py ingest --rebuild`.
"""
from __future__ import annotations

import os
import sqlite3

from .common import agent_spec_dir

HERE = os.path.dirname(os.path.abspath(__file__))
# Append-only. SCHEMA_VERSION == len(MIGRATIONS); never edit a shipped migration.
MIGRATIONS = ["schema.sql", "schema_v2_demo_seed.sql"]
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
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=%d" % BUSY_TIMEOUT_MS)
    return conn


def schema_version(conn: sqlite3.Connection) -> int:
    return conn.execute("PRAGMA user_version").fetchone()[0]


def migrate(conn: sqlite3.Connection) -> int:
    """Apply pending migrations; each runs in one transaction. Returns the resulting version."""
    current = schema_version(conn)
    if current > SCHEMA_VERSION:
        raise SchemaError("database schema v%d is newer than this harness (v%d); upgrade agent-spec"
                          % (current, SCHEMA_VERSION))
    for index in range(current, SCHEMA_VERSION):
        with open(os.path.join(HERE, MIGRATIONS[index]), encoding="utf-8") as fh:
            script = fh.read()
        try:
            conn.executescript("BEGIN;\n%s\nPRAGMA user_version = %d;\nCOMMIT;" % (script, index + 1))
        except sqlite3.Error:
            conn.rollback()
            raise
    return schema_version(conn)


def open_ready(path=None, readonly: bool = False) -> sqlite3.Connection:
    """connect() + migrate() for writers; readers get a read-only handle on an existing DB."""
    if readonly:
        return connect(path, readonly=True)
    conn = connect(path)
    migrate(conn)
    return conn
