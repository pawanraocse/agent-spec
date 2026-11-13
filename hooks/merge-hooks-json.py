#!/usr/bin/env python3
"""Merge algosec-agent-spec hooks into a Cursor hooks.json (idempotent).

Usage: merge-hooks-json.py <path-to-hooks.json>
"""
import json
import sys

SESSION_CMD = "python3 .cursor/hooks/agent-spec-session-start.py"
PRE_CMD = "python3 .cursor/hooks/agent-spec-pre-tool-use.py"
END_CMD = "python3 .cursor/hooks/agent-spec-session-end.py"
EVENT_CMD = "python3 .cursor/hooks/agent-spec-cursor-event.py"

# Seconds. The digest worst case is ~5 s (3 s graph build + 2 s doctor), so sessionStart
# gets double that; the preToolUse check is a stat() and must stay cheap.
TIMEOUTS = {
    "sessionStart": 10,
    "preToolUse": 5,
    "sessionEnd": 5,
    "stop": 5,
    "postToolUse": 3,
    "postToolUseFailure": 3,
    "subagentStart": 3,
    "subagentStop": 3,
    "preCompact": 3,
    "beforeSubmitPrompt": 3,
    "afterFileEdit": 3,
    "afterAgentResponse": 3,
}

# DV-001: every event the trace model needs. `stop` also keeps the session-end handler.
EVENT_HOOKS = ("beforeSubmitPrompt", "postToolUse", "postToolUseFailure", "subagentStart",
               "subagentStop", "afterFileEdit", "afterAgentResponse", "preCompact", "stop")


def ours(h):
    if not isinstance(h, dict):
        return False
    c = h.get("command") or ""
    if c in (SESSION_CMD, PRE_CMD, END_CMD, EVENT_CMD):
        return True
    if "agent-spec-digest.py --cursor-hook" in c:
        return True
    if "agent-spec-session-start" in c or "agent-spec-pre-tool-use" in c or "agent-spec-session-end" in c or "agent-spec-cursor-event" in c:
        return True
    return False


def main():
    path = sys.argv[1]
    try:
        with open(path) as fh:
            cfg = json.load(fh)
        if not isinstance(cfg, dict):
            cfg = {}
    except (OSError, ValueError):
        cfg = {}

    cfg["version"] = 1
    hooks = cfg.setdefault("hooks", {})

    wanted = {"sessionStart": [SESSION_CMD], "preToolUse": [PRE_CMD], "sessionEnd": [END_CMD],
              "stop": [END_CMD]}
    for event in EVENT_HOOKS:
        wanted.setdefault(event, []).append(EVENT_CMD)
    for event, cmds in wanted.items():
        handlers = [h for h in hooks.get(event, []) if not ours(h)]
        handlers.extend({"command": c, "timeout": TIMEOUTS.get(event, 3)} for c in cmds)
        hooks[event] = handlers

    with open(path, "w") as fh:
        json.dump(cfg, fh, indent=2)
        fh.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
