#!/usr/bin/env python3
"""agent-spec-doctor — is this workspace's harness installed, current and healthy?

  agent-spec-doctor.py                 full report, exit 1 if any check FAILs
  agent-spec-doctor.py --strict        exit 1 on WARN as well (release gate)
  agent-spec-doctor.py --json          machine-readable
  agent-spec-doctor.py --line          one line for the sessionStart digest (quick checks only)
  agent-spec-doctor.py --project DIR   check DIR instead of the current directory

Every FAIL/WARN prints the command that fixes it. Stdlib only. Fail-open for the
digest: --line never raises and always exits 0.

Statuses: OK, INFO (worth knowing, not a problem), WARN (degraded), FAIL (broken).
"""
import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
MARKER = "algosec-agent-spec auto-index"
MEMORY_INDEX_LIMIT = 8000
GRAPH_STALE_DAYS = 7
SESSION_MARKER = "agent-spec-session-start.py"
PRETOOL_MARKER = "agent-spec-pre-tool-use.py"
SESSION_END_MARKER = "agent-spec-session-end.py"
MCP_SCHEMA_TOKEN_LIMIT = 4000
MCP_LIMIT_ENV = "AGENT_SPEC_MCP_LIMIT"


class Ctx:
    def __init__(self, project, package):
        self.project = project
        self.package = package
        self.spec = os.path.join(project, ".agent-spec")
        home = os.path.expanduser("~")
        win = os.environ.get("WIN_CURSOR_HOME")
        self.cursor_home = win if win and os.path.isdir(os.path.join(win, ".cursor")) \
            else os.path.join(home, ".cursor")
        self.skills_dir = os.path.join(self.cursor_home, "skills")

    def script(self, name):
        for base in (os.path.join(self.spec, "bin"), HERE):
            path = os.path.join(base, name)
            if os.path.isfile(path):
                return path
        return None

    def register_cmd(self):
        installer = os.path.join(self.package, "install.sh") if self.package else "./install.sh"
        return '%s --register "%s"' % (installer, self.project)


def find_package():
    """The algosec-agent-spec clone: this script's parent if it has VERSION, else the marker."""
    parent = os.path.dirname(HERE)
    if os.path.isfile(os.path.join(parent, "VERSION")) and os.path.isdir(os.path.join(parent, "skills")):
        return parent
    marker = os.path.join(os.path.expanduser("~"), ".cursor", "skills", ".algosec-agent-spec-root")
    win = os.environ.get("WIN_CURSOR_HOME")
    if win:
        marker = os.path.join(win, ".cursor", "skills", ".algosec-agent-spec-root")
    try:
        root = open(marker, encoding="utf-8").read().strip()
    except OSError:
        return None
    return root if os.path.isfile(os.path.join(root, "VERSION")) else None


def read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def load_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def run(cmd, cwd, timeout=20):
    try:
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except Exception:
        return None


# --- checks: each returns [(id, status, message, fix)] ---------------------------------

def check_project(ctx):
    if os.path.isdir(ctx.spec):
        return [("project", "OK", "%s has .agent-spec/" % ctx.project, "")]
    return [("project", "FAIL", "no .agent-spec/ in %s" % ctx.project, ctx.register_cmd())]


def check_skills(ctx):
    if not os.path.isdir(ctx.skills_dir):
        return [("skills", "FAIL", "%s missing" % ctx.skills_dir, "./install.sh")]
    installed = {n for n in os.listdir(ctx.skills_dir)
                 if n.startswith("agent-spec") and os.path.isfile(os.path.join(ctx.skills_dir, n, "SKILL.md"))}
    if not installed:
        return [("skills", "FAIL", "no agent-spec-* skills in %s" % ctx.skills_dir, "./install.sh")]
    if ctx.package:
        wanted = {n for n in os.listdir(os.path.join(ctx.package, "skills"))
                  if os.path.isfile(os.path.join(ctx.package, "skills", n, "SKILL.md"))}
        missing = sorted(wanted - installed)
        # --lean installs omit the SDLC design skills on purpose; only flag the rest.
        lean = {"agent-spec-intent", "agent-spec-hld", "agent-spec-lld", "agent-spec-prd",
                "agent-spec-requirements", "agent-spec-tech-spec"}
        if missing and not set(missing) <= lean:
            return [("skills", "WARN", "%d package skill(s) not installed, e.g. %s"
                     % (len(missing), missing[0]), os.path.join(ctx.package, "install.sh"))]
    return [("skills", "OK", "%d skills installed" % len(installed), "")]


def _commands(hooks, event):
    return [h.get("command", "") for h in (hooks.get("hooks", {}).get(event) or [])
            if isinstance(h, dict)]


def check_hooks(ctx):
    path = os.path.join(ctx.project, ".cursor", "hooks.json")
    fix = ctx.register_cmd()
    if not os.path.isfile(path):
        return [("hooks", "FAIL", ".cursor/hooks.json missing — digest and nudges never run", fix)]
    data = load_json(path)
    if not isinstance(data, dict):
        return [("hooks", "FAIL", ".cursor/hooks.json is not valid JSON", fix)]
    out = []
    for event, marker, script in (("sessionStart", SESSION_MARKER, SESSION_MARKER),
                                  ("preToolUse", PRETOOL_MARKER, PRETOOL_MARKER)):
        mine = [c for c in _commands(data, event) if marker in c]
        if len(mine) != 1:
            out.append(("hooks", "FAIL", "%s has %d agent-spec handlers (want 1)" % (event, len(mine)), fix))
        elif not os.path.isfile(os.path.join(ctx.project, ".cursor", "hooks", script)):
            out.append(("hooks", "FAIL", "%s script .cursor/hooks/%s missing" % (event, script), fix))
    if not out:
        # Receipts (T-050/T-051) are optional: a registration that predates them still
        # works, so a missing session-end hook is a WARN with the re-register command.
        ends = [e for e in ("sessionEnd", "stop")
                if sum(1 for c in _commands(data, e) if SESSION_END_MARKER in c) == 1]
        script = os.path.join(ctx.project, ".cursor", "hooks", SESSION_END_MARKER)
        if len(ends) < 2 or not os.path.isfile(script):
            return [("hooks", "WARN", "session-end receipt hook not registered (no per-session receipts)", fix)]
        return [("hooks", "OK", "sessionStart + preToolUse + sessionEnd/stop registered, scripts present", "")]
    return out


def check_digest(ctx):
    digest = ctx.script("agent-spec-digest.py")
    if not digest:
        return [("digest", "FAIL", "agent-spec-digest.py missing", ctx.register_cmd())]
    res = run([sys.executable, digest, "--cursor-hook"], ctx.project, timeout=15)
    try:
        payload = json.loads(res.stdout) if res else None
    except ValueError:
        payload = None
    if not isinstance(payload, dict):
        return [("digest", "FAIL", "digest --cursor-hook did not emit JSON", ctx.register_cmd())]
    size = len(payload.get("additional_context", "").encode("utf-8"))
    out = [("digest", "OK", "digest JSON valid (%d B)" % size, "")]
    # Always-on cost: the rule file and the digest ride in every turn. 5 % of a turn's context
    # is the Phase 1 overhead target, so report the context size at which this stays below it.
    rule = os.path.join(ctx.project, ".cursor", "rules", "agent-spec.mdc")
    rule_bytes = os.path.getsize(rule) if os.path.isfile(rule) else 0
    tokens = (rule_bytes + size) // 4
    out.append(("footprint", "INFO",
                "always-on ~%d tokens/turn (rule %d B + digest %d B); under 5%% of a turn once "
                "context exceeds ~%d tokens" % (tokens, rule_bytes, size, tokens * 20), ""))
    return out


def check_graph(ctx):
    rebuild = "./.agent-spec/bin/agent-spec-index"
    graph = os.path.join(ctx.spec, "graph", "knowledge-graph.json")
    if not os.path.isfile(graph):
        return [("graph", "WARN", "graph not built", rebuild)]
    status = load_json(os.path.join(ctx.spec, "graph", ".status.json")) or {}
    try:
        finished = datetime.fromisoformat(status["finished"])
    except (KeyError, ValueError):
        return [("graph", "WARN", "graph has no build status (built by an older harness)", rebuild)]
    age = (datetime.now() - finished).total_seconds() / 86400.0
    if age > GRAPH_STALE_DAYS:
        return [("graph", "WARN",
                 "graph last built %.0f days ago — sessionStart hook may be off (Cursor Settings > "
                 "Hooks), timing out on a large repo, or this is a cloud session" % age, rebuild)]
    return [("graph", "OK", "graph built %.1f days ago, %s files" % (age, status.get("files", "?")), "")]


def check_memory(ctx):
    index = os.path.join(ctx.spec, "memory", "INDEX.md")
    size = os.path.getsize(index) if os.path.isfile(index) else 0
    if size > MEMORY_INDEX_LIMIT:
        return [("memory", "WARN", "memory INDEX.md is %d B (limit %d)" % (size, MEMORY_INDEX_LIMIT),
                 "./.agent-spec/bin/agent-spec-memory.py prune --older-than 90")]
    return [("memory", "OK", "memory index %d B (limit %d)" % (size, MEMORY_INDEX_LIMIT), "")]


def check_memory_lint(ctx):
    memory = ctx.script("agent-spec-memory.py")
    if not memory or not os.path.isdir(os.path.join(ctx.spec, "memory", "facts")):
        return []
    out = []
    res = run([sys.executable, memory, "index", "--check"], ctx.project)
    if res and res.returncode != 0:
        out.append(("memory", "WARN", "memory INDEX.md is stale",
                    "./.agent-spec/bin/agent-spec-memory.py index"))
    res = run([sys.executable, memory, "lint"], ctx.project)
    if res and res.returncode != 0:
        first = next((l for l in res.stdout.splitlines() if l.split(" ")[0].isupper()), "findings")
        out.append(("memory", "WARN", "memory lint: %s" % first.strip(),
                    "./.agent-spec/bin/agent-spec-memory.py lint"))
    return out


def check_register(ctx):
    registry = os.path.join(ctx.skills_dir, ".algosec-agent-spec-projects")
    here = os.path.realpath(ctx.project)
    if ctx.package and os.path.realpath(ctx.package) == here:
        return [("register", "INFO", "this is the algosec-agent-spec clone (refreshed by a bare ./install.sh)", "")]
    try:
        lines = [l.strip() for l in open(registry, encoding="utf-8") if l.strip()]
    except OSError:
        lines = []
    if any(os.path.realpath(l) == here for l in lines):
        return [("register", "OK", "workspace is registered", "")]
    parent = next((l for l in lines if here.startswith(os.path.realpath(l) + os.sep)), None)
    if parent:
        return [("register", "WARN", "you are inside registered root %s but %s is not itself registered "
                 "(open the registered folder in Cursor)" % (parent, here), ctx.register_cmd())]
    return [("register", "WARN", "workspace not in the registry — upgrades will not refresh it",
             ctx.register_cmd())]


def check_version(ctx):
    mdc = read(os.path.join(ctx.project, ".cursor", "rules", "agent-spec.mdc"))
    m = re.search(r"(?m)^version:\s*(\S+)", mdc)
    if not m:
        return [("version", "WARN", "agent-spec.mdc has no version stamp", ctx.register_cmd())]
    if not ctx.package:
        return [("version", "INFO", "harness %s (package not found; drift check skipped)" % m.group(1), "")]
    pkg = read(os.path.join(ctx.package, "VERSION")).strip()
    if pkg and pkg != m.group(1):
        return [("version", "WARN", "harness %s but package is %s" % (m.group(1), pkg), ctx.register_cmd())]
    return [("version", "OK", "harness matches package %s" % pkg, "")]


def _git_hooks_dir(project):
    res = run(["git", "rev-parse", "--git-path", "hooks"], project, timeout=3)
    if res and res.returncode == 0 and res.stdout.strip():
        raw = res.stdout.strip()
        return raw if os.path.isabs(raw) else os.path.normpath(os.path.join(project, raw))
    if os.path.isdir(os.path.join(project, ".git")):
        return os.path.join(project, ".git", "hooks")
    return None


def check_git_hooks(ctx):
    if not os.path.exists(os.path.join(ctx.project, ".git")):
        return [("git-hooks", "INFO", "not a git repo — auto-index git hooks not applicable", "")]
    hooks = _git_hooks_dir(ctx.project)
    if not hooks:
        return [("git-hooks", "INFO", "git hooks dir not found", "")]
    present = {n: MARKER in read(os.path.join(hooks, n))
               for n in ("post-checkout", "post-merge", "post-rewrite")}
    if all(present.values()):
        return [("git-hooks", "OK", "post-checkout, post-merge, post-rewrite installed", "")]
    if not present["post-rewrite"] and present["post-checkout"] and present["post-merge"]:
        return [("git-hooks", "WARN", "workspace predates post-rewrite hook — graph goes stale after "
                 "rebase/amend", ctx.register_cmd())]
    missing = [n for n, ok in present.items() if not ok]
    return [("git-hooks", "WARN", "git auto-index hooks missing: %s" % ", ".join(missing),
             ctx.register_cmd())]


def check_team(ctx):
    path = os.path.join(ctx.spec, "team.yaml")
    if not os.path.isfile(path):
        return [("team", "INFO", "no team.yaml (optional team defaults)", "")]
    digest = ctx.script("agent-spec-digest.py")
    if not digest:
        return []
    spec = importlib.util.spec_from_file_location("agent_spec_digest_for_doctor", digest)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    valid, errors = mod.parse_team_yaml(read(path))
    if errors:
        return [("team", "WARN", "team.yaml: %s" % "; ".join(errors[:3]),
                 "edit .agent-spec/team.yaml (keys: java_version, node_version, sdlc_track, default_branch)")]
    return [("team", "OK", "team.yaml valid (%d keys)" % len(valid), "")]


def check_audit(ctx):
    tokens = ctx.script("agent-spec-tokens.py")
    if not tokens:
        return [("audit", "WARN", "agent-spec-tokens.py missing", ctx.register_cmd())]
    res = run([sys.executable, tokens, "audit", "--scan", ctx.project], ctx.project, timeout=30)
    if res is None:
        return [("audit", "WARN", "token audit did not run", "")]
    if "no findings" in res.stdout:
        return [("audit", "OK", "token audit: no findings", "")]
    findings = [l.split("Finding.", 1)[1].strip() for l in res.stdout.splitlines() if "Finding." in l]
    fixes = [l.split("Fix.", 1)[1].strip() for l in res.stdout.splitlines() if "Fix." in l]
    return [("audit", "WARN", "token audit: %s" % (findings[0] if findings else "findings"),
             fixes[0] if fixes else "./.agent-spec/bin/agent-spec-tokens.py audit")]


def check_coexistence(ctx):
    """algosec-lean with Always Apply plus agent-spec.mdc doubles the always-on prefix."""
    for base in (os.path.join(ctx.project, ".cursor", "rules"),
                 os.path.join(ctx.cursor_home, "rules")):
        for name in ("algosec-lean.mdc", "algosec-lean.md"):
            text = read(os.path.join(base, name))
            if re.search(r"(?m)^alwaysApply:\s*true", text):
                return [("coexistence", "WARN",
                         "algosec-lean is Always Apply alongside agent-spec.mdc (%s)" % os.path.join(base, name),
                         "set alwaysApply: false in that file; keep one always-on style rule")]
    return [("coexistence", "OK", "no stacked always-on style rule", "")]


def check_onboarding(ctx):
    if os.path.exists(os.path.join(ctx.spec, ".onboarding-needed")):
        return [("onboarding", "INFO", "onboarding pending", "agent runs /agent-spec-onboard automatically; no user action")]
    return []


TEAM_FACTS_STALE_DAYS = 14


def check_team_facts(ctx):
    """T-053. Silent unless TEAM_FACTS_REPO is set or team facts exist. Stat-only (quick mode)."""
    team_dir = os.path.join(ctx.spec, "team-facts")
    repo = os.environ.get("TEAM_FACTS_REPO", "")
    facts = []
    try:
        facts = [n for n in os.listdir(team_dir) if n.endswith(".md")]
    except OSError:
        pass
    if repo and not facts:
        return [("team-facts", "WARN", "TEAM_FACTS_REPO is set but no team facts are merged",
                 ctx.register_cmd())]
    if not facts:
        return []
    if os.path.exists(os.path.join(team_dir, ".git")):
        return [("team-facts", "OK", "%d team fact file(s) from a submodule" % len(facts), "")]
    try:
        age = (datetime.now().timestamp() - os.path.getmtime(os.path.join(team_dir, ".synced"))) / 86400
    except OSError:
        return [("team-facts", "WARN", "team facts present but never synced (.synced missing)",
                 ctx.register_cmd())]
    if repo and age > TEAM_FACTS_STALE_DAYS:
        return [("team-facts", "WARN", "team facts last synced %d days ago" % age, ctx.register_cmd())]
    return [("team-facts", "OK", "%d team fact(s), synced %d day(s) ago" % (len(facts), age), "")]


def mcp_limit():
    try:
        val = int(os.environ.get(MCP_LIMIT_ENV, MCP_SCHEMA_TOKEN_LIMIT))
        return val if val > 0 else MCP_SCHEMA_TOKEN_LIMIT
    except ValueError:
        return MCP_SCHEMA_TOKEN_LIMIT


def check_mcp(ctx):
    limit = mcp_limit()
    candidates = [
        os.path.join(ctx.project, ".cursor", "mcp.json"),
        os.path.join(ctx.project, "mcp.json"),
        os.path.join(ctx.spec, "mcp.json"),
    ]
    cursor_home = getattr(ctx, "cursor_home", None)
    if cursor_home:
        candidates.append(os.path.join(cursor_home, "mcp.json"))

    found_files = []
    total_bytes = 0
    for path in candidates:
        if os.path.isfile(path):
            found_files.append(path)
            total_bytes += os.path.getsize(path)

    for d in (os.path.join(ctx.project, ".cursor", "mcp"), os.path.join(ctx.spec, "mcp")):
        if os.path.isdir(d):
            try:
                for name in os.listdir(d):
                    if name.endswith(".json"):
                        fp = os.path.join(d, name)
                        if os.path.isfile(fp):
                            found_files.append(fp)
                            total_bytes += os.path.getsize(fp)
            except OSError:
                pass

    if not found_files:
        return [("mcp", "OK", "no registered MCP tool schemas (limit %d tokens)" % limit, "")]

    tokens = (total_bytes + 3) // 4
    if tokens > limit:
        return [("mcp", "WARN",
                 "MCP tool schemas footprint is %d tokens (%d B across %d file(s)), exceeding %d token limit"
                 % (tokens, total_bytes, len(found_files), limit),
                 "prune unused tool schemas or configure lazy loading to avoid always-on context bloat")]

    return [("mcp", "OK", "MCP tool schemas %d tokens (limit %d)" % (tokens, limit), "")]


# (function, runs in --line quick mode). The digest calls --line on every session,
# so quick mode may only stat files — no subprocesses, and never the digest itself.
CHECKS = [
    (check_project, True), (check_skills, True), (check_hooks, True), (check_graph, True),
    (check_digest, False), (check_memory, True), (check_memory_lint, False),
    (check_register, True), (check_version, True), (check_git_hooks, True),
    (check_team, True), (check_team_facts, True), (check_audit, False), (check_coexistence, True),
    (check_onboarding, True), (check_mcp, True),
]


def run_checks(ctx, quick):
    results = []
    for fn, in_quick in CHECKS:
        if quick and not in_quick:
            continue
        try:
            results.extend(fn(ctx))
        except Exception as exc:  # a broken check must not hide the others
            results.append((fn.__name__.replace("check_", ""), "WARN", "check crashed: %s" % exc, ""))
        if results and results[-1][0] == "project" and results[-1][1] == "FAIL":
            break
    return results


def line_summary(results):
    issues = [r for r in results if r[1] in ("FAIL", "WARN")]
    if not issues:
        return "doctor: OK"
    issues.sort(key=lambda r: 0 if r[1] == "FAIL" else 1)
    first = issues[0]
    return "doctor: %d issue(s) — %s%s" % (
        len(issues), first[2][:80], (" | fix: " + first[3]) if first[3] else "")


def main():
    parser = argparse.ArgumentParser(description="agent-spec harness doctor")
    parser.add_argument("--project", default=os.getcwd())
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--line", action="store_true")
    parser.add_argument("--strict", action="store_true", help="WARN also fails")
    args = parser.parse_args()

    try:
        ctx = Ctx(os.path.abspath(args.project), find_package())
        results = run_checks(ctx, quick=args.line)
    except Exception as exc:
        if args.line:
            print("doctor: could not run (%s)" % exc)
            return 0
        raise

    if args.line:
        print(line_summary(results))
        return 0

    bad = [r for r in results if r[1] == "FAIL"]
    warn = [r for r in results if r[1] == "WARN"]
    ok = not bad and not (args.strict and warn)
    if args.json:
        print(json.dumps({"ok": ok, "checks": [
            {"id": i, "status": s, "message": m, "fix": f} for i, s, m, f in results]}, indent=2))
    else:
        print("agent-spec-doctor: %s" % ctx.project)
        for ident, status, msg, fix in results:
            print("  %-4s %-11s %s" % (status, ident, msg))
            if fix and status in ("FAIL", "WARN", "INFO"):
                print("       fix: %s" % fix)
        print("\n%d FAIL, %d WARN — %s" % (len(bad), len(warn), "green" if ok else "NOT green"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
