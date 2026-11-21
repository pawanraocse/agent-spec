---
name: "agent-spec-learn"
description: >-
  Learn from past work in three modes - distill corrections into facts, recall similar past experiences before a task, propose a skill from repeated ones. No code; publishing needs a human.
---

# agent-spec-learn

`/agent-spec-learn distill | recall <task> | propose`. Data: `.agent-spec/experience.jsonl`
(one JSON line per session or workflow run, written by the session-end hook and
`agent-spec-run.py finish`). Fields: `exp_id`, `kind`, `ts`, `task`, `status`, `tokens`,
`gates`, `retries`, `corrections`, `facts_injected`, `workflow_id`, `run_id`.
Reuse log: `.agent-spec/experience-reuse.jsonl` (`{"ts", "exp_id", "task"}`), written only by `recall`.

## distill

1. Check `.agent-spec/memory/staged-candidates.jsonl` first.
   - If present with `status: pending`: present the staged correction candidate:
     `"Found staged correction from session <session_id>: '<candidate>' (context: '<task>'). Accept to save as memory fact? [constraint | gotcha | decision | decline]"`
   - If accepted: run `agent-spec-memory.py add --type <type> --subject '<3 words>' --source 'session <id>' '<one sentence, why>'` (single quotes: backticks inside double quotes run as commands).
   - Update candidate status to `"status": "accepted"` in `staged-candidates.jsonl`.
   - If declined: update candidate status to `"status": "declined"`.
2. If no staged candidates, fall back to lines in `experience.jsonl` with `corrections` > 0, newest first, at most 10.
   - For each, ask one question: "What did you correct, and is it still true?"
   - Record confirmed ones with `agent-spec-memory.py add`; queue unconfirmed ones with
     `agent-spec-memory.py propose --evidence "<why>"` for the Proposals inbox.
3. Report: facts added, corrections declined, nothing else.

## recall

1. Run `./.agent-spec/bin/agent-spec-recall.py "<task text>"`. It searches this project's
   `experience.jsonl` and those of the repos that share a mesh with it (P3-014). It skips
   deprecated rows and ranks by matched task words, then promoted, then `status: success`, fewest retries and
   corrections, and lowest tokens. It prints the top 3 as
   `exp_id | status | gates | retries | task  [<repo>:<file>:<line>]`.
2. Keep the bracketed citation when you report a match, so a fix from another repo names that
   repo.
3. The script appends the shown matches to this project's `experience-reuse.jsonl`. Do not
   log them again.
4. Tell the developer what the best one did differently (gates, workflow) and stop. Never inject
   an experience into context unasked; it is a pointer, not a fact.

## propose

1. Count reuses per `exp_id`:
   `grep -o '"exp_id": *"[^"]*"' .agent-spec/experience-reuse.jsonl | sort | uniq -c | sort -rn`.
2. Take experiences reused at least 3 times with `status: success`.
3. For each, draft `.agent-spec/skill-proposals/<slug>.md` as an `agent-spec-wf-<slug>` workflow
   run by `/agent-spec-hub-runner <slug>`, never a loose global skill. Carry over the repeated task
   shape, the steps that worked (from its `workflow_id` or gates) and the failure modes seen. Map
   read-only lookups to `agent: agent-spec-search`, deterministic shell steps to `ai: false`, and
   human decisions to `gate: human`. Replace concrete ticket IDs, branches and paths with
   `<KEY>`, `<BRANCH>`, `<PATH>` parameters. Keep the description under 150 characters.
4. Validate it: `python3 bin/agent-spec-run.py validate .agent-spec/skill-proposals/<slug>.md`.
5. Stop. Publishing a proposal is a human decision made in the dashboard's Project › Proposals
   inbox (it validates and copies the draft). Never copy it yourself.

## Hard stops

- Never write a fact the developer did not confirm.
- Never copy transcript text into a fact or a proposal; paraphrase.
- Never publish a skill without approval.
- Never edit `experience.jsonl`; the ingestor and hooks own it.
