#!/usr/bin/env python3
"""agent-spec-recall.py — recall similar past experiences, across the repos of a mesh (P3-014).

  agent-spec-recall.py TASK [--limit N] [--json] [--no-log] [--peer PATH ...]

Searches `.agent-spec/experience.jsonl` in this project and in its peers, and prints the best
matches. Each match carries a citation, `<repo>:.agent-spec/experience.jsonl:<line>`, so a fix
recorded in repo A and found from repo B names repo A.

Peers are the repos that share a mesh with this project (P3-001):
  - the members listed in this project's `.agent-spec/mesh.json` (this project is a hub);
  - every registered project (`~/.cursor/skills/.algosec-agent-spec-projects`) whose
    `mesh.json` lists this project, plus that hub's other members;
  - any `--peer PATH` given.

Ranking follows the agent-spec-learn recall rules. A row whose latest override in its own
repo is `deprecated` is skipped. Then rows rank by: more matched task words, `promoted`
first, `status: success`, fewest retries + corrections, fewest tokens, then this project
before a peer. Each shown match is appended to this project's `experience-reuse.jsonl` unless
`--no-log` is given. The script only reads peers; it never writes to them.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys

EXP = os.path.join(".agent-spec", "experience.jsonl")
STOP = frozenset("""about after again also before being could does doing done from have into just like make
more most only other over same some such than that them then there these they this those through under
until very what when where which while will with would your the and for are but not you all can had her
was one our out use file files task please fix code""".split())


def words(text):
    return {w for w in re.findall(r"[a-z0-9_]+", (text or "").lower()) if len(w) >= 4 and w not in STOP}


def read_jsonl(path):
    rows = []
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for n, line in enumerate(fh, 1):
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict):
                    rows.append((n, row))
    except OSError:
        pass
    return rows


def manifest_members(hub):
    try:
        with open(os.path.join(hub, ".agent-spec", "mesh.json"), encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return []
    out = []
    for e in data.get("repos") or [] if isinstance(data, dict) else []:
        if isinstance(e, dict) and e.get("path"):
            out.append((str(e.get("repo_id") or e.get("id") or os.path.basename(e["path"])),
                        os.path.realpath(e["path"])))
    return out



def native_path(p: str, nt: bool = os.name == "nt") -> str:
    """Registry lines are written by install.sh. Under Git Bash that is `/c/Users/...`, which
    Windows Python would read as `C:\\c\\Users\\...`; map the drive back first."""
    m = re.match(r"^/([a-zA-Z])(/.*)?$", p)
    if nt and m:
        p = m.group(1).upper() + ":" + (m.group(2) or "/")
    return os.path.realpath(p)


def registry():
    path = os.path.join(os.path.expanduser("~"), ".cursor", "skills", ".algosec-agent-spec-projects")
    try:
        with open(path, encoding="utf-8") as fh:
            return [native_path(l.strip()) for l in fh if l.strip()]
    except OSError:
        return []


def peers(project, extra=()):
    """[(repo_id, path)] for every repo sharing a mesh with `project`, without `project` itself."""
    project = os.path.realpath(project)
    found = {}
    for rid, path in manifest_members(project):
        found.setdefault(path, rid)
    for hub in registry():
        if hub == project:
            continue
        members = manifest_members(hub)
        if any(path == project for _, path in members):
            found.setdefault(hub, os.path.basename(hub))
            for rid, path in members:
                found.setdefault(path, rid)
    for p in extra:
        rp = os.path.realpath(p)
        found.setdefault(rp, os.path.basename(rp))
    found.pop(project, None)
    return [(rid, path) for path, rid in sorted(found.items(), key=lambda kv: kv[1])
            if os.path.isfile(os.path.join(path, EXP))]


def overrides(path):
    out = {}
    for _, row in read_jsonl(os.path.join(path, ".agent-spec", "experience-overrides.jsonl")):
        if row.get("exp_id"):
            out[row["exp_id"]] = row.get("status")
    return out


def candidates(repo_id, path, want, local):
    decided = overrides(path)
    latest = {}
    for n, row in read_jsonl(os.path.join(path, EXP)):
        if row.get("exp_id"):
            latest[row["exp_id"]] = (n, row)  # the stop hook rewrites a session's line; keep the last
    out = []
    for exp_id, (n, row) in latest.items():
        if decided.get(exp_id) == "deprecated":
            continue
        hit = want & words(row.get("task"))
        if not hit:
            continue
        tok = row.get("tokens") or {}
        total = sum(v for v in tok.values() if isinstance(v, int)) if isinstance(tok, dict) else 0
        out.append({
            "repo": repo_id, "local": local, "exp_id": exp_id, "matched": sorted(hit),
            "promoted": decided.get(exp_id) == "promoted", "status": row.get("status"),
            "gates": row.get("gates"), "retries": row.get("retries") or 0,
            "corrections": row.get("corrections") or 0, "tokens": total,
            "workflow_id": row.get("workflow_id"), "task": (row.get("task") or "")[:200],
            "ts": row.get("ts"), "citation": "%s:%s:%d" % (repo_id, EXP, n),
        })
    return out


def rank_key(c):
    return (-len(c["matched"]), not c["promoted"], c["status"] != "success",
            c["retries"] + c["corrections"], c["tokens"], not c["local"])


def recall(project, task, limit=3, extra=()):
    want = words(task)
    if not want:
        return []
    project = os.path.realpath(project)
    pool = candidates(os.path.basename(project), project, want, True)
    for rid, path in peers(project, extra):
        pool.extend(candidates(rid, path, want, False))
    return sorted(pool, key=rank_key)[:limit]


def log_reuse(project, task, rows):
    path = os.path.join(project, ".agent-spec", "experience-reuse.jsonl")
    ts = datetime.datetime.now().replace(microsecond=0).isoformat()
    try:
        with open(path, "a", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps({"ts": ts, "exp_id": r["exp_id"], "task": task[:200], "repo": r["repo"],
                                     "citation": r["citation"]}, sort_keys=True) + "\n")
    except OSError:
        pass


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("task")
    ap.add_argument("--limit", type=int, default=3)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-log", action="store_true")
    ap.add_argument("--peer", action="append", default=[])
    ap.add_argument("--project", default=os.getcwd())
    args = ap.parse_args(argv)
    rows = recall(args.project, args.task, max(1, min(args.limit, 20)), args.peer)
    if rows and not args.no_log:
        log_reuse(os.path.realpath(args.project), args.task, rows)
    if args.json:
        print(json.dumps({"task": args.task, "matches": rows}, indent=1))
    elif not rows:
        print("no similar experience in this project or its mesh peers")
    else:
        for r in rows:
            print("%s | %s | gates %s | retries %s | %s  [%s]" % (
                r["exp_id"], r["status"], r["gates"], r["retries"], r["task"][:100], r["citation"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
