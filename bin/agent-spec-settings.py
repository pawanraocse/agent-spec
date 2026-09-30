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


def merge_hook(groups, path, matcher, timeout):
    """Ensure `path` is registered in `groups`. True when the file was changed."""
    entries = [
        h
        for group in groups
        if isinstance(group, dict)
        for h in group.get("hooks", [])
        if isinstance(h, dict)
    ]
    base = os.path.basename(path)
    for h in entries:
        cmd = h.get("command", "")
        if cmd == path:
            return False
        if MARKER in cmd and os.path.basename(cmd) == base:
            h["command"] = path
            return True
    if any(MARKER in h.get("command", "") for h in entries):
        return False
    group = {"hooks": [{"type": "command", "command": path, "timeout": timeout}]}
    if matcher:
        group["matcher"] = matcher
    groups.append(group)
    return True


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

    # Hooks are matched on the exact command path, and on the marker as a fallback for
    # a hook installed under an older name. Matching on the marker alone silently
    # stacked a second copy whenever the path did not contain it. An entry that is
    # ours (same file name) but registered under a different path is repaired in
    # place: the Windows app runs hooks in Git Bash, where an old /mnt/c/... path
    # exits 127 on every call.
    hooks = settings.setdefault("hooks", {})
    if merge_hook(hooks.setdefault("SessionStart", []), hook_path, None, 10):
        changed.append("SessionStart hook")

    # PreToolUse hook: input is 86.7% of the bill, and a skill body can only ask for
    # reading discipline. This is the only place it can be enforced.
    if pre_tool_path and merge_hook(hooks.setdefault("PreToolUse", []), pre_tool_path,
                                    "Read|Write|Bash", 5):
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
