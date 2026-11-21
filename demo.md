# Agent-Spec: Enterprise AI Context Intelligence

> **Pitch:** *"The infrastructure layer between AI agents and your codebase — eliminates amnesia, saves 99.6% of structural query tokens, enforces engineering discipline through deterministic pipeline gates, and preserves organizational knowledge across every session."*

---

## What This Is

Agent-spec is a **harness** that wraps Cursor (and Gemini CLI) with structural awareness, bounded memory, and deterministic engineering gates. Every component listed below ships in this repo and passes the self-test suite (`bin/agent-spec-selftest.sh`, 10/10).

---

## ⏱️ 5-Minute Demo — one story, offline (H-051)

One developer works in `orders-api`, one of four small services that really depend on each
other (`examples/mesh-demo/`). Every number on screen is read live from the demo project by
the dashboard, and each carries a Measured, Estimated or AI-judged badge. Nothing in this script
is a figure to read aloud.

**Before (off stage, network off is fine):**

```bash
bash examples/mesh-demo/demo-setup.sh /tmp/agent-spec-demo
cd /tmp/agent-spec-demo/orders-api && python3 .agent-spec/bin/agent-spec-platform.py serve
```

`demo-setup.sh` copies the four repos to `/tmp/agent-spec-demo` (the package is never written
to) and does the following:
- registers `orders-api` (project harness only) and writes the two onboarding files
  `/agent-spec-onboard` would write, because onboarding is an agent action and cannot run offline;
- builds the four-repo mesh;
- records a past fix in `orders-worker` and remembers one fact in `orders-api`
  ("routes are a public contract"), so the digest and the Impact tab have a fact to show;
- replays one recorded Cursor conversation through the real hooks;
- sends one edit of `orders_api/routes.py` to the real risk gate, which blocks it;
- proposes one more fact ("order ids are idempotency keys");
- ingests the platform database.

Open the printed dashboard URL, and keep a terminal in `/tmp/agent-spec-demo/orders-api`.

**Before each rehearsal (H-053):** `python3 examples/mesh-demo/demo-dryrun.py` builds the demo
twice in throwaway directories with the network off (`unshare -rn` on Linux), drives every
beat below with the same commands and the same dashboard calls the buttons make, and prints
each beat's time. A failed check names the beat. It does not replace rehearsing the talk.

| Time | Do | The audience sees |
|---|---|---|
| 0:00–0:30 **Install** | Show the `install.sh --register` line from the setup output, then `ls .cursor/hooks .agent-spec/bin` | The harness is plain files in the repo: hooks, rules and stdlib Python. There is no service to run. |
| 0:30–1:00 **Digest** | `python3 .agent-spec/bin/agent-spec-digest.py` | The block every new chat starts with: stack, graph, pipeline, last session and remembered facts, about 1.7 KB in place of opening four files. |
| 1:00–1:45 **Cross-repo blast radius** | `python3 .agent-spec/bin/graphify-mesh.py query --file orders-api:orders_api/routes.py`, then `python3 .agent-spec/bin/agent-spec-recall.py "worker processes orders.created twice"` | `shop-ui` calls `POST /api/orders` in this file, and `orders-worker` consumes the topic it publishes. Recall returns a fix recorded in a *different* repo and cites `orders-worker:.agent-spec/experience.jsonl:1`. |
| 1:45–2:30 **Tier-3 edit blocked** | Open the dashboard: **Today** leads with "1 risky edit waiting for approval" → **Review** (or Inbox › Risky edits) | The agent's edit of `routes.py` waits there. The tier is 3 because another repo calls the file. The agent was told to wait, and was not told how to approve its own action. |
| 2:30–3:00 **Approved in the dashboard** | Click **Approve once** | The approval works for one retry within 30 minutes, and the decision is a row in `metrics/risk.jsonl`. |
| 3:00–3:45 **Impact** | Activity › Requests → `/agent-spec-hook-probe collect` (the recorded chat, `conv-recorded-1`) → Impact tab | Every figure carries its Measured or Estimated badge. This recording reads no files, so it keeps **0** tokens out: say so, and do not claim a saving it does not show. Then scroll to the raw-code-full rule checks (3 of 3 held) and the fact the digest injected ("routes are a public contract"). Where a chat does keep tokens out, the saving is re-sends in that chat's context, not a lower total bill. |
| 3:45–4:15 **Learning proposal approved** | Inbox › Proposals → **Approve** on "order ids are idempotency keys" | The fact moves into memory. The next chat's digest carries it, and the decision is audited in `metrics/proposals.jsonl`. |
| 4:15–5:00 **Audit export** | Activity › Chats → expand "Rename GET /api/orders/{id}…" → **Export audit**, then `python3 .agent-spec/bin/agent-spec-platform.py audit --verify <file>` | A redacted JSONL of requests, tool actions, risk decisions and outcomes, hash-chained line by line. `--verify` names the first line that was edited. |

**Optional 30 seconds, local model (H-052):** when Ollama is running on this machine, the
Console tab runs a question against it with nothing leaving the machine. It is the only live
agent that works with the network off. Skip it when the Console says no backend. Cursor itself
cannot reach a local Ollama without a public tunnel, so the demo never claims it can.

**If anything misbehaves:** open the recorded request and press **Replay**. The trace plays at
real speed under a *Recorded* badge. If the machine itself fails, play
[`docs/demo/fallback-demo.mp4`](docs/demo/fallback-demo.mp4) (97 s, no audio): the same story,
terminal commands run live while recording and the dashboard driven in a real browser.
Re-record it after a UI change with `examples/mesh-demo/record-video.mjs` (its header has the
three commands).

**Afterwards:** `./uninstall.sh --unregister /tmp/agent-spec-demo/orders-api` removes the demo
project from the registry.

**What is not shown as measured:** token counts on tool and subagent spans. Only
`afterAgentResponse` carries measured input, output and cache counts (see
`tests/fixtures/hooks/README.md`). Durations from Cursor's local store are estimated from
message timestamps and badged so.

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
git clone <repo-url> && cd agent-spec
./install.sh --register /path/to/your/project
# Open the project in Cursor → new session → digest loads automatically
```

Self-test: `./bin/agent-spec-selftest.sh` — expects 10/10 green.
