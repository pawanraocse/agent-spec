#!/usr/bin/env python3
"""Local-model harness: Ollama discovery, the Ollama agent (hooks, dedupe, bare A/B arm), the
Agent Console stream API, the RAG accuracy eval with its tuned fusion weight, and the Showcase.
Every model call goes to an in-process fake Ollama on loopback; nothing leaves the machine."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TESTS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(TESTS)
sys.path.insert(0, os.path.join(REPO, "bin"))
sys.path.insert(0, TESTS)

from aspec_platform import agent_exec, db, ollama, rag_eval, retrieval, showcase  # noqa: E402
from _api_support import ApiCase  # noqa: E402

AGENT = os.path.join(REPO, "bin", "agent-spec-ollama-agent.py")
FAKE_CLI = os.path.join(TESTS, "fixtures", "fake_cursor_agent.py")
ENV_KEYS = ("AGENT_SPEC_OLLAMA_URL", "AGENT_SPEC_EMBED", "AGENT_SPEC_LLM", "AGENT_SPEC_CONSOLE",
            "AGENT_SPEC_FAKE_CURSOR_AGENT", "AGENT_SPEC_AGENT_BACKEND", "AGENT_SPEC_ALLOW_REMOTE_MODELS",
            "AGENT_SPEC_OLLAMA_MODEL")


class FakeOllama:
    """/api/tags, streaming /api/chat (a scripted list of turns) and /api/embed."""

    def __init__(self, turns=None):
        self.turns = list(turns or [])
        self.chats = []
        self.embeds = 0
        test = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                return

            def _send(self, payload: bytes):
                self.send_response(200)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def do_GET(self):
                self._send(json.dumps({"models": [
                    {"name": "coder:7b", "capabilities": ["completion", "tools"], "details": {}},
                    {"name": "nomic-embed-text:latest", "capabilities": ["embedding"], "details": {}},
                    {"name": "big:cloud", "capabilities": ["completion", "tools"], "details": {}}]}).encode())

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                if self.path == "/api/embed":
                    test.embeds += 1
                    vecs = [[t.lower().count(c) + 0.01 for c in "abcdefghijklmnopqrstuvwxyz"] for t in body["input"]]
                    return self._send(json.dumps({"embeddings": vecs}).encode())
                test.chats.append(body)
                turn = test.turns.pop(0) if test.turns else {"content": "done"}
                msg = {"role": "assistant", "content": turn.get("content", "")}
                if turn.get("call"):
                    msg["tool_calls"] = [{"function": {"name": turn["call"][0], "arguments": turn["call"][1]}}]
                lines = [{"message": msg, "done": False},
                         {"message": {"content": ""}, "done": True, "prompt_eval_count": 100, "eval_count": 7}]
                if not body.get("stream"):
                    return self._send(json.dumps({"message": msg, "done": True}).encode())
                self._send(b"".join(json.dumps(x).encode() + b"\n" for x in lines))

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = "http://127.0.0.1:%d" % self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


class EnvCase(unittest.TestCase):
    def setUp(self):
        self._saved = {k: os.environ.get(k) for k in ENV_KEYS}
        for k in ENV_KEYS:
            os.environ.pop(k, None)
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.addCleanup(self._restore)

    def _restore(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


class DiscoveryTest(EnvCase):
    def test_local_only_by_default(self):
        self.assertTrue(ollama.is_local("http://127.0.0.1:11434"))
        self.assertTrue(ollama.is_local("http://localhost:11434"))
        self.assertFalse(ollama.allowed("http://example.com:11434"))
        os.environ["AGENT_SPEC_ALLOW_REMOTE_MODELS"] = "1"
        self.assertTrue(ollama.allowed("http://example.com:11434"))

    def test_wsl_host_counts_as_local(self):
        orig = ollama.wsl_host
        ollama.wsl_host = lambda: "172.28.32.1"
        try:
            self.assertTrue(ollama.is_local("http://172.28.32.1:11434"))
            self.assertFalse(ollama.is_local("http://172.28.32.2:11434"))
            self.assertIn("http://172.28.32.1:11434", ollama.candidates())
        finally:
            ollama.wsl_host = orig

    def test_probe_lists_models_and_filters_chat(self):
        fake = FakeOllama()
        self.addCleanup(fake.close)
        os.environ["AGENT_SPEC_OLLAMA_URL"] = fake.url
        found = ollama.probe(force=True)
        self.assertEqual(found["url"], fake.url)
        self.assertEqual([m["name"] for m in ollama.chat_models(found["models"])], ["coder:7b"])  # no embed, no :cloud
        self.assertTrue(ollama.supports(found["models"], "coder:7b", "tools"))

    def test_probe_cache_follows_the_pinned_url(self):
        fake = FakeOllama()
        self.addCleanup(fake.close)
        os.environ["AGENT_SPEC_OLLAMA_URL"] = fake.url
        self.assertTrue(ollama.probe()["reachable"])
        os.environ["AGENT_SPEC_OLLAMA_URL"] = "http://example.com:11434"
        self.assertFalse(ollama.probe()["reachable"])   # not served from the old cache entry
        self.assertEqual(ollama.base_url(), "http://example.com:11434")  # pinned; _post_json refuses it

    def test_backend_prefers_free_local_model(self):
        fake = FakeOllama()
        self.addCleanup(fake.close)
        os.environ["AGENT_SPEC_OLLAMA_URL"] = fake.url
        ollama.probe(force=True)
        b = agent_exec.backend()
        self.assertEqual(b["kind"], "ollama")
        self.assertEqual(b["models"], ["coder:7b"])
        os.environ["AGENT_SPEC_AGENT_BACKEND"] = "nonesuch"
        self.assertIsNone(agent_exec.backend()["kind"])


RECORDER = r'''
import json, os, sys
data = json.loads(sys.stdin.read() or "{}")
with open(os.environ["HOOK_LOG"], "a") as fh:
    fh.write(json.dumps({"event": data.get("hook_event_name"), "tool": data.get("tool_name"),
                         "input_tokens": data.get("input_tokens"), "version": data.get("cursor_version")}) + "\n")
if data.get("hook_event_name") == "sessionStart":
    print(json.dumps({"additional_context": "stack: DIGEST-MARKER\nlast session: dropped for local models\n- [gotcha] savings live in where module: kept"}))
elif data.get("hook_event_name") == "preToolUse":
    path = str((data.get("tool_input") or {}).get("file_path", ""))
    print(json.dumps({"permission": "deny", "agent_message": "whole-file read blocked"} if path.endswith("big.py")
                     else {"permission": "allow"}))
'''


class OllamaAgentTest(EnvCase):
    def setUp(self):
        super().setUp()
        self.project = os.path.join(self.tmp, "proj")
        os.makedirs(os.path.join(self.project, ".cursor"))
        os.makedirs(os.path.join(self.project, "src"))
        with open(os.path.join(self.project, "src", "a.py"), "w") as fh:
            fh.write("def savings():\n    return 1\n")
        rec = os.path.join(self.tmp, "recorder.py")
        with open(rec, "w") as fh:
            fh.write(RECORDER)
        self.log = os.path.join(self.tmp, "hooks.log")
        cmd = {"command": "%s %s" % (sys.executable, rec), "timeout": 5}
        hooks = {ev: [cmd] for ev in ("sessionStart", "beforeSubmitPrompt", "preToolUse", "postToolUse",
                                      "postToolUseFailure", "afterAgentResponse", "stop")}
        with open(os.path.join(self.project, ".cursor", "hooks.json"), "w") as fh:
            json.dump({"version": 1, "hooks": hooks}, fh)

    def run_agent(self, turns, *extra):
        fake = FakeOllama(turns)
        self.addCleanup(fake.close)
        env = dict(os.environ, AGENT_SPEC_OLLAMA_URL=fake.url, HOOK_LOG=self.log, HOME=self.tmp)
        proc = subprocess.run([sys.executable, AGENT, "-p", "--workspace", self.project, *extra, "where is savings"],
                              capture_output=True, text=True, timeout=60, env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        lines = [json.loads(x) for x in proc.stdout.splitlines() if x.strip()]
        events = []
        if os.path.exists(self.log):
            with open(self.log) as fh:
                events = [json.loads(x) for x in fh]
        return lines, events, fake

    def test_tool_loop_fires_cursor_hooks_and_reports_usage(self):
        lines, events, fake = self.run_agent([{"call": ("Read", {"file_path": "src/a.py"})}, {"content": "src/a.py"}])
        result = lines[-1]
        self.assertEqual(result["type"], "result")
        self.assertEqual(result["result"], "src/a.py")
        self.assertEqual(result["usage"], {"input_tokens": 200, "output_tokens": 14})
        self.assertEqual(result["tools"], 1)
        self.assertEqual(lines[0]["type"], "system")
        self.assertEqual(lines[0]["request_id"], result["request_id"])
        self.assertEqual([e["event"] for e in events],
                         ["sessionStart", "beforeSubmitPrompt", "preToolUse", "postToolUse", "afterAgentResponse", "stop"])
        self.assertEqual(events[4]["input_tokens"], 200)
        system = fake.chats[0]["messages"][0]["content"]
        self.assertIn("DIGEST-MARKER", system)                 # the digest reached the model, slimmed:
        self.assertIn("savings live in where module", system)  # a fact sharing words with the prompt stays
        self.assertNotIn("last session", system)               # Cursor-session state is dropped
        self.assertIn("search_project", [t["function"]["name"] for t in fake.chats[0]["tools"]])

    def test_guard_deny_is_honoured(self):
        with open(os.path.join(self.project, "src", "big.py"), "w") as fh:
            fh.write("x = 1\n")
        lines, events, fake = self.run_agent([{"call": ("Read", {"file_path": "src/big.py"})}, {"content": "blocked"}])
        self.assertIn("postToolUseFailure", [e["event"] for e in events])
        tool_msg = [m for m in fake.chats[1]["messages"] if m["role"] == "tool"][0]
        self.assertIn("denied by harness: whole-file read blocked", tool_msg["content"])

    def test_repeated_call_is_not_rerun(self):
        call = {"call": ("Read", {"file_path": "src/a.py"})}
        lines, events, _ = self.run_agent([call, call, {"content": "src/a.py"}])
        self.assertEqual([e["event"] for e in events].count("postToolUse"), 1)
        self.assertEqual(lines[-1]["tools"], 1)

    def test_older_tool_results_are_compacted(self):
        big = "x" * 2000
        with open(os.path.join(self.project, "src", "b.py"), "w") as fh:
            fh.write((big + "\n") * 3)
        turns = [{"call": ("Read", {"file_path": "src/b.py"})}, {"call": ("Grep", {"pattern": "zzz"})}, {"content": "ok"}]
        _, _, fake = self.run_agent(turns)
        third = [m for m in fake.chats[2]["messages"] if m["role"] == "tool"]
        self.assertLess(len(third[0]["content"]), 400)          # the earlier Read was shrunk
        self.assertIn("chars elided", third[0]["content"])

    def test_budget_exhaustion_still_answers(self):
        turns = [{"call": ("Grep", {"pattern": "p%d" % i})} for i in range(5)] + [{"content": "answer from notes"}]
        lines, _, fake = self.run_agent(turns)
        self.assertEqual(lines[-1]["result"], "answer from notes")
        self.assertEqual(fake.chats[-1]["tools"], [])   # the final turn is tool-free

    def test_bare_arm_skips_harness_hooks_and_tools(self):
        lines, events, fake = self.run_agent([{"content": "guess"}], "--bare")
        names = [e["event"] for e in events]
        self.assertNotIn("sessionStart", names)
        self.assertNotIn("preToolUse", names)
        self.assertIn("afterAgentResponse", names)
        self.assertTrue(events[0]["version"].endswith("+bare"))
        tools = [t["function"]["name"] for t in fake.chats[0]["tools"]]
        self.assertNotIn("graphify_context", tools)
        self.assertNotIn("search_project", tools)
        self.assertTrue(lines[-1]["bare"])

    def test_skill_prompt_loads_the_installed_skill(self):
        skill = os.path.join(self.tmp, ".cursor", "skills", "agent-spec-demo")
        os.makedirs(skill)
        with open(os.path.join(skill, "SKILL.md"), "w") as fh:
            fh.write("DEMO-SKILL-BODY")
        fake = FakeOllama([{"content": "src/a.py"}])
        self.addCleanup(fake.close)
        env = dict(os.environ, AGENT_SPEC_OLLAMA_URL=fake.url, HOOK_LOG=self.log, HOME=self.tmp)
        for extra, expect in (([], True), (["--bare"], False)):
            proc = subprocess.run([sys.executable, AGENT, "-p", "--workspace", self.project, *extra,
                                   "/agent-spec-demo where is savings"], capture_output=True, text=True, timeout=60, env=env)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual("DEMO-SKILL-BODY" in fake.chats[-1]["messages"][0]["content"], expect)


class ConsoleApiTest(ApiCase):
    def setUp(self):
        self._saved = {k: os.environ.get(k) for k in ENV_KEYS}
        os.environ["AGENT_SPEC_FAKE_CURSOR_AGENT"] = FAKE_CLI
        os.environ["AGENT_SPEC_CONSOLE"] = "1"
        super().setUp()

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def _post(self, path, body):
        import http.client
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        data = json.dumps(body)
        conn.request("POST", path, body=data, headers={"Content-Type": "application/json", "X-Agent-Spec-Token": self.token,
                                                       "Origin": "http://127.0.0.1:%d" % self.port,
                                                       "Host": "127.0.0.1:%d" % self.port})
        resp = conn.getresponse()
        out = resp.status, json.loads(resp.read() or b"{}")
        conn.close()
        return out

    def test_status_reports_backend(self):
        s = self.get_json("/api/agent/status")
        self.assertTrue(s["enabled"])
        self.assertEqual(s["backend"], "fake")

    def test_session_streams_to_done(self):
        status, body = self._post("/api/agent/sessions", {"prompt": "hello", "mode": "ask"})
        self.assertEqual(status, 200, body)
        st, headers, raw = self.request("/api/agent/jobs/%s/stream" % body["job_id"])
        self.assertEqual(st, 200)
        self.assertEqual(headers["content-type"], "text/event-stream")
        text = raw.decode()
        self.assertIn("event: message", text)
        self.assertIn('"final": true', text)
        self.assertIn('"exit_code": 0', text)

    def test_unknown_job_and_bad_input(self):
        self.assertEqual(self.request("/api/agent/jobs/nope/stream")[0], 404)
        self.assertEqual(self._post("/api/agent/sessions", {"prompt": "x", "model": "a b;rm"})[0], 400)
        self.assertEqual(self._post("/api/agent/sessions", {"prompt": "  "})[0], 400)
        self.assertEqual(self._post("/api/agent/sessions", {"prompt": "x", "mode": "yolo"})[0], 400)

    def test_console_off_switch(self):
        os.environ["AGENT_SPEC_CONSOLE"] = "0"
        self.assertFalse(self.get_json("/api/agent/status")["enabled"])
        status, body = self._post("/api/agent/sessions", {"prompt": "hello"})
        self.assertEqual((status, body["error"]), (404, "console_frozen"))

    def test_stream_needs_token(self):
        self.assertEqual(self.request("/api/agent/jobs/x/stream", token=False)[0], 401)


def write(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


class RagEvalTest(EnvCase):
    def setUp(self):
        super().setUp()
        self.project = os.path.join(self.tmp, "proj")
        os.makedirs(os.path.join(self.project, ".agent-spec", "metrics"))
        write(self.project, "src/limiter.py", '"""Throttle outgoing requests with a token bucket per client."""\n\nclass Limiter:\n    pass\n')
        write(self.project, "src/billing.py", '"""Compute monthly invoices from metered usage records."""\n\ndef invoice():\n    return 0\n')
        write(self.project, "docs/OPS.md", "# Operations\n\nRestart the worker pool when the queue stalls for ten minutes.\n")
        os.environ["AGENT_SPEC_DB"] = os.path.join(self.tmp, "p.db")
        self.addCleanup(os.environ.pop, "AGENT_SPEC_DB", None)
        os.makedirs(os.path.dirname(rag_eval.golden_path(self.project)))
        with open(rag_eval.golden_path(self.project), "w") as fh:
            fh.write(json.dumps({"q": "token bucket throttle per client", "expect": "src/limiter.py"}) + "\n")
            fh.write(json.dumps({"q": "monthly invoices metered usage", "expect": "src/billing.py"}) + "\n")

    def index(self):
        conn = db.open_ready(db.db_path(self.project))
        with conn:
            retrieval.ingest_index(conn, self.project)
        return conn

    def test_keyword_scores_and_history(self):
        conn = self.index()
        with conn:
            r = rag_eval.run(conn, self.project, k=3, label="first")
        self.assertTrue(r["ok"])
        self.assertEqual(r["modes"]["keyword"]["hit1"], 1.0)
        self.assertNotIn("hybrid", r["modes"])   # no embedder configured
        self.assertEqual(rag_eval.latest(conn)["cases"], 2)
        with conn:
            rag_eval.run(conn, self.project, k=3, label="second")
        self.assertEqual([h["label"] for h in rag_eval.history(conn)], ["first", "second"])
        self.assertEqual(retrieval.fusion_weight(conn)["semantic_weight"], 1.0)   # untuned default

    def test_tuned_weight_is_stored_and_used(self):
        fake = FakeOllama()
        self.addCleanup(fake.close)
        os.environ["AGENT_SPEC_OLLAMA_URL"] = fake.url
        os.environ["AGENT_SPEC_EMBED"] = "ollama:nomic-embed-text"
        conn = self.index()
        self.assertEqual(retrieval.get_embedder().name, "ollama:nomic-embed-text#task-prefix")
        with conn:
            r = rag_eval.run(conn, self.project, k=3)
        self.assertIn("tuned", r["modes"])
        w = r["fusion"]["semantic_weight"]
        self.assertIn(w, rag_eval.SWEEP)
        self.assertEqual(retrieval.fusion_weight(conn)["semantic_weight"], w)
        with conn:   # a measured weight of 0 turns the embed call off entirely
            conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (retrieval.FUSION_KEY, json.dumps({"semantic_weight": 0})))
        before = fake.embeds
        res = retrieval.search(conn, "token bucket", {}, 3)
        self.assertEqual(res["mode"], "keyword")
        self.assertEqual(fake.embeds, before)

    def test_weighted_fusion(self):
        a = [{"chunk_id": 1, "snippet": ""}, {"chunk_id": 2, "snippet": ""}]
        b = [{"chunk_id": 2}, {"chunk_id": 1}]
        self.assertEqual(retrieval.fuse([("keyword", a), ("semantic", b)], 2, {"semantic": 0.0})[0]["chunk_id"], 1)
        self.assertEqual(retrieval.fuse([("keyword", a), ("semantic", b)], 2, {"semantic": 5.0})[0]["chunk_id"], 2)


class ShowcaseTest(EnvCase):
    def test_overview_with_events_and_bench(self):
        project = os.path.join(self.tmp, "proj")
        metrics = os.path.join(project, ".agent-spec", "metrics")
        os.makedirs(metrics)
        os.makedirs(os.path.join(project, ".agent-spec", "eval"))
        rows = [{"id": "e1", "ts": "2026-11-15T10:00:00.000Z", "event": "beforeSubmitPrompt", "conversation_id": "c1",
                 "generation_id": "g1", "model": "ollama:coder:7b", "prompt": "where is x", "cursor_version": "ollama-agent/1.0"},
                {"id": "e2", "ts": "2026-11-15T10:00:01.000Z", "event": "postToolUse", "conversation_id": "c1",
                 "generation_id": "g1", "model": "ollama:coder:7b", "tool_name": "Read", "target": "file_path=a.py",
                 "ranged": True, "status": "ok"},
                {"id": "e3", "ts": "2026-11-15T10:00:02.000Z", "event": "afterAgentResponse", "conversation_id": "c1",
                 "generation_id": "g1", "model": "ollama:coder:7b", "text": "a.py", "input_tokens": 500, "output_tokens": 20},
                {"id": "e4", "ts": "2026-11-15T10:00:03.000Z", "event": "stop", "conversation_id": "c1",
                 "generation_id": "g1", "model": "ollama:coder:7b", "status": "completed"}]
        with open(os.path.join(metrics, "events.jsonl"), "w") as fh:
            fh.writelines(json.dumps(r) + "\n" for r in rows)
        bench = [{"run_id": "r1", "ts": "2026-11-15T10:00:00Z", "case": 1, "arm": "harness", "correct": True, "tokens_in": 900,
                  "tools": 2, "ms": 4000, "prompt": "p", "expect": ["a.py"], "model": "ollama:coder:7b"},
                 {"run_id": "r1", "ts": "2026-11-15T10:00:05Z", "case": 1, "arm": "bare", "correct": False, "tokens_in": 300,
                  "tools": 1, "ms": 3000, "prompt": "p", "expect": ["a.py"], "model": "ollama:coder:7b"}]
        with open(os.path.join(project, ".agent-spec", "eval", "agent-bench-results.jsonl"), "w") as fh:
            fh.writelines(json.dumps(r) + "\n" for r in bench)
        out = showcase.overview(project, None)
        self.assertEqual(out["requests"], 1)
        self.assertEqual(out["tokens"]["billed_in"], 500)
        self.assertEqual(out["efficiency"]["ranged_read_pct"], 100.0)
        self.assertEqual(out["by_model"][0]["model"], "ollama:coder:7b")
        self.assertTrue(out["by_model"][0]["local"])
        self.assertEqual(out["prompts"][0]["prompt"], "where is x")
        self.assertEqual(out["prompts"][0]["origin"], "local")   # asked on purpose: not hidden like CLI runs
        self.assertEqual(out["bench"]["arms"]["harness"]["correct"], 1)
        self.assertEqual(out["bench"]["arms"]["bare"]["correct"], 0)
        self.assertEqual(out["bench"]["cases"][0]["expect"], ["a.py"])
        self.assertIsNone(out["skill_bench"])
        skill_rows = [dict(r, run_id="s1", arm=arm, skill="agent-spec-x" if arm == "skill" else None)
                      for r, arm in zip(bench, ("plain", "skill"))]
        with open(os.path.join(project, ".agent-spec", "eval", "skill-bench-results.jsonl"), "w") as fh:
            fh.writelines(json.dumps(r) + "\n" for r in skill_rows)
        out = showcase.overview(project, None)
        self.assertEqual(out["skill_bench"]["skill"], "agent-spec-x")
        self.assertEqual(out["skill_bench"]["arms"]["skill"]["tokens_in"], 300)
        self.assertEqual(out["bench"]["run_id"], "r1")      # the harness A/B is unaffected


class FirstServeTest(EnvCase):
    def test_summary_works_on_a_project_never_ingested(self):
        from aspec_platform import serve
        project = os.path.join(self.tmp, "fresh")
        os.makedirs(os.path.join(project, ".agent-spec", "platform"))
        path = db.db_path(project)
        conn = db.connect(path)
        conn.execute("CREATE TABLE unrelated (x)")   # a database another tool created first
        conn.close()
        with self.assertRaises(Exception):
            showcase.overview(project, db.connect(path, readonly=True))
        serve.ensure_db(project)
        out = showcase.overview(project, db.connect(path, readonly=True))
        self.assertEqual(out["requests"], 0)

if __name__ == "__main__":
    unittest.main()
