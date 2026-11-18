#!/usr/bin/env python3
"""Tests for agent-spec-tokens.py transcript detection and overhead attribution.

Run: python3 tests/test_tokens.py
"""
import importlib.util
import json
import os
import sys
import tempfile

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "agent_spec_tokens", os.path.join(REPO_DIR, "bin", "agent-spec-tokens.py"))
tokens = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tokens)


def _write(rows):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
    return path


def test_claude_transcript_opening_with_bookkeeping_rows():
    # Claude Code now starts a transcript with queue-operation rows; the first line
    # alone used to classify it as Cursor, which hid every harness attachment.
    path = _write([
        {"type": "queue-operation", "operation": "enqueue", "sessionId": "s"},
        {"type": "queue-operation", "operation": "dequeue", "sessionId": "s"},
        {"attachment": {"type": "hook_success", "hookEvent": "SessionStart",
                        "content": "<agent-spec-digest>x</agent-spec-digest>"},
         "type": "attachment"},
        {"type": "assistant", "message": {"usage": {"input_tokens": 1}}},
    ])
    assert tokens.transcript_format(path) == "claude"
    turns, rows = tokens.read_overhead(path)
    assert turns == 1
    assert "hook_success:SessionStart" in rows


def test_cursor_transcript():
    path = _write([
        {"role": "user", "message": {"content": [{"type": "text", "text":
            "<agent-spec-digest>abc</agent-spec-digest><user_query>hi</user_query>"}]}},
        {"role": "assistant", "message": {"content": [{"type": "text", "text": "ok"}]}},
    ])
    assert tokens.transcript_format(path) == "cursor"


def test_unreadable_lines_are_skipped():
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w") as fh:
        fh.write("not json\n\n")
        fh.write(json.dumps({"type": "summary", "sessionId": "s"}) + "\n")
    assert tokens.transcript_format(path) == "claude"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print("  ok", fn.__name__)
    print("%d tokens tests passed" % len(tests))
