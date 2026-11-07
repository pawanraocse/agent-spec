---
name: "agent-spec-wf-example"
description: >-
  Fixture workflow: gather -> analyze -> summarize, read-only. Run via /agent-spec-hub-runner to smoke-test run recording.
---

# agent-spec-wf-example

Read-only three-step workflow. Run it with `/agent-spec-hub-runner`.

```steps
- id: gather
  ai: true
  agent: agent-spec-search
  writes: []
  retries: 1
  timeout_s: 300
- id: analyze
  needs: [gather]
  ai: true
  agent: generalPurpose
  writes: []
  retries: 1
- id: summarize
  needs: [analyze]
  ai: true
  agent: generalPurpose
  writes: []
```

## Step prompts

**gather** — Locate the files and symbols relevant to the request. Return JSON
`{"files": [{"path": "", "why": ""}]}`. Paths and line numbers only; no file dumps.

**analyze** — Using the gather output, answer the request. Return JSON
`{"findings": [{"claim": "", "evidence": "path:line"}], "confidence": "HIGH|MEDIUM|LOW"}`.

**summarize** — Condense the findings to at most five lines. Return JSON
`{"summary": "", "citations": ["path:line"]}`.
