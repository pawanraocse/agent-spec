#!/usr/bin/env python3
"""The local agent's Groq mode (`--model groq:<name>`): OpenAI-shaped messages and tool ids,
measured usage, the remote-model gate, the key lookup, rate-limit waits, malformed tool calls,
and --resume. Every call goes to an in-process fake on loopback; nothing leaves the machine."""
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

from aspec_platform import redact  # noqa: E402
from test_local_agent import RECORDER  # noqa: E402

AGENT = os.path.join(REPO, "bin", "agent-spec-ollama-agent.py")
KEY = "gsk_" + "A1b2C3d4" * 6
CLEAR = ("GROQ_API_KEY", "AGENT_SPEC_GROQ_URL", "AGENT_SPEC_ALLOW_REMOTE_MODELS", "AGENT_SPEC_OLLAMA_URL",
         "AGENT_SPEC_OLLAMA_MODEL")


class FakeGroq:
    """POST /chat/completions answering from a scripted list. A turn is {"content"}, {"call": (name,
    args)}, {"status": 429|401|400, "error": {...}} or {"status": 429, "retry_after": "1"}."""

    def __init__(self, turns):
        self.turns, self.requests = list(turns), []
        test = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                return

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                test.requests.append({"path": self.path, "auth": self.headers.get("Authorization"),
                                      "agent": self.headers.get("User-Agent"), "body": body})
                turn = test.turns.pop(0) if test.turns else {"content": "done"}
                if turn.get("status"):
                    payload = json.dumps({"error": turn.get("error") or {"message": "slow down"}}).encode()
                    self.send_response(turn["status"])
                    if turn.get("retry_after"):
                        self.send_header("retry-after", turn["retry_after"])
                else:
                    msg = {"role": "assistant", "content": turn.get("content")}
                    if turn.get("call"):
                        msg["tool_calls"] = [{"id": "x", "type": "function", "function": {
                            "name": turn["call"][0], "arguments": json.dumps(turn["call"][1])}}]
                    payload = json.dumps({"choices": [{"message": msg}], "usage": {
                        "prompt_tokens": 300, "completion_tokens": 9,
                        "prompt_tokens_details": {"cached_tokens": 100}}}).encode()
                    self.send_response(200)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = "http://127.0.0.1:%d/openai/v1" % self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


class GroqAgentTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
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
        with open(os.path.join(self.project, ".cursor", "hooks.json"), "w") as fh:
            json.dump({"version": 1, "hooks": {ev: [cmd] for ev in ("sessionStart", "preToolUse", "postToolUse",
                                                                    "afterAgentResponse", "stop")}}, fh)

    def run_agent(self, turns, *extra, env_extra=None, fake_url=True, prompt="where is savings"):
        fake = FakeGroq(turns)
        self.addCleanup(fake.close)
        env = {k: v for k, v in os.environ.items() if k not in CLEAR}
        env.update(HOOK_LOG=self.log, HOME=self.tmp, GROQ_API_KEY=KEY)
        if fake_url:
            env["AGENT_SPEC_GROQ_URL"] = fake.url
        env.update(env_extra or {})
        proc = subprocess.run([sys.executable, AGENT, "-p", "--workspace", self.project, "--model", "groq:test-model",
                               *extra, prompt], capture_output=True, text=True, timeout=60, env=env)
        lines = [json.loads(x) for x in proc.stdout.splitlines() if x.strip()]
        return proc, lines, fake

    def test_tool_loop_on_groq(self):
        proc, lines, fake = self.run_agent([{"call": ("Read", {"file_path": "src/a.py"})}, {"content": "src/a.py"}])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = lines[-1]
        self.assertEqual(result["result"], "src/a.py")
        self.assertEqual(result["model"], "groq:test-model")
        self.assertEqual(result["usage"], {"input_tokens": 600, "output_tokens": 18})
        self.assertEqual([s.get("cached_tokens") for s in result["step_usage"]], [100, 100])
        self.assertEqual(fake.requests[0]["path"], "/openai/v1/chat/completions")
        self.assertEqual(fake.requests[0]["auth"], "Bearer " + KEY)
        self.assertFalse(fake.requests[0]["agent"].startswith("Python-urllib"))  # Cloudflare 1010
        self.assertEqual(fake.requests[0]["body"]["model"], "test-model")
        self.assertIn("Read", [t["function"]["name"] for t in fake.requests[0]["body"]["tools"]])
        second = fake.requests[1]["body"]["messages"]
        call = next(m for m in second if m.get("tool_calls"))
        answer = next(m for m in second if m["role"] == "tool")
        self.assertEqual(call["tool_calls"][0]["id"], answer["tool_call_id"])
        self.assertIsInstance(call["tool_calls"][0]["function"]["arguments"], str)
        self.assertIn("savings", answer["content"])
        self.assertTrue(all("tool_name" not in m for m in second))
        with open(self.log) as fh:
            events = [json.loads(x) for x in fh]
        after = next(e for e in events if e["event"] == "afterAgentResponse")
        self.assertEqual(after["input_tokens"], 600)

    def test_resume_sends_a_valid_history(self):
        proc, lines, _ = self.run_agent([{"call": ("Read", {"file_path": "src/a.py"})}, {"content": "src/a.py"}])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        proc, _, fake = self.run_agent([{"content": "the savings function"}], "--resume", lines[-1]["session_id"],
                                       prompt="which function?")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        msgs = fake.requests[0]["body"]["messages"]
        ids = [c["id"] for m in msgs for c in m.get("tool_calls") or []]
        answered = [m["tool_call_id"] for m in msgs if m["role"] == "tool"]
        self.assertEqual(ids, answered)
        self.assertEqual(msgs[-1], {"role": "user", "content": "which function?"})

    def test_remote_endpoint_needs_opt_in(self):
        proc, lines, fake = self.run_agent([], fake_url=False)
        self.assertEqual(proc.returncode, 3)
        self.assertIn("AGENT_SPEC_ALLOW_REMOTE_MODELS=1", lines[-1]["result"])
        self.assertEqual(fake.requests, [])

    def test_missing_key_and_key_file(self):
        proc, lines, _ = self.run_agent([], env_extra={"GROQ_API_KEY": ""})
        self.assertEqual(proc.returncode, 3)
        self.assertIn("groq_api_key", lines[-1]["result"])
        os.makedirs(os.path.join(self.tmp, ".config", "agent-spec"))
        with open(os.path.join(self.tmp, ".config", "agent-spec", "groq_api_key"), "w") as fh:
            fh.write(KEY + "\n")
        proc, lines, fake = self.run_agent([{"content": "ok"}], env_extra={"GROQ_API_KEY": ""})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(fake.requests[0]["auth"], "Bearer " + KEY)

    def test_rate_limit_is_waited_out(self):
        proc, lines, fake = self.run_agent([{"status": 429, "retry_after": "1"}, {"content": "src/a.py"}])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(len(fake.requests), 2)
        self.assertEqual(lines[-1]["result"], "src/a.py")

    def test_quota_past_the_wait_cap_exits_3(self):
        proc, lines, fake = self.run_agent([{"status": 429, "retry_after": "1319",
                                             "error": {"message": "Rate limit reached on tokens per day (TPD)"}}])
        self.assertEqual(proc.returncode, 3)
        self.assertIn("tokens per day", lines[-1]["result"])
        self.assertEqual(len(fake.requests), 1)

    def test_malformed_tool_call_falls_back_to_text_parser(self):
        bad = {"status": 400, "error": {"code": "tool_use_failed", "message": "bad call",
                                        "failed_generation": '{"name": "Read", "arguments": {"file_path": "src/a.py"}}'}}
        proc, lines, _ = self.run_agent([bad, {"content": "src/a.py"}])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(lines[-1]["tools"], 1)

    def test_empty_failed_generation_is_retried_not_answered(self):
        bad = {"status": 400, "error": {"code": "tool_use_failed", "message": "bad call", "failed_generation": ""}}
        proc, lines, fake = self.run_agent([bad, {"content": "src/a.py"}])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(lines[-1]["result"], "src/a.py")
        self.assertIn("plain text", fake.requests[1]["body"]["messages"][-1]["content"])

    def test_lowercase_text_call_runs(self):
        proc, lines, _ = self.run_agent([{"content": '{"name": "read", "arguments": {"file_path": "src/a.py"}}'},
                                         {"content": "src/a.py"}])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(lines[-1]["tools"], 1)
        self.assertEqual(lines[-1]["result"], "src/a.py")

    def test_bad_key_exits_3_without_echoing_it(self):
        proc, lines, _ = self.run_agent([{"status": 401, "error": {"message": "Invalid API Key " + KEY}}])
        self.assertEqual(proc.returncode, 3)
        self.assertIn("groq HTTP 401", lines[-1]["result"])
        self.assertNotIn(KEY, proc.stdout + proc.stderr)

    def test_unknown_model_exits_3(self):
        proc, lines, _ = self.run_agent([{"status": 404, "error": {"message": "The model does not exist"}}])
        self.assertEqual(proc.returncode, 3)
        self.assertIn("groq HTTP 404", lines[-1]["result"])

    def test_multi_turn_bench_runs_the_local_agent_on_groq(self):
        fake = FakeGroq([])  # every call answers "done": one model call per turn
        self.addCleanup(fake.close)
        tasks = os.path.join(self.tmp, "tasks.jsonl")
        with open(tasks, "w") as fh:
            fh.write(json.dumps({"id": "t", "turns": [{"prompt": "a?", "expect": ["done"]}, {"prompt": "b?"}]}) + "\n")
        env = {k: v for k, v in os.environ.items() if k not in CLEAR}
        env.update(HOOK_LOG=self.log, HOME=self.tmp, GROQ_API_KEY=KEY, AGENT_SPEC_GROQ_URL=fake.url)
        proc = subprocess.run([sys.executable, os.path.join(REPO, "bin", "agent-spec-cursor-bench.py"), "--agent",
                               "local", "--model", "groq:test-model", "--project", self.project, "--tasks", tasks],
                              capture_output=True, text=True, timeout=120, env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        with open(os.path.join(self.project, ".agent-spec", "eval", "cursor-bench-results.jsonl")) as fh:
            rows = [json.loads(x) for x in fh]
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0]["usage"], {"inputTokens": 200, "outputTokens": 9, "cacheReadTokens": 100})
        self.assertEqual(rows[0]["agent"], "local")
        by = {(r["arm"], r["turn"]): r for r in rows}
        self.assertEqual(by[("skill", 1)]["session_id"], by[("skill", 2)]["session_id"])
        self.assertIn("Local agent head-to-head", proc.stdout)
        self.assertIn("Not Cursor", proc.stdout)

    def test_groq_keys_are_redacted(self):
        self.assertNotIn(KEY, redact.redact("key is " + KEY))


if __name__ == "__main__":
    unittest.main()
