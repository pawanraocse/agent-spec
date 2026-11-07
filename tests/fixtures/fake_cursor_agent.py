#!/usr/bin/env python3
"""Fake cursor-agent for tests: streams NDJSON from AGENT_SPEC_FAKE_CLI_TRANSCRIPT."""
import json
import os
import sys
import time

def main():
    if os.environ.get("AGENT_SPEC_FAKE_CLI_SLEEP"):
        time.sleep(2)
        return 0
    transcript = os.environ.get("AGENT_SPEC_FAKE_CLI_TRANSCRIPT")
    if transcript and os.path.isfile(transcript):
        with open(transcript, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    print(line, flush=True)
                    time.sleep(0.01)
        print(json.dumps({"type": "result", "result": "ok"}), flush=True)
        return 0
    print(json.dumps({"type": "assistant", "text": "fake agent reply"}), flush=True)
    print(json.dumps({"type": "result", "result": "fake agent reply"}), flush=True)
    return 0

if __name__ == "__main__":
    sys.exit(main())
