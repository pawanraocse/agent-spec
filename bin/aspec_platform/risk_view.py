"""Risk panel and approvals for the dashboard (H-030, P4-016, P3-012).

Reads what the preToolUse risk gate wrote: pending tier-3 actions in
`.agent-spec/risk/approvals.json` and every blocked / warned / approved / denied / used event
in `metrics/risk.jsonl` (the approval trail). Decisions go through agent-spec-risk.py itself,
loaded by path, so the hook and the dashboard share one lock and one file format.

Allowed-code reason (DEC-15): *exact* — counts of logged events; no model.
"""
from __future__ import annotations

import importlib.util
import json
import os
from collections import Counter

from . import common

RECENT = 50


def _risk_module(project: str):
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for path in (os.path.join(common.agent_spec_dir(project), "bin", "agent-spec-risk.py"),
                 os.path.join(here, "agent-spec-risk.py")):
        if os.path.isfile(path):
            spec = importlib.util.spec_from_file_location("agent_spec_risk", path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    return None


def _events(project: str) -> list:
    path = os.path.join(common.agent_spec_dir(project), "metrics", "risk.jsonl")
    rows = []
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict) and row.get("event"):
                    rows.append(row)
    except OSError:
        pass
    return rows


def overview(project: str) -> dict:
    risk = _risk_module(project)
    events = _events(project)
    pending = risk.pending(project) if risk else []
    counts = Counter(e["event"] for e in events)
    tiers = Counter(str(e.get("tier")) for e in events if e["event"] in ("blocked", "warned"))
    by_session = {}
    for e in events:
        if e["event"] in ("blocked", "warned") and e.get("session"):
            row = by_session.setdefault(e["session"], {"session": e["session"], "tier2": 0, "tier3": 0})
            row["tier%s" % e.get("tier")] = row.get("tier%s" % e.get("tier"), 0) + 1
    return {
        "enabled": risk is not None,
        "config": risk.config(project) if risk else None,
        "pending": pending,
        "counts": {k: counts.get(k, 0) for k in ("blocked", "warned", "approved", "denied", "used", "error")},
        "tiers": {"2": tiers.get("2", 0), "3": tiers.get("3", 0)},
        "sessions": sorted(by_session.values(), key=lambda r: -(r["tier3"] * 100 + r["tier2"]))[:20],
        "recent": list(reversed(events[-RECENT:])),
        "log": ".agent-spec/metrics/risk.jsonl",
        "provenance": "measured",
    }


def decide(project: str, key: str, decision: str) -> dict:
    if decision not in ("approve", "deny"):
        raise ValueError("decision must be approve or deny")
    risk = _risk_module(project)
    if risk is None:
        raise ValueError("this project has no risk classifier; re-run install.sh --register")
    try:
        entry = risk.decide(project, key, decision == "approve", by="dashboard")
    except KeyError:
        raise ValueError("no pending action %s (already decided, or never blocked)" % key)
    return {"ok": True, "decision": decision, "action": entry}
