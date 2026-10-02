---
name: agent-spec-skill-creator
description: Create new skills, modify and improve existing skills, and measure skill performance. Use when users want to create a skill from scratch, edit, or optimize an existing skill, run evals to test a skill, benchmark skill performance with variance analysis, or optimize a skill's description for better triggering accuracy.
---

# Skill Creator

Helps users create, improve, and benchmark agent skills through a test-driven loop.

**Full workflow guide:** `docs/full-guide.md` — read it before starting. It contains the
complete instructions for every stage below, including subagent prompts, JSON schemas,
viewer commands, Claude.ai and Cowork adaptations. Do not reproduce it here.

## The loop (high level)

1. **Understand intent** — extract from conversation or interview the user.
2. **Draft the skill** — write `SKILL.md` following the anatomy in `docs/full-guide.md`.
3. **Write test cases** — 2–3 realistic prompts; save to `evals/evals.json`.
4. **Run evals** — spawn with-skill + baseline subagents in the same turn.
   Draft assertions while runs are in progress.
5. **Grade and view** — aggregate results; launch `eval-viewer/generate_review.py`.
   Show the human before revising anything yourself.
6. **Read feedback** — read `feedback.json`; improve the skill.
7. **Repeat** from step 4 until the user is satisfied.
8. **Optimize description** — run `scripts/run_loop.py` for triggering accuracy.
9. **Package** — `scripts/package_skill.py`; present the `.skill` file.

## Token cost rule

After each eval cycle:
```bash
./.agent-spec/bin/agent-spec-tokens.py
```
A skill invocation should add **< 400 tokens** to session context. Trim `SKILL.md`
if it exceeds this before iterating further.

## Key constraints

- SKILL.md body: ≤ 500 lines; evidence and rationale go in `docs/`, not the body.
- Always generate the eval viewer **before** evaluating outputs yourself.
- A cheaper arm that did less is not a saving — verify completion before comparing cost.
- Skill description is the primary trigger mechanism; optimize it last, after the body is stable.

## Reference files

- `docs/full-guide.md` — complete workflow, all stages, platform adaptations
- `agents/grader.md` — assertion evaluation instructions for grader subagent
- `agents/comparator.md` — blind A/B comparison instructions
- `agents/analyzer.md` — benchmark analysis instructions
- `references/schemas.md` — JSON schemas for evals.json, grading.json, benchmark.json
