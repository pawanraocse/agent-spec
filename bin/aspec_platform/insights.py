"""Read models for the dashboard and the proof pack (D-012, D-021, D-022): plain SQL, no writes.

`home` -> KPI chips, `gaps` -> rule-based flags, `run_detail` -> timeline / tools / subagents.
Every flag and KPI carries ids, counts and rule names only - never prompt text or file paths.
Timestamps are ISO-8601 UTC strings, so string comparison orders them.
"""
from __future__ import annotations

import glob
import json
import os
from datetime import datetime, timedelta, timezone
from statistics import median

from . import common, savings

EDIT_TOOLS = ("StrReplace", "Write", "EditNotebook", "ApplyPatch", "Edit", "MultiEdit")
SPIKE_FACTOR = 3
SPIKE_MIN_OTHERS = 5
SPIKE_FLOOR_TOKENS = 1000
TOKENS = "(tokens_input + tokens_output + tokens_cache_read)"
DEFAULT_WEIGHTS = {k: v[0] for k, v in savings.WEIGHTS.items()}


def _now(now):
    return now or common.utc_now()


def _parse(ts):
    return datetime.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)


def _window(conn, since):
    runs, tokens = conn.execute("SELECT COUNT(*), COALESCE(SUM(%s), 0) FROM requests WHERE started >= ?" % TOKENS,
                                (since,)).fetchone()
    return {"runs": runs, "tokens": tokens}


def home(conn, now=None) -> dict:
    now = _now(now)
    today = now[:10]
    week = (_parse(now) - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S")
    graph = conn.execute("SELECT ts, files, edges, symbols, cycles, age_s FROM graph_stats "
                         "ORDER BY ts DESC LIMIT 1").fetchone()
    graph = dict(graph) if graph else None
    if graph:  # age at snapshot time plus the time since
        graph["age_s"] += max(0, int((_parse(now) - _parse(graph["ts"])).total_seconds()))
    learning = {}
    for row in conn.execute("SELECT created, successes, record_json FROM experiences WHERE created IS NOT NULL "
                            "ORDER BY created"):
        try:
            rec = json.loads(row["record_json"] or "{}")
        except ValueError:
            rec = {}
        tok = rec.get("tokens") or {}
        day = learning.setdefault(row["created"][:10], {"day": row["created"][:10], "experiences": 0,
                                                        "successes": 0, "corrections": 0, "_tokens": 0})
        day["experiences"] += 1
        day["successes"] += row["successes"]
        day["corrections"] += int(rec.get("corrections") or 0)
        day["_tokens"] += int(tok.get("input", 0)) + int(tok.get("output", 0))
    trend = []
    for day in sorted(learning.values(), key=lambda d: d["day"])[-14:]:
        day["avg_tokens"] = day.pop("_tokens") // day["experiences"]
        trend.append(day)
    try:
        demo_n = conn.execute("SELECT COUNT(*) FROM requests WHERE source = 'demo_seed'").fetchone()[0]
    except Exception:
        demo_n = 0
    return {"now": now, "today": _window(conn, today), "last_7d": _window(conn, week), "graph": graph,
            "seeded": demo_n > 0,
            "demo_seed_count": demo_n,
            "saved_vs_baseline": {k: v for k, v in savings.savings(conn, DEFAULT_WEIGHTS).items()
                                  if k in ("estimate", "saved_tokens", "saved_usd", "naive_tokens", "graph_tokens")},
            "learning": trend}


def gaps(conn, now=None, limit=200, project=None) -> list:
    """Split gaps (DEC-15 / AF-006): deterministic facts + AI-judged findings."""
    out = []
    # 1. Deterministic facts (allowed: exact status flags & security blocks)
    for r in conn.execute("SELECT s.request_id, s.name, r.started FROM steps s JOIN requests r USING (request_id) "
                          "WHERE s.status = 'failed'"):
        out.append({"rule": "step_failed", "kind": "fact", "request_id": r["request_id"], "ts": r["started"],
                    "detail": "step %s failed" % r["name"]})
    for r in conn.execute("SELECT request_id, status, started FROM requests WHERE status IN ('failed', 'partial')"):
        out.append({"rule": "run_failed", "kind": "fact", "request_id": r["request_id"], "ts": r["started"],
                    "detail": "run ended %s" % r["status"]})
    for r in conn.execute("SELECT ts, tool, pattern FROM quarantine_events"):
        out.append({"rule": "secret_path_blocked", "kind": "fact", "request_id": None, "ts": r["ts"],
                    "detail": "%s blocked on pattern %s" % (r["tool"], r["pattern"])})

    # 2. AI-judged findings from .agent-spec/metrics/reviews/*.json
    if project:
        reviews_dir = os.path.join(common.agent_spec_dir(project), "metrics", "reviews")
        if os.path.isdir(reviews_dir):
            for path in glob.glob(os.path.join(reviews_dir, "*.json")):
                try:
                    data = common.read_json(path, {})
                    sid = os.path.basename(path)[:-5]
                    for imp in data.get("improvements", []):
                        detail_text = imp if isinstance(imp, str) else imp.get("message", str(imp))
                        out.append({
                            "rule": "ai_review_finding",
                            "kind": "ai_judged",
                            "request_id": sid,
                            "ts": data.get("reviewed_at") or data.get("ts"),
                            "detail": detail_text,
                            "model": data.get("model", "ai-reviewer"),
                        })
                except Exception:
                    pass

    out.sort(key=lambda g: g["ts"] or "", reverse=True)
    return out[:limit]


def run_detail(conn, request_id):
    """Timeline, per-tool cost, subagent health and waterfall for one run; None when it does not exist."""
    row = conn.execute("SELECT * FROM requests WHERE request_id = ?", (request_id,)).fetchone()
    if row is None:
        return None
    run = dict(row)
    run.pop("transcript_path", None)
    steps = [dict(s) for s in conn.execute(
        "SELECT step_id, ordinal, kind, name, status, started, duration_ms, tokens_input, tokens_output, "
        "tokens_cache_read, bytes_in, whole_file FROM steps WHERE request_id = ? ORDER BY ordinal", (request_id,))]
    tools = {}
    for s in steps:
        t = tools.setdefault(s["name"], {"name": s["name"], "kind": s["kind"], "calls": 0, "tokens": 0,
                                         "bytes_in": 0, "whole_file_reads": 0, "failed": 0})
        t["calls"] += 1
        t["tokens"] += s["tokens_input"] + s["tokens_output"] + s["tokens_cache_read"]
        t["bytes_in"] += s["bytes_in"]
        t["whole_file_reads"] += s["whole_file"]
        t["failed"] += 1 if s["status"] == "failed" else 0
    events = []
    if run.get("run_id"):
        events = [dict(e) for e in conn.execute(
            "SELECT ts, seq, type, step_id, tokens_input, tokens_output, duration_ms FROM events "
            "WHERE run_id = ? ORDER BY ts, seq LIMIT 500", (run["run_id"],))]
    subagents = [dict(a) for a in conn.execute(
        "SELECT agent, model, status, latency_ms, error FROM subagent_runs WHERE parent_request_id = ? "
        "ORDER BY started, id", (request_id,))]
    return {"run": run, "steps": steps, "events": events, "subagents": subagents,
            "tools": sorted(tools.values(), key=lambda t: (-t["tokens"], t["name"])),
            "waterfall": [{"name": s["name"], "kind": s["kind"], "ordinal": s["ordinal"], "status": s["status"],
                           "duration_ms": s["duration_ms"],
                           "tokens": s["tokens_input"] + s["tokens_output"] + s["tokens_cache_read"]} for s in steps]}


def _skill_frontmatter(path: str) -> dict:
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return {}
    if not lines or lines[0].strip() != "---":
        return {}
    meta = {}
    current_key = None
    multiline = []
    for line in lines[1:]:
        if line.strip() == "---":
            if current_key and multiline:
                meta[current_key] = " ".join(multiline).strip()
            break
        if line.startswith(" ") or line.startswith("\t"):
            if current_key:
                clean = line.strip()
                if clean:
                    multiline.append(clean)
            continue
        if current_key and multiline:
            meta[current_key] = " ".join(multiline).strip()
            multiline = []
            current_key = None
        key, sep, value = line.partition(":")
        if sep:
            k = key.strip()
            v = value.strip().strip("'\"")
            if v in (">", ">-", "|", "|-", ""):
                current_key = k
                multiline = []
            else:
                meta[k] = v
                current_key = k
    if current_key and multiline:
        meta[current_key] = " ".join(multiline).strip()
    if "name" in meta:
        meta["name"] = meta["name"].strip("'\"")
    return meta


def _skill_category(name: str) -> tuple[str, str]:
    nl = name.lower()
    if nl.startswith("agent-spec-wf-") or nl == "agent-spec-hub-runner":
        return "Workflows & Orchestration", "workflow"
    if any(k in nl for k in ("raw-code", "implement", "review", "solid", "self-review", "sdlc")):
        return "Coding & SDLC", "coding"
    if any(k in nl for k in ("learn", "remember", "compact", "snapshot", "persona", "debt")):
        return "Memory & Learning", "memory"
    if any(k in nl for k in ("prd", "tech-spec", "hld", "lld", "requirements", "intent", "doc-coauthoring")):
        return "Architecture & Specs", "architecture"
    if any(k in nl for k in ("blast-radius", "query-graph", "index-project", "investigate", "testing", "validation", "doctor", "prompt-audit")):
        return "Analysis & Safety", "analysis"
    return "Platform Tools", "platform"


def _skill_roots(project: str | None) -> list:
    roots = []
    for path in (os.path.expanduser("~/.cursor/skills"), os.path.expanduser("~/.cursor/skills-cursor")):
        if os.path.isdir(path):
            roots.append(path)
    if project:
        for rel in ("skills",):
            path = os.path.join(project, rel)
            if os.path.isdir(path):
                roots.append(path)
    return roots


def skills_catalog(conn, project: str | None = None) -> dict:
    """Installed skills (from SKILL.md headers) plus usage counts and categorization."""
    usage = [dict(r) for r in conn.execute(
        "SELECT s.name, COUNT(*) AS uses, MAX(r.started) AS last_used FROM steps s "
        "JOIN requests r ON r.request_id = s.request_id WHERE s.kind = 'skill' "
        "GROUP BY s.name ORDER BY uses DESC LIMIT 200")]
    usage_map = {u["name"]: u["uses"] for u in usage}
    seen = {}
    for root in _skill_roots(project):
        pattern = os.path.join(root, "**", "SKILL.md")
        for skill_md in glob.glob(pattern, recursive=True):
            folder = os.path.basename(os.path.dirname(skill_md))
            if folder in seen:
                continue
            meta = _skill_frontmatter(skill_md)
            name = meta.get("name") or folder
            desc = meta.get("description") or ""
            cat, tag = _skill_category(name)
            seen[folder] = {
                "id": folder,
                "name": name,
                "description": desc,
                "category": cat,
                "tag": tag,
                "uses": usage_map.get(name, 0),
                "is_workflow": name.startswith("agent-spec-wf-") or name == "agent-spec-hub-runner",
            }
    return {"skills": sorted(seen.values(), key=lambda s: (not s["is_workflow"], s["category"], s["name"].lower())), "usage": usage}


def session_detail(conn, session_id: str, project: str = None):
    """Plain-language session story: prompts, skills, tools, sub-agents, and a flow graph."""
    rows = conn.execute(
        "SELECT request_id, ordinal, substr(prompt_redacted, 1, 400) AS prompt, started, status, "
        "tokens_input, tokens_output, tokens_cache_read, workflow_id FROM requests "
        "WHERE session_id = ? ORDER BY ordinal", (session_id,)).fetchall()
    if not rows:
        return None
    story = []
    nodes = []
    edges = []
    for row in rows:
        r = dict(row)
        rid = r["request_id"]
        uid = "user-" + rid
        nodes.append({"id": uid, "label": "Developer Request", "type": "user", "detail": r.get("prompt") or ""})
        chain = uid
        steps = [dict(s) for s in conn.execute(
            "SELECT step_id, ordinal, kind, name, status, duration_ms, tokens_input, tokens_output FROM steps "
            "WHERE request_id = ? ORDER BY ordinal", (rid,))]
        skills, tools = [], []
        for s in steps:
            if s["kind"] == "skill":
                skills.append(s["name"])
                nid = "skill-" + s["step_id"]
                nodes.append({"id": nid, "label": s["name"], "type": "skill", "status": s["status"], "duration_ms": s["duration_ms"]})
                edges.append({"from": chain, "to": nid, "label": "skill routed"})
                chain = nid
            elif s["kind"] == "subagent":
                nid = "step-" + s["step_id"]
                nodes.append({"id": nid, "label": s["name"], "type": "subagent", "status": s["status"], "duration_ms": s["duration_ms"]})
                edges.append({"from": chain, "to": nid, "label": "task delegated"})
                chain = nid
            elif s["kind"] == "tool":
                tools.append(s["name"])
        agents = [dict(a) for a in conn.execute(
            "SELECT id, agent, model, status, latency_ms, error, child_request_id FROM subagent_runs "
            "WHERE parent_request_id = ? ORDER BY started, id", (rid,))]
        for sa in agents:
            nid = "agent-" + sa["id"]
            label = sa["agent"] or "helper agent"
            # Gather child steps/tools if available
            c_steps = []
            if sa.get("child_request_id"):
                c_steps = [dict(cs) for cs in conn.execute(
                    "SELECT kind, name, status, duration_ms FROM steps WHERE request_id = ? ORDER BY ordinal",
                    (sa["child_request_id"],))]
            sa["child_steps"] = c_steps
            nodes.append({"id": nid, "label": label, "type": "subagent", "status": sa["status"],
                          "detail": sa.get("error") or "", "model": sa.get("model"), "latency_ms": sa.get("latency_ms"),
                          "child_steps_count": len(c_steps)})
            edges.append({"from": chain, "to": nid, "label": "subagent executed"})
            chain = nid
        out_id = "answer-" + rid
        nodes.append({"id": out_id, "label": "Synthesized Result", "type": "assistant", "status": r["status"]})
        edges.append({"from": chain, "to": out_id, "label": "final result"})
        story.append({"request_id": rid, "ordinal": r["ordinal"], "prompt": r.get("prompt") or "",
                      "started": r.get("started"), "status": r["status"], "skills": skills,
                      "tools": tools[:20], "subagents": agents, "workflow_id": r.get("workflow_id"),
                      "tokens_total": (r.get("tokens_input") or 0) + (r.get("tokens_output") or 0) + (r.get("tokens_cache_read") or 0)})
    meta = dict(conn.execute(
        "SELECT MIN(started) AS started, COUNT(*) AS turns, COALESCE(SUM(%s), 0) AS tokens "
        "FROM requests WHERE session_id = ?" % TOKENS, (session_id,)).fetchone())
    # Calculate savings specific to this session
    session_savings = savings.savings(conn, DEFAULT_WEIGHTS, session_id=session_id)
    review_data = None
    if project:
        rev_path = os.path.join(common.agent_spec_dir(project), "metrics", "reviews", f"{session_id}.json")
        if os.path.isfile(rev_path):
            try:
                review_data = common.read_json(rev_path)
            except Exception:
                pass
    return {"session_id": session_id, "started": meta.get("started"), "turns": meta.get("turns"),
            "tokens": meta.get("tokens"), "savings": session_savings, "story": story,
            "review": review_data, "flow": {"nodes": nodes, "edges": edges}}
