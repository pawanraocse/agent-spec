#!/usr/bin/env python3
"""pre-tool-use.py — agent-spec PreToolUse hook.

Input discipline is 86.7% of the bill: cache re-reads are 56.7% and cache writes are
30.0%, against 13.2% for everything the assistant says. The four rules below are the
top rows of the measured methods table in docs/token-checklist.md, and until now they
existed only as sentences in a skill body that the model may or may not read. A skill
asks. A hook enforces.

Enforcement here means one refusal, not a wall. Each nudge fires once per target per
session; the immediate retry goes through. That keeps a genuine full rewrite or a
genuine whole-file read possible while making the cheap path the default one.

Safe by construction: silent outside an agent-spec project, and any unexpected input
exits 0 rather than blocking a tool call.
"""
import hashlib
import json
import os
import shlex
import sys
import tempfile
import time

# A Read with no range costs 35,966 B against 2,071 B for a 50-line window, and every
# byte is re-sent on every later turn. 20 kB is roughly 5,000 tokens.
READ_CAP = 20000
# A Write to an existing file re-sends every unchanged line, then carries it. Tool call
# inputs are 45.7% of everything a conversation accumulates, mostly this.
WRITE_CAP = 2000

FILTERED = ("|", ">", "head", "tail", "grep", "wc", "diffstat")


MARKER_TTL = 86400


def nudged_already(session_id, key):
    """True if this exact target was already refused in this session.

    State lives in the temp directory rather than in the repository: it is worthless
    after the session ends, and .agent-spec/ is a record, not a scratchpad.

    The key carries the working directory as well as the session, because a session
    that moves between projects should get the advice once per project, and because a
    reused session id would otherwise disable the hook permanently. Markers older than
    a day are swept on the way past so the directory cannot grow without bound.
    """
    root = os.path.join(tempfile.gettempdir(), "agent-spec-nudge")
    slug = hashlib.sha1(
        ("%s\x00%s\x00%s" % (session_id, os.getcwd(), key)).encode("utf-8")
    ).hexdigest()[:20]
    marker = os.path.join(root, slug)
    try:
        if os.path.getmtime(marker) > time.time() - MARKER_TTL:
            return True
    except OSError:
        pass
    os.makedirs(root, exist_ok=True)
    open(marker, "w").close()
    _sweep(root)
    return False


def _sweep(root):
    """Delete markers older than the TTL. Best effort; never fatal."""
    cutoff = time.time() - MARKER_TTL
    try:
        for name in os.listdir(root):
            path = os.path.join(root, name)
            try:
                if os.path.getmtime(path) < cutoff:
                    os.remove(path)
            except OSError:
                pass
    except OSError:
        pass


def size_of(path):
    try:
        return os.path.getsize(path)
    except OSError:
        return -1


def check(tool, args):
    """Return (key, message) for a call worth refusing once, or None."""
    if tool == "Read":
        path = args.get("file_path", "")
        if args.get("limit") or args.get("offset"):
            return None
        size = size_of(path)
        if size >= READ_CAP:
            return path, (
                "%s is %d B and this Read has no offset/limit. The whole file enters "
                "context and is re-sent every later turn. Query the graph "
                "(graphify-cli.py query --file), or grep -n for the line and Read a "
                "range around it. Retry as-is if you truly need all of it."
                % (path, size)
            )
        return None

    if tool == "Write":
        path = args.get("file_path", "")
        size = size_of(path)
        if size >= WRITE_CAP:
            return path, (
                "%s already exists at %d B. A Write re-sends every unchanged line and "
                "then carries it for the rest of the session; tool call inputs are "
                "45.7%% of what a conversation accumulates. Use Edit. Retry as-is if a "
                "full rewrite is genuinely intended." % (path, size)
            )
        return None

    if tool == "Bash":
        cmd = args.get("command", "")
        low = cmd.lower()
        if any(f in low for f in FILTERED):
            return None
        if "git diff" in low and not any(
            flag in low for flag in ("--stat", "--name-only", "--numstat", "--shortstat")
        ):
            return "git-diff", (
                "git diff without --stat pastes every changed line into context. Run "
                "git diff --stat first and open only the files that matter. Retry "
                "as-is if you need the full diff."
            )
        try:
            parts = shlex.split(cmd)
        except ValueError:
            return None
        if parts and parts[0] == "cat":
            for path in parts[1:]:
                if path.startswith("-"):
                    continue
                size = size_of(path)
                if size >= READ_CAP:
                    return path, (
                        "cat %s is %d B into context, re-sent every later turn. Use "
                        "grep -n to find the line, then sed -n to print a range. Retry "
                        "as-is if you need the whole file." % (path, size)
                    )
        return None

    return None


def main():
    if not os.path.isdir("./.agent-spec"):
        return 0
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0
    if not isinstance(payload, dict):
        return 0

    tool = payload.get("tool_name", "")
    args = payload.get("tool_input") or {}
    if not isinstance(args, dict):
        return 0

    try:
        hit = check(tool, args)
    except Exception:
        # Never let a bug here block a tool call. A missed nudge costs tokens; a
        # crashed hook costs the session.
        return 0
    if not hit:
        return 0

    key, message = hit
    if nudged_already(payload.get("session_id", "none"), tool + ":" + key):
        return 0
    sys.stderr.write("agent-spec input discipline: " + message + "\n")
    return 2


if __name__ == "__main__":
    sys.exit(main())
