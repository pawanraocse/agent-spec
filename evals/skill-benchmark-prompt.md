# Prompt: measure /agent-spec-raw-code-full in Claude Code

Paste everything below the line into a new Claude Code session opened in this repository. Keep
that session idle otherwise while the benchmark runs: it starts headless `claude -p` processes
(`--allow-nested`), and Claude Code warns that nested sessions share runtime state.

---

Measure whether the skill `/agent-spec-raw-code-full` saves money and tokens and keeps or
improves accuracy, in real Claude Code on `claude-haiku-5-5`. I need a result I can defend in
front of others, so the measurement must be honest: a negative or inconclusive result is a
valid outcome, and must be reported as such.

The tool already exists: `bin/agent-spec-cursor-bench.py --agent claude`. Read its docstring
and `docs/LIVE-TESTING.md` ("The same tasks in Claude Code, with edits") before starting. It
runs each task twice, plain and with the skill typed on turn 1. Each chat gets a fresh copy of
the repository. Both arms get the same `CLAUDE.md` and installed skill, with
`--setting-sources project`. The report gives Claude Code's own cost and token counts per
turn, plus a paired statistical table. The tasks are in `evals/cursor-bench.jsonl`: 3 question
tasks and 3 edit tasks, and edit turns are scored by check commands.

Rules:
- Do not change the bench, the tasks or the skill to make one arm look better. If you think a
  task or the bench is unfair to one arm, stop and tell me why instead of changing it.
- Do not commit. Do not print secrets or API keys.
- Run long commands in the background and wait for them; do not poll in a loop.
- Quote numbers exactly as the report prints them.

Steps:

1. Preflight. Run `claude --version` and `python3 tests/test_cursor_bench.py`. Both must
   succeed.

2. Smoke run:
   `python3 bin/agent-spec-cursor-bench.py --agent claude --allow-nested --only savings,fix-bug --keep`
   It must exit 0. In the report, "Skill body found in the saved chat" must be above 0 for the
   skill arm and 0 for the plain arm, and every turn must show a cost.
   - If the skill never loaded, or the plain arm loaded it, stop and diagnose with the kept
     workspaces under /tmp (prefix `aspec-claude-bench-`) and their session files under
     `~/.claude/projects/`. Then report to me.
   - Delete the kept workspaces afterwards.

3. Cost estimate. From the smoke run's cost per chat, estimate the full run (6 tasks × 3
   repeats × 2 arms = 36 chats). If it is above $10, tell me and wait for my approval.

4. Full run, in the background:
   `python3 bin/agent-spec-cursor-bench.py --agent claude --allow-nested --repeat 3`
   If it stops early (usage limit, exit 3), report what was completed and do not mix in
   numbers from other runs.

5. Verdict. Use the "Paired by chat" table:
   - "The skill saves cost" only if the 95% CI of the cost change is entirely below 0%.
   - "The skill costs more" only if it is entirely above 0%.
   - Otherwise: "no measurable difference at this sample size". Say how many more chats would
     be needed, judging from the CI width.
   - Do the same for all input tokens, cache-write tokens and output tokens.
   - Accuracy: compare correct turns per arm and the McNemar line. Never call a 1–2 turn
     difference a change.

6. Diagnosis. Use the per-turn rows in `.agent-spec/eval/cursor-bench-results.jsonl`, filtered
   by this run's `run_id`.
   - Per task: where does the skill help and where does it hurt?
   - Which metric drives the difference: the skill text written to the prompt cache, more or
     fewer tool calls, longer or shorter answers, or more turns failing?
   - Show the 3 turns with the largest cost difference between arms, with both answers.

7. If the skill does not clearly help, propose specific edits to
   `skills/agent-spec-raw-code-full/SKILL.md`, each tied to a finding from step 6. Do not apply
   them. A re-test after edits must use new tasks the edits were not tuned on, so also propose
   2 new edit tasks in the same format as `evals/cursor-bench.jsonl`.

8. Write a dated section with the verdict, the summary table, the paired table and the
   diagnosis at the end of `docs/evidence/H-050.md`. Label it "Claude Code on
   claude-haiku-5-5, not Cursor". Then give me a short summary:
   - one verdict sentence;
   - the exact claim we can make in a presentation, or "no claim" if the data does not
     support one;
   - what the proposed next step is.
