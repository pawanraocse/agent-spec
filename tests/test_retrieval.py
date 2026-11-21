#!/usr/bin/env python3
"""PI-001..PI-006: local project index, hybrid retrieval, ask, outcome signals, API routes."""
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TESTS_DIR)
from _api_support import ApiCase  # noqa: E402
from aspec_platform import db, ingest, retrieval, signals, traces  # noqa: E402
from test_traces import hook_rows  # noqa: E402


def write(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


CODE = "\n".join(["import os", "", "def buildFromEvents(rows):", '    """Turn hook rows into request traces."""',
                  "    return [r for r in rows if r]", ""] + ["x%d = %d" % (i, i) for i in range(120)] +
                 ["", "class RateLimiter:", "    def allow(self):", "        return True"])
DOC = "# Architecture\n\nThe dashboard reads SQLite.\n\n## Retention\n\nEvents are kept for ninety days.\n"


class Project(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.project = os.path.join(self.tmp, "proj")
        os.makedirs(os.path.join(self.project, ".agent-spec", "metrics"))
        write(self.project, "src/traces.py", CODE)
        write(self.project, "docs/ARCH.md", DOC)
        write(self.project, ".env", "API_KEY=sk-live-should-never-be-indexed")
        write(self.project, ".agent-spec/memory/facts/f1.md", "---\nsubject: retention\n---\nKeep events ninety days.\n")
        write(self.project, ".agent-spec/metrics/automation.jsonl", '{"x": 1}\n')
        write(self.project, "skills/demo/SKILL.md", "---\nname: demo\n---\n# Demo skill\nRuns the demo.\n")
        rows = hook_rows()
        with open(os.path.join(self.project, ".agent-spec", "metrics", "events.jsonl"), "w") as fh:
            fh.write("\n".join(json.dumps(r) for r in rows) + "\n")
        self.env = {k: os.environ.get(k) for k in ("AGENT_SPEC_DB", "AGENT_SPEC_EMBED", "AGENT_SPEC_LLM",
                                                   "AGENT_SPEC_OLLAMA_URL", "AGENT_SPEC_CURSOR_STORE")}
        os.environ["AGENT_SPEC_DB"] = os.path.join(self.tmp, "platform.db")
        os.environ["AGENT_SPEC_CURSOR_STORE"] = "0"
        for k in ("AGENT_SPEC_EMBED", "AGENT_SPEC_LLM", "AGENT_SPEC_OLLAMA_URL"):
            os.environ.pop(k, None)
        traces._CACHE.clear()

    def tearDown(self):
        for k, v in self.env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.tmp, ignore_errors=True)

    def index(self):
        return ingest.run(self.project, ["index"])["index"]

    def conn(self):
        return db.open_ready(db.db_path(self.project))


class IndexTest(Project):
    def test_classify_and_secrets(self):
        self.assertEqual(retrieval.classify("src/a.py"), "code")
        self.assertEqual(retrieval.classify("docs/A.md"), "doc")
        self.assertEqual(retrieval.classify("CURSOR.md"), "rule")
        self.assertEqual(retrieval.classify("skills/x/SKILL.md"), "rule")
        self.assertEqual(retrieval.classify(".agent-spec/memory/facts/f.md"), "memory")
        self.assertIsNone(retrieval.classify(".env"))
        self.assertIsNone(retrieval.classify("config/prod.pem"))
        self.assertIsNone(retrieval.classify(".agent-spec/metrics/events.jsonl"))
        self.assertIsNone(retrieval.classify("package-lock.json"))

    def test_split_terms(self):
        self.assertIn("build from events", retrieval.split_terms("buildFromEvents"))
        self.assertIn("rate limiter", retrieval.split_terms("rate_limiter"))

    def test_chunks_have_line_ranges(self):
        spans = retrieval.chunk_lines(CODE.splitlines(), markdown=False)
        self.assertEqual(spans[0][0], 1)
        self.assertEqual(spans[-1][1], len(CODE.splitlines()))
        self.assertTrue(all(e - s < retrieval.CHUNK_MAX for s, e, _ in spans))
        md = retrieval.chunk_lines(DOC.splitlines(), markdown=True)
        self.assertEqual([t for _, _, t in md], ["Architecture", "Architecture › Retention"])

    def test_index_is_incremental(self):
        first = self.index()
        self.assertEqual(first["errors"], 0)
        self.assertGreaterEqual(first["indexed"], 5)
        conn = self.conn()
        sources = {r[0] for r in conn.execute("SELECT source FROM index_sources")}
        self.assertNotIn(".env", sources)
        self.assertNotIn(".agent-spec/metrics/automation.jsonl", sources)
        body = " ".join(r[0] for r in conn.execute("SELECT body FROM chunks"))
        self.assertNotIn("sk-live", body)
        conn.close()
        again = self.index()
        self.assertEqual((again["indexed"], again["removed"]), (0, 0))
        write(self.project, "docs/ARCH.md", DOC + "\n## Backups\n\nNightly.\n")
        os.remove(os.path.join(self.project, "skills/demo/SKILL.md"))
        third = self.index()
        self.assertEqual((third["indexed"], third["removed"]), (1, 1))


class ReviewRegressionTest(Project):
    """Fixes from the 2026-11-18 H-001 review of retrieval.py and signals.py."""

    def test_terms_are_built_from_redacted_text(self):
        write(self.project, "src/settings.py",
              'AWS_SECRET_ACCESS_KEY = "AKIAQWERTYUIOPASDFGH"\nGITHUB_TOKEN = "ghp_abcdefghijklmnopqrstuvwxyz0123456789"\n')
        self.index()
        conn = self.conn()
        terms = " ".join(r[0] for r in conn.execute("SELECT terms FROM chunks WHERE source = 'src/settings.py'"))
        conn.close()
        self.assertNotIn("abcdefghijklmnopqrstuvwxyz", terms)
        self.assertNotIn("qwertyuiopasdfgh", terms.lower())

    def test_tracked_build_directory_is_indexed(self):
        write(self.project, "tools/build/compile.py", "def compileAll():\n    return 1\n")
        import subprocess
        subprocess.run(["git", "init", "-q", self.project], check=True)
        subprocess.run(["git", "-C", self.project, "add", "-A"], check=True)
        files = retrieval.project_files(self.project)
        self.assertIn("tools/build/compile.py", files)
        self.assertIn(".agent-spec/memory/facts/f1.md", files)

    def test_memory_survives_the_file_cap(self):
        old = retrieval.MAX_FILES
        retrieval.MAX_FILES = 1
        try:
            self.assertEqual(retrieval.project_files(self.project), [".agent-spec/memory/facts/f1.md"])
        finally:
            retrieval.MAX_FILES = old

    def test_non_object_json_is_an_embed_error(self):
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                body = b"[1, 2]"
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
        srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            with self.assertRaises(retrieval.EmbedError):
                retrieval._post_json("http://127.0.0.1:%d/api/embed" % srv.server_address[1], {}, 5)
        finally:
            srv.shutdown()
            srv.server_close()


class SearchTest(Project):
    def test_keyword_finds_identifiers_and_cites_lines(self):
        self.index()
        conn = self.conn()
        r = retrieval.search(conn, "build from events", {}, 5)
        self.assertEqual(r["mode"], "keyword")
        top = r["hits"][0]
        self.assertEqual(top["source"], "src/traces.py")
        self.assertRegex(top["ref"], r"^src/traces\.py:1-\d+$")
        self.assertEqual(top["matched_by"], ["keyword"])

    def test_filters(self):
        self.index()
        conn = self.conn()
        kinds = {h["kind"] for h in retrieval.search(conn, "retention ninety days", {"kinds": ["memory"]}, 10)["hits"]}
        self.assertEqual(kinds, {"memory"})
        paths = {h["source"] for h in retrieval.search(conn, "retention", {"path": "docs/"}, 10)["hits"]}
        self.assertEqual(paths, {"docs/ARCH.md"})

    def test_symlink_out_of_the_project_is_never_read(self):
        outside = os.path.join(self.tmp, "aws-credentials")
        with open(outside, "w") as fh:
            fh.write("aws_secret_access_key = outside-the-project-value\n")
        os.symlink(outside, os.path.join(self.project, "docs", "notes.md"))
        os.symlink(os.path.join(self.project, ".env"), os.path.join(self.project, "docs", "env.md"))
        self.index()
        conn = self.conn()
        sources = {r[0] for r in conn.execute("SELECT source FROM index_sources")}
        self.assertNotIn("docs/notes.md", sources)
        self.assertNotIn("docs/env.md", sources)
        body = " ".join(r[0] for r in conn.execute("SELECT body FROM chunks"))
        self.assertNotIn("outside-the-project-value", body)
        self.assertNotIn("sk-live", body)

    def test_requests_are_indexed_and_searchable(self):
        self.index()
        conn = self.conn()
        hits = retrieval.search(conn, "investigate npm test", {"kinds": ["request"]}, 5)["hits"]
        self.assertEqual(hits[0]["ref"], "gen-1")
        self.assertEqual(hits[0]["session_id"], "conv-1")

    def test_query_syntax_is_inert(self):
        self.index()
        conn = self.conn()
        for q in ('"unterminated', "NEAR(a b", "a AND OR NOT", "*", "col:value", ""):
            retrieval.search(conn, q, {}, 5)  # must not raise

    def test_ask_without_model_returns_sources_and_cursor_prompt(self):
        self.index()
        conn = self.conn()
        out = retrieval.ask(conn, self.project, "how are hook rows turned into traces", {}, 5)
        self.assertIsNone(out["answer"])
        self.assertTrue(out["cursor_prompt"].startswith("/agent-spec-ask "))
        self.assertIn("src/traces.py:", out["cursor_prompt"])


class FakeOllama:
    """A loopback stand-in for Ollama's /api/embed and /api/chat (bag-of-letters vectors)."""

    def __init__(self):
        test = self
        self.calls = []

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                return

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                test.calls.append(self.path)
                if self.path == "/api/embed":
                    vecs = [[t.lower().count(c) + 0.01 for c in "abcdefghijklmnopqrstuvwxyz"] for t in body["input"]]
                    out = {"embeddings": vecs}
                else:
                    out = {"message": {"content": "Traces are built in buildFromEvents [1]."}}
                data = json.dumps(out).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = "http://127.0.0.1:%d" % self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


class HybridTest(Project):
    def setUp(self):
        super().setUp()
        self.fake = FakeOllama()
        os.environ["AGENT_SPEC_OLLAMA_URL"] = self.fake.url
        os.environ["AGENT_SPEC_EMBED"] = "ollama:fake"

    def tearDown(self):
        self.fake.close()
        super().tearDown()

    def test_hybrid_fuses_semantic_hits(self):
        stats = self.index()
        self.assertGreater(stats["embedded"], 0)
        conn = self.conn()
        self.assertEqual(retrieval.index_status(conn)["mode"], "hybrid")
        r = retrieval.search(conn, "build from events", {}, 5)
        self.assertEqual(r["mode"], "hybrid")
        self.assertTrue(any("semantic" in h["matched_by"] for h in r["hits"]))

    def test_stored_vectors_are_used_without_the_env_var(self):
        """Unset AGENT_SPEC_EMBED: the model the index holds vectors for, when Ollama serves it."""
        from unittest import mock
        self.index()
        os.environ.pop("AGENT_SPEC_EMBED", None)
        conn = self.conn()
        up = {"url": self.fake.url, "reachable": True, "models": [{"name": "fake:latest"}]}
        with mock.patch.object(retrieval.ollama, "probe", return_value=up):
            self.assertEqual(retrieval.get_embedder(conn).name, "ollama:fake")
            self.assertEqual(retrieval.search(conn, "build from events", {}, 5)["mode"], "hybrid")
        down = {"url": None, "reachable": False, "models": []}
        with mock.patch.object(retrieval.ollama, "probe", return_value=down):
            self.assertIsNone(retrieval.get_embedder(conn), "Ollama off: keyword mode, no embed call")
        other = dict(up, models=["llama3:8b"])
        with mock.patch.object(retrieval.ollama, "probe", return_value=other):
            self.assertIsNone(retrieval.get_embedder(conn), "model not served: keyword mode")
        os.environ["AGENT_SPEC_EMBED"] = "none"
        with mock.patch.object(retrieval.ollama, "probe", return_value=up):
            self.assertIsNone(retrieval.get_embedder(conn), "none still forces keyword")

    def test_ask_with_local_model_is_labelled(self):
        os.environ["AGENT_SPEC_LLM"] = "ollama:fake"
        self.index()
        conn = self.conn()
        out = retrieval.ask(conn, self.project, "where are traces built", {}, 5)
        self.assertEqual(out["answer"]["provenance"], "ai_judged")
        self.assertEqual(out["answer"]["model"], "ollama:fake")
        self.assertEqual(out["answer"]["cited"], [1])
        self.assertIn("/api/chat", self.fake.calls)

    def test_remote_endpoint_refused(self):
        os.environ["AGENT_SPEC_OLLAMA_URL"] = "http://example.com:11434"
        os.environ.pop("AGENT_SPEC_ALLOW_REMOTE_MODELS", None)
        with self.assertRaises(retrieval.EmbedError):
            retrieval.get_embedder().embed(["x"])
        stats = self.index()  # embedding fails soft; keyword index still built
        self.assertEqual(stats["embedded"], 0)
        self.assertGreater(stats["chunks"], 0)


class SignalsTest(unittest.TestCase):
    def build(self, rows):
        t, s = traces.build_from_events(rows)
        return t, s

    def test_signals_from_hook_rows(self):
        rows = hook_rows()
        rows.insert(-2, dict(rows[6], id="e6b", ts=traces.iso(1_700_000_005_300)))  # same failing npm test again
        rows.insert(-2, dict(rows[0], id="e6c", ts=traces.iso(1_700_000_005_400), event="postToolUse",
                             tool_name="Shell", target="command=python3 -m pytest -q", duration_ms=50))
        t, s = self.build(rows)
        sig = signals.for_trace(t[0], [x for x in s if x["trace_id"] == "gen-1"], t, s)
        self.assertEqual(sig["provenance"], "measured")
        self.assertEqual(sig["tool_failures"]["count"], 2)
        self.assertEqual(sig["repeated_failures"][0]["target"], "npm test")
        self.assertEqual(sig["files_edited"]["files"], ["/p/a.py"])
        self.assertTrue(sig["verification"]["ran_after_last_edit"])
        self.assertEqual(sig["guard_blocks"], 1)
        self.assertTrue(sig["responded"])
        self.assertEqual(sig["rework_later"], {"files": [], "later_edits": {}})

    def test_tool_edit_without_file_event_still_counts(self):
        spans = [
            {"span_id": "a", "trace_id": "g", "kind": "edit", "name": "afterFileEdit", "start": "2026-01-01T00:00:01",
             "attributes": {"file_path": "/p/a.py"}},
            {"span_id": "b", "trace_id": "g", "kind": "edit", "name": "StrReplace", "start": "2026-01-01T00:00:01",
             "attributes": {"target": "file_path=/p/a.py"}},
            {"span_id": "c", "trace_id": "g", "kind": "edit", "name": "Delete", "start": "2026-01-01T00:00:02",
             "attributes": {"target": "file_path=/p/b.py"}},
        ]
        sig = signals.for_trace({"trace_id": "g", "session_id": "s", "source": "hook"}, spans)
        self.assertEqual(sig["files_edited"]["files"], ["/p/a.py", "/p/b.py"])

    def test_env_prefix_in_shell_command_is_kept(self):
        span = {"attributes": {"target": "CI=1 pytest -q"}}
        self.assertEqual(signals._target(span), "CI=1 pytest -q")

    def test_rework_in_later_request(self):
        rows = hook_rows() + [dict(r, id=r["id"] + "x", generation_id="gen-2",
                                   ts=traces.iso(1_700_000_100_000 + i)) for i, r in enumerate(hook_rows())]
        t, s = self.build(rows)
        first = next(x for x in t if x["trace_id"] == "gen-1")
        sig = signals.for_trace(first, [x for x in s if x["trace_id"] == "gen-1"], t, s)
        self.assertEqual(sig["rework_later"]["files"], ["/p/a.py"])
        self.assertIsNone(signals.for_trace(first, [])["verification"]["ran_after_last_edit"])


class ApiTest(ApiCase):
    def setUp(self):
        super().setUp()
        write(self.project, "src/limiter.py", "class RateLimiter:\n    def allow(self):\n        return True\n")
        self._store = os.environ.get("AGENT_SPEC_CURSOR_STORE")
        os.environ["AGENT_SPEC_CURSOR_STORE"] = "0"
        ingest.run(self.project, ["index"])

    def tearDown(self):
        if self._store is None:
            os.environ.pop("AGENT_SPEC_CURSOR_STORE", None)
        else:
            os.environ["AGENT_SPEC_CURSOR_STORE"] = self._store

    def get(self, path):
        status, _, body = self.request(path)
        return status, json.loads(body)

    def test_search_ask_index(self):
        status, data = self.get("/api/search?q=rate%20limiter&kind=code")
        self.assertEqual(status, 200)
        self.assertEqual(data["hits"][0]["source"], "src/limiter.py")
        status, data = self.get("/api/ask?q=rate%20limiter")
        self.assertEqual(status, 200)
        self.assertIn("cursor_prompt", data)
        status, data = self.get("/api/index")
        self.assertEqual(status, 200)
        self.assertTrue(data["ready"])
        self.assertIn("code", data["by_kind"])

    def test_bad_requests(self):
        self.assertEqual(self.get("/api/search")[0], 400)
        self.assertEqual(self.get("/api/signals")[0], 400)
        self.assertEqual(self.get("/api/signals?trace=nope")[0], 404)
        status, _, _ = self.request("/api/search?q=x", token=False)
        self.assertEqual(status, 401)


class DiversifyTest(unittest.TestCase):
    def test_one_file_cannot_fill_the_list(self):
        from aspec_platform import retrieval
        hits = [{"source": "big.py", "chunk_id": i} for i in range(6)] + [{"source": "small.py", "chunk_id": 9}]
        out = retrieval.diversify(hits, 5)
        self.assertEqual([h["source"] for h in out], ["big.py", "big.py", "small.py"])

    def test_question_filler_is_not_a_search_term(self):
        from aspec_platform import retrieval
        self.assertEqual(retrieval.fts_query("What is the purpose of the gate script?"), '"gate" OR "script"')


if __name__ == "__main__":
    unittest.main()
