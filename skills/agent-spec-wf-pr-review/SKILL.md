---
name: "agent-spec-wf-pr-review"
description: >-
  Review a branch against its base: diff, deep review, validation of each finding. Run via /agent-spec-hub-runner. Input is a branch or PR.
---

# agent-spec-wf-pr-review

`/agent-spec-hub-runner pr-review` with a branch name or PR id (base defaults to `develop`).
Read-only: findings are reported, never applied.

```steps
- id: diff
  ai: true
  agent: agent-spec-search
  writes: []
  retries: 1
- id: review
  needs: [diff]
  ai: true
  agent: generalPurpose
  skill: agent-spec-review
  model: deep
  writes: []
  retries: 1
- id: validate
  needs: [review]
  ai: true
  agent: generalPurpose
  writes: []
  retries: 1
```

## Step prompts

**diff** — Resolve the branch (remote first). Run `git diff --stat <base>...<branch>` and
`git diff --name-only`; for each changed file run `./.agent-spec/bin/graphify-cli.py query --file <path>`
and `./.agent-spec/bin/agent-spec-blast-radius <path>` for the three largest changes. For a PR id, use
the Bitbucket MCP tools (`bitbucket___getPullRequestDiffstat`) for metadata only. Return JSON
`{"base": "", "branch": "", "files": [{"path": "", "added": 0, "removed": 0, "dependents": 0}]}`.

**review** — Apply the review skill to the changed hunks only (`git diff -U5 <base>...<branch> -- <path>`
per file, never the whole diff at once). Blockers first, style last. Return JSON
`{"findings": [{"id": "F1", "severity": "blocker|major|minor|nit", "path": "", "line": 0,
"issue": "", "fix": ""}]}`.

**validate** — Re-read the cited lines for every `blocker` and `major` finding and try to disprove it.
Return JSON `{"verdicts": [{"id": "F1", "confirmed": true, "evidence": "path:line"}],
"summary": "", "merge_ready": false}`. Drop unconfirmed findings from the summary and say how many.

## Rules

- Committed code only; ignore the working tree.
- Do not comment on the PR unless the user asks.
