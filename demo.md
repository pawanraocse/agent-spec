# AlgoSec Agent-Spec: Enterprise AI Context Intelligence

> **Pitch:** *"The infrastructure layer between AI agents and your codebase — eliminates amnesia, saves 99.6% of structural query tokens, enforces engineering discipline through deterministic pipeline gates, and preserves organizational knowledge across every session."*

---

## What This Is

Agent-spec is a **harness** that wraps Cursor (and Gemini CLI) with structural awareness, bounded memory, and deterministic engineering gates. Every component listed below ships in this repo and passes the self-test suite (`bin/agent-spec-selftest.sh`, 10/10).

---

## ⏱️ 3-Minute Demo — the request-trace control plane (DEC-16, §14.8)

Every number the audience sees is read live from this repository by the dashboard; none is
written in this script. Each figure on screen carries a Measured, Estimated or AI-judged
badge.

**Before (2 minutes, off stage):**

```bash
./install.sh --register "$(pwd)"                      # hooks write every request to events.jsonl
python3 bin/agent-spec-platform.py ingest             # history, memory, graph, runs
python3 bin/agent-spec-platform.py serve              # open the printed URL; Cursor on the left
python3 bin/agent-spec-platform.py trace --list 5     # pick a fallback request for Replay
```

| Time | Do | The audience sees |
|---|---|---|
| 0:00–1:00 **Live** | In Cursor type `/agent-spec-investigate why does <a real failing test> fail` | The request appears at the top of the feed and its graph grows as hooks fire: prompt → skill → `agent-spec-search` subagent → reads → a red guard node if a whole-file read is blocked → response. The waterfall marks the slowest step. |
| 1:00–1:30 **Inspect** | Click the subagent node, then the Responses tab | Its task, summary, tool-call count, files touched and measured duration; then every response in order. "Copy investigate prompt" hands any span back to the agent. |
| 1:30–2:15 **Coach** | Review tab → copy `/agent-spec-session-review <id>` into Cursor; then open Coach | The grade and findings land, each linked to a span (hovering highlights it). Coach shows the top three issues across reviewed sessions with their weekly trend, a copyable fix prompt each, and measured p50/p95 per span kind. |
| 2:15–3:00 **Learning** | Open Learning | For each fact linked to a finding class (`/agent-spec-remember --addresses …`): findings per session before vs after it was recorded. A flat line is shown as flat. |

**If Cursor or the network misbehaves:** open any request and press **Replay** — the
recorded trace plays at real speed (1×/4×/16×) under a *Recorded* badge.

**What is not shown as measured:** token counts (Cursor's hook payloads carry none; see
`tests/fixtures/hooks/README.md`), and durations from Cursor's local store, which are
estimated from message timestamps and badged so.

---

## 🔬 10-Minute Deep Dive

### 1. Session Digest (`bin/agent-spec-digest.py`)

Replaces the old "open 4 files" protocol. Runs at session start via Cursor's `sessionStart` hook, emits a `<agent-spec-digest>` block capped at 2,600 bytes. Contains: stack info, graph stats, pipeline state, last session summary, remembered facts. Auto-rebuilds the graph if stale (<100ms incremental).

```bash
$ python3 .agent-spec/bin/agent-spec-digest.py
# <agent-spec-digest>
# stack: Python | 47 files, 89 internal edges, 0 cycles
# pipeline: gate 5 implement — feature: auth-refactor
# last session: Completed TokenValidator migration, tests green
# remembered: Auth tokens are JWTs; rate limit is 100/min
# </agent-spec-digest>
```

### 2. Graphify AST Index (`bin/graphify-build.py` + `bin/graphify-cli.py`)

Sub-second AST-based dependency graph. 10 commands: `query`, `search`, `stats`, `cycles`, `module`, `flow`, `services`, `endpoints`, `layers`, `context`. Auto-rebuilds on git checkout/merge/rewrite via `hooks/manage-git-hooks.py`.

```bash
$ graphify-cli.py query --file src/auth/TokenValidator.ts --depth 2
# [BLAST RADIUS] 3 files import this
#   <- services/gateway/ProxyHandler.ts
#   <- services/billing/PaymentAuth.ts
#   <- controllers/AdminController.ts
# [BLAST RADIUS depth 2] 1 file
#   <- routes/admin.ts

$ graphify-cli.py context --task "fix auth token validation"
# terms: auth token validation   files: 4 of 47
#   src/auth/TokenValidator.ts     (match | layer=service | dependents=3)
#   ...
```

### 3. preToolUse Guard (`hooks/cursor-pre-tool-use.py`)

Intercepts wasteful reads before they happen. Nudges once per target per session, then allows retry. Fail-open — never blocks the developer.

| Trigger | Nudge |
|---------|-------|
| `Read` on file >20 KB without offset/limit | "Query the graph or grep -n first" |
| `Write` on file >2 KB that already exists | "Prefer targeted edit over full rewrite" |
| `git diff` without `--stat` | "Run --stat first" |
| `cat` on file >20 KB | "Use grep -n, then ranged read" |

### 4. 6-Gate Implement Pipeline (`skills/agent-spec-implement/`)

Deterministic gates — not suggestions. Each gate must complete before the next begins.

| Gate | Name | What It Enforces |
|------|------|-----------------|
| G1 | Placement | Correct layer/module. Spans two → split. New service → needs ADR. |
| G2 | Tests First | Failing test before the fix. "Unknown" cases explicitly handled. |
| G3 | Build | Surgical diff. Match surrounding style. No adjacent code touched. |
| G4 | Boundary | Architecture tests: layering, purity, import direction. |
| G5 | Verify Clean | Full local gate: tests + linter + type checker. Real output pasted. |
| G6 | Self-Review | 2-pass self-review loop. Agent fixes its own lint/test failures. |

### 5. Bounded Memory (`bin/agent-spec-memory.py`)

Per-project fact store: `decision`, `constraint`, `gotcha`, `reference`. 40-fact cap, 1.2 KB digest cap, automatic rotation of old snapshots at 12 KB. Facts are dated, sourced, and searchable.

### 6. Token Measurement (`bin/agent-spec-tokens.py`)

Commands: `session`, `overhead`, `compare`, `corpus`, `context`, `tools`, `audit`, `list`. Reads Cursor agent transcripts (or Claude Code JSONL with `--claude`). Shows four-bucket weighted breakdown, tool call costs, and context growth curves. `audit` scans harness config for duplicate hooks, missing scripts, and secrets.

### 7. Expert Personas (`.agent-spec/personas/`)

11 personas with hard rules: `@REVIEWER` (default), `@ARCHITECT`, `@SECURITY`, `@API`, `@DATA`, `@DEVOPS`, `@PERF`, `@QA`, `@REFACTOR`, `@WRITER`, `@AI-ARCHITECT`. Activated with `"Activate: @PERSONA_NAME"`. Each carries inline absolute rules — not suggestions.

### 8. Standing Rules + Subagents

- `.cursor/rules/agent-spec.mdc` (~3 KB always-on) — confidence scoring, simplicity filters, hard stops
- `agent-spec-search` / `agent-spec-verify` subagents for off-thread delegation

### 9. Control Plane Dashboard & Subagent Debugging (End-User View)

Full React 19 SPA running on loopback (`http://127.0.0.1:8765`), tracking active sessions, token waterfalls, and governance in real time:
- **System Status Bar & Sparklines:** Live graph freshness, doctor health, hook event status, active jobs, and 7-day trend sparklines.
- **5-Step Interactive Guided Tour:** Built-in interactive walkthrough on the Home tab following the 3-minute pitch sequence.
- **Subagent Navigator & Token Flow:** Highlights subagent runs (e.g. `agent-spec-search`), showing context gauges, token flow curves, and failing test diagnosis.
- **ROI & Savings Telemetry:** Displays Graphify queries executed vs naive reads, calculating net token and dollar savings.
- **Gate Audit & Gaps:** Live green/red 6-gate pipeline status per ticket and deterministic gap detection.
- **AI-Judged Reviews & Prompt Composer:** Honest AI evaluation badge and prompt composer for Cursor slash commands.

### 10. Continuous Self-Learning Flywheel

Converts day-to-day developer corrections into persistent organizational intelligence:
- **Session 1:** Developer corrects agent (e.g., "Internal auth port is 8443, not 8080").
- **Distillation:** Fact persisted in `.agent-spec/memory/facts/`.
- **Session 2+:** Digest automatically injects the fact; subsequent sessions never repeat the error.
- **Flywheel Metric:** Track declining correction rate and retry frequency across sprints.

---

## 🏢 Enterprise Value Matrix

| Company Priority | Harness Mechanism | Concrete Demo Proof |
|------------------|-------------------|---------------------|
| **Efficiency** | `sessionStart` digest (<100ms) | Turns 5-min manual context setup into 0 seconds |
| **Token Savings** | Graphify AST + `preToolUse` | 152B vs 36KB per structural lookup (99.6% savings) |
| **Better Results** | 6-Gate SDLC + `@REVIEWER` | Eliminates speculative code and regressions before commit |
| **Transparency** | Local dashboard & token metrics | Real-time session timeline, waterfall, and gate receipts |
| **Security** | Local execution + secrets filter | No IP/prompts leave workstation; hard stop on secrets |
| **Subagent Ops** | Subagent Health Navigator | Instant diagnosis of failing background tasks |
| **Self-Learning** | Experience & memory flywheel | Corrections compound across developers and chats |

---

## ❓ FAQ

### "Isn't this just Cursor rules?"

| | Cursor Rules (`.mdc`) | Agent-Spec |
|---|---|---|
| **Memory** | None. Every session starts blank. | Bounded facts + snapshot rotation. Survives across sessions. |
| **Structural awareness** | None. Agent reads files to find dependencies. | AST graph. 152B vs 35,966B per query. |
| **Pipeline enforcement** | Voluntary. Developer invokes skills manually. | 6 deterministic gates with state tracking (`STATE.json`). |
| **Token discipline** | None. Agent reads whatever it wants. | `preToolUse` hook intercepts wasteful reads. Token measurement built in. |
| **Session continuity** | None. | Digest injects last session state + remembered facts at session start. |

### "What's the measured overhead?"

- Digest injection: **<100ms**, **~1.7 KB** — replaces ~6,000 tokens of file reads
- Graph query: **sub-second**, **152 bytes** — replaces ~36 KB of tree walking
- preToolUse hook: **<50ms** per check, fail-open
- Standing rules: **~3 KB** always-on context

### "Why does an enterprise need this?"

AI agents without structural awareness make locally correct changes that break transitive dependencies. Without bounded memory, every session re-discovers the same constraints. Without pipeline gates, engineering discipline is optional. Agent-spec makes these problems infrastructure, not prompts.

---

## 🗺️ Roadmap

**Sequence and task status:** [`todo-plan.md`](todo-plan.md). **Strategy and exit gates:** [`docs/MASTER-PLAN.md`](docs/MASTER-PLAN.md).  
**Dashboard panel map (Phase 2 shipped):** [`docs/DASHBOARD.md`](docs/DASHBOARD.md).  
Section **§9** is now shipped as the Control Plane v2 SPA; §10 self-learning flywheel is live via `.agent-spec/memory/`.

---

## Quick Start

```bash
git clone <repo-url> && cd algosec-agent-spec
./install.sh --register /path/to/your/project
# Open the project in Cursor → new session → digest loads automatically
```

Self-test: `./bin/agent-spec-selftest.sh` — expects 10/10 green.
