#!/usr/bin/env python3
"""Merge agent-spec's harness settings into a Claude Code settings.json.

Non-destructive by design. The file belongs to the user: this adds what is missing
and never rewrites a choice the user has already made. Re-running the installer must
be idempotent, so every insertion is guarded by an identity check rather than by
appending blindly.

Usage: agent-spec-settings.py <path-to-settings.json> <path-to-session-start-hook>
"""
import json
import os
import sys

MARKER = "agent-spec"


def main():
    if len(sys.argv) != 3:
        print("usage: agent-spec-settings.py <settings.json> <hook-path>", file=sys.stderr)
        return 2

    settings_path, hook_path = sys.argv[1], sys.argv[2]
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
