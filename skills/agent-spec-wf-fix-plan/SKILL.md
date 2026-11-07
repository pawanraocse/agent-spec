---
name: "agent-spec-wf-fix-plan"
description: >-
  RCA follow-on: turn an RCA result into a test-first fix plan a human approves before any edit. Run via /agent-spec-hub-runner. Input is an RCA run id or the root cause text.
---

# agent-spec-wf-fix-plan

`/agent-spec-hub-runner fix-plan` with a finished `agent-spec-wf-rca` run id (or pasted root cause).
Plans only. Editing starts after approval, through `/agent-spec-implement`.

```steps
- id: load
  ai: true
  agent: agent-spec-search
  writes: []
  retries: 1
- id: plan
  needs: [load]
  ai: true
  agent: generalPurpose
  model: deep
  writes: []
  retries: 1
- id: approve
  needs: [plan]
  gate: human
  ai: false
  writes: []
```

## Step prompts

**load** — If the request is a run id, read `.agent-spec/runs/<run_id>/result.json` and take the `rca`
step output; otherwise use the pasted text. Locate the existing tests for each evidence path with
`./.agent-spec/bin/graphify-cli.py query --file <path>`. Return JSON
`{"root_cause": "", "evidence": ["path:line"], "tests": [{"path": "", "covers": ""}],
"dependents": [""]}`. If the RCA confidence is LOW or UNKNOWN, return it as is.

**plan** — Write the smallest fix. Return JSON `{"failing_test": {"path": "", "asserts": ""},
"change": [{"path": "", "line": 0, "from": "", "to": ""}], "test_command": "", "risk": "",
"blast_radius": [""], "confidence": "HIGH|MEDIUM|LOW|UNKNOWN", "out_of_scope": [""]}`.
Name only classes and methods that appear in `load` output; never invent one. LOW or UNKNOWN: say
which fact is missing and stop.

**approve** — Human gate. Show the plan in chat; the runner records `gate.requested` and
`gate.resolved`. Approved means the developer runs `/agent-spec-implement` with this plan; this
workflow never edits files.
