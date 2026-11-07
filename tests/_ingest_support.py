"""Shared sandbox for the tests/test_ingest_*.py suites (synthetic data only)."""
import os
import shutil
import sys
import tempfile
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(TESTS_DIR)
FIXTURES = os.path.join(TESTS_DIR, "fixtures", "transcripts")
sys.path.insert(0, os.path.join(REPO_DIR, "bin"))

from aspec_platform import db, ingest  # noqa: E402


class IngestCase(unittest.TestCase):
    """A temp project with `.agent-spec/`, a transcript root and a private database."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.project = os.path.join(self.tmp, "proj")
        self.spec = os.path.join(self.project, ".agent-spec")
        self.root = os.path.join(self.tmp, "agent-transcripts")
        os.makedirs(self.spec)
        os.makedirs(self.root)
        self._env = {k: os.environ.get(k) for k in ("AGENT_SPEC_TRANSCRIPT_ROOT", "AGENT_SPEC_DB")}
        os.environ["AGENT_SPEC_TRANSCRIPT_ROOT"] = self.root
        os.environ["AGENT_SPEC_DB"] = os.path.join(self.tmp, "platform.db")
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        for key, value in self._env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, rel, text, mode="w"):
        path = os.path.join(self.project, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, mode, encoding=None if "b" in mode else "utf-8") as fh:
            fh.write(text)
        return path

    def fixture(self, name):
        with open(os.path.join(FIXTURES, name), encoding="utf-8") as fh:
            return fh.read()

    def transcript(self, session, text, sub_of=None, mode="w"):
        """Write `<root>/<session>/<session>.jsonl` (or `<root>/<sub_of>/subagents/<session>.jsonl`)."""
        base = os.path.join(self.root, sub_of, "subagents") if sub_of else os.path.join(self.root, session)
        os.makedirs(base, exist_ok=True)
        path = os.path.join(base, session + ".jsonl")
        with open(path, mode, encoding="utf-8") as fh:
            fh.write(text)
        return path

    def run_ingest(self, *what, rebuild=False):
        return ingest.run(self.project, list(what) or ["all"], rebuild=rebuild)

    def conn(self):
        return db.connect(os.environ["AGENT_SPEC_DB"])

    def count(self, table):
        conn = self.conn()
        try:
            return conn.execute("SELECT COUNT(*) FROM %s" % table).fetchone()[0]
        finally:
            conn.close()

    def dump(self):
        """Every row of the database as one string (for 'this text is nowhere in the DB')."""
        conn = self.conn()
        try:
            return "\n".join(conn.iterdump())
        finally:
            conn.close()
