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
import sys
import time

MAX_TRANSCRIPT = 20 * 1024 * 1024
STOP_DEBOUNCE_S = 30


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

    if transcript and os.path.isfile(transcript):
        if os.path.getsize(transcript) > MAX_TRANSCRIPT:
            return 0
        session = session or os.path.basename(transcript)[:-len(".jsonl")]

    if event == "stop" and session:
        existing = os.path.join(project, ".agent-spec", "metrics", "receipts", session + ".json")
        try:
            if os.path.getmtime(existing) > time.time() - STOP_DEBOUNCE_S:
                return 0
        except OSError:
            pass

    mod = load_receipt_module()
    if mod is None:
        return 0
    receipt = mod.build_receipt(project, session, transcript)
    if receipt:
        mod.write_receipt(project, receipt)
        mod.upsert_daily(project, receipt)
        if hasattr(mod, "upsert_experience"):
            mod.upsert_experience(project, mod.build_experience(project, receipt, session, transcript))
    response = {}
    if session and event in ("stop", "sessionEnd", "preCompact"):
        marker = os.path.join(project, ".agent-spec", f".snapshot-nudged-{session}")
        if not os.path.exists(marker):
            try:
                with open(marker, "w") as fh:
                    fh.write(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
                if receipt and (receipt.get("tokens", 0) > 40000 or receipt.get("turns", 0) >= 6):
                    response["followup_message"] = (
                        "Agent-Spec automated checkpoint: Run `/agent-spec-snapshot` to record your "
                        "work in SESSION-SNAPSHOT.md before concluding."
                    )
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
