#!/usr/bin/env python3
"""Print a compact project digest for the SessionStart hook.

The session-start protocol used to tell the agent to open four files. That cost
several thousand tokens before any work began, every single session. This reads the
same files once, outside the model, and emits only the facts a session actually
starts from. Everything else stays queryable on demand through graphify-cli.

Output is capped: a digest that grows without bound is the problem it was written to
solve. Prints nothing at all when there is no .agent-spec/ directory, so the hook is
silent in projects that do not use the framework.
"""
import json
import os
import re
import subprocess
import sys

ROOT = os.getcwd()
SPEC = os.path.join(ROOT, ".agent-spec")
MAX_BYTES = 2600


def read(path, limit=None):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read(limit) if limit else fh.read()
    except OSError:
        return ""


def load_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


RESUME_CAP = 600  # bytes of the digest spent on warm resume; the full snapshot costs ~9 KB to read
DATED_SECTION = re.compile(r"^## (\d{4}-\d{2}-\d{2}.*)$", re.M)


def _bullets(body, heading, limit):
    """The first `limit` bullet lines under a `### heading`, bold markers stripped."""
    m = re.search(r"^### " + re.escape(heading) + r"\s*$(.*?)(?=^### |\Z)", body, re.M | re.S)
    if not m:
        return []
    out = []
    for line in m.group(1).splitlines():
        line = line.strip()
        if not line:
            continue
        out.append(line.lstrip("-* ").replace("**", ""))
        if len(out) >= limit:
            break
    return out


def _clip_text(text, cap):
    return text if len(text) <= cap else text[:cap - 1].rstrip() + "…"


def resume_lines():
    """Warm resume (P4-009): the newest dated snapshot section's title, open items and the
    files it says to load, so a new chat does not open SESSION-SNAPSHOT.md to find them.

    Snapshots append dated `## YYYY-MM-DD …` sections before `## Archived sections`; the
    newest is the last dated heading in the file. Returns [] for the older format.
    """
    text = read(os.path.join(SPEC, "SESSION-SNAPSHOT.md"))
    heads = list(DATED_SECTION.finditer(text or ""))
    if not heads:
        return []
    last = heads[-1]
    end = re.search(r"^## ", text[last.end():], re.M)
    body = text[last.end(): last.end() + end.start()] if end else text[last.end():]
    lines = ["last session: " + _clip_text(last.group(1).strip(), 150)]
    load = _bullets(body, "Load next session", 1)
    if load:  # the files to open beat a third open item when the cap bites
        lines.append("  load: " + _clip_text(load[0], 200))
    for item in _bullets(body, "Open", 3):
        lines.append("  open: " + _clip_text(item, 140))
    out, used = [], 0
    for line in lines:
        if used + len(line) + 1 > RESUME_CAP:
            break
        out.append(line)
        used += len(line) + 1
    return out


def last_snapshot_summary():
    """The most recent snapshot's summary — snapshots append, so take the last section."""
    text = read(os.path.join(SPEC, "SESSION-SNAPSHOT.md"))
    if not text:
        return ""
    sections = text.split("\n# Session Snapshot")
    latest = sections[-1]
    lines = []
    capture = False
    for line in latest.split("\n"):
        if line.startswith("## Session Summary"):
            capture = True
            continue
        if capture:
            if line.startswith("## "):
                break
            if line.strip():
                lines.append(line.strip())
        if len(lines) >= 3:
            break
    return " ".join(lines)[:240]


def gate():
    state = load_json(os.path.join(SPEC, "sdlc", "STATE.json"))
    if state:
        return "gate %s %s — feature: %s" % (
            state.get("gate", "?"),
            state.get("gate_name", ""),
            state.get("feature", "unnamed"),
        )
    text = read(os.path.join(SPEC, "SESSION-SNAPSHOT.md"))
    for line in text.split("\n"):
        if line.startswith("Gate "):
            return line.strip()
    return "no SDLC pipeline in flight"


def graph_line():
    graph = load_json(os.path.join(SPEC, "graph", "knowledge-graph.json"))
    if not graph:
        return "graph: not built — run ./.agent-spec/bin/agent-spec-index"
    stats = graph.get("stats", {})
    hot = ", ".join(n for n, _ in stats.get("most_depended", [])[:3])
    line = "stack: %s | %s files, %s internal edges, %s cycles" % (
        graph.get("stack", "unknown"),
        stats.get("files", len(graph.get("nodes", []))),
        stats.get("internal_edges", "?"),
        stats.get("cycles", "?"),
    )
    return line + ("\nmost depended on: " + hot if hot else "")


def remembered():
    """Facts recorded with agent-spec-memory. Bounded by that tool, not by this one."""
    sibling = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent-spec-memory.py")
    for script in (os.path.join(SPEC, "bin", "agent-spec-memory.py"), sibling):
        if not os.path.exists(script):
            continue
        try:
            out = subprocess.run([sys.executable, script, "digest"], cwd=ROOT,
                                 capture_output=True, text=True, timeout=5)
        except (OSError, subprocess.SubprocessError):
            return ""
        return out.stdout.strip()
    return ""


REBUILD_HINT = "./.agent-spec/bin/agent-spec-index"
BUILD_LOCK_EXIT = 3  # graphify-build.py --quiet exits with this when another build holds the lock


def ensure_fresh_graph():
    """Ensure knowledge-graph.json is fresh before assembling digest; return its state.

    Runs a cache-backed incremental build (<100ms) on session start so uncommitted
    local file additions, edits, or deletes on the same branch are immediately reflected
    without manual indexing. Guaranteed fail-open with a timeout (default 3s,
    AGENT_SPEC_BUILD_TIMEOUT) and process concurrency locking.

    Returns a short label for the digest: "fresh", "incremental (42ms, 3 reparsed)",
    "stale (lock held ...)", "stale (timeout ...)", "stale (build failed ...)", or ""
    when there is no builder to ask.
    """
    if not os.path.isdir(SPEC):
        return ""

    candidates = [
        os.path.join(SPEC, "bin", "graphify-build.py"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "graphify-build.py"),
    ]
    builder = next((b for b in candidates if os.path.isfile(b)), None)
    if not builder:
        return ""

    try:
        timeout = float(os.environ.get("AGENT_SPEC_BUILD_TIMEOUT", "3"))
    except ValueError:
        timeout = 3.0
    try:
        res = subprocess.run([sys.executable, builder, "--quiet"], cwd=ROOT,
                             capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return "stale (timeout %gs — large repo or slow disk; run %s)" % (timeout, REBUILD_HINT)
    except Exception:
        return "stale (build did not run — run %s)" % REBUILD_HINT

    if res.returncode == BUILD_LOCK_EXIT:
        return "stale (lock held — another build is running; graph may lag a moment)"
    if res.returncode != 0:
        return "stale (build failed — run %s)" % REBUILD_HINT
    status = load_json(os.path.join(SPEC, "graph", ".status.json")) or {}
    if not status.get("reparsed"):
        return "fresh"
    return "incremental (%sms, %s reparsed)" % (status.get("duration_ms", "?"), status["reparsed"])


TEAM_KEYS = {
    "java_version": lambda v: re.fullmatch(r"\d+(\.\d+)*", v) is not None,
    "node_version": lambda v: re.fullmatch(r"\d+(\.\d+)*", v) is not None,
    "sdlc_track": lambda v: v in ("fast-track", "algorithm", "design", "full"),
    "default_branch": lambda v: re.fullmatch(r"[\w./-]+", v) is not None,
}


def parse_team_yaml(text):
    """Flat `key: value` subset (stdlib only). Returns (valid {key: value}, [error strings]).

    Unknown keys, malformed lines and invalid values are reported, never injected: a
    typo in team defaults must not become an instruction in every session.
    """
    valid, errors = {}, []
    for n, raw in enumerate(text.split("\n"), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if ":" not in line:
            errors.append("line %d: not 'key: value'" % n)
            continue
        key, value = (p.strip().strip("'\"") for p in line.split(":", 1))
        check = TEAM_KEYS.get(key)
        if check is None:
            errors.append("line %d: unknown key '%s'" % (n, key))
        elif not check(value):
            errors.append("line %d: invalid value for %s" % (n, key))
        else:
            valid[key] = value
    return valid, errors


def team_line():
    text = read(os.path.join(SPEC, "team.yaml"))
    if not text:
        return ""
    valid, _ = parse_team_yaml(text)
    if not valid:
        return ""
    return "team: " + " ".join("%s=%s" % kv for kv in valid.items())


def doctor_line():
    """One line from the doctor's quick mode; empty when the doctor is not installed."""
    candidates = [
        os.path.join(SPEC, "bin", "agent-spec-doctor.py"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent-spec-doctor.py"),
    ]
    script = next((c for c in candidates if os.path.isfile(c)), None)
    if not script:
        return ""
    try:
        out = subprocess.run([sys.executable, script, "--line"], cwd=ROOT,
                             capture_output=True, text=True, timeout=2)
    except Exception:
        return ""
    return out.stdout.strip()[:200]


def staged_learning_line():
    """Surfaces the first pending candidate from zero-touch distillation."""
    path = os.path.join(SPEC, "memory", "staged-candidates.jsonl")
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    row = json.loads(line)
                    if row.get("status") == "pending" and row.get("candidate"):
                        return 'learning candidate: "%s" — run `/agent-spec-learn distill` or confirm in chat to remember.' % row["candidate"][:90]
                except ValueError:
                    pass
    except OSError:
        pass
    return ""


def build_digest():
    """Assemble the digest text, or "" when this is not an agent-spec project."""
    if not os.path.isdir(SPEC):
        return ""

    graph_status = ensure_fresh_graph()

    out = ["<agent-spec-digest>"]

    if os.path.exists(os.path.join(SPEC, ".onboarding-needed")):
        out.append("ONBOARDING NEEDED (agent action, automatic) — run `/agent-spec-onboard` now, "
                   "silently, before answering. Never ask the user to run it.")

    out.append(graph_line())
    if graph_status:
        out.append("graph: " + graph_status)
    out.append("pipeline: " + gate())

    team = team_line()
    if team:
        out.append(team)
    doctor = doctor_line()
    if doctor:
        out.append(doctor)

    resume = resume_lines()
    summary = "" if resume else last_snapshot_summary()
    if resume:
        out.extend(resume)
    elif summary:
        out.append("last session: " + summary)

    facts = remembered()
    if facts:
        out.append("remembered:")
        out.append(facts)

    staged = staged_learning_line()
    if staged:
        out.append(staged)

    out.append(
        "Do NOT open PROJECT-INDEX.md, KNOWLEDGE-GRAPH.md or SESSION-SNAPSHOT.md to "
        "re-derive the above; it is already here. Query structure with "
        "./.agent-spec/bin/graphify-cli.py; read CONSTITUTION.md only before editing code. "
        "More facts: ./.agent-spec/bin/agent-spec-memory.py search <term>."
    )
    out.append("</agent-spec-digest>")

    text = "\n".join(out)
    return text[:MAX_BYTES] + ("" if len(text) <= MAX_BYTES else "\n[truncated]")


def main():
    text = build_digest()
    if not text:
        return 0
    sys.stdout.write(text + "\n")
    return 0


def cursor_hook():
    """Cursor's sessionStart hook: read the payload on stdin, emit the digest in
    the {"additional_context": ...} envelope Cursor injects into the session. Always
    prints valid JSON — {} when there is nothing to add — so the hook never fails."""
    try:
        if not sys.stdin.isatty():
            sys.stdin.read()
    except Exception:
        pass
    text = build_digest()
    payload = {"additional_context": text} if text else {}
    sys.stdout.write(json.dumps(payload))
    return 0


if __name__ == "__main__":
    if "--cursor-hook" in sys.argv[1:]:
        sys.exit(cursor_hook())
    sys.exit(main())
