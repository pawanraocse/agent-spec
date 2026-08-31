#!/usr/bin/env python3
"""Merge agent-spec's harness settings into a Claude Code settings.json.

Non-destructive by design. The file belongs to the user: this adds what is missing
and never rewrites a choice the user has already made. Re-running the installer must
be idempotent, so every insertion is guarded by an identity check rather than by
appending blindly.

Usage: agent-spec-settings.py <path-to-settings.json> <path-to-session-start-hook>
                              [<path-to-pre-tool-use-hook>]

The third argument is optional so that an older caller keeps working unchanged.
"""
import json
import os
import sys

MARKER = "agent-spec"


def main():
    if len(sys.argv) not in (3, 4):
        print("usage: agent-spec-settings.py <settings.json> <session-hook> "
              "[<pre-tool-use-hook>]", file=sys.stderr)
        return 2

    settings_path, hook_path = sys.argv[1], sys.argv[2]
    pre_tool_path = sys.argv[3] if len(sys.argv) == 4 else None
    changed = []

    settings = {}
    if os.path.exists(settings_path):
        try:
            with open(settings_path, encoding="utf-8") as fh:
                settings = json.load(fh)
        except ValueError as exc:
            # A malformed settings.json is the user's to fix. Overwriting it would
            # destroy every other preference in the file.
            print("settings.json is not valid JSON (%s) — left untouched" % exc, file=sys.stderr)
            return 1

    # Output style: only when the user has not chosen one. A style they picked
    # deliberately outranks our default.
    if not settings.get("outputStyle"):
        settings["outputStyle"] = MARKER
        changed.append("outputStyle=agent-spec")

    # SessionStart hook: matched on the exact command path, and on the marker as a
    # fallback for a hook installed under an older name. Matching on the marker alone
    # silently stacked a second copy whenever the path did not contain it.
    hooks = settings.setdefault("hooks", {})
    session_start = hooks.setdefault("SessionStart", [])
    existing = [
        h.get("command", "")
        for group in session_start
        if isinstance(group, dict)
        for h in group.get("hooks", [])
        if isinstance(h, dict)
    ]
    already = any(cmd == hook_path or MARKER in cmd for cmd in existing)
    if not already:
        session_start.append({
            "hooks": [{"type": "command", "command": hook_path, "timeout": 10}]
        })
        changed.append("SessionStart hook")

    # PreToolUse hook: input is 86.7% of the bill, and a skill body can only ask for
    # reading discipline. This is the only place it can be enforced. Matched the same
    # way as SessionStart so a re-run never stacks a second copy.
    if pre_tool_path:
        pre_tool = hooks.setdefault("PreToolUse", [])
        existing_pre = [
            h.get("command", "")
            for group in pre_tool
            if isinstance(group, dict)
            for h in group.get("hooks", [])
            if isinstance(h, dict)
        ]
        if not any(cmd == pre_tool_path or MARKER in cmd for cmd in existing_pre):
            pre_tool.append({
                "matcher": "Read|Write|Bash",
                "hooks": [{"type": "command", "command": pre_tool_path, "timeout": 5}],
            })
            changed.append("PreToolUse hook")

    if not changed:
        print("settings.json already current")
        return 0

    os.makedirs(os.path.dirname(settings_path) or ".", exist_ok=True)
    with open(settings_path, "w", encoding="utf-8") as fh:
        json.dump(settings, fh, indent=2)
        fh.write("\n")
    print("settings.json: " + ", ".join(changed))
    return 0


if __name__ == "__main__":
    sys.exit(main())
