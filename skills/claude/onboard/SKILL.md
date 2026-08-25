---
name: "onboard"
description: >-
  Learn this project once, so no later session has to re-read it. Fills PROJECT-INDEX.md and writes CONSTITUTION.md from what is actually in the repo — stack, build and test commands, layering, conventions, hard constraints. Runs automatically on the first session after install (marker file .agent-spec/.onboarding-needed) and then never again.
---

# onboard

The single most expensive habit an agent has is re-deriving the same project facts every
session. This runs once and writes them down.

## Gate

Only run when `.agent-spec/.onboarding-needed` exists, or the user asks explicitly.
If it is absent, say so in one line and stop — the project is already onboarded.

## Budget

**Read the graph, not the tree.** This whole skill should cost a handful of file reads.

1. `./.agent-spec/bin/graphify-cli.py stats` — module count, stack, hot files.
2. `./.agent-spec/bin/graphify-cli.py search <domain-word>` for the two or three
   concepts the project name suggests.
3. Read only what the graph names, and only these:
   - the build manifest (`pom.xml`, `package.json`, `pyproject.toml`, `go.mod`, …)
   - the README, if there is one
   - the top one or two entry points the graph ranks highest
   - one representative test file, for the test command and the assertion style
4. `git log --oneline -30` and `git log --format='%s' -100 | head -40` — commit
   conventions and what the project has actually been working on.

**Do not** walk `src/` file by file. If a question survives the four steps above, write
`[NEEDS CLARIFICATION]` and move on. That tag is the correct answer; a guess is not.

## Write

**`.agent-spec/PROJECT-INDEX.md`** — `graphify-build.py` already detected stack and
modules. Fill what it left blank and correct what it got wrong. Add: what this project
*is*, in two sentences; the module map with one line of purpose each; entry points; the
build, test and run commands, copied verbatim from the manifest or README.

**`.agent-spec/CONSTITUTION.md`** — replace the template placeholders with the real
thing. Every entry must be evidence-backed:

| Section | Fill from |
|---|---|
| 1. Project Context | README, manifest, the commit log's subject lines |
| 2. Hard Dependencies | the manifest's actual dependency list — not what is conventional for the stack |
| 3. Custom Project Rules | patterns visible in the code: layering, naming, error handling, where numbers or IO are allowed |
| 4. Banned Practices | what the code and commit history show the project deliberately avoids |

A rule you cannot point at a file for does not go in. An empty section beats an invented
one — the constitution is loaded every session, so a wrong line there is wrong forever.

## Close

1. Run `/self-review` on both files. Bounded, as always.
2. Report in five lines or fewer: stack, module count, build command, test command, and
   the count of `[NEEDS CLARIFICATION]` tags left behind.
3. `rm .agent-spec/.onboarding-needed`.
4. Ask the user to resolve the clarification tags. Those are the parts that will
   otherwise be re-guessed in every future session.

## Hard stops

- Never invent a build or test command. Run it, or quote it from a file, or tag it.
- Never write source code, never fix a bug, never refactor. This skill only reads and
  writes `.agent-spec/`.
- Never delete the marker before both files are written and reviewed.
