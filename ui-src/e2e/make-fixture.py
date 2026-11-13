#!/usr/bin/env python3
"""DV-061 fixture project: replays the documented hook payloads through hooks/cursor-event.py
(so the smoke covers hook -> events.jsonl -> API -> UI), plus one review and one linked fact."""
import json
import os
import subprocess
import sys
import time

root = os.path.abspath(sys.argv[1])
repo = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
spec = os.path.join(root, ".agent-spec")
for sub in ("metrics/reviews", "memory/facts"):
    os.makedirs(os.path.join(spec, sub), exist_ok=True)
events = os.path.join(spec, "metrics", "events.jsonl")
if os.path.exists(events):
    os.remove(events)
order = ["beforeSubmitPrompt", "postToolUse", "subagentStart", "subagentStop", "postToolUseFailure",
         "afterFileEdit", "afterAgentResponse", "stop"]
for name in order:
    with open(os.path.join(repo, "tests", "fixtures", "hooks", name + ".json"), encoding="utf-8") as fh:
        payload = json.load(fh)
    payload["workspace_roots"] = [root]
    payload.pop("duration", None) if name == "postToolUseFailure" else None
    subprocess.run([sys.executable, os.path.join(repo, "hooks", "cursor-event.py")], input=json.dumps(payload),
                   text=True, check=True)
    time.sleep(0.05)
with open(os.path.join(spec, "metrics", "reviews", "conv-fixture-1.json"), "w") as fh:
    json.dump({"conversation_id": "conv-fixture-1", "session_started": "2026-11-01T10:00:00Z", "grade": "B",
               "model": "fixture", "rubric_version": "2.0.0", "summary": "Fixture review.",
               "findings": [{"category": "slow_tool", "severity": "high", "title": "Shell test run timed out",
                             "detail": "npm test ran 30 s and failed", "trace_id": "gen-fixture-1",
                             "span_id": "", "fix_prompt": "Run the narrow test file through agent-spec-verify"}]}, fh)
with open(os.path.join(spec, "memory", "facts", "f-slow.md"), "w") as fh:
    fh.write("---\nid: f-slow\ntype: constraint\nsubject: narrow test runs\ncreated: 2026-10-01\n"
             "addresses: slow_tool\n---\nRun one test file, not the suite.\n")
print(root)
