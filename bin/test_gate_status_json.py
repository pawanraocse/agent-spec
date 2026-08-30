#!/usr/bin/env python3
"""Self-test: agent-spec-gate.py status --json emits valid, well-shaped JSON."""
import json
import subprocess
import sys
import os

SCRIPT = os.path.join(os.path.dirname(__file__), "agent-spec-gate.py")


def run():
    result = subprocess.run(
        [sys.executable, SCRIPT, "status", "--json"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        "status --json exited %d\nstdout: %s\nstderr: %s"
        % (result.returncode, result.stdout, result.stderr)
    )

    doc = json.loads(result.stdout)  # raises on invalid JSON

    # Top-level keys must be present.
    for key in ("feature", "gate", "gate_name", "next_command", "artifacts"):
        assert key in doc, "missing key %r in output" % key

    # gate must be a non-negative integer.
    assert isinstance(doc["gate"], int) and doc["gate"] >= 0, (
        "gate must be a non-negative int, got %r" % doc["gate"]
    )

    # artifacts must be a non-empty list, each entry with the three expected keys.
    assert isinstance(doc["artifacts"], list) and len(doc["artifacts"]) > 0, (
        "artifacts must be a non-empty list"
    )
    for entry in doc["artifacts"]:
        for key in ("name", "gate", "status"):
            assert key in entry, "artifact entry missing key %r: %r" % (key, entry)
        assert isinstance(entry["gate"], int), (
            "artifact gate must be int, got %r" % entry["gate"]
        )
        assert entry["status"] in ("present", "MISSING", "n/a (code)"), (
            "unexpected artifact status %r" % entry["status"]
        )

    # next_command must start with a slash (all skills do).
    assert doc["next_command"].startswith("/"), (
        "next_command %r does not start with '/'" % doc["next_command"]
    )

    print("OK — status --json is valid and well-shaped")


if __name__ == "__main__":
    run()
