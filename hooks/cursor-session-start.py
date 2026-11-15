#!/usr/bin/env python3
"""Cursor sessionStart hook — algosec-agent-spec.

MARKER: algosec-agent-spec:sessionStart

Injects the project digest via {"additional_context": ...}. Fail-open: always
prints valid JSON. Safe outside an agent-spec project (empty {}).
"""
import json
import os
import sys
import time


def remembered_lines(text):
    """The fact lines under the digest's `remembered:` heading, in order."""
    lines = text.splitlines()
    if "remembered:" not in lines:
        return []
    out = []
    for line in lines[lines.index("remembered:") + 1:]:
        if not line.startswith("- "):
            break
        out.append(line)
    return out


def record_injection(payload, text):
    """Append which facts this session's digest carried to metrics/injections.jsonl.

    Kept out of events.jsonl on purpose: every events.jsonl row becomes a dashboard
    conversation. Best effort; a failure here never blocks the digest."""
    try:
        conv = str(payload.get("conversation_id") or payload.get("session_id") or "")
        metrics = os.path.join(os.getcwd(), ".agent-spec", "metrics")
        if not conv or not os.path.isdir(metrics):
            return
        row = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "conversation_id": conv,
               "digest_bytes": len(text.encode("utf-8")), "facts": remembered_lines(text)}
        with open(os.path.join(metrics, "injections.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")
    except Exception:
        pass


def main():
    payload = {}
    try:
        if not sys.stdin.isatty():
            raw = sys.stdin.read()
            payload = json.loads(raw) if raw.strip() else {}
            if not isinstance(payload, dict):
                payload = {}
    except Exception:
        payload = {}

    # Prefer project bin; fall back to sibling digest in this hooks dir.
    candidates = [
        os.path.join(os.getcwd(), ".agent-spec", "bin", "agent-spec-digest.py"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent-spec-digest.py"),
    ]
    digest_path = next((p for p in candidates if os.path.isfile(p)), None)
    if not digest_path:
        sys.stdout.write("{}")
        return 0

    # Run as --cursor-hook by importing build path: execute module as subprocess
    # would re-read stdin; call build_digest via importlib instead.
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location("agent_spec_digest", digest_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        text = mod.build_digest()
        if text:
            record_injection(payload, text)
        sys.stdout.write(json.dumps({"additional_context": text} if text else {}))
    except Exception:
        sys.stdout.write("{}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
