#!/usr/bin/env python3
"""Remove algosec-agent-spec hook entries from hooks.json."""
import json
import sys

path = sys.argv[1]
try:
    with open(path) as fh:
        cfg = json.load(fh)
except (OSError, ValueError):
    sys.exit(0)
hooks = cfg.get("hooks") or {}
for event in list(hooks.keys()):
    kept = []
    for h in hooks.get(event) or []:
        if not isinstance(h, dict):
            kept.append(h)
            continue
        c = h.get("command") or ""
        if (
            "agent-spec-session-start" in c
            or "agent-spec-pre-tool-use" in c
            or "agent-spec-session-end" in c
            or "agent-spec-cursor-event" in c
            or "agent-spec-digest.py --cursor-hook" in c
        ):
            continue
        kept.append(h)
    hooks[event] = kept
cfg["hooks"] = hooks
with open(path, "w") as fh:
    json.dump(cfg, fh, indent=2)
    fh.write("\n")
