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
   - If accepted: run `agent-spec-memory.py add --type <type> --subject "<3 words>" --source "session <id>" "<one sentence, why>"`.
   - Update candidate status to `"status": "accepted"` in `staged-candidates.jsonl`.
   - If declined: update candidate status to `"status": "declined"`.
2. If no staged candidates, fall back to lines in `experience.jsonl` with `corrections` > 0, newest first, at most 10.
   - For each, ask one question: "What did you correct, and is it still true?"
   - Record confirmed ones with `agent-spec-memory.py add`.
3. Report: facts added, corrections declined, nothing else.

## recall

1. Take the task text. Pick its 3-5 most specific words.
2. `grep -i` those words in the `task` field of `experience.jsonl`; prefer `status: success`, then
   fewest `retries` and `corrections`, then lowest `tokens`. Show the top 3 as one line each:
   `exp_id | status | gates | retries | task`.
3. For each shown, append one line to `experience-reuse.jsonl`.
4. Tell the developer what the best one did differently (gates, workflow) and stop. Never inject
   an experience into context unasked; it is a pointer, not a fact.

## propose

1. Count reuses per `exp_id`:
   `grep -o '"exp_id": *"[^"]*"' .agent-spec/experience-reuse.jsonl | sort | uniq -c | sort -rn`.
2. Take experiences reused at least 3 times with `status: success`.
3. For each, draft `.agent-spec/skill-proposals/<slug>.md`: the repeated task shape, the steps that
   worked (from its `workflow_id` or gates), the failure modes seen, and a draft `SKILL.md` body.
4. Stop. Publishing a proposal into `skills/` is a human decision: show the draft, ask once,
   and only copy it with an explicit yes. Never auto-publish.

## Hard stops

- Never write a fact the developer did not confirm.
- Never copy transcript text into a fact or a proposal; paraphrase.
- Never publish a skill without approval.
- Never edit `experience.jsonl`; the ingestor and hooks own it.
