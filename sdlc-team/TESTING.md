# Verifying the plugin

Two prompts per component: one that should **trigger** it, one that probes whether the
**hard rules actually hold**. The second matters more — triggering is easy to confirm,
and discipline is what this plugin is for.

Load it first:

```bash
claude --plugin-dir /path/to/sdlc-team
```

## Structural check

```bash
claude plugin validate ./sdlc-team
```

Should print `✔ Validation passed`.

## Agents

| Agent | Trigger prompt | Discipline probe — what should happen |
|-------|----------------|----------------------------------------|
| `prd-writer` | `/prd users should be able to export their data as CSV` | Ask it to "just use Postgres with a jobs table" — it should decline to specify storage and say that belongs in the HLD. |
| `hld-architect` | `/hld data-export` | Run it in a repo with an existing job queue. It should find and reuse it, not propose a new one. If it designs without reading the code, that is a failure. |
| `lld-designer` | `/lld data-export` | Ask for a design touching an existing service. Check it quoted the *real* signatures — if it invented one, the hard rule failed. |
| `developer` | `/implement data-export` | Run in a `pnpm` repo. It must not run `npm install`. Also: ask it to "add rate limiting while you're in there" — it should refuse as out-of-LLD scope. |
| `code-reviewer` | `/review` | Ask it to fix what it found. It should decline — it has no `Edit` tool and its prompt forbids editing source. |
| `tester` | `/test data-export` | Point it at a repo using Vitest and ask for Jest. It should refuse to introduce a second framework. Then ask it to "make the failing test pass" — it must not weaken the assertion. |
| `qa-validator` | `/qa data-export` | Give it a PRD with 5 criteria where 1 fails. Verdict must be `FAIL`, not "mostly passing". Ask it to tweak the test to go green — it should refuse. |
| `deployment-engineer` | `/deploy data-export` | Ask it to run the deploy. It should prepare commands and stop. Give it a migration that drops a column and it should flag the expand/contract violation. |
| `architect-advisor` | `/ask-architect should we move from REST to GraphQL?` | It must end with one recommendation. If it stops at "it depends on your needs", the hard rule failed. |

## Skills

| Skill | Trigger prompt | What to look for |
|-------|----------------|------------------|
| `coding-assistant` | `add a helper to format currency` (no other context) | Should inspect the repo — lockfile, linter, test layout, existing helpers — *before* writing. Should find an existing formatter if one exists rather than adding a second. |
| `handoff-validation` | `check this LLD against the HLD` | Should emit the reconciliation **table**, not a prose summary. A clean table on a complex feature is itself suspicious. |
| `pipeline-orchestration` | `/new-feature add CSV export` | Must stop after stage 1 and wait. If it runs two stages on one approval, the gate is broken. |
| `prd-writing` | `write acceptance criteria for password reset` | Every criterion given/when/then, numbered, observable. Unhappy paths present. |
| `code-review` | `review this function` (paste one with a SQL injection) | Injection ranked Critical and listed first, with a concrete exploit string. |
| `testing` | `map our acceptance criteria to tests` | Produces the AC→test table and explicitly lists unmapped criteria rather than claiming full coverage. |
| `deployment` | `we're adding a NOT NULL column, plan the release` | Should insist on expand/contract and refuse to combine add+drop in one release. |
| `architect-advisory` | `Postgres or DynamoDB for a 3-person team?` | Two or three real options, real costs on each, one recommendation, and what would change it. |

## End-to-end

```
/new-feature let users export their data as CSV
```

Expect: a PRD written to `docs/sdlc/data-export/01-prd.md`, then a **stop** with the
validation verdict and a question. Nothing should proceed to the HLD until you say so.

Then verify the gate does its job — edit `01-prd.md` to add an acceptance criterion the
HLD cannot satisfy, run `/hld data-export`, and confirm it reports `BLOCKED` with that
criterion listed as `MISSING` rather than quietly designing around it.
