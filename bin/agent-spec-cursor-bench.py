#!/usr/bin/env python3
"""Head-to-head in real Cursor (H-050): the same multi-turn tasks run through the headless
Cursor agent, once plain and once opened with `/agent-spec-raw-code-full`, with Cursor's own
token counts. `--agent local` runs the same tasks through bin/agent-spec-ollama-agent.py instead
(local Ollama, or Groq with `--model groq:<name>`): not Cursor, but the same chats and turns.
`--agent claude` runs them through headless Claude Code (`claude -p`, default model
claude-haiku-5-5), which bills with the same prompt-cache prices as Cursor's Claude models.

    agent-spec-cursor-bench.py [--agent cursor|local|claude] [--project DIR] [--model M] [--repeat N] [--only ID,ID]
                               [--tasks FILE] [--skill NAME] [--force] [--timeout S]
    agent-spec-cursor-bench.py --agent claude --compare harness [--repeat N]

`--compare harness` measures the harness instead of a skill: a bare arm with the project's files
and nothing else, against a harness arm. Under `--agent claude` the harness arm adds CLAUDE.md
(CURSOR.md), the project's `.agent-spec/` (graph, memory, digest, CONSTITUTION) and a
SessionStart hook that injects the digest once per chat, as Cursor's sessionStart hook does.
Under `--agent cursor` it is the copy registered with `install.sh --project-only --register`
(rules, hooks, bins), with the project's own graph and memory copied over it. Both agents run
every chat in a fresh copy; Cursor gets `--trust --force` in both arms so either can run shell.
`graph calls` counts tool calls that ran `.agent-spec/bin/graphify-cli.py`. Tasks default to
`evals/harness-bench.jsonl`: navigation the graph should answer and decisions only memory holds.

Needs a Cursor plan that can run `cursor-agent -p` (the Free plan's usage limit stops it) and an
agent-spec install with the project registered, so both arms see the same rules and hooks; the
only difference between the arms is the skill. Cursor and the local agent run the question
tasks only, in the project itself; tasks marked `"edits": true` change code and run only under
`--agent claude`.

Claude Code runs every chat in a fresh copy of the project's files (git's view: tracked and
untracked, not ignored), with the skill in
`.claude/skills/` and the harness above (CLAUDE.md, `.agent-spec/`, the digest hook) in both arms, and with
`--setting-sources project`, so the user's own output style, hooks and memory reach neither arm.
A task may `setup` the copy (plant a bug) before turn 1; a turn with `check` is correct when
that shell command exits 0 in the copy afterwards. Correctness combines `check`, `expect` (all
strings) and `expect_any` (one of them). The copy and its Claude Code session files are deleted
after the chat unless `--keep`. The report adds Claude Code's cost per chat and a paired test:
how many chats the skill made cheaper, the total change with a bootstrap 95% CI, and an exact
sign test.

Tasks come from `evals/cursor-bench.jsonl` in this package (tracked, unlike `.agent-spec/`), one `{"id", "turns": [{"prompt",
"expect"}]}` per line. Each task is one Cursor chat: turn 1 starts it and later turns resume it
with `--resume <session_id>`, so the re-send of earlier turns is in the numbers. The skill arm
puts `/<skill>` before turn 1 only, as a user would; the skill says it persists.

Token counts are the `usage` block of each turn's `result` event (inputTokens, outputTokens,
cacheReadTokens, cacheWriteTokens), summed per task. A turn is correct when its answer contains
every `expect` string (case-insensitive). Arm order alternates per repeat, so neither arm always
gets the other's warm prompt cache.

Output, to send back:
    .agent-spec/eval/cursor-bench-results.jsonl   one row per turn
    .agent-spec/eval/cursor-bench-<run_id>.md     the summary table
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import platform
import random
import re
import shutil
import subprocess
import tempfile
import sys
import time
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from aspec_platform import agent_exec, common  # noqa: E402

LOCAL_AGENT = os.path.join(HERE, "agent-spec-ollama-agent.py")
TASKS = os.path.join(os.path.dirname(HERE), "evals", "cursor-bench.jsonl")
LOCAL_USAGE = {"input_tokens": "inputTokens", "output_tokens": "outputTokens"}
USAGE_KEYS = ("inputTokens", "outputTokens", "cacheReadTokens", "cacheWriteTokens")
LIMIT_MARKERS = ("usage limit", "ActionRequiredError", "not logged in", "Authentication required",
                 "Credit balance is too low", "Please run /login", "Invalid API key", "Failed to authenticate",
                 "authentication_error", "OAuth access token has expired")
CLAUDE_MODEL = "claude-haiku-5-5"
CLAUDE_USAGE = {"input_tokens": "inputTokens", "output_tokens": "outputTokens",
                "cache_read_input_tokens": "cacheReadTokens", "cache_creation_input_tokens": "cacheWriteTokens"}
# What a coding chat needs, nothing else: no web, no MCP. dontAsk denies anything not listed.
CLAUDE_TOOLS = ("Read,Grep,Glob,Edit,Write,MultiEdit,Skill,Bash(python3:*),Bash(grep:*),Bash(rg:*),Bash(ls:*),"
                "Bash(cat:*),Bash(head:*),Bash(tail:*),Bash(sed -n:*),Bash(git diff:*),Bash(git status:*),Bash(git grep:*),"
                "Bash(git log:*),Bash(wc:*),Bash(find:*),Bash(cd:*),Bash(bash -n:*),Bash(test:*),"
                "Bash(./.agent-spec/bin/graphify-cli.py:*),Bash(.agent-spec/bin/graphify-cli.py:*),"
                "Bash(./.agent-spec/bin/agent-spec-digest.py:*),Bash(./.agent-spec/bin/agent-spec-memory.py:*)")
WS_PREFIX = "aspec-claude-bench-"
HARNESS_TASKS = os.path.join(os.path.dirname(HERE), "evals", "harness-bench.jsonl")
# (control, treatment) arm names per comparison; rows carry these names.
ARMS = {"skill": ("plain", "skill"), "harness": ("bare", "harness")}
TREATED = {"skill", "harness"}
# Run state, history and the dashboard's own data: not part of what a chat is given.
HARNESS_SKIP = {"platform", "eval", "metrics", "benchmark", "platform.db", "__pycache__", ".build.lock"}
# A line of every digest; found in the saved chat, the SessionStart hook delivered it.
DIGEST_MARKER = "most depended on:"
GRAPH_CLI = ".agent-spec/bin/graphify-cli.py"
INSTALL_SH = os.path.join(os.path.dirname(HERE), "install.sh")
CLAUDE_PROJECTS = os.path.join(os.path.expanduser("~"), ".claude", "projects")


class Abort(Exception):
    """The Cursor agent cannot run at all (plan limit, login): stop instead of recording zeros."""


class SkillMissing(Abort):
    """The treated arm ran without its treatment (the skill, or the harness digest): the run is invalid."""


def eval_dir(project: str) -> str:
    return os.path.join(common.agent_spec_dir(project), "eval")


def load_tasks(path: str, only: str | None, edits: bool = False) -> list:
    ids = {i.strip() for i in (only or "").split(",") if i.strip()}
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            task = json.loads(line)
            if task.get("id") and isinstance(task.get("turns"), list) and (not ids or task["id"] in ids) \
                    and (edits or not task.get("edits")):
                out.append(task)
    return out


def find_cli(agent: str) -> str | None:
    if agent == "local":
        return LOCAL_AGENT if os.path.isfile(LOCAL_AGENT) else None
    if agent == "claude":
        fake = os.environ.get("AGENT_SPEC_FAKE_CLAUDE")
        return fake if fake and os.path.isfile(fake) else shutil.which("claude")
    fake = os.environ.get("AGENT_SPEC_FAKE_CURSOR_AGENT")
    if fake and os.path.isfile(fake):
        return fake
    return agent_exec._cursor_cli()


def cli_version(cli: str) -> str:
    try:
        return subprocess.check_output(agent_exec._cli_argv(cli, ["--version"]), text=True,
                                       stderr=subprocess.STDOUT, timeout=10).strip()[:60]
    except (subprocess.SubprocessError, OSError):
        return "unknown"


def claude_argv(model: str | None, session: str | None) -> list:
    argv = ["-p", "--output-format", "stream-json", "--verbose", "--model", model or CLAUDE_MODEL,
            "--setting-sources", "project", "--permission-mode", "dontAsk", "--allowedTools=" + CLAUDE_TOOLS]
    return argv + (["--resume", session] if session else [])


def transcript(session: str | None) -> str | None:
    """Claude Code's saved chat for `session`: the expanded /skill message is in it, not in stdout."""
    if not session or not re.fullmatch(r"[\w-]+", session):
        return None
    hits = glob.glob(os.path.join(CLAUDE_PROJECTS, "*", session + ".jsonl"))
    return hits[0] if hits else None


def run_turn(cli: str, project: str, prompt: str, model: str | None, session: str | None,
             force: bool, skill: str | None, timeout: int, agent: str = "cursor", marker: str | None = None,
             trust: bool = False) -> dict:
    if agent == "claude":
        return run_claude_turn(cli, project, prompt, model, session, timeout, marker)
    argv = ["-p", "--output-format", "stream-json"] + (["--trust"] if trust else [])
    if model:
        argv += ["--model", model]
    if session:
        argv += ["--resume", session]
    if force:
        argv.append("--force")
    t0 = time.monotonic()
    try:
        proc = subprocess.run(agent_exec._cli_argv(cli, argv + [prompt]), cwd=project, capture_output=True,
                              text=True, timeout=timeout)
        stdout, stderr, code = proc.stdout, proc.stderr, proc.returncode
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr, code = "timeout after %ds" % timeout, -1
    row = {"session_id": session, "model": model, "answer": "", "usage": None, "tools": 0, "graph_calls": 0,
           "skill_read": False, "exit": code, "seconds": round(time.monotonic() - t0, 1)}
    for line in stdout.splitlines():
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if not isinstance(obj, dict):
            continue
        typ = obj.get("type")
        if isinstance(obj.get("session_id"), str):
            row["session_id"] = obj["session_id"]
        if typ == "system" and isinstance(obj.get("model"), str):
            row["model"] = obj["model"]
        elif typ == "tool_call" and obj.get("subtype") == "started":
            row["tools"] += 1
            row["graph_calls"] += GRAPH_CLI in json.dumps(obj)
            if skill and skill in json.dumps(obj.get("tool_call") or obj) and "SKILL.md" in json.dumps(obj):
                row["skill_read"] = True
        elif typ == "result":
            row["answer"] = str(obj.get("result") or "")
            if isinstance(obj.get("usage"), dict):
                u = dict(obj["usage"])
                for src, dst in LOCAL_USAGE.items():  # the local agent's names, as Cursor's
                    u.setdefault(dst, u.get(src))
                row["usage"] = {k: u.get(k) for k in USAGE_KEYS if isinstance(u.get(k), int)}
                cached = sum(s.get("cached_tokens") or 0 for s in obj.get("step_usage") or [] if isinstance(s, dict))
                if cached and "cacheReadTokens" not in row["usage"]:
                    # OpenAI-style prompt_tokens already include the cached part: split it out.
                    row["usage"]["cacheReadTokens"] = cached
                    row["usage"]["inputTokens"] = max(0, row["usage"].get("inputTokens", 0) - cached)
    blob = (row["answer"] + "\n" + stderr)
    cannot_run = code == 3 and row["answer"].startswith("error:")  # the local agent's "cannot run" exit
    if (cannot_run or any(m.lower() in blob.lower() for m in LIMIT_MARKERS)) and row["usage"] is None:
        raise Abort((stderr or row["answer"]).strip()[-400:])
    if code != 0:
        row["stderr"] = stderr.strip()[-400:]
    return row


def run_claude_turn(cli: str, cwd: str, prompt: str, model: str | None, session: str | None, timeout: int,
                    marker: str | None) -> dict:
    """One `claude -p` turn. `marker` is a line of the skill body: seen in the saved chat, the
    skill was loaded (typed in the skill arm, or picked by the model in the plain arm)."""
    t0 = time.monotonic()
    try:
        # CLAUDECODE is dropped only under --allow-nested (main refuses otherwise).
        env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
        proc = subprocess.run(agent_exec._cli_argv(cli, claude_argv(model, session) + [prompt]), cwd=cwd,
                              capture_output=True, text=True, timeout=timeout, env=env)
        stdout, stderr, code = proc.stdout, proc.stderr, proc.returncode
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr, code = "timeout after %ds" % timeout, -1
    row = {"session_id": session, "model": model or CLAUDE_MODEL, "answer": "", "usage": None, "cost_usd": None,
           "tools": 0, "graph_calls": 0, "skill_read": False, "exit": code,
           "seconds": round(time.monotonic() - t0, 1)}
    error = False
    for line in stdout.splitlines():
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if not isinstance(obj, dict):
            continue
        if isinstance(obj.get("session_id"), str):
            row["session_id"] = obj["session_id"]
        typ = obj.get("type")
        if typ == "system" and obj.get("subtype") == "init" and isinstance(obj.get("model"), str):
            row["model"] = obj["model"]
        elif typ == "assistant":
            for block in (obj.get("message") or {}).get("content") or []:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    row["tools"] += 1
                    row["graph_calls"] += GRAPH_CLI in json.dumps(block)
        elif typ == "result":
            row["answer"] = str(obj.get("result") or "")
            error = bool(obj.get("is_error"))
            u = obj.get("usage")
            if isinstance(u, dict):
                row["usage"] = {dst: u[src] for src, dst in CLAUDE_USAGE.items() if isinstance(u.get(src), int)}
            if isinstance(obj.get("total_cost_usd"), (int, float)):
                row["cost_usd"] = round(float(obj["total_cost_usd"]), 6)
    path = transcript(row["session_id"])
    # The slash command expands into the saved chat before the API call, so the marker alone
    # proves nothing: count it only for a turn the model answered.
    if marker and path and (row["usage"] or {}).get("outputTokens"):
        try:
            with open(path, encoding="utf-8") as fh:
                row["skill_read"] = marker in fh.read()
        except OSError:
            pass
    blob = row["answer"] + "\n" + stderr
    if any(m.lower() in blob.lower() for m in LIMIT_MARKERS + ("cannot be launched inside another",)) \
            and not (row["usage"] or {}).get("outputTokens"):
        raise Abort((stderr or row["answer"]).strip()[-400:])
    if code != 0 or error:
        row["stderr"] = stderr.strip()[-400:]
    return row


def preflight_claude(cli: str, model: str | None, timeout: int) -> str | None:
    """One tiny real turn before any measurement. Returns why Claude Code cannot run, or None.
    Catches an expired login up front instead of after a run full of zero-cost turns."""
    ws = tempfile.mkdtemp(prefix=WS_PREFIX + "preflight-")
    row = {}
    try:
        row = run_claude_turn(cli, ws, "Reply with the single word: ok", model, None, timeout, None)
    except Abort as exc:
        return str(exc)
    finally:
        drop_workspace(ws, {row.get("session_id")} - {None})
    if not (row.get("usage") or {}).get("outputTokens"):
        return (row.get("stderr") or row.get("answer") or "no output tokens (exit %s)" % row.get("exit"))[-400:]
    return None


def skill_marker(skill: str) -> str | None:
    """The first body line of the installed skill, used to spot it in a saved chat."""
    try:
        with open(os.path.join(os.path.expanduser("~"), ".cursor", "skills", skill, "SKILL.md"), encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return None
    body = text.split("---", 2)[-1]
    for ln in body.splitlines():
        # The saved chat is JSON: quotes and backslashes are escaped, so match a plain-text run.
        run = re.match(r"[A-Za-z0-9 ,.()-]+", ln.strip())
        if run and len(run.group(0).strip()) >= 20 and not ln.startswith("#"):
            return run.group(0).strip()
    return None


def build_template(project: str, skill: str | None, harness: bool = True) -> str:
    """The project's files as git sees them (tracked and untracked, not ignored), in a git repo: the start of a
    Claude Code chat. `harness` adds CLAUDE.md, `.agent-spec/` and the digest hook; `skill` installs that skill."""
    tpl = tempfile.mkdtemp(prefix=WS_PREFIX + "tpl-")
    files = subprocess.check_output(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                                    cwd=project).decode().split("\0")
    for rel in filter(None, files):
        src = os.path.join(project, rel)
        if os.path.isfile(src) and not rel.startswith((".claude/", ".agent-spec/")):
            os.makedirs(os.path.dirname(os.path.join(tpl, rel)), exist_ok=True)
            shutil.copy2(src, os.path.join(tpl, rel))
    if skill:
        skill_dir = os.path.join(os.path.expanduser("~"), ".cursor", "skills", skill)
        shutil.copytree(skill_dir, os.path.join(tpl, ".claude", "skills", skill))
    if harness:
        add_harness(project, tpl)
    git(tpl, "init", "-q")
    git(tpl, "add", "-A")
    git(tpl, "commit", "-qm", "bench start", "--allow-empty")
    return tpl


def add_harness(project: str, tpl: str) -> None:
    """What a registered project gives Claude Code: the always-on rule as CLAUDE.md, the project's
    .agent-spec/ (graph, memory, bins) and the digest once per chat. A resumed turn is the same chat,
    so the hook matches `startup` only, or the digest would be re-sent on every bench turn."""
    rule = os.path.join(project, "CURSOR.md")
    if os.path.isfile(rule):
        shutil.copy2(rule, os.path.join(tpl, "CLAUDE.md"))
    src = common.agent_spec_dir(project)
    if os.path.isdir(src):
        shutil.copytree(src, os.path.join(tpl, ".agent-spec"), symlinks=True,
                        ignore=lambda d, names: [n for n in names if n in HARNESS_SKIP or n.endswith((".db-wal", ".db-shm"))])
    os.makedirs(os.path.join(tpl, ".claude"), exist_ok=True)
    hook = {"hooks": {"SessionStart": [{"matcher": "startup", "hooks": [
        {"type": "command", "command": "python3 .agent-spec/bin/agent-spec-digest.py", "timeout": 20}]}]}}
    with open(os.path.join(tpl, ".claude", "settings.json"), "w", encoding="utf-8") as fh:
        json.dump(hook, fh, indent=1)


def register_harness(project: str, tpl: str) -> None:
    """A Cursor harness copy the way a user gets one: install.sh registers it (rules, hooks, bins),
    then the project's own graph and memory replace the empty ones, and onboarding is marked done
    when the project itself is onboarded, so turn 1 is the task and not /agent-spec-onboard."""
    proc = subprocess.run(["bash", INSTALL_SH, "--project-only", "--register", tpl], capture_output=True, text=True,
                          timeout=600)
    if proc.returncode != 0:
        raise RuntimeError("install.sh --register failed: %s" % (proc.stderr or proc.stdout).strip()[-400:])
    src = common.agent_spec_dir(project)
    shutil.copytree(src, os.path.join(tpl, ".agent-spec"), symlinks=True, dirs_exist_ok=True,
                    ignore=lambda d, names: [n for n in names if n in HARNESS_SKIP or n.endswith((".db-wal", ".db-shm"))])
    marker = os.path.join(tpl, ".agent-spec", ".onboarding-needed")
    if not os.path.exists(os.path.join(src, ".onboarding-needed")) and os.path.exists(marker):
        os.remove(marker)


def git(cwd: str, *argv) -> None:
    subprocess.run(["git", "-c", "user.name=bench", "-c", "user.email=bench@localhost", *argv], cwd=cwd,
                   check=True, capture_output=True)


def make_workspace(template: str, task: dict) -> str:
    ws = tempfile.mkdtemp(prefix=WS_PREFIX)
    os.rmdir(ws)
    shutil.copytree(template, ws, symlinks=True)
    for step in task.get("setup") or []:
        path = os.path.join(ws, step["file"])
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        old, new = step["replace"]
        if old not in text:
            raise ValueError("setup of %s: %r not found in %s" % (task["id"], old, step["file"]))
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text.replace(old, new, 1))
    if task.get("setup"):
        git(ws, "commit", "-qam", "bench setup")
    return ws


def drop_workspace(ws: str, sessions: set) -> None:
    """The chat's copy and its Claude Code session folder; only folders this bench created."""
    for sid in sessions:
        path = transcript(sid)
        folder = os.path.dirname(path) if path else None
        if folder and WS_PREFIX.replace("_", "-") in os.path.basename(folder).replace("_", "-"):
            shutil.rmtree(folder, ignore_errors=True)
    if os.path.basename(ws).startswith(WS_PREFIX):
        shutil.rmtree(ws, ignore_errors=True)


def run_check(cmd: str, cwd: str) -> bool:
    try:
        # No bytecode: a same-size edit in the same second would otherwise be judged on a stale .pyc.
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        return subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, timeout=300, env=env).returncode == 0
    except subprocess.TimeoutExpired:
        return False


def is_correct(answer: str, expect, expect_any=None, check: bool | None = None) -> bool | None:
    parts = []
    low = answer.lower()
    if expect:
        parts.append(all(str(e).lower() in low for e in expect))
    if expect_any:
        parts.append(any(str(e).lower() in low for e in expect_any))
    if check is not None:
        parts.append(check)
    return all(parts) if parts else None


def run_task(cli: str, project: str, task: dict, arm: str, args, base: dict) -> list:
    claude = args.agent == "claude"
    copies = bool(args.templates)
    cwd = make_workspace(args.templates[arm], task) if copies else project
    rows, session, sessions = [], None, set()
    try:
        for n, turn in enumerate(task["turns"], 1):
            prompt = turn["prompt"]
            if arm == "skill" and n == 1:
                prompt = "/%s %s" % (args.skill, prompt)
            r = run_turn(cli, cwd, prompt, args.model, session, args.force,
                         args.skill if arm == "skill" else None, args.timeout, args.agent, args.marker,
                         trust=copies)
            session = r["session_id"] or session
            sessions.add(session)
            check = run_check(turn["check"], cwd) if turn.get("check") else None
            r.update(base, task=task["id"], arm=arm, turn=n, prompt=turn["prompt"], expect=turn.get("expect") or [],
                     check=check, correct=is_correct(r["answer"], turn.get("expect"), turn.get("expect_any"), check),
                     skill=args.skill if arm == "skill" else None, ts=common.utc_now())
            if not one_turn(r, task, arm, n, rows):
                break
        if claude and arm == "harness" and rows and not any(x["skill_read"] for x in rows):
            raise SkillMissing("the digest never reached the harness arm of %s: the SessionStart hook in "
                               ".claude/settings.json did not run with --setting-sources project." % task["id"])
        if claude and arm == "skill" and rows and not any(x["skill_read"] for x in rows):
            raise SkillMissing("the skill never loaded in the skill arm of %s: /%s did not expand. Check that Claude Code "
                        "finds .claude/skills/%s with --setting-sources project." % (task["id"], args.skill, args.skill))
    finally:
        if copies and not args.keep:
            drop_workspace(cwd, {s for s in sessions if s} if claude else set())
    return rows


def one_turn(r: dict, task: dict, arm: str, n: int, rows: list) -> bool:
    """Record and print one turn; False when the chat is dead."""
    r["answer"] = r["answer"][:2000]
    rows.append(r)
    u = r["usage"] or {}
    print("  %-12s %-5s turn %d  correct=%-5s in=%-7s cache_read=%-7s out=%-6s tools=%-2d %5.1fs%s" % (
        task["id"], arm, n, r["correct"], u.get("inputTokens", "-"), u.get("cacheReadTokens", "-"),
        u.get("outputTokens", "-"), r["tools"], r["seconds"],
        "" if r.get("cost_usd") is None else "  $%.4f" % r["cost_usd"]), flush=True)
    if r["exit"] != 0 and not r["answer"]:
        print("    exit %d: %s" % (r["exit"], r.get("stderr", "")[:200]), flush=True)
        return False  # a dead chat cannot be resumed; the remaining turns would measure nothing
    return True


def totals(rows: list) -> dict:
    t = {k: 0 for k in USAGE_KEYS}
    t.update(turns=len(rows), scored=0, correct=0, tools=0, seconds=0.0, no_usage=0, skill_read=0, cost_usd=0.0,
             costed=0, graph_calls=0)
    for r in rows:
        u = r.get("usage")
        if u:
            for k in USAGE_KEYS:
                t[k] += u.get(k) or 0
        else:
            t["no_usage"] += 1
        if r.get("correct") is not None:
            t["scored"] += 1
            t["correct"] += bool(r["correct"])
        t["tools"] += r.get("tools") or 0
        t["graph_calls"] += r.get("graph_calls") or 0
        t["seconds"] += r.get("seconds") or 0
        t["skill_read"] += bool(r.get("skill_read"))
        if isinstance(r.get("cost_usd"), (int, float)):
            t["cost_usd"] += r["cost_usd"]
            t["costed"] += 1
    t["all_input"] = t["inputTokens"] + t["cacheReadTokens"] + t["cacheWriteTokens"]
    t["seconds"] = round(t["seconds"], 1)
    return t


def delta(a, b) -> str:
    if not a:
        return "—"
    return "%+d%%" % round(100.0 * (b - a) / a)


def chat_sums(rows: list, key: str) -> list:
    """[(plain, skill)] per chat (task, repeat) for one metric: a usage key, all_input or cost_usd."""
    sums = {}
    for r in rows:
        u = r.get("usage") or {}
        if key == "cost_usd":
            v = r.get("cost_usd") or 0.0
        elif key == "all_input":
            v = sum(u.get(k) or 0 for k in ("inputTokens", "cacheReadTokens", "cacheWriteTokens"))
        else:
            v = u.get(key) or 0
        pair = sums.setdefault((r["task"], r.get("repeat")), [0, 0])
        pair[r["arm"] in TREATED] += v
    return [tuple(v) for _, v in sorted(sums.items())]


def sign_p(wins: int, n: int) -> float:
    """Exact two-sided sign test: chance of a split at least this uneven if neither arm is cheaper."""
    if not n:
        return 1.0
    k = min(wins, n - wins)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2.0 ** n
    return min(1.0, 2 * tail)


def boot_ci(pairs: list, rounds: int = 10000) -> tuple:
    """95% bootstrap CI (chats resampled) of sum(skill) / sum(plain) - 1, as percent."""
    rnd = random.Random(7)
    vals = []
    for _ in range(rounds):
        pick = [pairs[rnd.randrange(len(pairs))] for _ in pairs]
        p = sum(a for a, _ in pick)
        if p:
            vals.append(100.0 * (sum(b for _, b in pick) / p - 1))
    vals.sort()
    if not vals:
        return (None, None)
    return (vals[int(0.025 * len(vals))], vals[min(len(vals) - 1, int(0.975 * len(vals)))])


def paired_stats(rows: list, key: str, label: str) -> str | None:
    pairs = [(a, b) for a, b in chat_sums(rows, key) if a or b]
    if len(pairs) < 2:
        return None
    cheaper = sum(1 for a, b in pairs if b < a)
    dearer = sum(1 for a, b in pairs if b > a)
    p, w = sum(a for a, _ in pairs), sum(b for _, b in pairs)
    lo, hi = boot_ci(pairs)
    change = "%+.1f%%" % (100.0 * (w / p - 1)) if p else "—"
    ci = "%+.1f%% to %+.1f%%" % (lo, hi) if lo is not None else "—"
    return "| %s | %d | %d | %d | %s | %s | %.3g |" % (label, len(pairs), cheaper, dearer, change, ci,
                                                       sign_p(cheaper, cheaper + dearer))


def correctness_stats(rows: list, what: str = "skill") -> str | None:
    """Turns scored in both arms: how often only one arm got it right (exact McNemar)."""
    by = {}
    for r in rows:
        if r.get("correct") is not None:
            by.setdefault((r["task"], r.get("repeat"), r["turn"]), {})[r["arm"] in TREATED] = bool(r["correct"])
    both = [v for v in by.values() if len(v) == 2]
    if not both:
        return None
    only_plain = sum(1 for v in both if v[False] and not v[True])
    only_skill = sum(1 for v in both if v[True] and not v[False])
    return ("Correctness, %d turns scored in both arms: right only without the %s %d, right only with it %d "
            "(exact McNemar p = %.3g)." % (len(both), what, only_plain, only_skill,
                                          sign_p(only_skill, only_plain + only_skill)))


def paired(rows: list) -> tuple:
    """Rows of chats (task, repeat) that ran in both arms, and the count left out. A run stopped by
    a usage limit can finish a chat in one arm only; counting it would skew that arm's totals."""
    arms = {}
    for r in rows:
        arms.setdefault((r["task"], r.get("repeat")), set()).add(r["arm"] in TREATED)
    keep = [r for r in rows if arms[(r["task"], r.get("repeat"))] == {False, True}]
    return keep, sum(1 for a in arms.values() if len(a) < 2)


AGENT_TITLE = {"cursor": "Cursor", "local": "Local agent", "claude": "Claude Code"}
AGENT_LABEL = {"cursor": "Cursor agent", "local": "Not Cursor: bin/agent-spec-ollama-agent.py",
               "claude": "Not Cursor: Claude Code"}


def report(rows: list, meta: dict, skill: str) -> str:
    rows, unpaired = paired(rows)
    harness = meta.get("compare") == "harness"
    plain = totals([r for r in rows if r["arm"] not in TREATED])
    withs = totals([r for r in rows if r["arm"] in TREATED])
    a, b = ("Bare", "Harness") if harness else ("Plain", "/" + skill)
    what = "harness" if harness else "skill"
    lines = [
        ("# %s head-to-head: bare vs the agent-spec harness" % AGENT_TITLE[meta["agent"]]) if harness else
        ("# %s head-to-head: plain vs /%s" % (AGENT_TITLE[meta["agent"]], skill)), "",
        "Run `%s`, %s. %s `%s`, model `%s`, %d task(s) x %d turn(s), %d repeat(s), %s." % (
            meta["run_id"], meta["ts"], AGENT_LABEL[meta["agent"]], meta["cli_version"], meta["model"] or "default",
            meta["tasks"], meta["turns"], meta["repeat"], meta["os"]), "",
        "| Metric | %s | %s | Change |" % (a, b),
        "|---|---|---|---|",
    ]
    costed = plain["costed"] or withs["costed"]
    if costed:
        lines.append("| Cost (USD, Claude Code's own) | %.4f | %.4f | %s |" % (
            plain["cost_usd"], withs["cost_usd"], delta(plain["cost_usd"], withs["cost_usd"])))
    for label, key in (("Correct", None), ("Input tokens (uncached)", "inputTokens"),
                       ("Cache-read tokens", "cacheReadTokens"), ("Cache-write tokens", "cacheWriteTokens"),
                       ("All input (uncached + cache)", "all_input"), ("Output tokens", "outputTokens"),
                       ("Tool calls", "tools"), ("Graph calls (graphify-cli)", "graph_calls"),
                       ("Wall time (s)", "seconds")):
        if key is None:
            lines.append("| Correct | %d/%d | %d/%d | |" % (plain["correct"], plain["scored"], withs["correct"], withs["scored"]))
        else:
            lines.append("| %s | %s | %s | %s |" % (label, format(plain[key], ","), format(withs[key], ","),
                                                   delta(plain[key], withs[key])))
    metric = "cost_usd" if costed else "all_input"
    fmt = (lambda v: "$%.4f" % v) if costed else (lambda v: format(v, ","))  # noqa: E731
    lines += ["", "Per task (%s, correct turns):" % ("cost" if costed else "all input tokens"), "",
              "| Task | %s | %s | Change |" % (a, b), "|---|---|---|---|"]
    for tid in dict.fromkeys(r["task"] for r in rows):
        p = totals([r for r in rows if r["task"] == tid and r["arm"] not in TREATED])
        s = totals([r for r in rows if r["task"] == tid and r["arm"] in TREATED])
        lines.append("| %s | %s (%d/%d) | %s (%d/%d) | %s |" % (
            tid, fmt(p[metric]), p["correct"], p["scored"], fmt(s[metric]),
            s["correct"], s["scored"], delta(p[metric], s[metric])))
    stats = [x for x in (paired_stats(rows, k, lbl) for k, lbl in (
        ("cost_usd", "Cost (USD)"), ("all_input", "All input tokens"), ("inputTokens", "Uncached input"),
        ("cacheWriteTokens", "Cache-write tokens"), ("outputTokens", "Output tokens"))
        if k != "cost_usd" or costed) if x]
    if stats:
        lines += ["", "Paired by chat (the same task and repeat in both arms):", "",
                  "| Metric | Chats | %s cheaper | %s dearer | Total change | 95%% CI (bootstrap) | Sign test p |"
                  % (what.capitalize(), what.capitalize()),
                  "|---|---|---|---|---|---|---|"] + stats
    acc = correctness_stats(rows, what)
    if acc:
        lines += ["", acc]
    notes = []
    if unpaired:
        notes.append("%d chat(s) ran in one arm only (the run stopped early) and are left out." % unpaired)
    if plain["no_usage"] or withs["no_usage"]:
        notes.append("%d turn(s) returned no usage block and count as 0 tokens." % (plain["no_usage"] + withs["no_usage"]))
    if meta["agent"] == "cursor":
        notes.append("Skill file read seen in %d of %d skill-arm turn(s); Cursor may also attach it without a read."
                     % (withs["skill_read"], withs["turns"]))
    elif harness and meta["agent"] == "cursor":
        notes.append("Bare: the project's files only. Harness: the copy registered with install.sh --project-only "
                     "--register (rules, hooks, bins) and the project's .agent-spec/ (graph, memory) copied over it. "
                     "Whether cursor-agent ran the sessionStart hook is not visible in its output; CURSOR.md tells the "
                     "agent to run the digest itself when hooks are off. Both arms: --trust --force, no skill.")
    elif harness:
        notes.append("Digest found in the saved chat in %d of %d harness-arm turn(s) (it is injected once, at the start "
                     "of each chat), and in %d bare-arm turn(s)." % (withs["skill_read"], withs["turns"], plain["skill_read"]))
        notes.append("Bare: the project's files only, no CLAUDE.md, no .agent-spec/, no hooks. Harness: CURSOR.md as "
                     "CLAUDE.md, the project's .agent-spec/ (graph, memory, bins; not run state), the digest from a "
                     "SessionStart hook. No skill in either arm; no PreToolUse hook. --setting-sources project.")
        feats = meta.get("features") or {}
        if feats:
            notes.append("Tasks by the harness feature they exercise: %s. They were picked where the harness has "
                         "something to offer, so this measures that case, not an average coding chat."
                         % ", ".join("%s (%s)" % (k, ", ".join(v)) for k, v in sorted(feats.items())))
    elif meta["agent"] == "claude":
        notes.append("Skill body found in the saved chat in %d of %d skill-arm turn(s), and in %d plain-arm turn(s) "
                     "(the model loading it unasked)." % (withs["skill_read"], withs["turns"], plain["skill_read"]))
        notes.append("Both arms: a fresh copy of the tracked files, CURSOR.md as CLAUDE.md, the skill installed, "
                     "--setting-sources project. Edit turns are scored by their check command.")
    else:
        notes.append("The local agent puts the installed SKILL.md in the system prompt on turn 1, the way Cursor "
                     "attaches a skill; it is re-sent on every later model call.")
    chats = len({(r["task"], r.get("repeat")) for r in rows})
    if chats < 10:
        notes.append("n = %d chats per arm: a smoke test, not a benchmark." % chats)
    return "\n".join(lines + [""] + ["- " + n for n in notes]) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--project", default=os.getcwd())
    ap.add_argument("--model", help="cursor-agent --model (default: the account's default)")
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--only", help="comma-separated task ids")
    ap.add_argument("--tasks", help="task file (default: evals/cursor-bench.jsonl; with --compare harness, "
                                     "evals/harness-bench.jsonl)")
    ap.add_argument("--compare", choices=("skill", "harness"), default="skill",
                    help="skill: plain vs the skill, harness on in both arms; harness (claude only): bare Claude Code "
                         "vs CLAUDE.md + .agent-spec/ + the digest hook, no skill")
    ap.add_argument("--skill", default="agent-spec-raw-code-full")
    ap.add_argument("--agent", choices=("cursor", "local", "claude"), default="cursor",
                    help="cursor: cursor-agent; local: bin/agent-spec-ollama-agent.py (Ollama, or groq:<model>); "
                         "claude: claude -p (default model %s)" % CLAUDE_MODEL)
    ap.add_argument("--allow-nested", action="store_true",
                    help="claude: run from inside a Claude Code session (Claude Code warns that nested sessions share "
                         "runtime state; keep that session idle while the bench runs)")
    ap.add_argument("--keep", action="store_true", help="claude: keep each chat's workspace copy and session files")
    ap.add_argument("--force", action="store_true", help="pass --force (allow shell commands without approval)")
    ap.add_argument("--timeout", type=int, default=600, help="seconds per turn")
    args = ap.parse_args()
    project = os.path.abspath(args.project)
    harness = args.compare == "harness"
    args.tasks = args.tasks or (HARNESS_TASKS if harness else TASKS)
    if harness and args.agent == "local":
        print("--compare harness runs under --agent claude or cursor", file=sys.stderr)
        return 2
    if harness and args.agent == "cursor":
        args.force = True  # both arms: the graph is a shell command
    if harness and not os.path.isfile(os.path.join(common.agent_spec_dir(project), "graph", "knowledge-graph.json")):
        print("no graph in %s/.agent-spec: register and index the project first" % project, file=sys.stderr)
        return 2

    cli = find_cli(args.agent)
    if not cli and args.agent == "local":
        print("local agent missing: %s" % LOCAL_AGENT, file=sys.stderr)
        return 2
    if args.agent == "claude":
        if not cli:
            print("claude not found. Install Claude Code: https://claude.com/claude-code", file=sys.stderr)
            return 2
        if os.environ.get("CLAUDECODE") and not args.allow_nested:
            print("run this from your own terminal, not from inside a Claude Code session (CLAUDECODE is set), "
                  "or pass --allow-nested from a session that does nothing else while it runs", file=sys.stderr)
            return 2
    if not cli:
        print("cursor-agent not found. Install it: curl https://cursor.com/install -fsS | bash ; then: cursor-agent login",
              file=sys.stderr)
        return 2
    skill_md = os.path.join(os.path.expanduser("~"), ".cursor", "skills", args.skill, "SKILL.md")
    if not os.path.isfile(skill_md) and not os.environ.get("AGENT_SPEC_FAKE_CURSOR_AGENT") and args.agent != "local" \
            and not harness:
        print("skill not installed: %s. Run ./install.sh from the agent-spec clone." % skill_md, file=sys.stderr)
        return 2
    if args.agent != "claude" and not harness \
            and not os.path.isfile(os.path.join(project, ".cursor", "rules", "agent-spec.mdc")):
        print("warning: %s is not registered (no .cursor/rules/agent-spec.mdc); both arms run without the harness. "
              "Register it: ./install.sh --register %s" % (project, project), file=sys.stderr)
    tasks = load_tasks(args.tasks, args.only, args.agent == "claude" or harness) if os.path.isfile(args.tasks) else []
    if not tasks:
        print("no tasks in %s" % args.tasks, file=sys.stderr)
        return 2
    if args.agent == "claude":
        why = preflight_claude(cli, args.model, args.timeout)
        if why:
            print("claude -p cannot run a turn: %s\nIf the login expired, run `claude` in your terminal, type /login, "
                  "then rerun." % why, file=sys.stderr)
            return 3
    os.makedirs(eval_dir(project), exist_ok=True)
    args.templates = {}
    if args.agent == "cursor" and harness:
        args.templates = {"bare": build_template(project, None, harness=False),
                          "harness": build_template(project, None, harness=False)}
        register_harness(project, args.templates["harness"])
    elif args.agent == "claude" and harness:
        args.templates = {"bare": build_template(project, None, harness=False),
                          "harness": build_template(project, None, harness=True)}
    elif args.agent == "claude":
        tpl = build_template(project, args.skill)
        args.templates = {"plain": tpl, "skill": tpl}
    args.marker = (DIGEST_MARKER if harness else skill_marker(args.skill)) if args.agent == "claude" else None

    run_id = time.strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:6]
    model = args.model or (CLAUDE_MODEL if args.agent == "claude" else None)
    meta = {"run_id": run_id, "ts": common.utc_now(), "cli_version": cli_version(cli), "model": model,
            "agent": args.agent, "compare": args.compare,
            "features": {f: [t["id"] for t in tasks if t.get("feature") == f]
                         for f in sorted({t["feature"] for t in tasks if t.get("feature")})},
            "tasks": len(tasks), "turns": sum(len(t["turns"]) for t in tasks), "repeat": args.repeat,
            "os": "%s %s" % (platform.system(), platform.release())}
    base = {"run_id": run_id, "cli_version": meta["cli_version"], "os": meta["os"], "agent": args.agent,
            "compare": args.compare}
    out_path = os.path.join(eval_dir(project), "cursor-bench-results.jsonl")
    print("run %s: %d task(s), %d repeat(s), %s %s" % (run_id, len(tasks), args.repeat, args.agent, meta["cli_version"]),
          flush=True)
    rows = []
    stopped = False
    try:
        for rep in range(1, args.repeat + 1):
            for i, task in enumerate(tasks):
                c, t = ARMS[args.compare]
                order = (c, t) if (rep + i) % 2 else (t, c)
                for arm in order:
                    got = run_task(cli, project, task, arm, args, dict(base, repeat=rep))
                    with open(out_path, "a", encoding="utf-8") as fh:
                        for r in got:
                            fh.write(json.dumps(r) + "\n")
                    rows.extend(got)
    except Abort as exc:
        print("stopped: the %s agent cannot run here: %s" % (args.agent, exc), file=sys.stderr)
        if not rows or isinstance(exc, SkillMissing):
            return 3
        stopped = True
    finally:
        if not args.keep:
            for tpl in set(args.templates.values()):
                shutil.rmtree(tpl, ignore_errors=True)
    text = report(rows, meta, args.skill)
    md_path = os.path.join(eval_dir(project), "cursor-bench-%s.md" % run_id)
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write(text)
    print("\n" + text)
    print("results -> %s\nreport  -> %s" % (out_path, md_path))
    if stopped:
        print("the run stopped early: the report covers only the chats above", file=sys.stderr)
    return 3 if stopped else 0


if __name__ == "__main__":
    sys.exit(main())
