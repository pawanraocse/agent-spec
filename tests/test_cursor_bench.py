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
                             "workflow": os.path.isfile(".cursor/rules/agent-spec-workflow.mdc"),
                             "digest_bytes": os.path.getsize(".agent-spec/bin/agent-spec-digest.py")
                             if os.path.isfile(".agent-spec/bin/agent-spec-digest.py") else 0,
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
if os.path.isfile(".cursor/rules/agent-spec-workflow.mdc") and "--resume" not in argv:
    print(json.dumps({"type": "tool_call", "subtype": "started", "session_id": session,
                      "tool_call": {"readToolCall": {"args": {"path": ".cursor/rules/agent-spec-workflow.mdc"}}}}))
if os.path.isfile(".cursor/rules/agent-spec.mdc"):
    print(json.dumps({"type": "tool_call", "subtype": "started", "session_id": session, "tool_call": {
        "shellToolCall": {"args": {"command": "./.agent-spec/bin/graphify-cli.py callers --symbol f"}}}}))
resumed = "--resume" in argv
answer = "It is savings.py, 152 B, /api/savings in serve.py" + (" and made_up_helper.py" if os.environ.get("FAKE_PHANTOM") else "")
print(json.dumps({"type": "result", "session_id": session, "result": answer,
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

    def _mod(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("cbench", SCRIPT)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_a_turn_that_waits_on_a_background_task_keeps_both_results(self):
        """claude -p ends such a turn twice; usage is per segment, total_cost_usd a running total."""
        mod = self._mod()
        fake = os.path.join(self.tmp, "two-results")
        seg = lambda text, out, cost: json.dumps({"type": "result", "session_id": "s1", "result": text,
                                                   "total_cost_usd": cost, "usage": {"input_tokens": 4,
                                                   "output_tokens": out, "cache_read_input_tokens": 100}})
        with open(fake, "w") as fh:
            fh.write("#!/bin/sh\ncat <<'EOF'\n%s\n%s\nEOF\n" % (
                seg("5 failed: test_savings, test_redact, test_insights", 150, 0.002),
                seg("The notice adds nothing new.", 254, 0.006)))
        os.chmod(fake, 0o755)
        row = mod.run_claude_turn(fake, self.tmp, "run the suite", None, None, 30, None)
        self.assertIn("test_redact", row["answer"])
        self.assertIn("adds nothing new", row["answer"])
        self.assertEqual(row["usage"], {"inputTokens": 8, "outputTokens": 404, "cacheReadTokens": 200})
        self.assertEqual(row["cost_usd"], 0.006)

    def test_phantom_names_flag_files_the_project_does_not_have(self):
        mod = self._mod()
        known = {"serve.py", "savings.py", "readme.md"}
        got = mod.phantom_names("See bin/aspec_platform/serve.py, routes.py, Node.js, README.md and new.py",
                                known, {"new.py"})
        self.assertEqual(got, ["routes.py"])

    def test_files_the_chat_or_harness_made_are_not_invented(self):
        mod = self._mod()
        with tempfile.TemporaryDirectory() as ws:
            os.makedirs(os.path.join(ws, ".agent-spec", "memory", "snapshots"))
            for rel in ("CLAUDE.md", ".agent-spec/memory/snapshots/snapshots-through-20261121-104101.md"):
                open(os.path.join(ws, rel), "w").close()
            known = {"serve.py"} | mod.TRANSIENT_FILES | mod.workspace_names(ws)
            got = mod.phantom_names("Per CLAUDE.md I wrote .agent-spec/HANDOFF.md; older sections went to "
                                    "snapshots-through-20261121-104101.md, see serve.py and ghost.py", known, set())
        self.assertEqual(got, ["ghost.py"])

    def test_report_breaks_out_features_budgets_and_turn_position(self):
        mod = self._mod()

        def row(task, arm, turn, feature, correct, tools=0, budget=None, phantom=(), graph=0):
            return {"task": task, "repeat": 1, "arm": arm, "turn": turn, "correct": correct, "feature": feature,
                    "usage": {"inputTokens": 100}, "tools": tools, "seconds": 1.0, "graph_calls": graph,
                    "tools_ok": None if budget is None else tools <= budget, "phantom": list(phantom)}
        rows = [row("d", "bare", 1, "direct", True, 0, 0), row("d", "harness", 1, "direct", True, 2, 0),
                row("g", "bare", 1, "graph", True, 3), row("g", "harness", 1, "graph", True, 1, graph=1)]
        rows += [row("l", "bare", n, "long-chat", n < 6, phantom=["x.py"] if n >= 6 else ()) for n in range(1, 8)]
        rows += [row("l", "harness", n, "long-chat", True) for n in range(1, 8)]
        text = mod.report(rows, {"agent": "cursor", "compare": "harness", "run_id": "r", "ts": "t", "cli_version": "v",
                                 "model": "m", "tasks": 3, "turns": 9, "repeat": 1, "os": "x"}, "s")
        self.assertIn("| Within tool budget (max_tools) | 1/1 | 0/1 | |", text)
        self.assertIn("| graph | 100 | 100 | +0% | 1.0 | 1.0 | 1/1 | 1/1 | 0/1 | 1/1 | 0 | 0 |", text)
        self.assertIn("| turns 6+ | 0/2, 2 invented | 2/2, 0 invented |", text)
        self.assertIn("| Invented file names | 2 | 0 |", text)

    def _git_project(self):
        for argv in (["init", "-q"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "x",
                                                     "--allow-empty"]):
            subprocess.run(["git"] + argv, cwd=self.project, check=True, capture_output=True)
        os.makedirs(os.path.join(self.project, ".agent-spec", "memory", "facts"))
        os.makedirs(os.path.join(self.project, ".agent-spec", "graph"))
        with open(os.path.join(self.project, ".agent-spec", "graph", "knowledge-graph.json"), "w") as fh:
            fh.write("{}")

    def test_compare_versions_installs_each_arm_from_its_own_ref(self):
        base = "4852bfe"  # v2.0.0: one always-on rule, no workflow rule
        if subprocess.run(["git", "-C", REPO, "cat-file", "-e", base + "^{commit}"], capture_output=True).returncode:
            self.skipTest("history for %s not in this clone" % base)
        self._git_project()
        # A user's own registered workspace: the bench's installs must neither list nor refresh it.
        home = os.path.join(self.tmp, "home")
        mine = os.path.join(self.tmp, "mine")
        os.makedirs(os.path.join(home, ".cursor", "skills"))
        os.makedirs(mine)
        registry = os.path.join(home, ".cursor", "skills", ".agent-spec-projects")
        with open(registry, "w") as fh:
            fh.write(mine + "\n")
        cwd_log = os.path.join(self.tmp, "cwd.log")
        env = dict(os.environ, AGENT_SPEC_FAKE_CURSOR_AGENT=self.fake, FAKE_LOG=self.log, FAKE_CWD_LOG=cwd_log,
                   TMPDIR=self.tmp, FAKE_PHANTOM="1", HOME=home)
        proc = subprocess.run([sys.executable, SCRIPT, "--project", self.project, "--tasks", self.tasks,
                               "--compare", "versions", "--base-ref", base], capture_output=True, text=True,
                              env=env, timeout=300)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        with open(cwd_log) as fh:
            seen = [json.loads(x) for x in fh]
        self.assertTrue(all(x["rules"] and x["hooks"] and x["memory"] for x in seen), seen)
        self.assertEqual(sorted(x["workflow"] for x in seen), [False, False, True, True])
        digests = {x["workflow"]: x["digest_bytes"] for x in seen}
        self.assertNotEqual(digests[False], digests[True], "each arm runs its own version's digest")
        rows = self.rows()
        self.assertEqual(sorted({r["arm"] for r in rows}), ["base", "head"])
        self.assertEqual({r["arm"]: r["workflow_read"] for r in rows if r["turn"] == 1},
                         {"base": False, "head": True})
        self.assertTrue(all("made_up_helper.py" in r["phantom"] for r in rows), rows)
        self.assertIn("harness at 4852bfe", proc.stdout)
        self.assertIn("| Metric | Base 4852bfe | Head | Change |", proc.stdout)
        self.assertIn("| Workflow rule reads (turns) | 0 | 1 |", proc.stdout)
        with open(registry) as fh:
            self.assertEqual(fh.read(), mine + "\n", "the bench must not add its copies to the user's registry")
        self.assertFalse(os.path.exists(os.path.join(mine, ".cursor")), "the bench must not refresh user workspaces")
        self.assertEqual([n for n in os.listdir(self.tmp) if n.startswith("aspec-claude-bench-")], [])

    def test_compare_versions_refuses_an_unknown_ref(self):
        self._git_project()
        env = dict(os.environ, AGENT_SPEC_FAKE_CURSOR_AGENT=self.fake, FAKE_LOG=self.log)
        proc = subprocess.run([sys.executable, SCRIPT, "--project", self.project, "--tasks", self.tasks,
                               "--compare", "versions", "--base-ref", "no-such-ref-xyz"], capture_output=True,
                              text=True, env=env, timeout=60)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("unknown git ref", proc.stderr)

    def test_task_files_parse_and_direct_tasks_carry_a_budget(self):
        mod = self._mod()
        direct = mod.load_tasks(mod.DIRECT_TASKS, None)
        self.assertGreaterEqual(len(direct), 5)
        self.assertTrue(all(t.get("max_tools") is not None and t.get("tier") for t in direct))
        both = mod.load_tasks(mod.DIRECT_TASKS + "," + mod.HARNESS_TASKS, None, edits=True)
        self.assertEqual(len(both), len(direct) + len(mod.load_tasks(mod.HARNESS_TASKS, None, edits=True)))
        longest = max(len(t["turns"]) for t in mod.load_tasks(mod.HARNESS_TASKS, None))
        self.assertGreaterEqual(longest, 8, "a long chat measures accuracy late in the conversation")

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
                         "skill": os.path.isdir(".claude/skills"),
                         "agents": sorted(os.listdir(".claude/agents")) if os.path.isdir(".claude/agents") else [],
                         "workflow": os.path.isfile(".cursor/rules/agent-spec-workflow.mdc"),
                         "answer_keys": [d for d in ("evals", "harness-test") if os.path.exists(d)],
                         "pre_tool": [g["matcher"] + ":" + os.path.basename(h["command"].split()[-1]) for g in
                                      (json.load(open(".claude/settings.json")).get("hooks", {}).get("PreToolUse", [])
                                       if os.path.exists(".claude/settings.json") else []) for h in g["hooks"]
                                      if os.path.isfile(h["command"].split()[-1])]}) + "\n")
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
# Like real Claude Code, total_cost_usd under --resume is the session's running total.
cost_file = os.path.join(folder, session + ".cost")
total = (float(open(cost_file).read()) if os.path.exists(cost_file) else 0.0) + (0.01 if skill else 0.02)
with open(cost_file, "w") as fh:
    fh.write(repr(total))
print(json.dumps({"type": "system", "subtype": "init", "session_id": session, "model": "claude-haiku-5-5"}))
print(json.dumps({"type": "assistant", "session_id": session, "message": {"content": [
    {"type": "tool_use", "name": "Read", "input": {}}] * (1 if skill else 2)}}))
print(json.dumps({"type": "result", "session_id": session, "result": "size is in conf.txt", "is_error": False,
                  "total_cost_usd": total,
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
        os.makedirs(os.path.join(self.project, "evals"))
        os.makedirs(os.path.join(self.project, "harness-test"))
        for name, body in (("conf.txt", "size=152\n"), ("CURSOR.md", "rule\n"), ("CURSOR-WORKFLOW.md", "flow\n"),
                           ("bug.txt", "broken\n"), ("evals/key.jsonl", "size is 152\n"),
                           ("harness-test/README.md", "size is 152\n")):
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
        for flag in ("--setting-sources", "--strict-mcp-config", "--model", "--permission-mode"):
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

    def test_cost_gate_fails_when_the_treated_arm_is_over_budget(self):
        ok = self.run_bench("--only", "q")
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertIn("**Cost gate: PASS** — cost $0.0100 vs base $0.0200 (limit +0.0%), correct 1 vs 1.", ok.stdout)
        # The skill arm is 50% cheaper here; a limit of -60% demands more than that.
        tight = self.run_bench("--only", "q", "--max-cost-change", "-60")
        self.assertEqual(tight.returncode, 4, tight.stderr)
        self.assertIn("**Cost gate: FAIL** — cost $0.0100 is over the limit $0.0080", tight.stdout)
        self.assertIn("Cost gate: FAIL", tight.stderr)

    def test_new_chat_starts_a_fresh_session_in_the_same_copy(self):
        with open(self.tasks, "w") as fh:
            fh.write(json.dumps({"id": "c", "turns": [
                {"prompt": "Change size to 200", "check": "grep -q size=200 conf.txt"},
                {"prompt": "Which file?", "expect": ["conf.txt"]},
                {"prompt": "Is size 200?", "new_chat": True, "check": "grep -q size=200 conf.txt"},
                {"prompt": "Which file again?", "expect": ["conf.txt"]}]}) + "\n")
        proc = self.run_bench()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        with open(self.log) as fh:
            calls = [json.loads(x) for x in fh][1:]  # drop the preflight turn
        for arm_calls in (calls[:4], calls[4:]):
            resumed = ["--resume" in c["argv"] for c in arm_calls]
            self.assertEqual(resumed, [False, True, False, True])
            self.assertEqual(len({c["cwd"] for c in arm_calls}), 1)  # the edit from chat 1 is still there
        with open(os.path.join(self.project, ".agent-spec", "eval", "cursor-bench-results.jsonl")) as fh:
            rows = [json.loads(x) for x in fh]
        self.assertTrue(all(r["correct"] for r in rows))
        plain = sorted((r for r in rows if r["arm"] == "plain"), key=lambda r: r["turn"])
        self.assertEqual([r["cost_usd"] for r in plain], [0.02, 0.02, 0.02, 0.02])  # never a running total
        self.assertEqual([r["cost_cum_usd"] for r in plain], [0.02, 0.04, 0.02, 0.04])
        self.assertNotEqual(plain[1]["session_id"], plain[2]["session_id"])

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
        # CLAUDE.md points at the code-work rule; Claude Code never attaches it, so it must be there to Read.
        self.assertEqual((bare["workflow"], harness["workflow"]), (False, True))
        self.assertEqual((bare["agents"], harness["agents"]), ([], ["agent-spec-search.md", "agent-spec-verify.md"]))
        # The task file and kept results hold the expected answers: neither arm may grep them.
        self.assertEqual((bare["answer_keys"], harness["answer_keys"]), ([], []))
        self.assertEqual((bare["pre_tool"], harness["pre_tool"]), ([], ["Bash:agent-spec-pre-tool-use.py"]))
        self.assertTrue(any(a.startswith("--allowedTools=") and ",Agent," in a for a in calls[0]["argv"]))
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
