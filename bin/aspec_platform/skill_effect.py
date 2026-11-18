"""Skill effectiveness (PI-011): per skill, how often it ran and how those requests went.

Per skill:
  requests       requests whose trace names the skill (measured)
  failure_rate   share of those requests that ended in error, or had a failed tool call (measured)
  rework_rate    share whose edited files were edited again later in the same chat (measured)
  quality        median `overall` score the session reviews gave those requests (ai_judged),
                 shown only once MIN_REVIEWED requests carry a score — below that,
                 "not enough data" rather than a number that would not survive the next review.

A baseline row ("no skill") holds requests that ran no skill, so a skill's numbers have
something to be compared with. Allowed-code reason (DEC-15): *exact* counts and a median.
"""
from __future__ import annotations

import json
import os
import statistics

from . import common, signals
from . import traces as tr

MIN_REVIEWED = 10
MIN_REQUESTS = 5
NO_SKILL = "(no skill)"


def _quality_by_trace(project: str) -> dict:
    folder = os.path.join(common.agent_spec_dir(project), "metrics", "reviews")
    out = {}
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return out
    for name in names:
        if not name.endswith(".json"):
            continue
        try:
            with open(os.path.join(folder, name), encoding="utf-8") as fh:
                review = json.load(fh)
        except (OSError, ValueError):
            continue
        for q in (review.get("quality") or []) if isinstance(review, dict) else []:
            if isinstance(q, dict) and q.get("trace_id") and isinstance(q.get("overall"), (int, float)):
                out[q["trace_id"]] = float(q["overall"])
    return out


def overview(project: str, conn=None) -> dict:
    all_t, all_s = tr.all_traces(project, conn)
    all_t = [t for t in all_t if t.get("origin") != "cli" and t.get("source") != "demo_seed"]
    by_trace, by_session = {}, {}
    for s in all_s:
        by_trace.setdefault(s["trace_id"], []).append(s)
    for t in all_t:
        by_session.setdefault(t.get("session_id"), []).append(t)
    quality = _quality_by_trace(project)
    rows = {}
    for t in all_t:
        spans = by_trace.get(t["trace_id"], [])
        session = by_session.get(t.get("session_id"), [t])
        sig = signals.for_trace(t, spans, session, [s for x in session for s in by_trace.get(x["trace_id"], [])])
        failed = t.get("status") in ("error", "failed") or sig["tool_failures"]["count"] > 0
        rework = bool((sig.get("rework_later") or {}).get("files"))
        for skill in (t.get("skills") or [NO_SKILL]):
            r = rows.setdefault(skill, {"skill": skill, "requests": 0, "failed": 0, "reworked": 0,
                                        "edited": 0, "scores": []})
            r["requests"] += 1
            r["failed"] += 1 if failed else 0
            if sig["files_edited"]["count"]:
                r["edited"] += 1
                r["reworked"] += 1 if rework else 0
            if t["trace_id"] in quality:
                r["scores"].append(quality[t["trace_id"]])
    out = []
    for r in rows.values():
        scores = r.pop("scores")
        enough = r["requests"] >= MIN_REQUESTS
        out.append(dict(
            r,
            failure_rate=round(r["failed"] / r["requests"], 3) if enough else None,
            rework_rate=round(r["reworked"] / r["edited"], 3) if enough and r["edited"] else None,
            reviewed=len(scores),
            quality=round(statistics.median(scores), 2) if len(scores) >= MIN_REVIEWED else None,
            note=None if len(scores) >= MIN_REVIEWED else "not enough data (%d of %d reviewed requests)"
            % (len(scores), MIN_REVIEWED),
        ))
    out.sort(key=lambda r: (r["skill"] == NO_SKILL, -r["requests"]))
    return {"skills": out, "min_reviewed": MIN_REVIEWED, "min_requests": MIN_REQUESTS,
            "provenance": {"requests": "measured", "failure_rate": "measured", "rework_rate": "measured",
                           "quality": "ai_judged"}}
