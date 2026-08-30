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


def main():
    if not os.path.isdir(SPEC):
        return 0

    out = ["<agent-spec-digest>"]

    if os.path.exists(os.path.join(SPEC, ".onboarding-needed")):
        out.append("ONBOARDING NEEDED — run /agent-spec-onboard before anything else.")

    out.append(graph_line())
    out.append("pipeline: " + gate())

    summary = last_snapshot_summary()
    if summary:
        out.append("last session: " + summary)

    facts = remembered()
    if facts:
        out.append("remembered:")
        out.append(facts)

    out.append(
        "Do NOT open PROJECT-INDEX.md, KNOWLEDGE-GRAPH.md or SESSION-SNAPSHOT.md to "
        "re-derive the above; it is already here. Query structure with "
        "./.agent-spec/bin/graphify-cli.py; read CONSTITUTION.md only before editing code. "
        "More facts: ./.agent-spec/bin/agent-spec-memory.py search <term>."
    )
    out.append("</agent-spec-digest>")

    text = "\n".join(out)
    sys.stdout.write(text[:MAX_BYTES] + ("\n" if len(text) <= MAX_BYTES else "\n[truncated]\n"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
