"""Coach, Learning, Panels and Catalog read models (DEC-16 §14.6-§14.7; DV-041, DV-050, DV-055, DV-056).

Judgement is never made here. Findings, their categories and fix prompts come from the
`agent-spec-session-review` skill (`.agent-spec/metrics/reviews/<conversation_id>.json`), and
which finding class a memory fact addresses comes from the model at `/agent-spec-remember`
(`addresses:` frontmatter). This module only groups and counts.

Allowed-code reason: exact computation (counts, windows, trends) and plumbing (file reads,
schema validation of panel files).
"""
from __future__ import annotations

import glob
import json
import os
import re
from datetime import datetime, timedelta, timezone

from . import common, traces

SEVERITY = {"high": 3, "medium": 2, "low": 1}
PANEL_TYPES = ("kpi", "table", "timeline")
PROVENANCE = ("measured", "estimated", "ai_judged", "demo_seed")
_SLUG = re.compile(r"[^a-z0-9_]+")


def _slug(text) -> str:
    return _SLUG.sub("_", str(text or "").lower()).strip("_")[:48] or "uncategorised"


def _read_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def reviews(project) -> list:
    """Every review file, normalised to {session_id, reviewed_at, grade, model, findings[]}.
    Rubric 2.x files carry `findings`; 1.x files carry `evidence` verdicts, mapped one-to-one."""
    out = []
    for path in sorted(glob.glob(os.path.join(common.agent_spec_dir(project), "metrics", "reviews", "*.json"))):
        data = _read_json(path)
        if not isinstance(data, dict):
            continue
        sid = str(data.get("conversation_id") or data.get("session_id") or os.path.basename(path)[:-5])
        findings = []
        for f in data.get("findings") or []:
            if isinstance(f, dict):
                findings.append({"category": _slug(f.get("category")), "severity": str(f.get("severity") or "medium"),
                                 "title": str(f.get("title") or f.get("category") or "")[:200],
                                 "detail": str(f.get("detail") or "")[:600], "span_id": f.get("span_id"),
                                 "trace_id": f.get("trace_id"), "fix_prompt": str(f.get("fix_prompt") or "")[:400]})
        if not findings:
            for e in data.get("evidence") or []:
                if isinstance(e, dict) and e.get("verdict") in ("warn", "fail"):
                    findings.append({"category": _slug(e.get("check")), "severity": "high" if e["verdict"] == "fail" else "medium",
                                     "title": str(e.get("check") or "")[:200], "detail": str(e.get("note") or "")[:600],
                                     "span_id": e.get("span_id") or e.get("event_id"), "trace_id": e.get("trace_id"),
                                     "fix_prompt": ""})
        out.append({"session_id": sid, "reviewed_at": data.get("reviewed_at"),
                    "session_started": data.get("session_started") or data.get("reviewed_at"),
                    "grade": data.get("grade"), "score": data.get("score"), "model": data.get("model"),
                    "rubric_version": data.get("rubric_version"), "summary": data.get("summary"),
                    "findings": findings})
    out.sort(key=lambda r: r.get("session_started") or "")
    return out


def _week(ts) -> str:
    try:
        d = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return "unknown"
    y, w, _ = d.isocalendar()
    return "%d-W%02d" % (y, w)


def coach_issues(project, conn=None, top: int = 3, weeks: int = 6) -> dict:
    """Top issues across reviewed sessions (AI-judged findings, counted exactly) with a weekly trend."""
    revs = reviews(project)
    now = datetime.now(timezone.utc)
    week_keys = [_week((now - timedelta(weeks=i)).isoformat()) for i in range(weeks - 1, -1, -1)]
    groups = {}
    for r in revs:
        for f in r["findings"]:
            g = groups.setdefault(f["category"], {"category": f["category"], "count": 0, "sessions": set(),
                                                   "severity": 0, "trend": {k: 0 for k in week_keys},
                                                   "examples": [], "fix_prompt": "", "title": f["title"]})
            g["count"] += 1
            g["sessions"].add(r["session_id"])
            g["severity"] = max(g["severity"], SEVERITY.get(f["severity"], 2))
            wk = _week(r.get("session_started"))
            if wk in g["trend"]:
                g["trend"][wk] += 1
            if f.get("fix_prompt"):
                g["fix_prompt"] = f["fix_prompt"]
            g["examples"].append({"session_id": r["session_id"], "trace_id": f.get("trace_id"),
                                  "span_id": f.get("span_id"), "title": f["title"], "detail": f["detail"]})
    issues = []
    for g in groups.values():
        trend = [{"week": k, "count": v} for k, v in g["trend"].items()]
        issues.append({"category": g["category"], "title": g["title"], "count": g["count"],
                       "sessions": len(g["sessions"]), "severity": {3: "high", 2: "medium", 1: "low"}[g["severity"]],
                       "trend": trend, "examples": g["examples"][-5:][::-1], "fix_prompt": g["fix_prompt"],
                       "provenance": "ai_judged"})
    issues.sort(key=lambda i: (-(i["count"] * SEVERITY[i["severity"]]), i["category"]))
    graded = [r for r in revs if r.get("grade")]
    return {"reviewed_sessions": len(revs), "issues": issues[:top], "all_categories": len(issues),
            "grades": [{"session_id": r["session_id"], "grade": r["grade"], "score": r["score"],
                        "reviewed_at": r["reviewed_at"], "model": r["model"]} for r in graded][-20:],
            "provenance": "ai_judged"}


# ---- Learning (DV-050, exact) -----------------------------------------------------------------

def _frontmatter(path) -> dict:
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            lines = fh.read(8192).splitlines()
    except OSError:
        return {}
    if not lines or lines[0].strip() != "---":
        return {}
    meta = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        key, sep, val = line.partition(":")
        if sep and not line.startswith((" ", "\t")):
            meta[key.strip()] = val.strip().strip("\"'")
    return meta


def _list(val):
    if isinstance(val, list):
        return [_slug(v) for v in val if v]
    val = str(val or "").strip().strip("[]")
    return [_slug(v) for v in val.split(",") if v.strip()]


def learners(project) -> list:
    """Memory facts and experiences with their creation date and the finding classes they address."""
    spec = common.agent_spec_dir(project)
    out = []
    for path in sorted(glob.glob(os.path.join(spec, "memory", "facts", "*.md"))):
        m = _frontmatter(path)
        out.append({"id": m.get("id") or os.path.basename(path)[:-3], "kind": "fact", "type": m.get("type") or "",
                    "subject": m.get("subject") or "", "created": m.get("created") or "",
                    "addresses": _list(m.get("addresses")), "status": m.get("status") or "active"})
    for path in sorted(glob.glob(os.path.join(spec, "experiences", "**", "*.json"), recursive=True)):
        e = _read_json(path)
        if isinstance(e, dict):
            out.append({"id": str(e.get("id") or e.get("exp_id") or os.path.basename(path)[:-5]), "kind": "experience",
                        "type": str(e.get("tier") or "candidate"), "subject": str(e.get("title") or e.get("signature") or ""),
                        "created": str(e.get("created") or ""), "addresses": _list(e.get("addresses")),
                        "status": str(e.get("tier") or "candidate")})
    return out


def recurrence(project, window: int = 10) -> list:
    """For each learner that names `addresses`: matching findings per session in the `window`
    reviewed sessions before it was created against the `window` after. Flat stays flat."""
    revs = reviews(project)
    out = []
    for item in learners(project):
        if not item["addresses"] or not item["created"]:
            continue
        before = [r for r in revs if (r.get("session_started") or "") < item["created"]][-window:]
        after = [r for r in revs if (r.get("session_started") or "") >= item["created"]][:window]

        def hits(rs):
            return sum(1 for r in rs for f in r["findings"] if f["category"] in item["addresses"])

        b, a = hits(before), hits(after)
        out.append({"id": item["id"], "kind": item["kind"], "subject": item["subject"], "created": item["created"],
                    "addresses": item["addresses"], "before_sessions": len(before), "after_sessions": len(after),
                    "before_findings": b, "after_findings": a,
                    "before_rate": round(b / len(before), 3) if before else None,
                    "after_rate": round(a / len(after), 3) if after else None,
                    "verdict": ("insufficient data" if not before or not after else
                                "fewer" if a / len(after) < b / len(before) else
                                "more" if a / len(after) > b / len(before) else "flat"),
                    "provenance": "measured"})
    return out


def learning(project, conn=None, window: int = 10) -> dict:
    items = learners(project)
    by_month = {}
    for i in items:
        if i["kind"] == "fact" and i["created"]:
            by_month[i["created"][:7]] = by_month.get(i["created"][:7], 0) + 1
    injections = []
    if conn is not None:
        try:
            injections = [dict(r) for r in conn.execute(
                "SELECT r.request_id, r.started, COUNT(f.fact_id) AS facts FROM requests r "
                "JOIN fact_injections f ON f.request_id = r.request_id GROUP BY r.request_id "
                "ORDER BY r.started DESC LIMIT 30")]
        except Exception:
            injections = []
    tiers = {}
    for i in items:
        if i["kind"] == "experience":
            tiers[i["type"]] = tiers.get(i["type"], 0) + 1
    rec = recurrence(project, window)
    return {"recurrence": rec, "window": window, "unlinked": sum(1 for i in items if not i["addresses"]),
            "facts_total": sum(1 for i in items if i["kind"] == "fact"),
            "facts_by_month": [{"month": k, "count": v} for k, v in sorted(by_month.items())],
            "experience_tiers": tiers, "injections": injections[::-1],
            "reviewed_sessions": len(reviews(project))}


# ---- Panels (DV-056) and catalog (DV-055) ------------------------------------------------------

def validate_panel(data) -> str | None:
    """None when the panel is valid, else the reason. Shapes: kpi | table | timeline."""
    if not isinstance(data, dict):
        return "not an object"
    if data.get("type") not in PANEL_TYPES:
        return "type must be one of %s" % ", ".join(PANEL_TYPES)
    if not data.get("title"):
        return "title is required"
    if data.get("provenance") not in PROVENANCE:
        return "provenance must be one of %s" % ", ".join(PROVENANCE)
    if data["type"] == "kpi" and not isinstance(data.get("value"), (int, float, str)):
        return "kpi needs a value"
    if data["type"] == "table" and not (isinstance(data.get("columns"), list) and isinstance(data.get("rows"), list)):
        return "table needs columns[] and rows[]"
    if data["type"] == "timeline" and not isinstance(data.get("events"), list):
        return "timeline needs events[]"
    return None


def panels(project) -> dict:
    root = os.path.join(common.agent_spec_dir(project), "metrics", "panels")
    ok, bad = [], []
    for path in sorted(glob.glob(os.path.join(root, "*", "*.json")))[:200]:
        skill = os.path.basename(os.path.dirname(path))
        data = _read_json(path)
        why = validate_panel(data)
        entry = {"skill": skill, "file": os.path.relpath(path, root)}
        if why:
            bad.append(dict(entry, error=why))
        else:
            ok.append(dict(entry, panel=data, mtime=int(os.path.getmtime(path))))
    return {"panels": ok, "invalid": bad}


def _dashboard_block(path) -> dict:
    """The `dashboard:` mapping from a SKILL.md frontmatter (one level, plus `- item` lists)."""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            lines = fh.read(16384).splitlines()
    except OSError:
        return {}
    if not lines or lines[0].strip() != "---":
        return {}
    block, inside, key = {}, False, None
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if not line.startswith((" ", "\t")):
            inside = line.split(":", 1)[0].strip() == "dashboard"
            continue
        if not inside or not line.strip():
            continue
        stripped = line.strip()
        if stripped.startswith("- ") and key:
            block.setdefault(key, [])
            if isinstance(block[key], list):
                block[key].append(stripped[2:].strip().strip("\"'"))
            continue
        k, sep, v = stripped.partition(":")
        if sep:
            key = k.strip()
            v = v.strip()
            if v.startswith("[") and v.endswith("]"):
                block[key] = [x.strip().strip("\"'") for x in v[1:-1].split(",") if x.strip()]
            elif v:
                block[key] = v.strip("\"'")
    return block


def catalog(project, conn=None) -> dict:
    """Skills with their `dashboard:` self-description, defaults when absent, and trace usage."""
    from . import insights
    roots = insights._skill_roots(project)
    seen = {}
    for root in roots:
        for path in glob.glob(os.path.join(root, "**", "SKILL.md"), recursive=True):
            folder = os.path.basename(os.path.dirname(path))
            if folder in seen:
                continue
            meta = insights._skill_frontmatter(path)
            dash = _dashboard_block(path)
            name = meta.get("name") or folder
            cat, _tag = insights._skill_category(name)
            seen[folder] = {"id": folder, "name": name, "description": (meta.get("description") or "")[:300],
                            "category": dash.get("category") or cat, "icon": dash.get("icon") or "sparkles",
                            "emits": dash.get("emits") if isinstance(dash.get("emits"), list) else [],
                            "steps": dash.get("steps") if isinstance(dash.get("steps"), list) else [],
                            "self_described": bool(dash), "is_workflow": name.startswith("agent-spec-wf-")}
    try:
        all_t, _ = traces.all_traces(project, conn)
    except Exception:
        all_t = []
    uses = {}
    for t in all_t:
        for s in t.get("skills") or []:
            uses[s] = uses.get(s, 0) + 1
    for s in seen.values():
        s["uses"] = uses.get(s["name"], 0) + uses.get(s["id"], 0)
    return {"skills": sorted(seen.values(), key=lambda s: (s["category"], s["name"])),
            "self_described": sum(1 for s in seen.values() if s["self_described"])}
