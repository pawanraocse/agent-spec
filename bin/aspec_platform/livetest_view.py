"""Live tests page: the latest `agent-spec-livetest.py` run, the run history, and a guarded
"Run now" that launches the matrix in the background.

Results are the JSON files the runner writes under `.agent-spec/eval/live/`; nothing here
re-computes a verdict. One run at a time: `running.json` holds the pid, and a pid that is no
longer alive clears it, so a crashed run never blocks the button.
"""
from __future__ import annotations

import glob
import json
import os
import subprocess
import sys
import threading
import time

from . import common

HERE = os.path.dirname(os.path.abspath(__file__))
RUNNER = os.path.normpath(os.path.join(HERE, "..", "agent-spec-livetest.py"))
HISTORY = 30
_START = threading.Lock()  # the dashboard server is threaded; two clicks must not start two runs
TIERS = {"quick": ["--only", "L01,L02,L03,L04,L05,L16"], "live": [], "full": ["--full"]}


def _dir(project: str) -> str:
    return os.path.join(common.agent_spec_dir(project), "eval", "live")


def _load(path: str):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _alive(pid) -> bool:
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, ValueError, TypeError):
        return False


def running(project: str):
    path = os.path.join(_dir(project), "running.json")
    state = _load(path)
    if not state:
        return None
    if not _alive(state.get("pid")):
        try:
            os.remove(path)
        except OSError:
            pass
        return None
    log = os.path.join(_dir(project), "running.log")
    try:
        with open(log, encoding="utf-8", errors="replace") as fh:
            lines = [l.rstrip() for l in fh if l.strip()]
    except OSError:
        lines = []
    return dict(state, progress=lines[-40:])


def overview(project: str) -> dict:
    d = _dir(project)
    runs = []
    for path in sorted(glob.glob(os.path.join(d, "2*.json")))[-HISTORY:]:
        r = _load(path)
        if isinstance(r, dict) and isinstance(r.get("summary"), dict):
            runs.append({k: r.get(k) for k in ("run_id", "started", "finished", "models", "full", "summary")})
    latest = _load(os.path.join(d, "latest.json"))
    return {"latest": latest if isinstance(latest, dict) else None, "history": runs, "running": running(project),
            "available": os.path.isfile(RUNNER), "tiers": sorted(TIERS),
            "command": "python3 bin/agent-spec-livetest.py --full --models all"}


def start(project: str, body: dict) -> dict:
    """Launch one run in the background. body: {"tier": quick|live|full, "all_models": bool}."""
    tier = str(body.get("tier") or "live")
    if tier not in TIERS:
        raise ValueError("tier must be one of %s" % ", ".join(sorted(TIERS)))
    if not os.path.isfile(RUNNER):
        raise ValueError("agent-spec-livetest.py is not installed next to the dashboard")
    with _START:
        return _start(project, tier, body.get("all_models") is True)


def _start(project: str, tier: str, all_models: bool) -> dict:
    if running(project):
        return {"ok": False, "error": "a live test run is already in progress"}
    d = _dir(project)
    os.makedirs(d, exist_ok=True)
    argv = [sys.executable, RUNNER, "--project", project] + TIERS[tier]
    if all_models:
        argv += ["--models", "all"]
    with open(os.path.join(d, "running.log"), "w", encoding="utf-8") as log:
        proc = subprocess.Popen(argv, cwd=project, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                start_new_session=True)
    state = {"pid": proc.pid, "started": common.utc_now(), "tier": tier, "all_models": all_models}
    with open(os.path.join(d, "running.json"), "w", encoding="utf-8") as fh:
        json.dump(state, fh)
    return {"ok": True, "running": state, "started_at": time.time()}
