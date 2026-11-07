"""Shared harness for tests/test_api*.py: a live stdlib server on an ephemeral port (synthetic data only)."""
import http.client
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(TESTS_DIR)
sys.path.insert(0, os.path.join(REPO_DIR, "bin"))

from aspec_platform import db  # noqa: E402


def seed(path):
    """Two requests (one child), three steps, two tasks."""
    conn = db.open_ready(path)
    conn.executescript("""
    INSERT INTO requests (request_id, session_id, ordinal, prompt_redacted, status, started,
                          tokens_input, tokens_output, tokens_cache_read)
      VALUES ('R1', 'S1', 1, 'first prompt', 'success', '2026-10-31T10:00:00.000Z', 100, 40, 10),
             ('R2', 'S1', 2, 'second prompt', 'failed',  '2026-10-31T11:00:00.000Z', 200, 80, 20);
    INSERT INTO steps (step_id, request_id, ordinal, kind, name, tokens_input)
      VALUES ('T1', 'R1', 1, 'tool', 'Read', 50), ('T2', 'R1', 2, 'skill', 'agent-spec-implement', 5),
             ('T3', 'R2', 1, 'tool', 'Shell', 7);
    INSERT INTO tasks (task_id, title, status, effort) VALUES ('D-001', 'schema', 'done', '1d'),
                                                              ('D-020', 'api', 'open', '2d');
    """)
    conn.commit()
    conn.close()


class ApiCase(unittest.TestCase):
    """Starts `serve.make_server` on 127.0.0.1:0 against a seeded temp database."""

    def setUp(self):
        from aspec_platform import serve
        self.serve = serve
        self.tmp = tempfile.mkdtemp()
        self.project = os.path.join(self.tmp, "proj")
        os.makedirs(os.path.join(self.project, ".agent-spec"))
        self.dbpath = os.path.join(self.tmp, "platform.db")
        self._env = os.environ.get("AGENT_SPEC_DB")
        os.environ["AGENT_SPEC_DB"] = self.dbpath
        seed(self.dbpath)
        self.httpd, self.token = serve.make_server(self.project, "127.0.0.1", 0)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, kwargs={"poll_interval": 0.02},
                                       daemon=True)
        self.thread.start()
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        if self._env is None:
            os.environ.pop("AGENT_SPEC_DB", None)
        else:
            os.environ["AGENT_SPEC_DB"] = self._env
        shutil.rmtree(self.tmp, ignore_errors=True)

    def request(self, path, method="GET", host=None, headers=None, token=True):
        """Return (status, headers, body-bytes). `token=True` sends the launch token header."""
        hdrs = dict(headers or {})
        if token is True:
            hdrs["X-Agent-Spec-Token"] = self.token
        elif token:
            hdrs["X-Agent-Spec-Token"] = token
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.putrequest(method, path, skip_host=True)
        conn.putheader("Host", "127.0.0.1:%d" % self.port if host is None else host)
        for key, value in hdrs.items():
            conn.putheader(key, value)
        conn.endheaders()
        resp = conn.getresponse()
        body = resp.read()
        out = (resp.status, dict((k.lower(), v) for k, v in resp.getheaders()), body)
        conn.close()
        return out

    def get_json(self, path, **kw):
        status, headers, body = self.request(path, **kw)
        self.assertEqual(status, 200, body[:200])
        return json.loads(body.decode("utf-8"))
