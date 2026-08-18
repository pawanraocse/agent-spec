---
name: coding-assistant
description: "Repo-aware coding discipline. Read CLAUDE.md, detect the real stack from lockfiles, linter config, test setup and commit history, then write SOLID, testable code that matches what is already there. Load before writing or suggesting ANY code in an unfamiliar repo, and whenever choosing a library, test framework, or file location."
---

# Coding Assistant

Code that is technically correct but stylistically foreign is a defect. It fails
review, it fights the linter, and it teaches the next reader that conventions here
are optional.

**Never assume a stack. Detect it.** The cost of detection is a handful of shell
commands; the cost of assuming is a rewrite.

## Step 1 — Read the project's own instructions first

```bash
for f in CLAUDE.md AGENTS.md CONTRIBUTING.md .cursorrules .github/copilot-instructions.md; do
  [ -f "$f" ] && echo "=== $f ===" && cat "$f"
done
```

Project instructions outrank everything in this skill. If `CLAUDE.md` says
"no dependency injection frameworks," that is the end of the discussion, whatever
general best practice says. Also check for nested `CLAUDE.md` in the directory you
are editing — they override the root for that subtree.

## Step 2 — Detect the stack from evidence

Run these before writing anything. Each answers a question you would otherwise guess.

### Package manager — the lockfile is the authority

```bash
ls -1 package-lock.json pnpm-lock.yaml yarn.lock bun.lockb \
      poetry.lock uv.lock Pipfile.lock requirements.txt \
      Cargo.lock go.sum Gemfile.lock composer.lock \
      pom.xml build.gradle build.gradle.kts 2>/dev/null
```

The lockfile decides your install command. A repo with `pnpm-lock.yaml` gets
`pnpm add`, never `npm install` — running the wrong one rewrites the lockfile and
produces a diff nobody asked for.

### Linter and formatter — match, do not impose

```bash
ls -1 .eslintrc* eslint.config.* biome.json* .prettierrc* prettier.config.* \
      ruff.toml .ruff.toml setup.cfg tox.ini .flake8 \
      .rubocop.yml .golangci.yml rustfmt.toml .editorconfig 2>/dev/null
grep -lE '"(lint|format)"' package.json 2>/dev/null
grep -A15 -E '^\[tool\.(ruff|black|mypy)\]' pyproject.toml 2>/dev/null
```

Read the config, do not just note its existence. Line width, quote style, semicolons
and import order are all decided there. If a formatter is configured, run it on your
output before presenting the change.

### Test framework and layout

```bash
ls -1 vitest.config.* jest.config.* playwright.config.* cypress.config.* \
      pytest.ini conftest.py 2>/dev/null
grep -E '"(test|test:unit|test:e2e)"' package.json 2>/dev/null
find . -path ./node_modules -prune -o \
       \( -name '*.test.*' -o -name '*.spec.*' -o -name 'test_*.py' -o -name '*_test.go' \) -print 2>/dev/null | head -20
```

That last command answers three questions at once: which framework, which naming
convention (`.test.ts` vs `.spec.ts`, `test_x.py` vs `x_test.py`), and **where tests
live** — colocated beside source, or in a parallel `tests/` tree. Match all three.

### Naming and structure conventions

```bash
find src app lib -maxdepth 2 -type d 2>/dev/null | head -30
find src app lib -maxdepth 2 -type f 2>/dev/null | head -30
```

Infer and then follow: `kebab-case.ts` vs `PascalCase.tsx` vs `snake_case.py`;
grouping by layer (`controllers/`, `services/`) vs by feature (`auth/`, `billing/`).
Adding a feature-grouped module to a layer-grouped repo is a structural regression
even when every file is individually well written.

### Commit style

```bash
git log --oneline -20
git log -3 --format='%B'
```

Detect Conventional Commits (`feat:`, `fix(scope):`), ticket prefixes (`PROJ-123:`),
capitalization, imperative vs past tense, and whether bodies are used. Match it.

### Existing utilities — before you write a helper, look for it

```bash
grep -rn "export function\|export const" src/utils src/lib src/helpers 2>/dev/null | head -30
```

The most common avoidable defect in agent-written code is a fourth `formatDate`.
Search before you add.

## Step 3 — Write to the conventions you found

### SOLID, applied proportionally

| Principle | In practice | Failure mode it prevents |
|-----------|-------------|--------------------------|
| **S**ingle responsibility | One reason to change per unit | The 900-line service nobody can test |
| **O**pen/closed | Extend via new types, not new `switch` arms | Editing five files to add one case |
| **L**iskov substitution | Subtypes honor the base contract | The override that throws on a valid input |
| **I**nterface segregation | Narrow, role-shaped interfaces | Test doubles stubbing nine unused methods |
| **D**ependency inversion | Depend on abstractions; inject them | Business logic that needs a live database to test |

Apply these in proportion to the problem. A three-line pure function does not need an
interface, a factory, and a strategy. **Speculative abstraction is a defect too** —
the standard is "justified by actual reuse or a real seam," never "might help later."

### Testability is a design property

If you cannot test it without a network, a clock, or a database, the design is wrong —
not the test. Inject those as dependencies. Prefer pure functions for logic and push
I/O to the edges.

### Errors

Match the repo's existing strategy: typed errors, result types, or exceptions. Never
introduce a second paradigm alongside the first. Never swallow an error to make a
signature tidy.

## Step 4 — Verify before presenting

```bash
# use the repo's own scripts, discovered in step 2
<lint command> && <format command> && <test command>
```

If you cannot run them, say so explicitly rather than implying the code is verified.
"I could not run the test suite in this environment" is a useful sentence. Silence
that lets the reader assume tests passed is not.

## Currency

Stack detection above is durable — lockfiles and config files change slowly. **Specific
tool and version recommendations are not.** Before recommending a library, framework
version, or "current best practice," verify it against the repo's actual manifest and,
where it matters, current upstream docs. Do not hard-code a version you remember; read
the one the repo pins. Anything in `references/` may have aged — treat it as a starting
point to confirm, not a fact.

## Framework references

Load only the one that matches what you detected:

- `references/typescript.md` — Node/TS: module style, strictness, test layout
- `references/python.md` — packaging, typing, pytest conventions
- `references/go.md` — package layout, error wrapping, table-driven tests

## Anti-patterns

- Running `npm install` in a `pnpm`/`yarn`/`bun` repo.
- Adding a formatter or linter the repo did not ask for.
- Introducing a second HTTP client, date library, or test framework.
- Reformatting untouched lines, burying the real change in whitespace noise.
- Writing a new utility that already exists three directories over.
- Adding a dependency to solve what ten lines of stdlib would.
