#!/usr/bin/env python3
"""Backlog CLI (D-004.1): the only sanctioned way to read or modify todo-plan.md.

  agent-spec-backlog.py list [--status S] [--slice N]
  agent-spec-backlog.py find <text>
  agent-spec-backlog.py show <ID>
  agent-spec-backlog.py set <ID> <status> [--evidence "command + result"]
  agent-spec-backlog.py json

Statuses: `[ ]` open, `[~]` in progress, `[x]` done, `[-]` deferred. `[x]` needs
--evidence; evidence lands in docs/evidence/<ID>.md next to the plan, so the plan stays small.
P-numbers and dependencies come from the tables in docs/IMPLEMENTATION-GUIDE.md section 14.
"""
import argparse
import datetime
import json
import os
import re
import sys
import tempfile

STATUSES = {"[ ]": "[ ]", "[~]": "[~]", "[x]": "[x]", "[-]": "[-]",
            " ": "[ ]", "~": "[~]", "x": "[x]", "-": "[-]",
            "open": "[ ]", "wip": "[~]", "done": "[x]", "deferred": "[-]"}
ROW = re.compile(r"^\| `\[([ ~x-])\]` \| (.+) \|\s*$")
SLICE = re.compile(r"^## Slice (\S+)")
GUIDE_ROW = re.compile(r"^\| (P\d+\.\d+) \| (\S+)[^|]*\| ([^|]*) \|")


class BacklogError(Exception):
    pass


def default_root():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return root if os.path.exists(os.path.join(root, "todo-plan.md")) else os.getcwd()


def evidence_path(plan, task_id):
    return os.path.join(os.path.dirname(os.path.abspath(plan)), "docs", "evidence", task_id + ".md")


def read_evidence(plan, task_id):
    try:
        with open(evidence_path(plan, task_id), encoding="utf-8") as fh:
            return [l[2:].strip() for l in fh if l.startswith("- ")]
    except OSError:
        return []


def guide_map(guide):
    """ID -> (P#, deps list) from the guide's section 14 tables."""
    out = {}
    try:
        with open(guide, encoding="utf-8") as fh:
            for line in fh:
                m = GUIDE_ROW.match(line)
                if m:
                    deps = [d.strip() for d in m.group(3).split(",") if re.match(r"P\d", d.strip())]
                    out.setdefault(m.group(2), (m.group(1), deps))
    except OSError:
        pass
    return out


def parse(plan, guide):
    pmap, rows, slice_ = guide_map(guide), [], ""
    with open(plan, encoding="utf-8") as fh:
        for n, line in enumerate(fh, 1):
            s = SLICE.match(line)
            if s:
                slice_ = s.group(1)
                continue
            m = ROW.match(line)
            if not m:
                continue
            cells = [c.strip() for c in m.group(2).split(" | ")]
            if len(cells) < 3:
                continue
            tid = cells[0]
            p, deps = pmap.get(tid, ("", []))
            rows.append({"task_id": tid, "slice": slice_, "p_number": p,
                         "title": cells[1].replace("**", ""),
                         "status": "[%s]" % m.group(1),
                         "acceptance": cells[2] if len(cells) > 3 else "",
                         "effort": cells[-1] if len(cells) > 3 else "",
                         "deps": deps, "evidence": read_evidence(plan, tid), "line": n})
    return rows


def find_row(rows, task_id):
    hits = [r for r in rows if r["task_id"] == task_id]
    if not hits:
        raise BacklogError("unknown task ID '%s'" % task_id)
    if len(hits) > 1:
        raise BacklogError("task ID '%s' appears %d times in the plan" % (task_id, len(hits)))
    return hits[0]


def fmt(r):
    return "%s  %-8s %-6s s%-4s %s" % (r["status"], r["task_id"], r["p_number"] or "-",
                                       r["slice"], r["title"])


def cmd_set(args):
    rows = parse(args.plan, args.guide)
    row = find_row(rows, args.id)
    status = STATUSES.get(args.status.lower())
    if not status:
        raise BacklogError("unknown status '%s' (use [ ] [~] [x] [-])" % args.status)
    if status == "[x]" and not args.evidence:
        raise BacklogError("refusing [x] for %s without --evidence \"command + result\"" % args.id)
    with open(args.plan, encoding="utf-8", newline="") as fh:
        lines = fh.read().splitlines(keepends=True)
    i = row["line"] - 1
    lines[i] = re.sub(r"^\| `\[[ ~x-]\]`", "| `%s`" % status, lines[i], count=1)
    if args.evidence:
        path = evidence_path(args.plan, args.id)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("- %s %s %s\n" % (datetime.datetime.now().isoformat(timespec="seconds"),
                                      status, " ".join(args.evidence.split())))
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(args.plan)), prefix=".backlog-")
    with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
        fh.write("".join(lines))
    os.replace(tmp, args.plan)
    print("%s: %s -> %s" % (args.id, row["status"], status))


def main(argv=None):
    root = default_root()
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--plan", default=os.path.join(root, "todo-plan.md"))
    ap.add_argument("--guide", default=os.path.join(root, "docs", "IMPLEMENTATION-GUIDE.md"))
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("list")
    p.add_argument("--status")
    p.add_argument("--slice")
    sub.add_parser("find").add_argument("text")
    sub.add_parser("show").add_argument("id")
    p = sub.add_parser("set")
    p.add_argument("id")
    p.add_argument("status")
    p.add_argument("--evidence")
    sub.add_parser("json")
    args = ap.parse_args(argv)
    try:
        if not os.path.exists(args.plan):
            raise BacklogError("plan not found: %s" % args.plan)
        if args.cmd == "set":
            return cmd_set(args) or 0
        rows = parse(args.plan, args.guide)
        if args.cmd == "json":
            print(json.dumps([{k: v for k, v in r.items() if k != "line"} for r in rows], indent=2))
        elif args.cmd == "list":
            want = STATUSES.get(args.status.lower()) if args.status else None
            if args.status and not want:
                raise BacklogError("unknown status '%s'" % args.status)
            for r in rows:
                if (not want or r["status"] == want) and (not args.slice or r["slice"] == args.slice):
                    print(fmt(r))
        elif args.cmd == "find":
            t = args.text.lower()
            for r in rows:
                if t in (r["task_id"] + " " + r["title"] + " " + r["acceptance"]).lower():
                    print(fmt(r))
        else:
            r = find_row(rows, args.id)
            print(fmt(r))
            print("acceptance: %s\neffort: %s" % (r["acceptance"], r["effort"] or "-"))
            print("P#: %s\ndepends: %s" % (r["p_number"] or "-", ", ".join(r["deps"]) or "-"))
            print("evidence:" + ("" if r["evidence"] else " -"))
            for e in r["evidence"]:
                print("  - " + e)
    except BacklogError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
