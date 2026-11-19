#!/usr/bin/env python3
"""Tests for agent-spec-cursor-bench.py (H-050 Cursor half), against a fake cursor-agent."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(REPO, "bin", "agent-spec-cursor-bench.py")

FAKE = r'''#!/usr/bin/env python3
import json, os, sys
argv = sys.argv[1:]
if "--version" in argv:
    print("2026.11.11-fake"); sys.exit(0)
log = os.environ["FAKE_LOG"]
with open(log, "a") as fh:
    fh.write(json.dumps(argv) + "\n")
if os.environ.get("FAKE_CWD_LOG"):
    with open(os.environ["FAKE_CWD_LOG"], "a") as fh:
        fh.write(json.dumps({"cwd": os.getcwd(), "rules": os.path.isfile(".cursor/rules/agent-spec.mdc"),
                             "hooks": os.path.isfile(".cursor/hooks.json"),
                             "memory": os.path.isdir(".agent-spec/memory/facts"),
                             "onboarding": os.path.exists(".agent-spec/.onboarding-needed")}) + "\n")
if os.environ.get("FAKE_LIMIT"):
    print("ActionRequiredError: You've hit your usage limit", file=sys.stderr); sys.exit(1)
prompt = argv[-1]
session = argv[argv.index("--resume") + 1] if "--resume" in argv else "sess-%d" % sum(1 for _ in open(log))
print(json.dumps({"type": "system", "subtype": "init", "session_id": session, "model": "fake-model"}))
if prompt.startswith("/agent-spec-raw-code-full"):
    print(json.dumps({"type": "tool_call", "subtype": "started", "session_id": session,
                      "tool_call": {"readToolCall": {"args": {"path": "~/.cursor/skills/agent-spec-raw-code-full/SKILL.md"}}}}))
print(json.dumps({"type": "tool_call", "subtype": "started", "session_id": session,
                  "tool_call": {"readToolCall": {"args": {"path": "x.py"}}}}))
if os.path.isfile(".cursor/rules/agent-spec.mdc"):
    print(json.dumps({"type": "tool_call", "subtype": "started", "session_id": session, "tool_call": {
        "shellToolCall": {"args": {"command": "./.agent-spec/bin/graphify-cli.py callers --symbol f"}}}}))
resumed = "--resume" in argv
print(json.dumps({"type": "result", "session_id": session, "result": "It is savings.py, 152 B, /api/savings in serve.py",
                  "usage": {"inputTokens": 100 + (900 if resumed else 0), "outputTokens": 10,
                            "cacheReadTokens": 50, "cacheWriteTokens": 0}}))
'''


class CursorBenchTest(unittest.TestCase):

    def test_report_leaves_out_chats_run_in_one_arm(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("cbench", SCRIPT)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        row = lambda task, rep, arm, n: {"task": task, "repeat": rep, "arm": arm, "turn": 1, "correct": True,  # noqa: E731
                                         "usage": {"inputTokens": n}, "tools": 0, "seconds": 1}
        rows = [row("a", 1, "plain", 100), row("a", 1, "skill", 150), row("a", 2, "skill", 999)]
        kept, left = mod.paired(rows)
        self.assertEqual((len(kept), left), (2, 1))
        text = mod.report(rows, {"agent": "local", "run_id": "r", "ts": "t", "cli_version": "v", "model": "m",
                                 "tasks": 1, "turns": 1, "repeat": 2, "os": "x"}, "s")
        self.assertIn("| All input (uncached + cache) | 100 | 150 | +50% |", text)
        self.assertIn("1 chat(s) ran in one arm only", text)
        self.assertIn("n = 1 chats per arm", text)

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.project = os.path.join(self.tmp, "proj")
        self.eval = os.path.join(self.project, ".agent-spec", "eval")
        os.makedirs(self.eval)
        task = {"id": "savings", "turns": [{"prompt": "Which file?", "expect": ["savings.py"]},
                                           {"prompt": "Which endpoint?", "expect": ["/api/nope"]}]}
        self.tasks = os.path.join(self.tmp, "cursor-bench.jsonl")
        with open(self.tasks, "w") as fh:
            fh.write(json.dumps(task) + "\n")
        self.fake = os.path.join(self.tmp, "fake_agent.py")
        with open(self.fake, "w") as fh:
            fh.write(FAKE)
        self.log = os.path.join(self.tmp, "calls.log")

    def run_bench(self, **extra_env):
        env = dict(os.environ, AGENT_SPEC_FAKE_CURSOR_AGENT=self.fake, FAKE_LOG=self.log, **extra_env)
        return subprocess.run([sys.executable, SCRIPT, "--project", self.project, "--tasks", self.tasks], capture_output=True,
                              text=True, env=env, timeout=60)

    def rows(self):
        with open(os.path.join(self.eval, "cursor-bench-results.jsonl")) as fh:
            return [json.loads(l) for l in fh if l.strip()]

    def test_compare_harness_registers_one_copy_and_counts_graph_calls(self):
        for argv in (["init", "-q"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "x",
                                                     "--allow-empty"]):
            subprocess.run(["git"] + argv, cwd=self.project, check=True, capture_output=True)
        facts = os.path.join(self.project, ".agent-spec", "memory", "facts")
        os.makedirs(facts)
        os.makedirs(os.path.join(self.project, ".agent-spec", "graph"))
        with open(os.path.join(self.project, ".agent-spec", "graph", "knowledge-graph.json"), "w") as fh:
            fh.write("{}")
        cwd_log = os.path.join(self.tmp, "cwd.log")
        env = dict(os.environ, AGENT_SPEC_FAKE_CURSOR_AGENT=self.fake, FAKE_LOG=self.log, FAKE_CWD_LOG=cwd_log,
                   TMPDIR=self.tmp)
        proc = subprocess.run([sys.executable, SCRIPT, "--project", self.project, "--tasks", self.tasks,
                               "--compare", "harness"], capture_output=True, text=True, env=env, timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        with open(cwd_log) as fh:
            seen = [json.loads(x) for x in fh]
        bare = [x for x in seen if not x["rules"]]
        harness = [x for x in seen if x["rules"]]
        self.assertEqual((len(bare), len(harness)), (2, 2))
        self.assertTrue(all(x["hooks"] and x["memory"] and not x["onboarding"] for x in harness), harness)
        self.assertFalse(any(x["memory"] for x in bare))
        self.assertNotIn(self.project, {x["cwd"] for x in seen})
        with open(self.log) as fh:
            calls = [json.loads(x) for x in fh]
        self.assertTrue(all("--trust" in c and "--force" in c for c in calls))
        self.assertIn("| Graph calls (graphify-cli) | 0 | 2 |", proc.stdout)
        self.assertEqual([n for n in os.listdir(self.tmp) if n.startswith("aspec-claude-bench-")], [])

    def test_both_arms_resume_and_report(self):
        proc = self.run_bench()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        rows = self.rows()
        self.assertEqual(sorted((r["arm"], r["turn"]) for r in rows),
                         [("plain", 1), ("plain", 2), ("skill", 1), ("skill", 2)])
        with open(self.log) as fh:
            calls = [json.loads(l) for l in fh if l.strip()]
        # Turn 2 resumes the chat turn 1 opened; the skill prefix is on turn 1 only.
        firsts = [c for c in calls if "--resume" not in c]
        seconds = [c for c in calls if "--resume" in c]
        self.assertEqual(len(firsts), 2)
        self.assertEqual(len(seconds), 2)
        self.assertEqual(sum(c[-1].startswith("/agent-spec-raw-code-full ") for c in calls), 1)
        by = {(r["arm"], r["turn"]): r for r in rows}
        self.assertEqual(by[("skill", 2)]["session_id"], by[("skill", 1)]["session_id"])
        self.assertTrue(by[("skill", 1)]["skill_read"])
        self.assertFalse(by[("plain", 1)]["skill_read"])
        self.assertEqual(by[("plain", 1)]["tools"], 1)
        self.assertEqual(by[("skill", 1)]["tools"], 2)
        self.assertTrue(by[("plain", 1)]["correct"])
        self.assertFalse(by[("plain", 2)]["correct"])
        self.assertEqual(by[("plain", 2)]["usage"]["inputTokens"], 1000)
        md = [f for f in os.listdir(self.eval) if f.startswith("cursor-bench-2") and f.endswith(".md")]
        self.assertEqual(len(md), 1)
        with open(os.path.join(self.eval, md[0])) as fh:
            text = fh.read()
        self.assertIn("| Correct | 1/2 | 1/2 | |", text)
        self.assertIn("| Input tokens (uncached) | 1,100 | 1,100 | +0% |", text)
        self.assertIn("| All input (uncached + cache) | 1,200 | 1,200 | +0% |", text)
        self.assertIn("Skill file read seen in 1 of 2", text)

    def test_usage_limit_stops_without_rows(self):
        proc = self.run_bench(FAKE_LIMIT="1")
        self.assertEqual(proc.returncode, 3)
        self.assertIn("usage limit", proc.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.eval, "cursor-bench-results.jsonl")))

    def test_missing_cli(self):
        env = {k: v for k, v in os.environ.items() if k != "AGENT_SPEC_FAKE_CURSOR_AGENT"}
        env["PATH"] = self.tmp  # no cursor-agent on PATH
        proc = subprocess.run([sys.executable, SCRIPT, "--project", self.project, "--tasks", self.tasks], capture_output=True,
                              text=True, env=env, timeout=60)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("cursor-agent not found", proc.stderr)


FAKE_CLAUDE = r'''#!/usr/bin/env python3
import json, os, re, sys, uuid
argv = sys.argv[1:]
if "--version" in argv:
    print("9.9.9 (Claude Code fake)"); sys.exit(0)
if os.environ.get("CLAUDECODE"):
    print("Error: Claude Code cannot be launched inside another Claude Code session.", file=sys.stderr); sys.exit(1)
with open(os.environ["FAKE_LOG"], "a") as fh:
    fh.write(json.dumps({"argv": argv, "cwd": os.getcwd(), "claude_md": os.path.exists("CLAUDE.md"),
                         "graph": os.path.isdir(".agent-spec/graph"), "run_state": os.path.isdir(".agent-spec/platform"),
                         "skill": os.path.isdir(".claude/skills")}) + "\n")
with open(os.environ["FAKE_LOG"]) as fh:
    ncall = sum(1 for _ in fh)
prompt = argv[-1]
if os.environ.get("FAKE_AUTH_FAIL") and ncall >= int(os.environ["FAKE_AUTH_FAIL"]):
    # What Claude Code 2.x prints for an expired login: exit 1, a result event, zero usage.
    print(json.dumps({"type": "result", "session_id": str(uuid.uuid4()), "is_error": True, "total_cost_usd": 0,
                      "result": "Failed to authenticate. API Error: 401 {\"type\":\"error\",\"error\":{\"type\":"
                                "\"authentication_error\",\"message\":\"OAuth access token has expired.\"}}",
                      "usage": {"input_tokens": 0, "output_tokens": 0}}))
    sys.exit(1)
session = argv[argv.index("--resume") + 1] if "--resume" in argv else str(uuid.uuid4())
folder = os.path.join(os.environ["HOME"], ".claude", "projects", re.sub(r"[^A-Za-z0-9]", "-", os.getcwd()))
os.makedirs(folder, exist_ok=True)
saved = prompt
if "--resume" not in argv and os.path.exists(".claude/settings.json"):
    import subprocess
    for group in json.load(open(".claude/settings.json")).get("hooks", {}).get("SessionStart", []):
        if group.get("matcher", "startup") == "startup":
            for h in group["hooks"]:
                saved += subprocess.run(h["command"], shell=True, capture_output=True, text=True).stdout
if prompt.startswith("/agent-spec-raw-code-full") and not os.environ.get("FAKE_NO_SKILL"):
    saved += json.dumps("Governs every reply and tool call until \"stop\".")
with open(os.path.join(folder, session + ".jsonl"), "a") as fh:
    fh.write(json.dumps({"message": saved}) + "\n")
if "Change" in prompt:
    with open("conf.txt", "w") as fh:
        fh.write("size=200\n")
skill = prompt.startswith("/")
print(json.dumps({"type": "system", "subtype": "init", "session_id": session, "model": "claude-haiku-5-5"}))
print(json.dumps({"type": "assistant", "session_id": session, "message": {"content": [
    {"type": "tool_use", "name": "Read", "input": {}}] * (1 if skill else 2)}}))
print(json.dumps({"type": "result", "session_id": session, "result": "size is in conf.txt", "is_error": False,
                  "total_cost_usd": 0.01 if skill else 0.02,
                  "usage": {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 1000,
                            "cache_creation_input_tokens": 200}}))
'''


class ClaudeBenchTest(unittest.TestCase):
    """--agent claude: a fresh copy per chat, setup and checks, cost, paired statistics, cleanup."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(__import__("shutil").rmtree, self.tmp, True)
        self.home = os.path.join(self.tmp, "home")
        skill = os.path.join(self.home, ".cursor", "skills", "agent-spec-raw-code-full")
        os.makedirs(skill)
        with open(os.path.join(skill, "SKILL.md"), "w") as fh:
            fh.write('---\nname: x\n---\n\n# x\n\nGoverns every reply and tool call until "stop".\n')
        self.project = os.path.join(self.tmp, "proj")
        os.makedirs(self.project)
        for name, body in (("conf.txt", "size=152\n"), ("CURSOR.md", "rule\n"), ("bug.txt", "broken\n")):
            with open(os.path.join(self.project, name), "w") as fh:
                fh.write(body)
        for argv in (["init", "-q"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "x"]):
            subprocess.run(["git"] + argv, cwd=self.project, check=True, capture_output=True)
        self.tasks = os.path.join(self.tmp, "tasks.jsonl")
        with open(self.tasks, "w") as fh:
            fh.write(json.dumps({"id": "q", "turns": [{"prompt": "Where is size?", "expect": ["conf.txt"]}]}) + "\n")
            fh.write(json.dumps({"id": "e", "edits": True,
                                 "setup": [{"file": "bug.txt", "replace": ["broken", "planted"]}],
                                 "turns": [{"prompt": "Which file?", "expect_any": ["nope", "conf.txt"]},
                                           {"prompt": "Change size to 200", "check": "grep -q size=200 conf.txt"},
                                           {"prompt": "Is bug.txt planted?", "check": "grep -q planted bug.txt"}]}) + "\n")
        self.fake = os.path.join(self.tmp, "fake_claude.py")
        with open(self.fake, "w") as fh:
            fh.write(FAKE_CLAUDE)
        self.log = os.path.join(self.tmp, "calls.log")
        self.tmpdir = os.path.join(self.tmp, "t")
        os.makedirs(self.tmpdir)

    def run_bench(self, *extra, **env_extra):
        env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
        env.update(AGENT_SPEC_FAKE_CLAUDE=self.fake, FAKE_LOG=self.log, HOME=self.home, TMPDIR=self.tmpdir, **env_extra)
        return subprocess.run([sys.executable, SCRIPT, "--agent", "claude", "--project", self.project, "--tasks", self.tasks,
                               *extra], capture_output=True, text=True, env=env, timeout=120)

    def test_runs_each_chat_in_a_fresh_copy_and_reports_paired_stats(self):
        proc = self.run_bench("--repeat", "2")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        with open(os.path.join(self.project, ".agent-spec", "eval", "cursor-bench-results.jsonl")) as fh:
            rows = [json.loads(x) for x in fh]
        self.assertEqual(len(rows), 16)  # (1 + 3 turns) x 2 arms x 2 repeats
        with open(self.log) as fh:
            calls = [json.loads(x) for x in fh]
        first = calls[0]["argv"]
        for flag in ("--setting-sources", "--model", "--permission-mode"):
            self.assertIn(flag, first)
        self.assertEqual(first[first.index("--model") + 1], "claude-haiku-5-5")
        self.assertEqual(first[first.index("--setting-sources") + 1], "project")
        self.assertEqual(calls[0]["argv"][-1], "Reply with the single word: ok")  # the preflight turn
        cwds = {c["cwd"] for c in calls[1:]}
        self.assertEqual(len(cwds), 8)  # one copy per chat; never the project itself
        self.assertNotIn(self.project, cwds)
        edits = [r for r in rows if r["task"] == "e"]
        self.assertTrue(all(r["correct"] for r in edits), [(r["turn"], r["check"]) for r in edits])
        self.assertEqual(open(os.path.join(self.project, "conf.txt")).read(), "size=152\n")
        skill = [r for r in rows if r["arm"] == "skill"]
        self.assertTrue(all(r["skill_read"] for r in skill if r["turn"] == 1))
        self.assertFalse(any(r["skill_read"] for r in rows if r["arm"] == "plain"))
        self.assertEqual(rows[0]["usage"], {"inputTokens": 10, "outputTokens": 5, "cacheReadTokens": 1000,
                                            "cacheWriteTokens": 200})
        self.assertIn("| Cost (USD, Claude Code's own) | 0.1600 | 0.1200 | -25% |", proc.stdout)
        self.assertIn("| Cost (USD) | 4 | 4 | 0 | -25.0% |", proc.stdout)
        self.assertIn("Correctness, 8 turns scored in both arms", proc.stdout)
        self.assertEqual(os.listdir(self.tmpdir), [])  # every copy deleted
        self.assertEqual(os.listdir(os.path.join(self.home, ".claude", "projects")), [])

    def test_stops_when_the_skill_never_loads(self):
        proc = self.run_bench("--only", "q", FAKE_NO_SKILL="1")
        self.assertEqual(proc.returncode, 3, proc.stdout + proc.stderr)
        self.assertIn("the skill never loaded", proc.stderr)

    def test_expired_login_stops_before_any_chat(self):
        proc = self.run_bench(FAKE_AUTH_FAIL="1")
        self.assertEqual(proc.returncode, 3, proc.stdout + proc.stderr)
        self.assertIn("OAuth access token has expired", proc.stderr)
        self.assertIn("/login", proc.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.project, ".agent-spec", "eval", "cursor-bench-results.jsonl")))
        self.assertEqual(os.listdir(self.tmpdir), [])

    def test_login_expiring_mid_run_stops_with_exit_3(self):
        proc = self.run_bench("--only", "e", FAKE_AUTH_FAIL="6")  # preflight + chat 1 (3 turns) + 1 turn pass
        self.assertEqual(proc.returncode, 3, proc.stdout + proc.stderr)
        self.assertIn("stopped:", proc.stderr)
        with open(os.path.join(self.project, ".agent-spec", "eval", "cursor-bench-results.jsonl")) as fh:
            rows = [json.loads(x) for x in fh]
        self.assertEqual(len(rows), 3)  # the finished chat only; no zero-cost turn kept
        self.assertTrue(all(r["usage"]["outputTokens"] for r in rows))

    def test_compare_harness_runs_bare_against_the_harness(self):
        aspec = os.path.join(self.project, ".agent-spec")
        for d in ("graph", "bin", "platform"):
            os.makedirs(os.path.join(aspec, d))
        with open(os.path.join(aspec, "graph", "knowledge-graph.json"), "w") as fh:
            fh.write("{}")
        with open(os.path.join(aspec, "bin", "agent-spec-digest.py"), "w") as fh:
            fh.write("print('most depended on: conf.txt')\n")
        proc = self.run_bench("--compare", "harness", "--only", "q")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        with open(self.log) as fh:
            calls = [json.loads(x) for x in fh][1:]  # after the preflight
        self.assertEqual(len(calls), 2)
        bare, harness = sorted(calls, key=lambda c: c["claude_md"])
        self.assertEqual((bare["claude_md"], bare["graph"], bare["skill"]), (False, False, False))
        self.assertEqual((harness["claude_md"], harness["graph"], harness["run_state"], harness["skill"]),
                         (True, True, False, False))
        self.assertFalse(any(c["argv"][-1].startswith("/") for c in calls))
        with open(os.path.join(aspec, "eval", "cursor-bench-results.jsonl")) as fh:
            rows = [json.loads(x) for x in fh]
        self.assertEqual(sorted(r["arm"] for r in rows), ["bare", "harness"])
        self.assertEqual({r["arm"]: r["skill_read"] for r in rows}, {"bare": False, "harness": True})
        self.assertIn("bare vs the agent-spec harness", proc.stdout)
        self.assertIn("| Metric | Bare | Harness | Change |", proc.stdout)

    def test_compare_harness_stops_when_the_digest_never_arrives(self):
        aspec = os.path.join(self.project, ".agent-spec")
        os.makedirs(os.path.join(aspec, "graph"))
        with open(os.path.join(aspec, "graph", "knowledge-graph.json"), "w") as fh:
            fh.write("{}")
        proc = self.run_bench("--compare", "harness", "--only", "q")  # no digest script
        self.assertEqual(proc.returncode, 3, proc.stdout + proc.stderr)
        self.assertIn("the digest never reached", proc.stderr)

    def test_refuses_to_nest_in_claude_code(self):
        proc = self.run_bench(CLAUDECODE="1")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("your own terminal", proc.stderr)

    def test_allow_nested_runs_without_passing_claudecode_on(self):
        proc = self.run_bench("--only", "q", "--allow-nested", CLAUDECODE="1")
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_other_agents_skip_edit_tasks(self):
        spec = __import__("importlib.util").util.spec_from_file_location("cb2", SCRIPT)
        mod = __import__("importlib.util").util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertEqual([t["id"] for t in mod.load_tasks(self.tasks, None)], ["q"])
        self.assertEqual([t["id"] for t in mod.load_tasks(self.tasks, None, True)], ["q", "e"])
        self.assertAlmostEqual(mod.sign_p(0, 6), 0.03125)


if __name__ == "__main__":
    unittest.main()
