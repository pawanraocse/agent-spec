#!/usr/bin/env python3
"""agent-spec pipeline state.

The gates existed before this script; what did not exist was anywhere to record
which gate a feature had reached. That left the ordering in the agent's head, where
it survives exactly as long as the context window does. STATE.json puts it on disk,
so a new session, a different agent or a human can all read the same answer.

  status                      where the pipeline is, and what is missing
  check <gate>                exit 1 if that gate's preconditions are unmet
  set <gate> [--feature NAME] record that a gate has been passed
  trace                       requirement coverage across every artifact
  reset                       start a new feature at gate 0
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime

ROOT = os.getcwd()
SDLC = os.path.join(ROOT, ".agent-spec", "sdlc")
STATE_PATH = os.path.join(SDLC, "STATE.json")

# gate number -> (name, skill, artifact it produces, artifacts it requires)
GATES = [
    ("REQUIREMENTS", "/agent-spec-requirements", "01-REQUIREMENTS.md", []),
    ("TECH-SPEC",    "/agent-spec-tech-spec",    "02-TECH-SPEC.md",    ["01-REQUIREMENTS.md"]),
    ("PRD",          "/agent-spec-prd",          "03-PRD.md",          ["02-TECH-SPEC.md"]),
    ("HLD",          "/agent-spec-hld",          "04-HLD.md",          ["03-PRD.md"]),
    ("LLD",          "/agent-spec-lld",          "05-LLD.md",          ["04-HLD.md"]),
    ("DEVELOPMENT",  "/agent-spec-implement",    None,                 ["05-LLD.md"]),
    ("REVIEW",       "/agent-spec-review",       "06-REVIEW.md",       ["05-LLD.md"]),
    ("TESTING",      "/agent-spec-testing",      "07-TEST-REPORT.md",  ["06-REVIEW.md"]),
    ("VALIDATION",   "/agent-spec-validation",   "08-VALIDATION.md",   ["07-TEST-REPORT.md",
                                                             "01-REQUIREMENTS.md"]),
]

REQ_ID = re.compile(r"\b((?:REQ|NFR|US)-[A-Z0-9]+-?\d*)\b")


def load_state():
    try:
        with open(STATE_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {"feature": None, "gate": 0, "gate_name": GATES[0][0],
                "artifacts": {}, "history": []}


def save_state(state):
    os.makedirs(SDLC, exist_ok=True)
    state["updated"] = datetime.now().isoformat(timespec="seconds")
    with open(STATE_PATH, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2)
        fh.write("\n")


def artifact_path(name):
    return os.path.join(SDLC, name)


def has_artifact(name):
    """Present as itself, or as a per-service split.

    The LLD gate writes one file per service — `05-LLD-orders.md`, `05-LLD-billing.md` —
    so an exact-name check would report the gate as never run on precisely the projects
    the gate matters most for.
    """
    if os.path.exists(artifact_path(name)):
        return True
    stem = name[:-3] if name.endswith(".md") else name
    try:
        return any(f.startswith(stem + "-") and f.endswith(".md") for f in os.listdir(SDLC))
    except OSError:
        return False


def cmd_status(args):
    state = load_state()
    gate = state.get("gate", 0)
    name, skill, produces, requires = GATES[min(gate, len(GATES) - 1)]

    if getattr(args, "output_json", False):
        artifacts = []
        for i, (gname, gskill, produced, _) in enumerate(GATES):
            if produced is None:
                status = "n/a (code)"
            else:
                status = "present" if has_artifact(produced) else "MISSING"
            artifacts.append({"name": produced or gname, "gate": i, "status": status})
        doc = {
            "feature": state.get("feature") or None,
            "gate": gate,
            "gate_name": name,
            "next_command": skill,
            "artifacts": artifacts,
        }
        print(json.dumps(doc, indent=2))
        return 0

    print("feature: %s" % (state.get("feature") or "[unnamed — run reset --feature]"))
    print("gate:    %d %s   next command: %s" % (gate, name, skill))
    print("")
    print("artifact                 gate  status")
    for i, (gname, gskill, produced, _) in enumerate(GATES):
        if produced is None:
            mark = "n/a (code)"
        else:
            mark = "present" if has_artifact(produced) else "MISSING"
        print("  %-22s %4d  %s" % (produced or gname, i, mark))
    return 0


def cmd_check(args):
    gate = args.gate
    if not 0 <= gate < len(GATES):
        print("no such gate: %d" % gate, file=sys.stderr)
        return 2
    name, skill, produces, requires = GATES[gate]
    missing = [r for r in requires if not has_artifact(r)]
    if missing:
        print("BLOCKED at gate %d %s — missing: %s" % (gate, name, ", ".join(missing)))
        print("Run the gate that produces it first. Never write the upstream document "
              "yourself to unblock this one.")
        return 1
    print("gate %d %s: preconditions met" % (gate, name))
    return 0


def cmd_set(args):
    state = load_state()
    gate = args.gate
    if not 0 <= gate < len(GATES):
        print("no such gate: %d" % gate, file=sys.stderr)
        return 2
    name, skill, produces, _ = GATES[gate]
    if args.feature:
        state["feature"] = args.feature
    state["gate"] = gate
    state["gate_name"] = name
    if produces and has_artifact(produces):
        state.setdefault("artifacts", {})[produces] = datetime.now().isoformat(timespec="seconds")
    state.setdefault("history", []).append(
        {"gate": gate, "name": name, "at": datetime.now().isoformat(timespec="seconds")})
    save_state(state)
    nxt = GATES[gate + 1] if gate + 1 < len(GATES) else None
    print("gate %d %s recorded." % (gate, name))
    print("next: %s (%s)" % (nxt[1], nxt[0]) if nxt else "pipeline complete.")
    return 0


def cmd_trace(args):
    """Which requirement IDs survive into each downstream artifact.

    A requirement that appears in 01 and nowhere else was dropped. Nothing else in
    the pipeline notices that, because every individual document is internally
    consistent — which is exactly why it needs checking mechanically.
    """
    source = artifact_path("01-REQUIREMENTS.md")
    if not os.path.exists(source):
        print("No 01-REQUIREMENTS.md — nothing to trace.")
        return 1
    ids = sorted(set(REQ_ID.findall(open(source, encoding="utf-8").read())))
    if not ids:
        print("01-REQUIREMENTS.md contains no REQ-/NFR-/US- identifiers. Add them: "
              "traceability needs something to trace.")
        return 1

    downstream = [g[2] for g in GATES[1:] if g[2]]
    texts = {}
    for name in downstream:
        stem = name[:-3]
        try:
            parts = [f for f in sorted(os.listdir(SDLC))
                     if f == name or (f.startswith(stem + "-") and f.endswith(".md"))]
        except OSError:
            parts = []
        texts[name] = "\n".join(
            open(os.path.join(SDLC, f), encoding="utf-8").read() for f in parts) or None

    header = "%-16s %s" % ("requirement", "  ".join(n.split("-")[0] for n in downstream))
    print(header)
    dropped = []
    for rid in ids:
        row = []
        for name in downstream:
            text = texts[name]
            row.append("  %s " % ("-" if text is None else ("Y" if rid in text else ".")))
        print("%-16s %s" % (rid, "".join(row)))
        if all(cell.strip() != "Y" for cell in row):
            dropped.append(rid)

    print("")
    print("%d requirements, %d appear in no downstream artifact" % (len(ids), len(dropped)))
    if dropped:
        print("DROPPED: " + ", ".join(dropped))
        return 1
    return 0


def cmd_reset(args):
    state = {"feature": args.feature, "gate": 0, "gate_name": GATES[0][0],
             "artifacts": {}, "history": []}
    save_state(state)
    print("pipeline reset for '%s'. Start with /agent-spec-requirements." % args.feature)
    return 0


def main():
    parser = argparse.ArgumentParser(description="agent-spec pipeline state")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("status")
    p.add_argument("--json", dest="output_json", action="store_true",
                   help="print status as machine-readable JSON")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("check")
    p.add_argument("gate", type=int)
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("set")
    p.add_argument("gate", type=int)
    p.add_argument("--feature", default=None)
    p.set_defaults(func=cmd_set)

    sub.add_parser("trace").set_defaults(func=cmd_trace)

    p = sub.add_parser("reset")
    p.add_argument("--feature", required=True)
    p.set_defaults(func=cmd_reset)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
