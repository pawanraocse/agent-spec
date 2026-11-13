#!/usr/bin/env python3
"""Fail-open hook event spine for Cursor (DEC-16 / DV-001).

Registered for beforeSubmitPrompt, postToolUse, postToolUseFailure, subagentStart,
subagentStop, afterFileEdit, afterAgentResponse, preCompact and stop. Reads only the
fields Cursor documents (cursor.com/docs/hooks): the common schema on every hook
(`hook_event_name`, `conversation_id`, `generation_id`, `model`, `cursor_version`,
`workspace_roots`, `transcript_path`) plus each event's own fields. Appends one redacted,
truncated row to `<workspace_roots[0]>/.agent-spec/metrics/events.jsonl`.

The dashboard builds traces from these rows: `generation_id` is the request (trace),
`conversation_id` the session, and each row becomes a span.

`AGENT_SPEC_HOOK_RECORD=1` additionally saves the raw payload of each event type to
`.agent-spec/metrics/hook-payloads/<event>.json` (prompt and response text redacted), which
is how DV-002 records live fixtures.

Allowed-code reason: plumbing (and latency: the hook runs on every tool call, so it must
be cheap and never block the agent). It prints nothing and always exits 0.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import uuid

MAX_STDIN = 1 << 20
TEXT_CAP = {"prompt": 500, "text": 2000, "task": 500, "summary": 2000, "description": 200,
            "error_message": 500}
EVENTS = ("beforeSubmitPrompt", "postToolUse", "postToolUseFailure", "subagentStart",
          "subagentStop", "afterFileEdit", "afterAgentResponse", "preCompact", "stop")

# Core hooks never import the platform extra (test_platform_guard), so redaction is inline:
# key=value secrets, private keys, AWS key ids, bearer tokens, URL credentials, sk- style keys.
_SECRET = re.compile(
    r"(?i)((?:password|passwd|pwd|secret|token|api[_-]?key|apikey|authorization|credentials?)\S*?\s*[:=]\s*)"
    r"(?:Bearer\s+|Basic\s+)?[\"']?[^\s\"',;]+[\"']?"
    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?(?:-----END [A-Z ]*PRIVATE KEY-----|\Z)"
    r"|\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"
    r"|(?i:\bBearer\s+)[A-Za-z0-9._~+/=-]{8,}"
    r"|(?<=://)[^/\s:@]+:[^@\s/]+(?=@)"
    r"|\b(?:sk|pk|rk|ghp|gho|xox[abp])[-_][A-Za-z0-9_-]{16,}")


def _redact(text) -> str:
    return _SECRET.sub(lambda m: (m.group(1) or "") + "[REDACTED]", str(text))


def _utc(epoch: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(epoch)) + ".%03dZ" % int((epoch % 1) * 1000)


def _int(val):
    return int(val) if isinstance(val, (int, float)) and not isinstance(val, bool) else None


def _clip(redact, val, cap: int) -> str:
    s = redact(str(val or ""))
    return s if len(s) <= cap else s[:cap] + "…"


def _as_dict(tool_input):
    if isinstance(tool_input, str):
        try:
            parsed = json.loads(tool_input)
            return parsed if isinstance(parsed, dict) else None
        except ValueError:
            return None
    return tool_input if isinstance(tool_input, dict) else None


def _tool_target(tool_input) -> str:
    """One short description of what a tool call touched (redacted by the caller)."""
    obj = _as_dict(tool_input)
    if obj is None:
        return str(tool_input or "")[:200]
    for key in ("file_path", "path", "target_file", "command", "pattern", "query", "url",
                "glob_pattern", "target_directory", "subagent_type", "description"):
        if obj.get(key):
            return "%s=%s" % (key, str(obj[key])[:200])
    return json.dumps(obj, sort_keys=True)[:200]


def handle_event(raw: str, default_event: str = "", redact=None, now: float | None = None) -> dict | None:
    """Payload text -> one events.jsonl row, or None when the payload is unusable."""
    if not raw or not raw.strip():
        return None
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    redact = redact or _redact
    now = time.time() if now is None else now
    event = str(data.get("hook_event_name") or default_event or "unknown")[:48]
    row = {
        "id": uuid.uuid4().hex[:16],
        "ts": _utc(now),
        "event": event,
        "conversation_id": str(data.get("conversation_id") or data.get("session_id") or "unknown")[:128],
        "generation_id": str(data.get("generation_id") or "")[:128] or None,
    }
    for key in ("model", "cursor_version"):
        if data.get(key):
            row[key] = str(data[key])[:80]
    if data.get("transcript_path"):
        row["transcript_path"] = str(data["transcript_path"])[:400]

    if event == "beforeSubmitPrompt":
        row["prompt"] = _clip(redact, data.get("prompt"), TEXT_CAP["prompt"])
        row["prompt_chars"] = len(str(data.get("prompt") or ""))
        if isinstance(data.get("attachments"), list):
            row["attachments"] = len(data["attachments"])
    elif event in ("postToolUse", "postToolUseFailure"):
        tool_input = data.get("tool_input")
        obj = _as_dict(tool_input)
        row["tool_name"] = str(data.get("tool_name") or "unknown")[:64]
        if data.get("tool_use_id"):
            row["tool_use_id"] = str(data["tool_use_id"])[:128]
        row["target"] = _clip(redact, _tool_target(tool_input), 240)
        if obj is not None and row["tool_name"] in ("Read", "read_file", "ReadFile"):
            row["ranged"] = any(k in obj for k in ("offset", "limit", "start_line", "end_line"))
        row["input_bytes"] = len(json.dumps(tool_input)) if tool_input is not None else 0
        if "tool_output" in data:
            row["output_bytes"] = len(str(data.get("tool_output") or ""))
        if _int(data.get("duration")) is not None:
            row["duration_ms"] = _int(data["duration"])
        if event == "postToolUseFailure":
            row["status"] = "error"
            row["error_message"] = _clip(redact, data.get("error_message"), TEXT_CAP["error_message"])
            if data.get("failure_type"):
                row["failure_type"] = str(data["failure_type"])[:32]
            if isinstance(data.get("is_interrupt"), bool):
                row["is_interrupt"] = data["is_interrupt"]
        else:
            row["status"] = "ok"
    elif event in ("subagentStart", "subagentStop"):
        for key in ("subagent_id", "subagent_type", "parent_conversation_id", "tool_call_id",
                    "subagent_model", "status"):
            if data.get(key) is not None:
                row[key] = str(data[key])[:128]
        for key in ("task", "description", "summary"):
            if data.get(key):
                row[key] = _clip(redact, data[key], TEXT_CAP[key])
                row[key + "_bytes"] = len(str(data[key]))
        for key in ("duration_ms", "message_count", "tool_call_count", "loop_count"):
            if _int(data.get(key)) is not None:
                row[key] = _int(data[key])
        if isinstance(data.get("is_parallel_worker"), bool):
            row["is_parallel_worker"] = data["is_parallel_worker"]
        if isinstance(data.get("modified_files"), list):
            row["modified_files"] = [str(f)[:300] for f in data["modified_files"][:50]]
        if data.get("agent_transcript_path"):
            row["agent_transcript_path"] = str(data["agent_transcript_path"])[:400]
    elif event == "afterFileEdit":
        row["file_path"] = str(data.get("file_path") or "")[:400]
        edits = [e for e in data.get("edits") or [] if isinstance(e, dict)] if isinstance(data.get("edits"), list) else []
        row["edit_count"] = len(edits)
        row["chars_added"] = sum(len(str(e.get("new_string") or "")) for e in edits)
        row["chars_removed"] = sum(len(str(e.get("old_string") or "")) for e in edits)
    elif event == "afterAgentResponse":
        row["text"] = _clip(redact, data.get("text"), TEXT_CAP["text"])
        row["text_chars"] = len(str(data.get("text") or ""))
    elif event == "preCompact":
        if data.get("trigger"):
            row["trigger"] = str(data["trigger"])[:16]
        for key in ("context_usage_percent", "context_tokens", "context_window_size", "message_count",
                    "messages_to_compact"):
            if _int(data.get(key)) is not None:
                row[key] = _int(data[key])
        if isinstance(data.get("is_first_compaction"), bool):
            row["is_first_compaction"] = data["is_first_compaction"]
    elif event == "stop":
        if data.get("status"):
            row["status"] = str(data["status"])[:32]
        if _int(data.get("loop_count")) is not None:
            row["loop_count"] = _int(data["loop_count"])
    return row


def workspace_root(data) -> str:
    """workspace_roots[0] (documented), then CURSOR_PROJECT_DIR, then cwd."""
    roots = data.get("workspace_roots") if isinstance(data, dict) else None
    if isinstance(roots, list) and roots and isinstance(roots[0], str) and os.path.isdir(roots[0]):
        return roots[0]
    env = os.environ.get("CURSOR_PROJECT_DIR")
    if env and os.path.isdir(env):
        return env
    return os.getcwd()


def _record(metrics: str, event: str, data: dict, redact) -> None:
    """DV-002: keep the latest raw payload per event type, free-text fields redacted."""
    safe = dict(data)
    for key in ("prompt", "text", "summary", "task", "tool_output", "user_email"):
        if safe.get(key) is not None:
            safe[key] = _clip(redact, safe[key], 400)
    out = os.path.join(metrics, "hook-payloads")
    os.makedirs(out, exist_ok=True)
    name = re.sub(r"[^A-Za-z]", "", event) or "unknown"
    with open(os.path.join(out, name + ".json"), "w", encoding="utf-8") as fh:
        json.dump(safe, fh, indent=2, sort_keys=True)
        fh.write("\n")


def main() -> int:
    try:
        default_event = sys.argv[1].lstrip("-") if len(sys.argv) > 1 else ""
        raw = sys.stdin.read(MAX_STDIN)
        try:
            data = json.loads(raw) if raw.strip() else {}
        except ValueError:
            data = {}
        root = workspace_root(data)
        if not os.path.isdir(os.path.join(root, ".agent-spec")):
            return 0  # not a harnessed workspace: write nothing
        redact = _redact
        row = handle_event(raw, default_event, redact)
        if not row:
            return 0
        metrics = os.path.join(root, ".agent-spec", "metrics")
        os.makedirs(metrics, exist_ok=True)
        with open(os.path.join(metrics, "events.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, separators=(",", ":")) + "\n")
        if os.environ.get("AGENT_SPEC_HOOK_RECORD") and isinstance(data, dict):
            _record(metrics, row["event"], data, redact)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
