---
name: "agent-spec-wf-rca"
description: >-
  Root-cause a Jira bug: Jira via MCP, graph context and blast radius, log parse, cited root cause. Run via /agent-spec-hub-runner. Input is a Jira key.
dashboard:
  category: Workflow
  icon: bug
  emits: [workflow, run_step]
  steps: [fetch, graph, logs, rca]
---

# agent-spec-wf-rca

`/agent-spec-hub-runner rca` with the Jira key (for example `AVC-123`) as the request.
Read-only: no step edits source. The output is a diagnosis, never a fix.

```steps
- id: fetch
  ai: true
  agent: generalPurpose
  writes: []
  retries: 1
  timeout_s: 300
- id: graph
  needs: [fetch]
  ai: true
  agent: agent-spec-search
  writes: []
  retries: 1
- id: logs
  needs: [fetch]
  ai: true
  agent: generalPurpose
  writes: []
  retries: 1
- id: rca
  needs: [graph, logs]
  ai: true
  agent: generalPurpose
  skill: agent-spec-investigate
  model: deep
  writes: []
  retries: 1
```

## Step prompts

**fetch** — Call the Cursor MCP tool `jira___getIssue` (server `user-algosec-atlassian`) for the key
in the request, then `jira___getIssueComments` and `jira___getIssueAttachments`. Pre-filter raw API responses
using `./.agent-spec/bin/agent-spec-mcp-filter.py` before context injection to prune schemas and metadata. Check
`reviewed-examples/README.md` for the Jira label convention and read any matching example.
Return JSON `{"key": "", "summary": "", "symptom": "", "expected": "", "steps_to_reproduce": "",
"components": [], "attachments": [{"name": "", "kind": "log|screenshot|other"}],
"candidate_terms": []}`. Keep fields, never the raw page; drop secrets and customer names.

**graph** — Use `fetch.candidate_terms` and `fetch.symptom`. Run
`./.agent-spec/bin/graphify-cli.py context --task "<symptom + terms>"`, then `query --file <path>`
for each hit, then `./.agent-spec/bin/agent-spec-blast-radius <path>` for the two most likely files.
Return JSON `{"suspects": [{"path": "", "why": ""}], "blast_radius": [{"path": "", "dependents": 0}]}`.
Paths and counts only; no file dumps.

**logs** — Parse the log attachments or log text from `fetch` (download with `jira___downloadAttachment`
only if kind is `log`). Group repeated lines, keep the first error, last error, and the first stack
frame in project code. Return JSON `{"errors": [{"line": "", "count": 0, "frame": "path:line"}],
"timeline": ""}`. If there is no log, return `{"errors": [], "timeline": "no logs"}`; do not invent one.

**rca** — Follow the investigate skill: name the cause with evidence, write no fix. Read only the
ranges named by `graph.suspects` and `logs.errors[].frame`. Return JSON
`{"root_cause": "", "evidence": ["path:line"], "alternatives_rejected": [{"idea": "", "why": ""}],
"blast_radius": [""], "confidence": "HIGH|MEDIUM|LOW|UNKNOWN", "next_check": ""}`.
Every claim carries a `path:line`. Under two citations, confidence is at most LOW.

## Rules

- Never post the result back to Jira unless the user asks.
- A missing Jira MCP means `fetch` fails: stop and say so; do not guess the ticket.
