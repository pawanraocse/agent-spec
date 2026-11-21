"""Today: the dashboard's landing page. What needs you, what the harness did for you, and the pulse.

Allowed-code reason (DEC-15): plumbing and exact counts only. Every item reads a view module
that already exists (risk, proposals, index health, live tests, hook coverage, reviews, memory,
automations, traces) and re-states its count. Nothing here judges a session or a fact: where a
judgement is needed, the item's action is a *skill* the user runs in Cursor or in the Console
(`/agent-spec-session-review`, `/agent-spec-investigate`, `/agent-spec-hook-probe`, ...), and
the skill writes the artifact the other pages read. Only actions that are exact (rebuild the
graph, refresh the mesh) call the server directly.

Each source runs in its own try block, so one unreadable log never blanks the page.
"""
from __future__ import annotations

import os
import re
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from . import common, traces

PULSE_DAYS = 14
RECENT = 8
UNREVIEWED_DAYS = 7     # chats this recent with no review are offered for one
UNREVIEWED_MIN_REQ = 2  # a one-question chat is not worth a review
SNAPSHOT_STALE_H = 24   # requests newer than the last snapshot by this much -> offer /agent-spec-snapshot

# Rank: what blocks the agent first, then what is broken, then what would make it better.
LEVELS = {"blocked": 0, "broken": 1, "improve": 2}


def _guard(errors: list, name: str, fn, default=None):
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001 — one source never blanks the page
        errors.append("%s: %s" % (name, str(exc)[:160]))
        return default


def _iso_day(ts) -> str | None:
    return ts[:10] if isinstance(ts, str) and len(ts) >= 10 else None


def _short(text, n=90) -> str:
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    return text if len(text) <= n else text[: n - 1] + "…"


def _item(level, key, title, detail, action, link=None, count=None) -> dict:
    return {"id": key, "level": level, "title": title, "detail": detail, "action": action,
            "link": link, "count": count}


def _skill(command: str, prompt: str, console: bool = False) -> dict:
    """A skill the user runs. `console` = read-only, so the dashboard's Agent Console can run it too."""
    return {"kind": "skill", "command": command, "prompt": prompt, "console": console}


def _api(label: str, path: str, body: dict) -> dict:
    return {"kind": "api", "label": label, "path": path, "body": body}


def _link(label: str, to: str) -> dict:
    return {"kind": "link", "label": label, "to": to}


# ---------------------------------------------------------------- attention

def _attention(project, conn, errors, all_t) -> list:
    from . import health, livetest_view, observe, platform_data, proposals, risk_view

    items = []

    risk = _guard(errors, "risk", lambda: risk_view.overview(project), {}) or {}
    pending = risk.get("pending") or []
    if pending:
        top = pending[0]
        items.append(_item("blocked", "risk", "%d risky edit%s waiting for approval" % (len(pending), "" if len(pending) == 1 else "s"),
                           "The guard stopped a %s of %s (tier %s: %s)." % (
                               str(top.get("tool") or "change").lower(), top.get("file") or os.path.basename(str(top.get("target") or "")) or "a file",
                               top.get("tier", 3), _short(", ".join(top.get("reasons") or []) or "shared code", 80)),
                           _link("Review", "/risk"), "/risk", len(pending)))

    props = _guard(errors, "proposals", lambda: proposals.overview(project), {}) or {}
    pp = props.get("pending") or []
    if pp:
        items.append(_item("blocked", "proposals", "%d learning proposal%s to decide" % (len(pp), "" if len(pp) == 1 else "s"),
                           "Facts and workflow skills the learning loop suggested. Nothing applies until you click.",
                           _link("Open inbox", "/proposals"), "/proposals", len(pp)))

    hl = _guard(errors, "index-health", lambda: health.overview(project, None), {}) or {}
    g = hl.get("graph") or {}
    if g.get("state") in ("missing", "failed", "behind"):
        detail = {"missing": "No dependency graph yet: graph-first answers fall back to file reads.",
                  "failed": "The last background build failed: %s" % _short(g.get("error") or "see Index health", 120),
                  "behind": "HEAD moved since the graph was built, so blast radius may miss new files."}[g["state"]]
        items.append(_item("broken", "graph", "Knowledge graph is %s" % {"missing": "missing", "failed": "failing", "behind": "behind HEAD"}[g["state"]],
                           detail, _api("Rebuild graph", "/api/index-health", {"action": "rebuild-graph"}), "/project/index"))
    mesh = hl.get("mesh") or {}
    if mesh.get("drifted"):
        items.append(_item("broken", "mesh", "%d mesh repo%s moved since the mesh was built" % (mesh["drifted"], "" if mesh["drifted"] == 1 else "s"),
                           "Cross-repo blast radius is computed from the old commits.",
                           _api("Refresh mesh", "/api/index-health", {"action": "refresh-mesh"}), "/project/repos"))

    live = _guard(errors, "livetest", lambda: livetest_view.overview(project), {}) or {}
    latest = live.get("latest") or {}
    failed = [c for c in latest.get("cases") or [] if c.get("status") == "FAIL"]
    if failed and not live.get("running"):
        c = failed[0]
        prompt = ("Live test %s (%s) failed on %s: %s. Criterion: %s. Find the cause in bin/agent-spec-livetest.py and the "
                  "code that case exercises; name the file and line, and propose the smallest fix." % (
                      c.get("id"), c.get("title"), c.get("model") or "the local model", _short(c.get("error"), 300), c.get("criterion")))
        items.append(_item("broken", "livetest", "%d live test%s failing" % (len(failed), "" if len(failed) == 1 else "s"),
                           "%s %s — %s" % (c.get("id"), c.get("title"), _short(c.get("error"), 140)),
                           _skill("/agent-spec-investigate", "/agent-spec-investigate " + prompt, console=True), "/project/live", len(failed)))

    bar = _guard(errors, "status", lambda: platform_data.api_status_bar(project, conn), {}) if conn is not None else {}
    cov = (bar or {}).get("hook_coverage") or {}
    probe_missing = [ev for ev in cov.get("missing") or [] if "hook-probe" in str((cov.get("hints") or {}).get(ev, ""))]
    if cov.get("registered") and not cov.get("fired"):
        items.append(_item("improve", "hooks", "No Cursor hook has fired in this project yet",
                           "Open the folder in Cursor with Hooks enabled and send one chat; the probe then proves all %d." % cov["registered"],
                           _skill("/agent-spec-hook-probe", "/agent-spec-hook-probe"), "/project/health"))
    elif cov.get("action_needed") or probe_missing:
        items.append(_item("broken" if cov.get("action_needed") else "improve", "hooks",
                           "%d of %d Cursor hooks never fired" % (cov.get("registered", 0) - cov.get("fired", 0), cov.get("registered", 0)),
                           "Unproven: %s. Traces miss what those hooks record; the probe fires each one." % ", ".join(cov.get("missing") or []),
                           _skill("/agent-spec-hook-probe", "/agent-spec-hook-probe"), "/project/health"))
    doctor = (bar or {}).get("doctor") or {}
    if doctor.get("status") in ("fail", "warn"):
        items.append(_item("broken", "doctor", "Doctor reports %s" % doctor["status"], "Install or registry problem; the Health page lists each check.",
                           _link("Open Health", "/project/health"), "/project/health"))

    # Chats nobody reviewed: the Coach and Learning pages are empty without reviews, and a review
    # is a judgement, so the action is the review skill, one chat per click.
    reviewed = {r["session_id"] for r in _guard(errors, "reviews", lambda: observe.reviews(project), []) or []}
    cutoff = (datetime.now(timezone.utc) - timedelta(days=UNREVIEWED_DAYS)).strftime("%Y-%m-%d")
    chats = defaultdict(lambda: {"n": 0, "last": "", "prompt": ""})
    for t in all_t:
        if t.get("source") != "hook" or t.get("origin") == "cli" or not t.get("prompt") or t.get("status") == "demo_seed":
            continue
        c = chats[t.get("session_id")]
        c["n"] += 1
        if (t.get("start") or "") > c["last"]:
            c["last"] = t.get("start") or ""
        if not c["prompt"]:
            c["prompt"] = t["prompt"]
    todo = sorted(((sid, c) for sid, c in chats.items()
                   if sid and sid not in reviewed and c["n"] >= UNREVIEWED_MIN_REQ and c["last"][:10] >= cutoff),
                  key=lambda kv: kv[1]["last"], reverse=True)
    if todo:
        sid, c = todo[0]
        items.append(_item("improve", "review", "%d recent chat%s never reviewed" % (len(todo), "" if len(todo) == 1 else "s"),
                           "Newest: “%s” (%d requests). Reviews feed Coach, Learning and skill quality." % (_short(c["prompt"], 70), c["n"]),
                           _skill("/agent-spec-session-review", "/agent-spec-session-review %s" % sid), "/chats/%s" % sid, len(todo)))

    if conn is not None:
        learn = _guard(errors, "learning", lambda: observe.learning(project, conn), {}) or {}
        if learn.get("unlinked") and learn.get("reviewed_sessions"):
            items.append(_item("improve", "facts", "%d memory facts not linked to a mistake class" % learn["unlinked"],
                               "Learning cannot tell whether a fact prevents a repeat until it names the finding it addresses.",
                               _skill("/agent-spec-learn", "/agent-spec-learn link: for each fact in .agent-spec/memory/facts/ that prevents a "
                                      "mistake, name the agent-spec-session-review category it addresses and re-record it with "
                                      "/agent-spec-remember --addresses <category>."), "/learning", learn["unlinked"]))

    snap = os.path.join(common.agent_spec_dir(project), "SESSION-SNAPSHOT.md")
    try:
        snap_ts = os.path.getmtime(snap)
    except OSError:
        snap_ts = None
    newest = max((t.get("start") or "" for t in all_t if t.get("source") == "hook" and t.get("prompt")), default="")
    if newest:
        try:
            newest_ts = datetime.strptime(newest[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp()
        except ValueError:
            newest_ts = None
        if newest_ts and (snap_ts is None or newest_ts - snap_ts > SNAPSHOT_STALE_H * 3600):
            items.append(_item("improve", "snapshot", "Work since the last session snapshot is not handed off",
                               "The next chat starts without it. A snapshot also promotes durable facts to memory.",
                               _skill("/agent-spec-snapshot", "/agent-spec-snapshot"), None))

    gates = _guard(errors, "gates", lambda: platform_data.api_gates(project), {}) or {}
    if gates.get("feature"):
        items.append(_item("improve", "sdlc", "SDLC pipeline in flight: %s" % _short(gates["feature"], 60),
                           "Gate %s %s is due." % (gates.get("current_gate"), gates.get("current_gate_name") or ""),
                           _skill("/agent-spec-sdlc", "/agent-spec-sdlc"), "/project/health"))

    items.sort(key=lambda i: LEVELS.get(i["level"], 9))
    return items


# ---------------------------------------------------------------- pulse and value

def _pulse(all_t) -> list:
    today = datetime.now(timezone.utc).date()
    days = {(today - timedelta(days=i)).isoformat(): {"requests": 0, "tools": 0, "errors": 0, "guard": 0, "local": 0}
            for i in range(PULSE_DAYS - 1, -1, -1)}
    for t in all_t:
        d = days.get(_iso_day(t.get("start")) or "")
        if d is None or t.get("status") == "demo_seed" or t.get("origin") == "cli":
            continue
        d["requests"] += 1
        d["tools"] += t.get("tool_count") or 0
        d["errors"] += t.get("error_count") or 0
        d["guard"] += t.get("guard_count") or 0
        d["local"] += 1 if t.get("origin") == "local" else 0
    return [dict(day=k, **v) for k, v in days.items()]


def _value(project, conn, errors, all_t, all_s) -> dict:
    from . import automations, memory_view, skill_savings

    sv = _guard(errors, "skill-savings", lambda: skill_savings.overview(project, conn, all_t, all_s), {}) or {}
    auto = _guard(errors, "automations", lambda: automations.overview(project), {}) or {}
    facts = _guard(errors, "memory", lambda: memory_view.facts(project, conn), []) or []
    real = [t for t in all_t if t.get("status") != "demo_seed" and t.get("origin") != "cli"]
    week = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
    totals = auto.get("totals") or {}
    titles = {a.get("id"): a.get("title") for a in auto.get("automations") or []}
    return {
        "requests": len(real),
        "requests_7d": sum(1 for t in real if (t.get("start") or "")[:10] >= week),
        "chats": len({t.get("session_id") for t in real}),
        "kept_out": sv.get("kept_out"), "resend_avoided": sv.get("resend_avoided"),
        "by_lever": sv.get("by_lever") or {}, "labels": sv.get("labels") or {},
        "guard_blocks": sum(t.get("guard_count") or 0 for t in real),
        "tool_calls": sum(t.get("tool_count") or 0 for t in real),
        "subagents": sum(t.get("subagent_count") or 0 for t in real),
        "facts": len(facts),
        "facts_injected": sum(int(f.get("injections_count") or 0) for f in facts if isinstance(f, dict)),
        "automation_runs": totals.get("runs"), "automations_on": totals.get("enabled"),
        "automations_total": len(auto.get("automations") or []),
        "autopilot": _autopilot(auto.get("recent") or [], titles),
        "provenance": {"kept_out": "estimated", "resend_avoided": "estimated", "rest": "measured"},
    }


def _autopilot(rows: list, titles: dict, limit: int = 6) -> list:
    """Newest first; repeats of the same step with the same outcome fold into one row with a count,
    so ten no-op graph refreshes do not hide the one skill sync that mattered."""
    out, seen = [], {}
    for r in rows:
        key = (r.get("name"), r.get("status"), r.get("reason"))
        if key in seen:
            seen[key]["times"] += 1
            continue
        if len(out) == limit:
            continue
        row = {"ts": r.get("ts"), "id": r.get("name"), "label": titles.get(r.get("name"), r.get("name")),
               "status": r.get("status"), "reason": _short(r.get("reason"), 80), "ms": r.get("duration_ms"), "times": 1}
        seen[key] = row
        out.append(row)
    return out


def _recent(all_t) -> list:
    rows = sorted((t for t in all_t if t.get("prompt") and t.get("status") != "demo_seed" and t.get("origin") != "cli"),
                  key=lambda t: t.get("start") or "", reverse=True)[:RECENT]
    return [{"trace_id": t["trace_id"], "session_id": t.get("session_id"), "prompt": _short(t.get("prompt"), 140),
             "status": t.get("status"), "start": t.get("start"), "duration_ms": t.get("duration_ms"),
             "skills": t.get("skills") or [], "tools": t.get("tool_count") or 0, "errors": t.get("error_count") or 0,
             "guard": t.get("guard_count") or 0, "subagents": t.get("subagent_count") or 0,
             "model": t.get("model"), "origin": t.get("origin")} for t in rows]


def _skills(all_t) -> list:
    c = Counter()
    last = {}
    for t in all_t:
        if t.get("status") == "demo_seed":
            continue
        for s in t.get("skills") or []:
            c[s] += 1
            last[s] = max(last.get(s, ""), t.get("start") or "")
    return [{"skill": s, "uses": n, "last": last.get(s)} for s, n in c.most_common(6)]


def overview(project: str, conn) -> dict:
    errors: list = []
    started = time.monotonic()
    all_t, all_s = _guard(errors, "traces", lambda: traces.all_traces(project, conn), ([], [])) or ([], [])
    from . import health
    g = _guard(errors, "graph", lambda: health.graph_health(project), {}) or {}
    attention = _attention(project, conn, errors, all_t)
    return {
        "project": {"name": os.path.basename(os.path.abspath(project)), "branch": (g.get("head") or {}).get("branch"),
                    "sha": ((g.get("head") or {}).get("sha") or "")[:7] or None, "graph": g.get("state")},
        "attention": attention,
        "counts": {lvl: sum(1 for i in attention if i["level"] == lvl) for lvl in LEVELS},
        "value": _value(project, conn, errors, all_t, all_s),
        "pulse": _pulse(all_t),
        "recent": _recent(all_t),
        "skills": _skills(all_t),
        "errors": errors,
        "ms": int((time.monotonic() - started) * 1000),
    }
