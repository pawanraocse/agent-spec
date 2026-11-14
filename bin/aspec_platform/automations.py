"""Automations panel (HA-006): what the harness ran on its own, and the switches for it.

Each automation is a step a person or the model used to have to remember. The hooks and
`agent-spec-ensure.py` append one row per run to `.agent-spec/metrics/automation.jsonl` and
skip any automation listed in `.agent-spec/automation.json` {"disabled": [...]}. This module
reads both and writes only the config. Every count is measured from the log; nothing is
estimated. Allowed-code reason: plumbing (DEC-15).
"""
from __future__ import annotations

import json
import os
import tempfile
import time
from collections import Counter

from . import common

# id -> what it replaces. `env` is an environment switch that wins over the panel.
REGISTRY: list[dict] = [
    {"id": "register", "title": "Register or refresh the harness", "trigger": "skill preflight",
     "kind": "script", "replaces": "running install.sh --register by hand in each project",
     "env": "AGENT_SPEC_AUTO_REGISTER"},
    {"id": "graph-refresh", "title": "Refresh the knowledge graph", "trigger": "stop after an edit or shell command; preflight when missing",
     "kind": "script", "replaces": "re-running the indexer after files move, appear or disappear", "env": None},
    {"id": "snapshot-rotate", "title": "Rotate the session snapshot", "trigger": "sessionEnd",
     "kind": "script", "replaces": "agent-spec-memory.py rotate after each snapshot", "env": None},
    {"id": "snapshot-followup", "title": "Record a session snapshot", "trigger": "stop on a long chat",
     "kind": "skill", "replaces": "remembering /agent-spec-snapshot before a chat ends", "env": None},
    {"id": "context-nudge", "title": "Suggest a fresh chat", "trigger": "stop when context passes break-even",
     "kind": "skill", "replaces": "guessing when a reset pays for itself", "env": "AGENT_SPEC_CONTEXT_NUDGE"},
]
IDS = frozenset(a["id"] for a in REGISTRY)
RECENT = 40
OK = frozenset(("ok", "installed", "built", "started", "sent"))


def _config_path(project: str) -> str:
    return os.path.join(common.agent_spec_dir(project), "automation.json")


def _log_path(project: str) -> str:
    return os.path.join(common.agent_spec_dir(project), "metrics", "automation.jsonl")


def disabled(project: str) -> set[str]:
    try:
        with open(_config_path(project), encoding="utf-8") as fh:
            return {str(x) for x in (json.load(fh).get("disabled") or [])}
    except (OSError, ValueError, AttributeError):
        return set()


def _rows(project: str) -> list[dict]:
    rows = []
    try:
        with open(_log_path(project), encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict) and row.get("name") in IDS:
                    rows.append(row)
    except OSError:
        pass
    return rows


def overview(project: str) -> dict:
    rows = _rows(project)
    off = disabled(project)
    by_name: dict[str, list[dict]] = {}
    for r in rows:
        by_name.setdefault(r["name"], []).append(r)
    items = []
    for spec in REGISTRY:
        mine = by_name.get(spec["id"], [])
        statuses = Counter(str(r.get("status")) for r in mine)
        durations = [r["duration_ms"] for r in mine if isinstance(r.get("duration_ms"), int)]
        env = spec["env"]
        env_off = bool(env) and os.environ.get(env) == "0"
        items.append(dict(spec, enabled=spec["id"] not in off and not env_off,
                          switched_off=spec["id"] in off, env_off=env_off,
                          runs=len(mine), succeeded=sum(n for s, n in statuses.items() if s in OK),
                          failed=statuses.get("failed", 0), statuses=dict(statuses),
                          duration_ms_total=sum(durations) if durations else None,
                          last=mine[-1] if mine else None))
    day_ago = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 86400))
    return {
        "automations": items,
        "totals": {"runs": len(rows), "succeeded": sum(1 for r in rows if r.get("status") in OK),
                   "failed": sum(1 for r in rows if r.get("status") == "failed"),
                   "last_24h": sum(1 for r in rows if str(r.get("ts") or "") >= day_ago),
                   "enabled": sum(1 for i in items if i["enabled"]), "count": len(items)},
        "recent": list(reversed(rows[-RECENT:])),
        "config": os.path.relpath(_config_path(project), project),
        "log": os.path.relpath(_log_path(project), project),
    }


def set_enabled(project: str, automation_id: str, enabled: bool) -> dict:
    """Write the switch atomically; the next hook run reads it. Unknown ids are refused."""
    if automation_id not in IDS:
        raise ValueError("unknown automation: %s" % automation_id)
    off = disabled(project)
    (off.discard if enabled else off.add)(automation_id)
    path = _config_path(project)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".automation-", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump({"disabled": sorted(off)}, fh, indent=2)
        fh.write("\n")
    os.replace(tmp, path)
    return overview(project)
