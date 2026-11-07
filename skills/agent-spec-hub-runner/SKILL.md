---
name: "agent-spec-hub-runner"
description: >-
  Run a workflow skill (agent-spec-wf-*) step by step with Cursor Task subagents, recording state through agent-spec-run.py. Resumable and idempotent.
---

# agent-spec-hub-runner

Input: a workflow id (`example` → `/agent-spec-wf-example`) and the user's request.

## Run

```bash
RUN=./.agent-spec/bin/agent-spec-run.py
$RUN validate <workflow SKILL.md>
$RUN start --workflow <id> --request "<request verbatim>" [--budget-usd N]
```

Keep `run_id` from the output. Exit 3 = refused: read `error`, fix, never bypass.
Interrupted run: `$RUN resume <run_id>`, then continue with its `ready` list.

## Loop

Repeat until `$RUN status <run_id>` shows no `ready` steps:

1. Take every step in `ready`.
2. `$RUN step-start <run_id> <step> --agent <A> --model <tier> [--inputs-json J]`
   - `"reuse": true` → skip the work; its `output` file is the result.
3. Run the step as a Task subagent: `agent-spec-search` for read-only lookups,
   `generalPurpose` otherwise. Prompt = step prompt + outputs of `needs` steps.
4. `$RUN step-end <run_id> <step> --status success --output-json '<result>'
   [--tokens-in N --tokens-out N]`

## Step kinds

- `ai: true` → Task subagent (`agent:`); if the step has `skill:`, read that SKILL.md and prepend it to the prompt (`step-start --skill <name>`).
- `ai: false` → run the shell command given in the step prompt; non-zero exit = failed step (record stderr in `--error`).
- Fetch steps (Jira, Bitbucket): an AI step whose prompt names the Cursor MCP tool to call; store the fields in `--output-json`, never the raw page.

## Parallel

- Independent ready steps → parallel Task calls in one message.
- Disjoint, non-empty `writes` sets → parallel.
- Overlapping `writes`, or any `writes` when the workspace has no git → serialize.

## Retry

- Step errors → `$RUN event <run_id> retry --step <step> --payload-json '{"attempt": n}'`, retry once.
- Second retry → raise `--model` one tier (fast → standard → deep), record `retry`.
- Still failing, or `retries` exhausted → `step-end --status failed --error "<msg>"`.
- Steps that need a failed step → `step-end --status skipped`.

## Human gate

`gate: human` → `$RUN event <run_id> gate.requested --step <step>`, ask the user in chat,
wait. Then `$RUN event <run_id> gate.resolved --step <step> --payload-json '{"approved": true}'`.
Rejected → `step-end --status skipped`.

## Budget

`step-end` returns `budget_exceeded`. When true: stop, tell the user, wait for approval.

## Finish

```bash
$RUN finish <run_id>
```

Answer with `result.json` content: status, one line per step, citations as `path:line`.
`partial` or `failed` → name the failed steps and their errors.

## Hard stops

- Never edit run files by hand.
- Never re-run a step whose `step-start` returned `reuse: true`.
- Never run a step before its `needs` are finished.
- Never pass secrets in `--request` or outputs.
