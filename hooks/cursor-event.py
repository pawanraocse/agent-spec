#!/usr/bin/env python3
"""Fail-open hook event spine for Cursor (DEC-15 / AF-001).

Appends sanitized event rows to .agent-spec/metrics/events.jsonl.
Latency floor < 5ms. Allowed-code reason: per-call latency & plumbing.
"""
from __future__ import annotations

import json
import os
import sys
import time


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _safe_str(val, max_len: int = 250) -> str:
    s = str(val or "")
    # Mask obvious secret tokens or environment keys
    if "api_key" in s.lower() or "token" in s.lower() or "secret" in s.lower():
        return "[REDACTED]"
    return s[:max_len]


def handle_event(raw: str, default_event: str = "generic") -> dict | None:
    if not raw.strip():
        return None
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return None

    event_type = data.get("event") or data.get("type") or default_event
    session_id = data.get("session_id") or data.get("sessionId") or "unknown"

    row = {
        "ts": _utc_now(),
        "event": event_type,
        "session_id": str(session_id)[:128],
    }

    tool = data.get("tool_name") or data.get("toolName") or (data.get("tool") or {}).get("name")
    if tool:
        row["tool"] = _safe_str(tool, 64)

    if "status" in data:
        row["status"] = _safe_str(data["status"], 32)
    elif "error" in data:
        row["status"] = "failed"
        row["error"] = _safe_str(data["error"])

    for ms_key in ("duration_ms", "durationMs", "latency_ms", "latencyMs"):
        if ms_key in data and isinstance(data[ms_key], (int, float)):
            row["duration_ms"] = int(data[ms_key])
            break

    tokens = data.get("tokens") or data.get("token_count")
    if isinstance(tokens, dict):
        row["tokens"] = {
            "input": int(tokens.get("input") or tokens.get("prompt") or 0),
            "output": int(tokens.get("output") or tokens.get("completion") or 0),
        }
    elif isinstance(tokens, (int, float)):
        row["tokens"] = {"total": int(tokens)}

    subagent = data.get("subagent") or data.get("agent") or data.get("subagentId")
    if subagent:
        row["subagent"] = _safe_str(subagent, 64)

    return row


def main():
    try:
        default_event = sys.argv[1].lstrip("-") if len(sys.argv) > 1 else "generic"
        raw = sys.stdin.read(65536)
        row = handle_event(raw, default_event)
        if not row:
            return 0

        # Target directory: .agent-spec/metrics/
        cwd = os.getcwd()
        metrics_dir = os.path.join(cwd, ".agent-spec", "metrics")
        os.makedirs(metrics_dir, exist_ok=True)
        events_path = os.path.join(metrics_dir, "events.jsonl")

        with open(events_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
