#!/usr/bin/env python3
"""Tests for bin/aspec_platform/db.py (D-001, P2.3): schema, WAL, migrations, path override.

Run: python3 tests/test_platform_db.py
"""
import os
import subprocess
import sys
import tempfile
import unittest

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_DIR, "bin"))

from aspec_platform import db  # noqa: E402

REQUIRED_TABLES = {
    "requests", "steps", "subagent_runs", "events", "gate_events", "tasks", "memory_facts",
    "fact_injections", "experiences", "graph_stats", "ingest_offsets", "fts_docs",
    "quarantine_events", "meta",
}


class DbTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, "sub", "platform.db")
        os.environ.pop("AGENT_SPEC_DB", None)

    def tables(self, conn):
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')").fetchall()
        return {r[0] for r in rows}

    def test_migrate_creates_every_table_and_sets_version(self):
        conn = db.connect(self.path)
        db.migrate(conn)
        self.assertTrue(REQUIRED_TABLES <= self.tables(conn), REQUIRED_TABLES - self.tables(conn))
        self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], db.SCHEMA_VERSION)
        # contract: schema version == migration count
        self.assertEqual(db.SCHEMA_VERSION, len(db.MIGRATIONS))

    def test_wal_and_foreign_keys(self):
        conn = db.connect(self.path)
        self.assertEqual(conn.execute("PRAGMA journal_mode").fetchone()[0].lower(), "wal")
        self.assertEqual(conn.execute("PRAGMA foreign_keys").fetchone()[0], 1)

    def test_migrate_is_idempotent(self):
        conn = db.connect(self.path)
        db.migrate(conn)
        conn.execute("INSERT INTO meta(key, value) VALUES ('k', 'v')")
        conn.commit()
        db.migrate(conn)
        self.assertEqual(conn.execute("SELECT value FROM meta WHERE key='k'").fetchone()[0], "v")

    def test_newer_database_is_refused(self):
        conn = db.connect(self.path)
        db.migrate(conn)
        conn.execute("PRAGMA user_version = %d" % (db.SCHEMA_VERSION + 5))
        with self.assertRaises(db.SchemaError):
            db.migrate(conn)

    def test_env_override_wins(self):
        os.environ["AGENT_SPEC_DB"] = os.path.join(self.tmp, "x.db")
        try:
            self.assertEqual(db.db_path(self.tmp), os.path.join(self.tmp, "x.db"))
        finally:
            os.environ.pop("AGENT_SPEC_DB", None)
        self.assertEqual(db.db_path(self.tmp),
                         os.path.join(self.tmp, ".agent-spec", "platform", "platform.db"))

    def test_fts5_round_trip(self):
        conn = db.connect(self.path)
        db.migrate(conn)
        conn.execute("INSERT INTO fts_docs(kind, ref, title, body) VALUES ('file','a.py','a','graph blast radius')")
        hit = conn.execute("SELECT ref FROM fts_docs WHERE fts_docs MATCH 'blast'").fetchall()
        self.assertEqual([r[0] for r in hit], ["a.py"])

    def test_cli_init_creates_db(self):
        proj = tempfile.mkdtemp()
        os.makedirs(os.path.join(proj, ".agent-spec"))
        cli = os.path.join(REPO_DIR, "bin", "agent-spec-platform.py")
        r = subprocess.run([sys.executable, cli, "init", "--project", proj],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.isfile(os.path.join(proj, ".agent-spec", "platform", "platform.db")))
        r2 = subprocess.run([sys.executable, cli, "init", "--project", proj],
                            capture_output=True, text=True)
        self.assertEqual(r2.returncode, 0, r2.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=1)
