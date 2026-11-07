#!/usr/bin/env python3
"""Cursor sessionStart hook — algosec-agent-spec.

MARKER: algosec-agent-spec:sessionStart

Injects the project digest via {"additional_context": ...}. Fail-open: always
prints valid JSON. Safe outside an agent-spec project (empty {}).
"""
import json
import os
import sys


def main():
    try:
        if not sys.stdin.isatty():
            sys.stdin.read()
    except Exception:
        pass

    # Prefer project bin; fall back to sibling digest in this hooks dir.
    candidates = [
        os.path.join(os.getcwd(), ".agent-spec", "bin", "agent-spec-digest.py"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent-spec-digest.py"),
    ]
    digest_path = next((p for p in candidates if os.path.isfile(p)), None)
    if not digest_path:
        sys.stdout.write("{}")
        return 0

    # Run as --cursor-hook by importing build path: execute module as subprocess
    # would re-read stdin; call build_digest via importlib instead.
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location("agent_spec_digest", digest_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        text = mod.build_digest()
        payload = {"additional_context": text} if text else {}
        sys.stdout.write(json.dumps(payload))
    except Exception:
        sys.stdout.write("{}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
