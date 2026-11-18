"""Multi-repo home (P3-006) and self-service repo onboarding (P3-007).

Reads the hub's `mesh.json` and `graph/mesh-graph.json` written by graphify-mesh.py:
one row per member (files, branch, SHA, freshness, drift), cross-repo edge counts per repo
pair, and token totals per repo rolled up from this machine's request traces by workspace
(no source leaves the machine). Add and remove run graphify-mesh.py itself with an argv list,
and each run is an automation row (`mesh-add`, `mesh-remove`).

Allowed-code reason (DEC-15): *plumbing* and *exact* counts; no model.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time

from . import common
from . import traces as tr

REPO_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,80}$")
TIMEOUT = 300


def _spec(project):
    return common.agent_spec_dir(project)


def _read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def _git(path, *args):
    try:
        res = subprocess.run(["git", "-C", path] + list(args), capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    return res.stdout.strip() if res.returncode == 0 else None


def _mesh_cli(project):
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for path in (os.path.join(_spec(project), "bin", "graphify-mesh.py"), os.path.join(here, "graphify-mesh.py")):
        if os.path.isfile(path):
            return path
    return None


def _tokens_by_workspace(project, conn):
    try:
        all_t, _ = tr.all_traces(project, conn)
    except Exception:  # noqa: BLE001 — token roll-up is additive
        return {}
    out = {}
    for t in all_t:
        ws = t.get("workspace")
        if not ws:
            continue
        key = os.path.realpath(ws)
        row = out.setdefault(key, {"requests": 0, "tokens": 0})
        row["requests"] += 1
        row["tokens"] += sum(int(t.get(k) or 0) for k in ("input_tokens", "output_tokens"))
    return out


def overview(project: str, conn=None) -> dict:
    manifest = _read(os.path.join(_spec(project), "mesh.json")) or {"repos": []}
    graph = _read(os.path.join(_spec(project), "graph", "mesh-graph.json")) or {}
    files = {}
    for n in graph.get("nodes") or []:
        files[n.get("repo")] = files.get(n.get("repo"), 0) + 1
    tokens = _tokens_by_workspace(project, conn)
    repos = []
    for r in manifest.get("repos") or []:
        if not isinstance(r, dict):
            continue
        path = r.get("path") or ""
        exists = os.path.isdir(path)
        head = _git(path, "rev-parse", "HEAD") if exists else None
        repos.append({
            "repo_id": r.get("repo_id"), "path": path, "exists": exists,
            "files": files.get(r.get("repo_id"), 0),
            "branch": _git(path, "symbolic-ref", "--short", "-q", "HEAD") if exists else None,
            "head_sha": head, "built_sha": r.get("head_sha"), "updated": r.get("updated"),
            "drifted": bool(r.get("head_sha") and head and head != r.get("head_sha")),
            "usage": tokens.get(os.path.realpath(path)) if exists else None,
        })
    pairs = {}
    for e in graph.get("edges") or []:
        if not e.get("cross_repo"):
            continue
        a, b = str(e["source"]).split(":", 1)[0], str(e["target"]).split(":", 1)[0]
        row = pairs.setdefault((a, b), {"source": a, "target": b, "total": 0, "by_type": {}})
        row["total"] += 1
        row["by_type"][e.get("type")] = row["by_type"].get(e.get("type"), 0) + 1
    hot = {}
    for e in graph.get("edges") or []:
        if e.get("cross_repo"):
            hot[e["target"]] = hot.get(e["target"], 0) + 1
    return {"hub": project, "built": bool(graph), "repos": repos,
            "pairs": sorted(pairs.values(), key=lambda p: -p["total"]),
            "hot_files": [{"file": f, "callers": n} for f, n in sorted(hot.items(), key=lambda x: -x[1])[:15]],
            "provenance": "measured"}


def query(project: str, file_id: str) -> dict:
    cli = _mesh_cli(project)
    if not cli:
        raise ValueError("graphify-mesh.py not found")
    if not file_id or len(file_id) > 500 or "\0" in file_id:
        raise ValueError("file is required as <repo_id>:<path>")
    res = subprocess.run([sys.executable, cli, "query", "--file", file_id, "--json"], cwd=project,
                         capture_output=True, text=True, timeout=60)
    if res.returncode != 0:
        raise ValueError((res.stderr or res.stdout).strip().splitlines()[-1][:300] if (res.stderr or res.stdout) else "query failed")
    return json.loads(res.stdout)


def _log(project, row):
    metrics = os.path.join(_spec(project), "metrics")
    os.makedirs(metrics, exist_ok=True)
    row = dict({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "source": "dashboard"}, **row)
    with open(os.path.join(metrics, "automation.jsonl"), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, separators=(",", ":")) + "\n")


def change(project: str, action: str, path: str = "", repo_id: str = "") -> dict:
    """Add a repo by path (then rebuild the mesh) or remove one by id."""
    cli = _mesh_cli(project)
    if not cli:
        raise ValueError("graphify-mesh.py not found")
    if action == "add":
        path = os.path.abspath(os.path.expanduser(str(path or "")))
        if not os.path.isdir(path):
            raise ValueError("not a directory: %s" % path)
        if os.path.realpath(path) == os.path.realpath(project):
            pass  # the hub may be a member of its own mesh
        argv = ["add", path] + (["--id", repo_id] if repo_id else [])
        if repo_id and not REPO_ID.match(repo_id):
            raise ValueError("repo id may hold letters, digits, dot, dash and underscore only")
        name = "mesh-add"
    elif action == "remove":
        if not REPO_ID.match(str(repo_id or "")):
            raise ValueError("repo_id is required")
        argv, name = ["remove", repo_id], "mesh-remove"
    else:
        raise ValueError("action must be add or remove")
    started = time.monotonic()
    steps = []
    for step in (argv, ["build"]):
        res = subprocess.run([sys.executable, cli] + step, cwd=project, capture_output=True, text=True, timeout=TIMEOUT)
        steps.append((res.stdout or res.stderr).strip().splitlines()[-3:])
        if res.returncode != 0:
            msg = ((res.stderr or res.stdout).strip().splitlines() or ["failed"])[-1][:300]
            _log(project, {"name": name, "status": "failed", "reason": "%s %s" % (action, path or repo_id),
                           "error": msg, "duration_ms": int((time.monotonic() - started) * 1000)})
            raise ValueError(msg)
        if action == "remove" and not _read(os.path.join(_spec(project), "mesh.json")).get("repos"):
            break  # an empty mesh has nothing to build
    duration = int((time.monotonic() - started) * 1000)
    _log(project, {"name": name, "status": "ok", "reason": "%s %s" % (action, path or repo_id), "duration_ms": duration})
    return {"ok": True, "action": action, "duration_ms": duration, "output": [l for s in steps for l in s]}
