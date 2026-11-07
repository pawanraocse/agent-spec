"""Read-only aggregators for dashboard v2 routes (DEC-14). Stdlib only."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone

from . import common

_GATES = [
    ("REQUIREMENTS", "/agent-spec-requirements", "01-REQUIREMENTS.md", []),
    ("TECH-SPEC", "/agent-spec-tech-spec", "02-TECH-SPEC.md", ["01-REQUIREMENTS.md"]),
    ("PRD", "/agent-spec-prd", "03-PRD.md", ["02-TECH-SPEC.md"]),
    ("HLD", "/agent-spec-hld", "04-HLD.md", ["03-PRD.md"]),
    ("LLD", "/agent-spec-lld", "05-LLD.md", ["04-HLD.md"]),
    ("DEVELOPMENT", "/agent-spec-implement", None, ["05-LLD.md"]),
    ("REVIEW", "/agent-spec-review", "06-REVIEW.md", ["05-LLD.md"]),
    ("TESTING", "/agent-spec-testing", "07-TEST-REPORT.md", ["06-REVIEW.md"]),
    ("VALIDATION", "/agent-spec-validation", "08-VALIDATION.md", ["07-TEST-REPORT.md", "01-REQUIREMENTS.md"]),
]

_doctor_cache: tuple[float, dict] | None = None


def _graph_path(project: str) -> str:
    return os.path.join(common.agent_spec_dir(project), "graph", "knowledge-graph.json")


def load_graph(project: str) -> dict | None:
    return common.read_json(_graph_path(project))


def api_graph(project: str, conn) -> dict:
    graph = load_graph(project) or {}
    edges = [e for e in graph.get("edges", []) if e.get("type", "imports") == "imports"]
    fan_in = Counter(e["target"] for e in edges)
    nodes = []
    for n in graph.get("nodes", []):
        nid = n.get("id") or n.get("path", "")
        nodes.append({
            "id": nid,
            "type": n.get("type", "file"),
            "lang": n.get("lang"),
            "layer": n.get("layer"),
            "in_degree": fan_in.get(nid, 0),
        })
    stats = graph.get("stats") or {}
    row = conn.execute("SELECT files, edges, cycles, age_s, ts FROM graph_stats ORDER BY ts DESC LIMIT 1").fetchone()
    db_stats = dict(row) if row else {}
    return {"nodes": nodes, "edges": edges, "stats": {**stats, **db_stats}}


def match_graph_node(graph: dict, file_arg: str) -> str | None:
    nodes = graph.get("nodes", [])
    if not file_arg:
        return None
    key = file_arg.replace("\\", "/").lstrip("./")
    by_id = {n.get("id", ""): n for n in nodes}
    if key in by_id:
        return key
    ends = [n.get("id", "") for n in nodes if n.get("id", "").endswith(key)]
    if len(ends) == 1:
        return ends[0]
    return None


def api_graph_blast(project: str, file_arg: str, depth: int = 2) -> dict:
    graph = load_graph(project)
    if not graph:
        return {"target": file_arg, "direct_dependents": [], "transitive_count": 0, "blast_files": []}
    node = match_graph_node(graph, file_arg)
    if not node:
        return {"target": file_arg, "direct_dependents": [], "transitive_count": 0, "blast_files": [], "error": "not_found"}
    edges = [e for e in graph.get("edges", []) if e.get("type", "imports") == "imports"]
    direct = sorted({e["source"] for e in edges if e["target"] == node})
    seen, frontier = set(direct) | {node}, set(direct)
    for _level in range(2, max(2, depth + 1)):
        frontier = {e["source"] for e in edges if e["target"] in frontier} - seen
        if not frontier:
            break
        seen |= frontier
    blast = sorted(seen - {node})
    return {
        "target": node,
        "direct_dependents": direct,
        "transitive_count": len(blast),
        "blast_files": blast,
    }


def api_memory(conn) -> dict:
    facts = []
    for row in conn.execute(
            "SELECT m.fact_id, m.type, m.subject, m.bytes, m.confidence, m.scope, m.updated, "
            "(SELECT COUNT(*) FROM fact_injections fi WHERE fi.fact_id = m.fact_id) AS injections_count "
            "FROM memory_facts m ORDER BY m.updated DESC"):
        facts.append(dict(row))
    return {"facts": facts}


def api_experiences(conn) -> dict:
    out = []
    for row in conn.execute(
            "SELECT exp_id, title, tier, confidence, uses, successes, record_json FROM experiences ORDER BY created"):
        rec = dict(row)
        task = ""
        try:
            task = json.loads(rec.pop("record_json") or "{}").get("task", "")
        except ValueError:
            pass
        rec["task"] = task
        out.append(rec)
    return {"experiences": out}


def _has_artifact(sdlc_dir: str, name: str | None) -> bool:
    if not name:
        return True
    path = os.path.join(sdlc_dir, name)
    if os.path.exists(path):
        return True
    stem = name[:-3] if name.endswith(".md") else name
    try:
        return any(f.startswith(stem + "-") and f.endswith(".md") for f in os.listdir(sdlc_dir))
    except OSError:
        return False


def api_gates(project: str) -> dict:
    sdlc = os.path.join(common.agent_spec_dir(project), "sdlc")
    state = common.read_json(os.path.join(sdlc, "STATE.json"), {"gate": 0, "gate_name": "REQUIREMENTS"})
    gates = []
    for idx, (name, skill, artifact, _req) in enumerate(_GATES):
        gates.append({
            "gate": idx,
            "name": name,
            "skill": skill,
            "status": "ok" if _has_artifact(sdlc, artifact) else "missing",
            "artifact": artifact,
        })
    req_trace = []
    req_path = os.path.join(sdlc, "01-REQUIREMENTS.md")
    if os.path.isfile(req_path):
        try:
            text = open(req_path, encoding="utf-8").read()
        except OSError:
            text = ""
        for line in text.splitlines():
            if line.strip().startswith("REQ-"):
                req_trace.append(line.strip()[:120])
    return {
        "current_gate": int(state.get("gate", 0)),
        "current_gate_name": state.get("gate_name", "REQUIREMENTS"),
        "feature": state.get("feature"),
        "gates": gates,
        "req_trace": req_trace[:50],
    }


def api_run_events(project: str, run_id: str) -> dict:
    base = os.path.join(common.agent_spec_dir(project), "runs", run_id, "events.jsonl")
    events = []
    if not os.path.isfile(base):
        return {"run_id": run_id, "events": events}
    try:
        with open(base, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except ValueError:
                    continue
    except OSError:
        pass
    return {"run_id": run_id, "events": events}


def api_pricing(project: str) -> dict:
    path = os.path.join(common.agent_spec_dir(project), "pricing.json")
    data = common.read_json(path)
    if not data:
        data = {
            "active_preset": "placeholder",
            "as_of": "1970-01-01",
            "source": "default",
            "presets": {
                "placeholder": {
                    "input": 0,
                    "cache_read": 0,
                    "cache_write": 0,
                    "output": 0,
                }
            },
        }
    return data


def api_doctor(project: str) -> dict:
    global _doctor_cache
    now = time.time()
    if _doctor_cache and now - _doctor_cache[0] < 60:
        return _doctor_cache[1]
    script = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agent-spec-doctor.py")
    if not os.path.isfile(script):
        out = {"ok": False, "checks": [{"id": "doctor", "status": "FAIL", "message": "doctor script missing", "fix": ""}]}
        _doctor_cache = (now, out)
        return out
    try:
        proc = subprocess.run(
            [sys.executable, script, "--json"],
            cwd=project,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if proc.returncode != 0 and not proc.stdout.strip():
            out = {"ok": False, "checks": [{"id": "doctor", "status": "FAIL", "message": proc.stderr.strip()[:200], "fix": ""}]}
        else:
            out = json.loads(proc.stdout)
    except (subprocess.TimeoutExpired, ValueError, OSError) as exc:
        out = {"ok": False, "checks": [{"id": "doctor", "status": "FAIL", "message": str(exc), "fix": ""}]}
    _doctor_cache = (now, out)
    return out


def count_demo_seed(conn) -> int:
    try:
        return conn.execute("SELECT COUNT(*) FROM requests WHERE source = 'demo_seed'").fetchone()[0]
    except Exception:
        return 0


def api_status_bar(project: str, conn, active_jobs: int = 0) -> dict:
    # 1. Graph freshness
    graph_row = conn.execute("SELECT ts, age_s FROM graph_stats ORDER BY ts DESC LIMIT 1").fetchone()
    age_s = 0
    if graph_row:
        base_age = graph_row["age_s"] or 0
        try:
            ts_dt = datetime.strptime(graph_row["ts"][:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
            extra_s = max(0, int((datetime.now(timezone.utc) - ts_dt).total_seconds()))
            age_s = base_age + extra_s
        except Exception:
            age_s = base_age

    if age_s < 3600:
        graph_text = f"{max(1, age_s // 60)}m old"
    elif age_s < 86400:
        graph_text = f"{age_s // 3600}h old"
    else:
        graph_text = f"{age_s // 86400}d old"

    stale_graph = age_s > (7 * 86400)

    # 2. Hook dots
    hooks_file = os.path.join(project, ".cursor", "hooks.json")
    hooks_info = {
        "session_start": False,
        "pre_tool_use": False,
        "session_end": False,
        "git_reindex": False,
    }
    if os.path.isfile(hooks_file):
        try:
            hdata = common.read_json(hooks_file, {})
            hk = hdata.get("hooks", {})
            hooks_info["session_start"] = bool(hk.get("sessionStart"))
            hooks_info["pre_tool_use"] = bool(hk.get("preToolUse"))
            hooks_info["session_end"] = bool(hk.get("sessionEnd") or hk.get("stop"))
        except Exception:
            pass

    git_hooks_dir = os.path.join(project, ".git", "hooks")
    if os.path.isdir(git_hooks_dir):
        hooks_info["git_reindex"] = os.path.isfile(os.path.join(git_hooks_dir, "post-checkout"))
    else:
        hooks_info["git_reindex"] = True  # Not a git repo, so not missing

    # 3. Doctor dot
    doc = api_doctor(project)
    doc_status = "ok"
    if not doc.get("ok"):
        checks = doc.get("checks", [])
        if any(c.get("status") == "FAIL" for c in checks):
            doc_status = "fail"
        elif any(c.get("status") == "WARN" for c in checks):
            doc_status = "warn"

    # 4. Snapshot health
    snap_path = os.path.join(common.agent_spec_dir(project), "SESSION-SNAPSHOT.md")
    snap_size = os.path.getsize(snap_path) if os.path.isfile(snap_path) else 0
    rotation_due = snap_size > 40 * 1024

    return {
        "graph": {
            "age_s": age_s,
            "text": graph_text,
            "stale": stale_graph,
        },
        "hooks": hooks_info,
        "doctor": {
            "status": doc_status,
            "ok": doc_status == "ok",
        },
        "snapshot": {
            "size_bytes": snap_size,
            "rotation_due": rotation_due,
        },
        "active_jobs": active_jobs,
    }

