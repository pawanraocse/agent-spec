# AI SDLC Team

A drop-in Claude Code plugin that gives any repository a virtual engineering team:
product requirements through deployment as nine specialist subagents, gated by explicit
handoffs, plus an always-available repo-aware coding assistant and an on-demand
architecture advisor.

**Design principle:** each stage reconciles its output against the previous stage's
artifact and reports anything that does not add up, rather than silently proceeding.
A dropped requirement should surface at the next gate — not in production.

---

## Install

### Quickest — run the installer

From wherever you cloned this repo:

```bash
./sdlc-team/install.sh /path/to/your-project
```

On Windows:

```powershell
.\sdlc-team\install.ps1 C:\path\to\your-project
```

Omit the path to install into the current directory. Both scripts copy the plugin to
`<project>/.claude/skills/sdlc-team/`, verify the install, run `claude plugin validate`
if the CLI is on PATH, and warn you if `.gitignore` would hide it from teammates.

Flags: `--force` / `-Force` to overwrite an existing install, `--dev` / `-Dev` to skip
copying and just print the `--plugin-dir` command.

> **Restart Claude Code afterwards.** It only picks up `.claude/skills/` that existed
> when the session started. A mid-session install looks broken but is not.

Then try `/prd add CSV export`. If that command is not found, try the namespaced form
`/sdlc-team:prd`.

### Manual — if you would rather not run a script

```bash
mkdir -p your-project/.claude/skills
cp -R sdlc-team your-project/.claude/skills/sdlc-team
```

Commit `.claude/skills/sdlc-team/` and it loads automatically for everyone who clones
the repo, once they accept the workspace trust prompt.

### Session-only, no install

```bash
claude --plugin-dir /path/to/sdlc-team
```

Loads for that session only. Best for evaluating it.

### Verify

```bash
claude plugin validate ./sdlc-team
```

No dependencies and no marketplace registration are required.

---

## The pipeline

```
/new-feature "password reset"
     │
     ├─ 1. prd-writer ──────────► 01-prd.md          what & why, acceptance criteria
     ├─ 2. hld-architect ───────► 02-hld.md          components, data flow, NFR budgets
     ├─ 3. lld-designer ────────► 03-lld.md          interfaces, schemas, error taxonomy
     ├─ 4. developer ───────────► code + 04-implementation.md
     ├─ 5. code-reviewer ───────► 05-review.md       severity-ranked findings
     ├─ 6. tester ──────────────► tests + 06-test-plan.md
     ├─ 7. qa-validator ────────► 07-qa-signoff.md   PASS / PASS-WITH-GAPS / FAIL
     └─ 8. deployment-engineer ─► 08-deployment.md   version, rollback, release notes
```

Artifacts are written to `docs/sdlc/<feature-slug>/`, alongside a `pipeline-state.md`
that tracks progress so a run survives a session break.

### How handoffs work

Each agent runs as a subagent in its own context. **Files on disk are the only durable
handoff** — the orchestrator passes paths, not contents, and each agent reads its own
inputs. That keeps the main context small and, more importantly, keeps each stage's
reconciliation honest: an agent checks against the real upstream artifact, not a summary
of it.

### The validation gate

Every pipeline agent must, before handing off, reconcile its output against its input
item by item and classify each as `COVERED`, `PARTIAL`, `MISSING`, `CONTRADICTS`,
`OUT-OF-SCOPE`, or `ADDED` (in the output but traceable to no upstream item — scope
creep). The result is appended to its artifact as a table with a verdict:

| Verdict | Meaning |
|---------|---------|
| `CLEAR` | Nothing unreconciled; hand off |
| `CLEAR WITH NOTES` | Partials and deferrals, each with a reason |
| `BLOCKED` | Something is `MISSING` or `CONTRADICTS` — **the pipeline stops** |

A `BLOCKED` verdict is a report to you, not a failure to work around. The shared
procedure lives in the `handoff-validation` skill, referenced by all eight pipeline
agents — one definition, so it cannot drift between them.

### Confirmation gates

The orchestrator stops after **every** stage and presents what was produced, the
validation verdict, anything needing your decision, and the proposed next stage. It does
not chain stages on a single approval, and does not read silence as consent.

This is why orchestration runs in your main conversation rather than as an agent:
**subagents cannot pause to ask you anything.** They receive one instruction and return
one summary. Putting the pipeline inside a subagent would silently discard every gate.

---

## Commands

| Command | Does |
|---------|------|
| `/new-feature <description>` | Runs all 8 stages with confirmation between each |
| `/prd <description>` | Stage 1 — PRD |
| `/hld <slug>` | Stage 2 — high level design |
| `/lld <slug>` | Stage 3 — low level design |
| `/implement <slug>` | Stage 4 — write the code |
| `/review [slug\|range]` | Stage 5 — review the diff |
| `/test <slug>` | Stage 6 — test plan and tests |
| `/qa <slug>` | Stage 7 — independent sign-off |
| `/deploy <slug>` | Stage 8 — release plan (prepares only) |
| `/ask-architect <question>` | Ad-hoc advice, no artifacts |

Stage commands work standalone — use `/review` on a PR without ever running `/new-feature`.
When an upstream artifact is missing, the agent says so instead of inventing it.

---

## Agents

| Agent | Model | Can edit code? | Role |
|-------|-------|----------------|------|
| `prd-writer` | opus | no | Feature idea → testable acceptance criteria |
| `hld-architect` | opus | no | PRD → components, data flow, trade-offs, NFR budgets |
| `lld-designer` | opus | no | HLD → interfaces, schemas, API contracts, errors |
| `developer` | opus | **yes** | LLD → code in the repo's existing conventions |
| `code-reviewer` | opus | no | Diff → severity-ranked findings |
| `tester` | sonnet | **yes** | Tests mapped 1:1 to acceptance criteria |
| `qa-validator` | sonnet | no | Independent sign-off against the PRD |
| `deployment-engineer` | sonnet | **yes** | CI/CD, versioning, rollback — never deploys |
| `architect-advisor` | opus | no | Options → trade-offs → one recommendation |

`code-reviewer` and `qa-validator` have no `Edit` tool **by design**. An agent that can
modify the code it is checking is not a gate. They keep `Write` for their own artifacts
only, which their prompts state explicitly — a prompt-level constraint, not a sandbox.

`deployment-engineer` prepares releases and never executes one. Deploying is a human
decision with human accountability.

---

## Skills

Each agent's process lives in a skill, so the knowledge is reusable outside the agent —
you can load `code-review` in a normal conversation without spawning a reviewer.

| Skill | Holds |
|-------|-------|
| `prd-writing` | Acceptance-criteria quality bars, goals vs non-goals, metrics |
| `hld-design` | Component decomposition, ADR-shaped decisions, NFR budgeting |
| `lld-design` | Interface precision, migration reversibility, error taxonomy |
| `code-review` | Severity model, security checklist, SOLID checks |
| `testing` | Pyramid, AC-to-test mapping, flakiness avoidance |
| `qa-validation` | Independent verification procedure, verdict rules |
| `deployment` | Semver by consumer impact, expand/contract, rollback structure |
| `architect-advisory` | Options → trade-offs → recommendation, calibrated to stakes |
| `coding-assistant` | **Cross-cutting.** Stack detection, SOLID, repo conventions |
| `pipeline-orchestration` | Stage sequencing, artifact routing, gate handling |
| `handoff-validation` | **The gate.** One reconciliation procedure, shared by all stages |

### `coding-assistant`

The one every code-touching agent loads first. It refuses to assume a stack — it reads
`CLAUDE.md`, then detects the package manager from the lockfile, the linter and formatter
from config, the test framework and file-naming convention from existing tests, the
layout from the directory tree, and the commit style from `git log`. Then it writes code
matching what it found.

Framework specifics live in `skills/coding-assistant/references/` (`typescript.md`,
`python.md`, `go.md`) and load only when relevant, keeping the main skill small.

---

## Currency

Tooling recommendations age. Skills that touch versions, CI actions, or "current best
practice" say so in the body and instruct the agent to verify against the repo's actual
manifest and current upstream docs rather than asserting from memory. The detection
procedures — lockfiles, config discovery, commit-style inference — are durable; the
specific tool opinions in `references/` are the part to re-check over time.

---

## Layout

```
sdlc-team/
├── .claude-plugin/plugin.json
├── agents/           9 subagents
├── commands/        10 slash commands
├── skills/          11 skills
│   └── coding-assistant/references/   framework specifics, loaded on demand
├── install.sh       installer (WSL / Linux / macOS)
├── install.ps1      installer (Windows)
├── TESTING.md       verification prompts per agent and skill
└── README.md
```

---

## Notes

- `commands/` is the older of the two mechanisms; the docs now point new plugins at
  `skills/` for invocable entry points. It works today and is what this plugin uses.
- Agent `skills:` entries use bare skill names. If your Claude Code build requires
  namespacing for plugin skills, they become `sdlc-team:<name>`.
- The pipeline writes to `docs/sdlc/`. To relocate it, change the path in
  `skills/pipeline-orchestration/SKILL.md` and the agent prompts.
