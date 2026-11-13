---
name: "agent-spec-session-review"
description: >-
  Review one Cursor conversation from its request traces and write span-cited findings the dashboard Coach and Learning views read. Use after a session, on "review this session", or from the dashboard's Review button.
dashboard:
  category: Coach
  icon: gavel
  emits: [review]
---

# agent-spec-session-review (rubric 2.0.0)

You are the judge; no score is computed in code. Read the traces, decide what was slow,
wasteful or unsafe, and write one JSON file. The dashboard only groups and counts what
you write, so every finding must point at a real span.

## 1. Read the traces

```bash
./.agent-spec/bin/agent-spec-platform.py trace --list 20             # find the conversation
./.agent-spec/bin/agent-spec-platform.py trace --session <conversation_id>
```

(In the package repo itself the CLI is `bin/agent-spec-platform.py`.) Each line is
`span_id kind name status duration_ms in=bytes out=bytes note`. `source=cursor_store`
means durations are estimated from message timestamps; say so when you cite one.
Read `.agent-spec/metrics/quarantine.jsonl` only if a `guard` span needs context.
Never open the transcript in full; if you must, read a range around one span.

## 2. Judge against these categories

Use exactly these `category` values so the Coach trend and Learning recurrence line up:

| category | Finding when |
|---|---|
| `whole_file_read` | a large file read without a range where a graph query or `grep -n` + range would do |
| `no_graph_query` | a structural question (callers, blast radius, where X lives) answered by reading files |
| `redundant_read` | the same file or search repeated without anything changing in between |
| `slow_tool` | one tool span dominates the request and a narrower call existed |
| `failed_tool_retry` | a failed tool call repeated unchanged |
| `missing_delegation` | noisy test/build/search output landed in the main context instead of a subagent |
| `oversized_handoff` | a subagent got a vague or huge task, or returned a summary too large to use |
| `guard_ignored` | a guard block was worked around instead of respected |
| `context_bloat` | a compaction, or outputs far larger than the task needed |
| `missing_gate` | code edited with no declared gate or test first |
| `secret_exposure` | a secret-shaped value reached a prompt, output or file |
| `off_task` | work outside what the prompt asked |

Also record what went well (`pros`), each with a span id. Do not invent a finding to fill a
category; an empty `findings` list is a valid result.

## 3. Write `.agent-spec/metrics/reviews/<conversation_id>.json`

```json
{
  "conversation_id": "<id>",
  "session_started": "<ISO start of the first trace>",
  "reviewed_at": "<ISO now, UTC>",
  "model": "<your model id>",
  "rubric_version": "2.0.0",
  "grade": "A|B|C|D|F",
  "summary": "<two sentences>",
  "pros": [{"span_id": "<id>", "text": "<what was good>"}],
  "findings": [{
    "category": "<from the table>",
    "severity": "high|medium|low",
    "title": "<one line>",
    "detail": "<why, with the numbers from the span>",
    "trace_id": "<trace>",
    "span_id": "<span>",
    "fix_prompt": "<one line the user can paste into Cursor to avoid this next time>"
  }],
  "evidence": [{"span_id": "<id>", "check": "<category>", "verdict": "pass|warn|fail"}]
}
```

Then write a dashboard panel (Project › Panels; schema in `docs/DASHBOARD.md`):
`.agent-spec/metrics/panels/agent-spec-session-review/last-review.json` =
`{"type": "kpi", "title": "Last review grade", "value": "<grade>", "hint": "<conversation_id>, <n> findings", "provenance": "ai_judged"}`.

## 4. Close the learning loop

If a category already appears in three or more earlier reviews
(`ls .agent-spec/metrics/reviews/`), propose one fact to the user, do not write it yourself:

```bash
./.agent-spec/bin/agent-spec-memory.py add --type constraint --subject "<short>" \
  --addresses <category> --source "review <conversation_id>" "<one-sentence rule>"
```

The Learning view then measures whether that category becomes rarer after the fact's date.

## Hard stops

- Every finding and every pro cites a `span_id` that exists in the trace output.
- No finding from a span you did not read. No grade without at least one cited span.
- Prompt and response text in your output stays paraphrased; never copy a secret-shaped value.
- Runs on demand or from a scheduled automation, never from a per-turn hook.
