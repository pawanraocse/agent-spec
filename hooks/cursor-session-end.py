#!/usr/bin/env python3
"""Cursor sessionEnd / stop hook — algosec-agent-spec session receipt.

MARKER: algosec-agent-spec:sessionEnd

Writes .agent-spec/metrics/receipts/<session>.json and upserts a row in
.agent-spec/metrics/daily.jsonl (T-050 / T-051). Registered for both `sessionEnd` (once,
when the chat closes) and `stop` (every agent turn, so a crash still leaves a receipt);
the daily row is replaced per session, never duplicated, and `stop` skips the work when
the receipt is under 30 s old.

Fail-open: always prints valid JSON ({} — no followup_message, so `stop` never loops) and
exits 0. Safe outside an agent-spec project.
"""
import importlib.util
import json
import os
import re
import subprocess
import sys
import time

MAX_TRANSCRIPT = 20 * 1024 * 1024
STOP_DEBOUNCE_S = 30
# The context check reads Cursor's whole store, which on WSL (/mnt/c) means copying it (tens
# of MB). Context grows over minutes, not turns, so one check per chat per interval is enough.
CONTEXT_CHECK_S = 300
CONVERSATION_ID = re.compile(r"^[\w.:-]{1,160}$")  # same rule as traces.load_review
GRAPH_DIRTY = ".graph-dirty"  # written by cursor-event.py (HA-002)
ROTATE_TIMEOUT_S = 3  # sessionEnd's own budget is 5 s and the receipt runs after this


def load_receipt_module():
    candidates = [
        os.path.join(os.getcwd(), ".agent-spec", "bin", "agent-spec-receipt.py"),
    ]
    path = next((p for p in candidates if os.path.isfile(p)), None)
    if not path:
        return None
    spec = importlib.util.spec_from_file_location("agent_spec_receipt", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_by_path(name, filename):
    """A platform module loaded by file path, not as a package import (DEC-03: the harness
    must keep working when the platform is not installed). None when absent or broken."""
    for base in (os.path.join(os.getcwd(), ".agent-spec", "bin", "aspec_platform"),
                 os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin", "aspec_platform")):
        path = os.path.join(base, filename)
        if os.path.isfile(path):
            try:
                spec = importlib.util.spec_from_file_location(name, path)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                return mod
            except Exception:
                return None
    return None


def automation_enabled(project, name):
    """HA-006: the dashboard's Automations panel turns one off by listing it in
    .agent-spec/automation.json {"disabled": [...]}. Unreadable config means enabled."""
    try:
        with open(os.path.join(project, ".agent-spec", "automation.json"), encoding="utf-8") as fh:
            disabled = json.load(fh).get("disabled") or []
        return name not in disabled
    except (OSError, ValueError, AttributeError):
        return True


def log_automation(project, name, status, reason="", duration_ms=None, session=None):
    """HA-006: one row per automation run in metrics/automation.jsonl, read by the dashboard.
    Kept out of events.jsonl, which the trace builder turns into conversations."""
    row = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "name": name, "status": status,
           "reason": reason, "source": "hook"}
    if duration_ms is not None:
        row["duration_ms"] = duration_ms
    if session:
        row["session"] = str(session)[:128]
    try:
        metrics = os.path.join(project, ".agent-spec", "metrics")
        os.makedirs(metrics, exist_ok=True)
        with open(os.path.join(metrics, "automation.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, separators=(",", ":")) + "\n")
    except OSError:
        pass


def refresh_graph(project, session=None):
    """HA-002: rebuild the knowledge graph in the background after an edit or a shell command
    (the event spine writes the marker) may have changed it.

    The marker is spent before the build starts, so an edit that lands mid-build marks the
    graph dirty again. Detached, so the hook's timeout never waits on it; the builder's own
    lock turns an overlapping run into a no-op.
    """
    marker = os.path.join(project, ".agent-spec", GRAPH_DIRTY)
    builder = os.path.join(project, ".agent-spec", "bin", "graphify-build.py")
    if not os.path.exists(marker) or not os.path.isfile(builder):
        return
    if not automation_enabled(project, "graph-refresh"):
        return  # the marker stays: turning it back on rebuilds at the next stop
    try:
        os.remove(marker)
        subprocess.Popen([sys.executable, builder, "--quiet"], cwd=project,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
        log_automation(project, "graph-refresh", "started", "files changed since the last build",
                       session=session)
    except (OSError, ValueError, subprocess.SubprocessError):
        log_automation(project, "graph-refresh", "failed", "could not start the builder", session=session)


def rotate_snapshot(project, session=None):
    """HA-003: archive old SESSION-SNAPSHOT.md sections at chat end. A no-op under the
    threshold; the snapshot skill also runs it, but only when the skill runs to its last step."""
    script = os.path.join(project, ".agent-spec", "bin", "agent-spec-memory.py")
    if not os.path.isfile(script) or not automation_enabled(project, "snapshot-rotate"):
        return
    started = time.time()
    try:
        res = subprocess.run([sys.executable, script, "rotate"], cwd=project, stdin=subprocess.DEVNULL,
                             capture_output=True, text=True, timeout=ROTATE_TIMEOUT_S)
        status = "ok" if res.returncode == 0 else "failed"
        reason = (res.stdout or res.stderr or "").strip().splitlines()[-1:] or [""]
    except (OSError, subprocess.SubprocessError) as exc:
        status, reason = "failed", [type(exc).__name__]
    log_automation(project, "snapshot-rotate", status, reason[0][:200],
                   int((time.time() - started) * 1000), session)


def context_nudge(project, conversation_id):
    """One measured follow-up per chat when a reset pays for itself (context budget).

    Reads Cursor's own `contextTokensUsed` for this chat and the fresh-chat floor; nudges only
    on a `reset` verdict, and only once (marker). Off with AGENT_SPEC_CONTEXT_NUDGE=0.
    """
    if not conversation_id or os.environ.get("AGENT_SPEC_CONTEXT_NUDGE", "1") == "0":
        return None
    if not CONVERSATION_ID.match(str(conversation_id)):  # it becomes part of a file name
        return None
    marker = os.path.join(project, ".agent-spec", f".context-nudged-{conversation_id}")
    if os.path.exists(marker):
        return None
    try:
        interval = float(os.environ.get("AGENT_SPEC_CONTEXT_CHECK_S", CONTEXT_CHECK_S))
    except ValueError:
        interval = CONTEXT_CHECK_S
    checked = os.path.join(project, ".agent-spec", "metrics", "context-checked", conversation_id)
    try:
        if time.time() - os.path.getmtime(checked) < interval:
            return None
    except OSError:
        pass
    try:
        os.makedirs(os.path.dirname(checked), exist_ok=True)
        with open(checked, "w") as fh:
            fh.write(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    except OSError:
        return None
    cb = _load_by_path("agent_spec_context_budget", "context_budget.py")
    cs = _load_by_path("agent_spec_cursor_sessions", "cursor_sessions.py")
    if cb is None or cs is None:
        return None
    usage = cs.context_usage() or {}
    mine = (usage.get("by_id") or {}).get(conversation_id)
    if not mine:
        return None
    fixed = cb.fixed_tokens(mine.get("breakdown")) if hasattr(cb, "fixed_tokens") else None
    floor = cb.machine_floor(usage) if hasattr(cb, "machine_floor") else usage.get("floor")
    b = cb.budget(mine.get("used"), fixed or floor, mine.get("limit"))
    if not b or b["verdict"] != "reset":
        return None
    try:
        with open(marker, "w") as fh:
            json.dump(b, fh)
    except OSError:
        return None
    return cb.nudge_text(b)


def main():
    try:
        raw = "" if sys.stdin.isatty() else sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
        if not isinstance(payload, dict):
            payload = {}
    except (ValueError, OSError):
        payload = {}

    if not os.path.isdir(os.path.join(os.getcwd(), ".agent-spec")):
        return 0

    project = os.getcwd()
    session = payload.get("session_id") or payload.get("conversation_id")
    transcript = payload.get("transcript_path")
    event = payload.get("hook_event_name") or ""

    # Deterministic upkeep first: neither needs the model, and neither may be skipped by the
    # debounce or a follow-up returning early below.
    if event in ("stop", "sessionEnd"):
        refresh_graph(project, payload.get("conversation_id") or session)
    if event == "sessionEnd":
        rotate_snapshot(project, payload.get("conversation_id") or session)

    # /agent-spec-hook-probe leaves this marker; afterAgentResponse and stop have fired by now,
    # so hand the chat its own collect turn. One-shot: the marker goes before the reply does.
    probe = os.path.join(project, ".agent-spec", ".hook-probe-pending")
    if event == "stop" and os.path.exists(probe):
        try:
            os.remove(probe)
            return {"followup_message": "/agent-spec-hook-probe collect"}
        except OSError:
            pass

    # Measured context check first: it costs one indexed read of Cursor's store, runs before
    # the receipt debounce, and replaces the snapshot nudge (compact writes the state anyway).
    nudge = None
    if event == "stop":
        try:
            if automation_enabled(project, "context-nudge"):
                nudge = context_nudge(project, payload.get("conversation_id"))
                if nudge:
                    log_automation(project, "context-nudge", "sent", "context past the reset break-even",
                                   session=payload.get("conversation_id"))
        except Exception:
            nudge = None

    if transcript and os.path.isfile(transcript):
        if os.path.getsize(transcript) > MAX_TRANSCRIPT:
            return {"followup_message": nudge} if nudge else 0
        session = session or os.path.basename(transcript)[:-len(".jsonl")]

    if event == "stop" and session:
        existing = os.path.join(project, ".agent-spec", "metrics", "receipts", session + ".json")
        try:
            if os.path.getmtime(existing) > time.time() - STOP_DEBOUNCE_S:
                return {"followup_message": nudge} if nudge else 0
        except OSError:
            pass

    mod = load_receipt_module()
    if mod is None:
        return {"followup_message": nudge} if nudge else 0
    receipt = mod.build_receipt(project, session, transcript)
    if receipt:
        mod.write_receipt(project, receipt)
        mod.upsert_daily(project, receipt)
        if hasattr(mod, "upsert_experience"):
            mod.upsert_experience(project, mod.build_experience(project, receipt, session, transcript))
    if nudge:
        return {"followup_message": nudge}
    response = {}
    if session and event in ("stop", "sessionEnd", "preCompact"):
        marker = os.path.join(project, ".agent-spec", f".snapshot-nudged-{session}")
        tokens = receipt.get("tokens") if receipt else None
        total = sum(v for v in tokens.values() if isinstance(v, int) and not isinstance(v, bool)) \
            if isinstance(tokens, dict) else (tokens or 0)
        # The marker is written only when the nudge fires: writing it on the first small turn
        # used the one-shot up before the chat ever grew.
        if not os.path.exists(marker) and receipt and (total > 40000 or receipt.get("turns", 0) >= 6) \
                and automation_enabled(project, "snapshot-followup"):
            try:
                with open(marker, "w") as fh:
                    fh.write(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
                # HA-001: the command itself, so the skill runs instead of being asked for.
                response["followup_message"] = "/agent-spec-snapshot"
                log_automation(project, "snapshot-followup", "sent",
                               "%d turns, %d tokens" % (receipt.get("turns", 0), total), session=session)
            except OSError:
                pass

    return response


if __name__ == "__main__":
    resp = {}
    try:
        resp = main() or {}
    except Exception:
        resp = {}
    sys.stdout.write(json.dumps(resp))
    sys.exit(0)
