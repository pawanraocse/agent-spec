"""Index health (H-020): is this project's index current, and how big are its logs?

Allowed-code reason (DEC-15): *exact* — every value is read from files on disk or from git;
nothing is estimated. The dashboard's Index health panel answers "is my index current?"
without a terminal, and its two buttons run the same scripts the hooks run.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime

from . import common

# Append-only files the harness writes. H-041 adds retention; until then this panel shows
# how fast each one grows so a runaway log is visible.
LOGS = (
    ("events", "metrics/events.jsonl"),
    ("automation", "metrics/automation.jsonl"),
    ("injections", "metrics/injections.jsonl"),
    ("daily", "metrics/daily.jsonl"),
    ("hook payloads", "metrics/hook-payloads"),
    ("receipts", "metrics/receipts"),
    ("graph history", "graph/stats-history.jsonl"),
    ("platform db", "platform/platform.db"),
)
BUILD_TIMEOUT = 180
ACTIONS = ("rebuild-graph", "refresh-mesh", "apply-retention")


def _read_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def _size(path) -> tuple[int, int | None]:
    """(bytes, lines) for a file; (bytes, files) for a directory."""
    if os.path.isdir(path):
        total, n = 0, 0
        for dirpath, _, names in os.walk(path):
            for name in names:
                try:
                    total += os.path.getsize(os.path.join(dirpath, name))
                    n += 1
                except OSError:
                    pass
        return total, n
    try:
        size = os.path.getsize(path)
    except OSError:
        return 0, None
    lines = None
    if path.endswith(".jsonl") and size <= 64 * 1024 * 1024:
        with open(path, "rb") as fh:
            lines = sum(1 for _ in fh)
    return size, lines


def _git(project, *args):
    try:
        res = subprocess.run(["git", "-C", project] + list(args), capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    return res.stdout.strip() if res.returncode == 0 else None


def _builder(project, name):
    spec = common.agent_spec_dir(project)
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for path in (os.path.join(spec, "bin", name), os.path.join(here, name)):
        if os.path.isfile(path):
            return path
    return None


def graph_health(project: str) -> dict:
    gdir = os.path.join(common.agent_spec_dir(project), "graph")
    graph_path = os.path.join(gdir, "knowledge-graph.json")
    status = _read_json(os.path.join(gdir, ".status.json")) or {}
    built = os.path.isfile(graph_path)
    git = status.get("git") or {}
    if built and not git:  # status from an older builder: the graph itself may carry it
        git = (_read_json(graph_path) or {}).get("git") or {}
    head = _git(project, "rev-parse", "HEAD")
    branch = _git(project, "symbolic-ref", "--short", "-q", "HEAD")
    age_s = None
    if status.get("finished"):
        try:
            age_s = int((datetime.now() - datetime.fromisoformat(status["finished"])).total_seconds())
        except ValueError:
            pass
    if not built:
        state = "missing"
    elif status.get("state") == "failed":
        state = "failed"
    elif head and git.get("head_sha") and head != git["head_sha"]:
        state = "behind"
    elif git.get("operation"):
        state = "mid-" + git["operation"]
    else:
        state = "current"
    cache = os.path.join(gdir, ".cache.json")
    return {
        "state": state,
        "built": built,
        "finished": status.get("finished"),
        "age_s": age_s,
        "duration_ms": status.get("duration_ms"),
        "reparsed": status.get("reparsed"),
        "files": status.get("files"),
        "graph_git": git or None,
        "head": {"sha": head, "branch": branch or ("(detached)" if head else None)},
        "last_failure": status.get("last_failure"),
        "error": status.get("error") if status.get("state") == "failed" else None,
        "cache_bytes": os.path.getsize(cache) if os.path.isfile(cache) else 0,
        "graph_bytes": os.path.getsize(graph_path) if built else 0,
    }


def mesh_health(project: str) -> dict | None:
    """Mesh members (graphify-mesh.py's manifest `repos`) and whether each one's HEAD moved
    since its graph was built (H-012)."""
    manifest = _read_json(os.path.join(common.agent_spec_dir(project), "mesh.json"))
    if not manifest:
        return None
    members = []
    for m in manifest.get("repos") or []:
        if not isinstance(m, dict):
            continue
        path = m.get("path") or ""
        recorded = m.get("head_sha")
        head = _git(path, "rev-parse", "HEAD") if os.path.isdir(path) else None
        members.append({"id": m.get("repo_id"), "path": path, "exists": os.path.isdir(path),
                        "head_sha": head, "built_sha": recorded, "updated": m.get("updated"),
                        "drifted": bool(recorded and head and recorded != head)})
    return {"members": members, "drifted": sum(1 for m in members if m["drifted"])}


def logs(project: str) -> list:
    spec = common.agent_spec_dir(project)
    out = []
    for name, rel in LOGS:
        path = os.path.join(spec, rel)
        if rel == "platform/platform.db":
            path = os.environ.get("AGENT_SPEC_DB") or path
        size, count = _size(path)
        out.append({"name": name, "path": rel, "exists": os.path.exists(path), "bytes": size,
                    ("files" if os.path.isdir(path) else "lines"): count})
    return out


def overview(project: str, conn=None) -> dict:
    index = None
    if conn is not None:
        from . import retrieval
        st = retrieval.index_status(conn)
        index = {"ready": st.get("ready"), "mode": st.get("mode"), "last": st.get("last"),
                 "sources": sum(v.get("sources", 0) for v in (st.get("by_kind") or {}).values()),
                 "chunks": sum(v.get("chunks", 0) for v in (st.get("by_kind") or {}).values())}
    graph = graph_health(project)
    mesh = mesh_health(project)
    problems = []
    if graph["state"] in ("missing", "failed", "behind"):
        problems.append({"missing": "graph not built", "failed": "last graph build failed",
                         "behind": "graph is older than HEAD"}[graph["state"]])
    if mesh and mesh["drifted"]:
        problems.append("%d mesh member(s) moved since the mesh was built" % mesh["drifted"])
    from . import retention
    return {"graph": graph, "mesh": mesh, "index": index, "logs": logs(project),
            "retention": dict(retention.config(project), archives=retention.archives(project)),
            "total_log_bytes": sum(entry["bytes"] for entry in logs(project)),
            "problems": problems, "actions": list(ACTIONS), "provenance": "measured"}


def _log_automation(project, row):
    metrics = os.path.join(common.agent_spec_dir(project), "metrics")
    try:
        os.makedirs(metrics, exist_ok=True)
        row = dict({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "source": "dashboard"}, **row)
        with open(os.path.join(metrics, "automation.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, separators=(",", ":")) + "\n")
    except OSError:
        pass


def run_action(project: str, action: str) -> dict:
    """Run one control action synchronously and record it in automation.jsonl."""
    if action not in ACTIONS:
        raise ValueError("unknown action %r (expected one of %s)" % (action, ", ".join(ACTIONS)))
    if action == "apply-retention":
        from . import retention
        started = time.monotonic()
        actions = retention.apply(project)
        duration = int((time.monotonic() - started) * 1000)
        _log_automation(project, {"name": "log-retention", "status": "ok", "reason": "dashboard apply-retention",
                                  "duration_ms": duration})
        return {"ok": True, "action": action, "duration_ms": duration,
                "output": ["%s: %s archived" % (a["file"], a.get("archived_rows", a.get("archived_files", 0)))
                           for a in actions] or ["nothing over its size cap"]}
    if action == "rebuild-graph":
        script, argv, name = _builder(project, "graphify-build.py"), ["--quiet"], "graph-refresh"
    else:
        script, argv, name = _builder(project, "graphify-mesh.py"), ["build"], "mesh-refresh"
        if not os.path.isfile(os.path.join(common.agent_spec_dir(project), "mesh.json")):
            raise ValueError("this project has no mesh.json; add a member with graphify-mesh.py add first")
    if not script:
        raise ValueError("builder not found for %s" % action)
    started = time.monotonic()
    try:
        res = subprocess.run([sys.executable, script] + argv, cwd=project, capture_output=True,
                             text=True, timeout=BUILD_TIMEOUT)
        ok, tail = res.returncode == 0, (res.stderr or res.stdout or "").strip().splitlines()[-3:]
    except subprocess.TimeoutExpired:
        ok, tail = False, ["timed out after %ds" % BUILD_TIMEOUT]
    duration = int((time.monotonic() - started) * 1000)
    _log_automation(project, {"name": name, "status": "built" if ok else "failed",
                              "reason": "dashboard %s" % action, "duration_ms": duration,
                              **({} if ok else {"error": " | ".join(tail)[:300]})})
    return {"ok": ok, "action": action, "duration_ms": duration, "output": tail}
