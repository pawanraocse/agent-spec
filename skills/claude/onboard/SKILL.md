---
name: "onboard"
description: >-
  Learn this project once and write it to PROJECT-INDEX + CONSTITUTION. Auto-runs on first session after install.
---

# onboard

The single most expensive habit an agent has is re-deriving the same project facts every
session. This runs once and writes them down.

## Gate

Only run when `.agent-spec/.onboarding-needed` exists, or the user asks explicitly.
If it is absent, say so in one line and stop — the project is already onboarded.

## Budget

**Graph-guided, not a tree walk.** The graph tells you which files matter, so you read a
handful of the right ones instead of hundreds of arbitrary ones.

1. `./.agent-spec/bin/graphify-cli.py stats` — stack, size, cycles, and the
   most-depended-upon files.
2. **Read the top 5 most-depended files.** This is the important step. Conventions live in
   the code every other file imports: how errors are raised, how types are declared, how
   layers talk, what the naming looks like. Five files buys most of the constitution.
3. `./.agent-spec/bin/graphify-cli.py module <dir>` for the two or three largest modules —
   which layers depend on which, and whether the dependency direction is consistent.
4. Read the build manifest, the README if there is one, and one test file (for the test
   command and the assertion style).
5. `git log --format='%s' -100` — commit conventions, and what the project actually works on.

That is roughly ten reads. Do not walk `src/` file by file; if you want more, ask the
graph for it.

## Infer, do not interrogate

Anything the code can show, **write down** — do not turn it into a question. Mark a
derived claim `[INFERRED]` so the user can correct it at a glance. An `[INFERRED]` line
that is slightly wrong is cheap to fix; a question the user has to answer costs them more
than the line was worth.

Reserve `[NEEDS CLARIFICATION]` for what genuinely is not in the repository:

- why the project exists, and who uses it
- business, regulatory or contractual constraints
- deployment target and environments, when nothing in the repo names them
- decisions with no artifact — a convention followed nowhere consistently

## Write

**`.agent-spec/PROJECT-INDEX.md`** — `graphify-build.py` already detected stack and
modules. Fill what it left blank and correct what it got wrong. Add: what this project
*is*, in two sentences; the module map with one line of purpose each; entry points; the
build, test and run commands, copied verbatim from the manifest or README.

**`.agent-spec/CONSTITUTION.md`** — replace the template placeholders with the real
thing. Every entry must be evidence-backed:

| Section | Fill from |
|---|---|
| 1. Project Context | README, manifest, commit subjects |
| 2. Hard Dependencies | the manifest's real dependency list — not what is conventional for the stack |
| 3. Custom Project Rules | the top-5 files: layering, naming, error handling, typing, where IO and arithmetic are allowed |
| 4. Banned Practices | what the code and commit history show the project avoids — a pattern absent everywhere in a large codebase is a rule |

Every line points at a file you read. A line you cannot source does not go in — the
constitution loads every session, so a wrong line there is wrong forever. But absence of
proof is not a reason to leave the section empty: write what the code shows and mark it
`[INFERRED]`.

## Close

1. Run `/self-review` on both files. Bounded, as always.
2. Report in five lines or fewer: stack, module count, build command, test command, and
   the counts of `[INFERRED]` and `[NEEDS CLARIFICATION]`.
3. `rm .agent-spec/.onboarding-needed`.
4. **Ask at most three questions, once, at the end.** Pick the three whose answers change
   the most downstream work. If you have more than three, you did not read enough — go
   back and read, then ask three. Never interrogate section by section as you write.

## Hard stops

- Never invent a build or test command. Run it, or quote it from a file, or tag it.
- Never ask about something the code answers. Read the file instead — that is the whole
  point of this skill.
- Never write source code, never fix a bug, never refactor. This skill only reads and
  writes `.agent-spec/`.
- Never delete the marker before both files are written and reviewed.
