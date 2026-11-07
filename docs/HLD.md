# High-level design — algosec-agent-spec harness

Back-link: [README](../README.md) · [Confluence (canonical publish)](https://algo-confluence.algosec.com/pages/viewpage.action?pageId=234765194)

**Package version:** see [`VERSION`](../VERSION). **Scope:** Cursor IDE engineering harness (client-side only).

> **Confluence:** Paste into [234765194](https://algo-confluence.algosec.com/pages/viewpage.action?pageId=234765194). Diagrams in this doc are **tables only** (no Mermaid). Optional PNG charts available on Confluence.

---

## How to use this document

| Path | Audience | Time | Start here |
|------|----------|------|------------|
| **Demo / leadership** | Exec, EM, presenter | 5–12 min | [30-second pitch](#30-second-pitch) → [Live demo runbook](#live-demo-runbook-10-minutes) → [Leadership FAQ (short)](#leadership-faq-short) |
| **Architecture** | Tech lead, senior dev | 20–30 min | §2 System context → §5.1 lifecycle → §5.2 SDLC tracks → §7 Security |
| **Install & operate** | Dev enabling harness | As needed | §8 Install · §9 Rollback · §11 Operations · [Appendix C](#appendix-c-script-inventory) |

### At a glance

| Pain (vanilla Cursor) | Harness answer | Measured lever ([token-efficiency.md](token-efficiency.md)) |
|------------------------|----------------|-------------------------------------------------------------|
| Turn-1 amnesia | `sessionStart` digest | ~1.7 KB orientation |
| Whole-file reads | `graphify-cli.py` | ~152 B vs ~35,966 B per lookup |
| Test logs in chat | `agent-spec-verify` | Verdict on main thread only |
| Context rot | `/agent-spec-compact` | 480,083 → 53,191 tokens (one session) |

### 30-second pitch

**algosec-agent-spec** is a **client-side** Cursor harness: global `/agent-spec-*` skills, per-repo rules and hooks, and `.agent-spec/` on disk. No harness servers. It orients the agent in milliseconds, nudges away from expensive context habits, runs **nine SDLC gates (0–8)** when scope requires it, and preserves decisions in git between chats.

---

## 1. Purpose and scope

**Purpose:** Give developers a repeatable way to orient on a codebase, query structure instead of loading large files, gate multi-step design work, and preserve decisions on disk between IDE sessions.

**In scope:**

- Machine-wide skill packages (`/agent-spec-*` commands).
- Per-repository harness: rules, hooks, binaries, graph, memory, SDLC gate state.
- Local measurement of session transcripts (`agent-spec-tokens.py`).

**Out of scope:**

- Hosted services, runtime components in AlgoSec data centers, or changes to product application CI unless a team opts in (e.g. `agent-spec-selftest.sh`).
- Mandatory third-party integrations (MCP servers are optional and user-configured in the IDE).

### 1.1 The Developer Experience: A Day in the Life (Before vs. After)

Compare a typical morning in **vanilla Cursor** vs **with `algosec-agent-spec`** (Confluence-friendly table; no diagram required).

| Time | Moment | Vanilla Cursor | With harness |
|------|--------|----------------|--------------|
| **09:00** | Open a fresh chat | Turn-1 amnesia: re-explain stack, ticket, and constraints (~5 min). | `sessionStart` injects a **~1.7 KB** digest in sub-50 ms. Example opener: *"Resuming Gate 1 on AuthService. Auth port is 8443. What's next?"* |
| **09:30** | Explore architecture (e.g. callers of `RuleEngine`) | Many whole-file reads (~35,000 tokens); cost and cache churn. | `graphify-cli.py` structural query (**~152 B**); avoid loading entire files. |
| **10:15** | Run the test suite | Full console log in chat (e.g. 2,000 lines); passing output re-billed every turn. | `agent-spec-verify` subagent: off-thread run, **verdict + failures only** on main thread (e.g. *VERDICT: PASS — 42 tests green*). |
| **11:00** | Finish a task / reset context | Thread at ~90k tokens ("context rot") or **New Chat** and lose narrative. | `/agent-spec-compact`: large token drop (measured **−88.9%** on one session); decisions in `SESSION-SNAPSHOT.md` on disk. |

---

## 2. System context & architecture layers

**System context (client-side only — no harness server):**

| Zone | Component | Location | Relationship |
|------|-----------|----------|--------------|
| Developer machine | Cursor IDE | Desktop app | Drives chat, tools, rules, hooks |
| Developer machine | Native hooks | `sessionStart`, `preToolUse` | Call `.cursor/hooks/agent-spec-*.py` |
| Developer machine | Global skills | `~/.cursor/skills/agent-spec-*` | On-demand `/agent-spec-*` in any project |
| Registered workspace | Standing rules | `.cursor/rules/agent-spec.mdc` | Always-on protocol in prompt prefix |
| Registered workspace | Hook adapters | `.cursor/hooks/agent-spec-*.py` | Bridge hooks → `.agent-spec/bin/` |
| Registered workspace | Git lifecycle hooks | `.git/hooks/post-checkout`, `post-merge`, `post-rewrite` | Non-blocking auto-reindexing on branch switch/pull/rebase |
| Registered workspace | Task subagents | `.cursor/agents/agent-spec-*.md` | Off-thread search / verify |
| Registered workspace | Project brain | `.agent-spec/` | Graph, memory, SDLC, binaries |
| External (optional) | Cursor LLM | Cloud inference | IDE only; harness scripts do not call out |
| External (optional) | MCP servers | User-configured in IDE | Optional integrations |

### 2.1 Architectural layers

The system is structured into three clean, isolated operational layers:

| Layer | Physical location | Components & contents | Lifecycle & governance |
|---|---|---|---|
| **1. Global Skills** | `~/.cursor/skills/agent-spec-*` | 31 on-demand command packages (`/agent-spec-*`) | Installed once per machine via `./install.sh`. Available across all Cursor projects. |
| **2. Registered Workspace** | `<project-root>/.cursor/` & `.agent-spec/` | Standing rules (`agent-spec.mdc`), hook adapters, subagents, dependency graph, memory facts, SDLC state | Registered once per app repo via `./install.sh --register`. Project-specific state committed to git. |
| **3. External Boundary** | Cloud / Network | Cursor LLM inference endpoints; optional user-configured MCP servers | **Zero harness servers.** No telemetry, code, or prompts are sent to any external server. |

---

### 2.2 Step-by-step execution flow

When an engineer works in Cursor, the harness executes through six discrete, non-blocking steps:

1. **Bootstrapping (Global Commands):** Cursor reads `~/.cursor/skills/` on startup. The 31 `/agent-spec-*` commands become instantly callable in any chat without project configuration.
2. **Session Start & Orientation Injection:** When the developer opens a new chat, Cursor’s native `sessionStart` hook runs `.cursor/hooks/agent-spec-session-start.py`, which executes `agent-spec-digest.py`. It verifies graph freshness (<50ms check against Git `HEAD`/`index` with a 3-second fail-open safety net), reads bounded facts and graph stats from `.agent-spec/`, and injects a **~1.7 KB digest** into the prompt envelope, eliminating AI amnesia.
3. **Standing Rule Binding:** Cursor loads `.cursor/rules/agent-spec.mdc` into the cached prompt prefix. This binds the model to non-negotiable engineering rules: `[CONFIDENCE]` scoring, ranged reads, and persona boundaries.
4. **Guardrail Interception (`preToolUse`):** When the AI issues a tool call (reading a file, running a shell command, or editing code), the `preToolUse` hook intercepts it. If an expensive pattern is detected (e.g. attempting to read a 35KB file whole), the hook issues a one-shot nudge to use `graphify-cli.py` or ranged reads. The hook is **strictly fail-open**—it returns `{"permission": "allow"}` if any exception occurs.
5. **Off-Thread Delegation:** When running heavy searches or verifying test suites, the AI delegates the work to `.cursor/agents/` (Task subagents). These run on background threads using faster models, returning only distilled 1-line answers to prevent bloating the main conversation context.
6. **On-Disk Persistence:** When architectural decisions are made or gates are passed, tools write directly to disk (`.agent-spec/memory/facts/`, `SESSION-SNAPSHOT.md`, and `.agent-spec/sdlc/*.md`). These files are committed to git, making the AI's memory visible, reviewable, and permanent.

---

### 2.3 Core architectural invariants (Guarantees for leadership)

- **Zero Infrastructure Footprint:** There is no harness daemon, database, or hosted backend. All logic runs client-side under the developer’s local OS user account.
- **Fail-Open Reliability:** Hooks never block or lock the developer’s IDE. Any error in a hook defaults to `allow`.
- **Air-Gapped IP & Data Privacy:** No telemetry, source code, or internal AlgoSec business logic leaves the developer’s workstation.
- **Non-Destructive Coexistence:** Harness files are stored strictly under `.agent-spec/` and standard `.cursor/` paths. Application source code and `.env` credentials are never modified.

---

### 2.4 Live demo runbook (~10 minutes)

Use a **registered app repo** (has `.agent-spec/`). From the package clone, use `bin/` instead of `.agent-spec/bin/`.

#### Act 1 — Orientation (~2 min)

| | |
|---|---|
| **Say** | “Every new chat gets a bounded digest—not a repo dump.” |
| **Do** | `python3 .agent-spec/bin/agent-spec-digest.py` |
| **Look for** | Stack, graph stats, pipeline gate, remembered constraints, last session line |

#### Act 2 — Discipline (~4 min)

| | |
|---|---|
| **Say** | “Structure queries replace whole-file reads.” |
| **Do** | `./.agent-spec/bin/graphify-cli.py context --task "blast radius for digest"` then `query` on a real file |
| **Optional** | `python3 .agent-spec/bin/agent-spec-tokens.py session` (Hooks on) |

#### Act 3 — Memory & gates (~4 min)

| | |
|---|---|
| **Say** | “State lives on disk; compact resets the chat, not the project.” |
| **Do** | `./.agent-spec/bin/agent-spec-gate.py status` · skim `.agent-spec/SESSION-SNAPSHOT.md` |
| **Close** | `/agent-spec-compact` → new chat; digest still carries snapshot summary |

**Package-clone smoke test (no registered repo):**

```bash
python3 bin/agent-spec-digest.py
python3 bin/agent-spec-tokens.py session
./check-install.sh
```

#### Measured impact (demo slides)

Source: [token-efficiency.md](token-efficiency.md), [token-checklist.md](token-checklist.md).

**Bytes saved per discipline** (one action, measured on repo files):

| Discipline | Bytes saved (approx.) |
|------------|----------------------:|
| Graph query vs whole-file read | 35,814 |
| `grep` vs `cat` whole file | 34,788 |
| 50-line ranged read vs whole file | 33,895 |
| `git diff --stat` vs full diff | 33,403 |
| Filtered test logs vs raw output | 5,010 |

**Context size before vs after compact** (tokens, two measured sessions):

| Measurement | Tokens |
|-------------|-------:|
| Session A — before compact | 480,083 |
| Session A — after compact | 53,191 |
| Session B — before compact | 308,223 |
| Session B — after compact | 46,101 |

---

## 3. Repository layout (package clone)

| Path | Role |
|------|------|
| [`skills/`](../skills/) | Skill packages copied to `~/.cursor/skills/` |
| [`bin/`](../bin/) | Python/bash tools; subset deployed to `.agent-spec/bin/` |
| [`hooks/`](../hooks/) | Cursor hook adapters + `merge-hooks-json.py` / `unmerge-hooks-json.py` |
| [`agents/`](../agents/) | Task runner prompts → `.cursor/agents/` |
| [`personas/`](../personas/), [`pipeline/`](../pipeline/), [`rules/`](../rules/), [`coding-standards/`](../coding-standards/), [`anti-hallucination/`](../anti-hallucination/), [`templates/`](../templates/) | Framework content → `.agent-spec/<name>/` on register |
| [`CURSOR.md`](../CURSOR.md) | Source for `.cursor/rules/agent-spec.mdc` |
| [`install.sh`](../install.sh) / [`uninstall.sh`](../uninstall.sh) / [`check-install.sh`](../check-install.sh) | Install, verify, rollback |

---

## 4. Deployment surfaces

| Surface | Location | Install |
|---------|----------|---------|
| **Global skills** | `~/.cursor/skills/agent-spec-*` | `./install.sh` (once per machine) |
| **Registry** | `~/.cursor/skills/.algosec-agent-spec-projects` | Updated on `--register` |
| **Package root marker** | `~/.cursor/skills/.algosec-agent-spec-root` | Points at package clone |
| **Project harness** | `.agent-spec/`, `.cursor/rules`, `.cursor/hooks`, `.cursor/agents` | `./install.sh --register "<absolute Cursor workspace root>"` |

---

## 5. Components and interactions

### 5.1 End-to-end session lifecycle (The 4-stage loop)

The harness operates through four distinct lifecycle phases designed to maximize reasoning quality while eliminating token waste:

| Step | Stage | Actor | Action | Outcome |
|------|-------|-------|--------|---------|
| 1 | **1 — Orientation** | Cursor IDE | Fires `sessionStart` | Hook runs |
| 2 | 1 — Orientation | Hook adapter | Invokes `agent-spec-digest.py` | Digest build starts |
| 3 | 1 — Orientation | `agent-spec-digest.py` | Reads facts, gate, snapshot from disk | Bounded project state loaded |
| 4 | 1 — Orientation | Hook → IDE | Injects `<agent-spec-digest>` | **~1.7 KB** context on turn 1 |
| 5 | **2 — In-turn discipline** | IDE | `preToolUse` on read / diff / shell | Hook inspects pattern |
| 6 | 2 — In-turn discipline | Hook | Expensive payload (e.g. >30 KB whole file) | One-shot nudge: graphify / ranged read |
| 7 | 2 — In-turn discipline | Hook | Otherwise, or on hook error | `permission: allow` (fail-open) |
| 8 | **3 — Delegation** | IDE | Task: `agent-spec-search` or `-verify` | Heavy work off main thread |
| 9 | 3 — Delegation | Subagent | Returns summary only | Main chat stays small |
| 10 | **4 — Compaction** | Developer / agent | `/agent-spec-compact` | Appends `SESSION-SNAPSHOT.md` |
| 11 | 4 — Compaction | Developer | New chat | Large token drop; state remains on disk |

| Lifecycle stage | Mechanism | Primary benefit |
|---|---|---|
| **1. Orientation** | `sessionStart` hook runs `agent-spec-digest.py` | Eliminates turn-1 amnesia in **~1.7 KB** without scanning the codebase tree. |
| **2. In-turn discipline** | Standing `agent-spec.mdc` + `preToolUse` hook | Prevents expensive 35KB whole-file reads; promotes 150-byte Graphify queries. |
| **3. Heavy delegation** | Background subagents (`agent-spec-search`, `-verify`) | Keeps noisy build logs and 500-line test outputs off the main reasoning thread. |
| **4. Compaction** | `/agent-spec-compact` + disk snapshots | Drops token carry-over by **−88.9%** (480k → 53k) while preserving state on disk. |

### 5.2 Intelligent router & asymmetric SDLC tracks

Choosing between skills is handled by the `/agent-spec` router. To prevent developer friction and avoid waterfall overhead, the SDLC adapts dynamically across **4 asymmetric tracks**:

| Track | Scope & complexity | Required gates | Ideal for |
|---|---|---|---|
| **Fast-Track** | Narrow scope (≤3 files, 1 service), low algorithm | **Gates 5–8 only** (Gates 0–4 skipped) | Everyday bug fixes, minor endpoint tweaks, config changes |
| **Algorithm** | Narrow scope, complex algorithm/logic | **Gate 1**, then **Gates 5–8** | Optimization algorithms, math modules, state machines |
| **Design** | Wide scope (cross-service, new API), standard logic | **Gates 0–4**, then **Gates 5–8** | Schema migrations, new service APIs, integration contracts |
| **Full Track** | Wide scope, high algorithm, mission-critical | **All 9 gates (0–8)** with `REQ-` tracing | Core architecture changes, greenfield services |

*Status and lineage are checked on demand via `./.agent-spec/bin/agent-spec-gate.py status`.*

### 5.3 Durable on-disk memory & state architecture

Rather than relying on volatile in-memory chat history or external cloud databases, all state is persisted as plain, git-trackable files under `.agent-spec/`:

| Store | Location | Written by | Bound / Lifecycle | Why on disk? |
|---|---|---|---|---|
| **Knowledge Graph** | `.agent-spec/graph/knowledge-graph.json` | `graphify-build.py` | Auto-indexed via Git hooks (`post-checkout`/`post-merge`) & sessionStart safety net (<100ms incremental) | Instant ~150B structural queries without whole-repo parsing |
| **Project Index** | `.agent-spec/PROJECT-INDEX.md` | `/agent-spec-onboard` | One-time generation on repo setup | Persistent project blueprint (stack, modules, dependencies) |
| **Constitution** | `.agent-spec/CONSTITUTION.md` | Team / `/agent-spec-onboard` | Static project rules & banned patterns | Non-negotiable architectural guardrails loaded into prompt cache |
| **Durable Facts** | `.agent-spec/memory/facts/` | `/agent-spec-remember` | Hard cap: 40 facts (older pruned) | Permanent team constraints and traps injected into every future digest |
| **Session Narrative** | `.agent-spec/SESSION-SNAPSHOT.md` | `/agent-spec-snapshot` | Append-only; rotated past 12 KB | Complete auditable decision log that survives new chats and reboots |
| **SDLC Lineage** | `.agent-spec/sdlc/*.md` | SDLC skills | Gate-by-gate markdown artifacts | 1:1 traceability from `REQ-` IDs to test validation |

#### 5.3.1 Snapshot lifecycle & rotation mechanics (Bounded memory vs. unbounded growth)

A common trap in AI development harnesses is allowing project history to grow without bounds. Past a certain point, every new chat session pays a heavy tax re-reading tens of thousands of tokens of stale conversation logs. `algosec-agent-spec` enforces **bounded memory by design**:

| Dimension | Live File (`SESSION-SNAPSHOT.md`) | Archived Stores (`memory/snapshots/*.md`) |
|---|---|---|
| **Storage Threshold** | Capped at **12 KB** (`SNAPSHOT_BYTES = 12000`). | Unbounded on disk (historical git archive). |
| **Active Retention** | Keeps only the **2 newest sections** (`SNAPSHOT_KEEP = 2`). | Preserved permanently in dated files (`snapshots-through-*.md`). |
| **Context Overhead** | **~240 characters** (distilled 3-line summary injected by hook). | **0 tokens** (never loaded on session startup). |
| **Rotation Trigger** | Automated rotation when file exceeds 12 KB threshold. | Static, append-only files; never modified after rotation. |

Rotation flow diagram: [Appendix B — Snapshot rotation](#appendix-b-snapshot-rotation).

**How engineers and agents locate historical decisions:**
1. **Automated Breadcrumb Index:** When rotation archives sections, it appends a clean `## Archived sections` markdown index to the bottom of `SESSION-SNAPSHOT.md`, listing the date, summary sentence, and file path for every archived chunk.
2. **Instant CLI Overview (`agent-spec-memory.py snapshots`):** Developers or auditors run `python3 .agent-spec/bin/agent-spec-memory.py snapshots` to inspect every session boundary, byte size, and summary across live and archived files in milliseconds.
3. **Keyword Fact Search (`agent-spec-memory.py search <term>`):** Specific constraints or architectural decisions (e.g. ports, flags, traps) are queried on-demand without opening files.

### 5.4 Workspace harness anatomy (.agent-spec/)

Just as `.git/` manages version control and `.cursor/` manages IDE hook adapters, `.agent-spec/` serves as the **repository-local cognitive runtime and governance layer**. It requires zero external databases or cloud services; all governance, code intelligence, and memory are stored directly in the repository as lightweight, git-trackable files.

The `.agent-spec/` directory is organized into **six architectural pillars**:

| # | Pillar | Key paths | One-line value |
|---|--------|-----------|----------------|
| 1 | **Memory & state** | `SESSION-SNAPSHOT.md`, `memory/`, `TECH-DEBT-REGISTER.md` | Survives chat reboot without re-injecting huge history |
| 2 | **Identity & guardrails** | `CONSTITUTION.md`, `PROJECT-INDEX.md`, `rules/`, `anti-hallucination/` | Constitution, index, anti-hallucination rules |
| 3 | **Code intelligence** | `graph/knowledge-graph.json`, `graph/KNOWLEDGE-GRAPH.md` | AST graph; blast radius without whole-repo reads |
| 4 | **Local execution** | `.agent-spec/bin/` (digest, gate, tokens, graphify) | Scripts stay local; hooks call in sub-50 ms |
| 5 | **Standards & personas** | `personas/`, `coding-standards/` | `@REVIEWER`, `@SECURITY`, AlgoSec standards |
| 6 | **Delivery pipeline** | `pipeline/`, `sdlc/`, `templates/` | Nine-gate SDLC (0–8) and `agent-spec-gate.py` |

Created / updated / consumed matrix: [Appendix A — Six pillars (detail)](#appendix-a-six-pillars-detail).

### 5.5 Personas in action: Real-world guardrail dialogues

Instead of acting as a generic, agreeable chatbot that rubber-stamps dangerous code, activating personas turns Cursor into a skeptical senior engineer:

#### Scenario 1: Catching SQL Injection (`@SECURITY`)
> **Developer:** *"Generate a quick query to fetch device policy by ID."*  
> **Standard Cursor:** `String query = "SELECT * FROM policies WHERE id = '" + id + "';";`  
> **`@SECURITY` with Harness:**  
> 🛑 **BLOCKED by @SECURITY:**  
> *"Security Violation: Direct string concatenation creates SQL injection risk. Parameterized query required.*  
> `PreparedStatement stmt = conn.prepareStatement("SELECT * FROM policies WHERE id = ?");`  
> *[CONFIDENCE: HIGH] — Reference: .agent-spec/rules/ABSOLUTE-RULES.md"*

#### Scenario 2: Catching Speculative Over-Abstraction (`@REVIEWER`)
> **Developer:** *"Let's build a notification handler for alerts."*  
> **Standard Cursor:** Generates an `AbstractNotificationFactory`, 4 interfaces, and a speculative generic event bus.  
> **`@REVIEWER` with Harness:**  
> 🛑 **CHALLENGED by @REVIEWER:**  
> *"Over-Abstraction Alert: The requirements document only specifies email alerts. Building a dynamic factory violates Simplicity-First. Implement a single 20-line EmailNotifier first. Add abstraction only when channel #2 is required.*  
> *The Senior Engineer Test: Would a principal engineer say this is over-engineered? Yes."*

---

## 6. Dependencies

| Dependency | Required | Notes |
|------------|----------|-------|
| Cursor IDE | Yes | Skills, rules, hooks, Task runners |
| `python3` | Yes | Digest, graph, gate, memory, hooks |
| Git workspace | Yes | Registered path = folder opened in IDE title bar |
| MCP servers | No | User optional; not installed by harness |
| Network | IDE default | Harness scripts do not call out by themselves |

---

## 7. Security boundaries

| Topic | Behavior |
|-------|----------|
| **Execution identity** | Same OS user as the developer; full workspace access. |
| **Secrets** | `install.sh` does not modify `.env` or credential files. Do not store secrets in memory facts. |
| **Hooks** | Fail-open; not a security enforcement layer. |
| **Data location** | Memory and SDLC artifacts live in git — team-visible. |
| **Supply chain** | Install copies from trusted internal package clone; pin version/tag for audits. |
| **Untrusted input** | Tickets, web pages, and issue text can influence IDE behavior like any editing session; use investigate-first workflow and security persona for reviews. |
| **Telemetry** | Harness does not upload transcripts; tokens CLI reads local files only. |

---

## 8. Installation (reproducible)

```bash
cd /path/to/algosec-agent-spec
chmod +x install.sh check-install.sh uninstall.sh
./install.sh
./check-install.sh
./install.sh --register "/absolute/path/of/folder/opened/in/Cursor"
./check-install.sh "/absolute/path/of/folder/opened/in/Cursor"
```

Enable **Hooks** in Cursor Settings. Set **Customize → Rules → agent-spec → Always Apply**. Open a **new chat** to receive the digest.

**Idempotency:** Re-running `install.sh` or `--register` merges `hooks.json` via `merge-hooks-json.py`.

**Flags:** `--skills-only`, `--lean`, `--force-reindex`, `--force` (overwrites preserved templates — avoid on active projects).

### Install flow

| Order | Step | What runs | When |
|------:|------|-----------|------|
| 1 | `install.sh` | Entry point | Every install |
| 2 | `copy_skills` | Copies `agent-spec-*` → `~/.cursor/skills/` | Every install |
| 3 | `install_project` | Registers workspace harness | `./install.sh --register "<root>"` |
| 4 | `copy_framework_dirs` | personas, pipeline, templates → `.agent-spec/` | On register |
| 5 | `write_agent-spec.mdc` | Standing rules from `CURSOR.md` | On register |
| 6 | `merge_hooks_json` | Idempotent hook merge | On register |
| 7 | `install_git_hooks` | Idempotent git hook injection (`post-checkout`, `post-merge`, `post-rewrite`) | On register (if `.git` present) |
| 8 | `copy_bin_scripts` | `bin/` → `.agent-spec/bin/` | On register |
| 9 | `graphify-build.py` | Builds knowledge graph | Graph missing or `--force-reindex` |

**Upgrade:** `git pull` in package clone → `./install.sh` refreshes skills, `bin/`, framework copies, hooks, rules; preserves constitution, SDLC, memory, graph unless `--force` / `--force-reindex`.

---

## 9. Rollback (reproducible)

| Goal | Command | Removed | Retained |
|------|---------|---------|----------|
| Harness off one repo | `./uninstall.sh --unregister <workspace>` | rules, hook scripts, task runner files; hooks.json markers; git hook markers | `.agent-spec/` |
| Global skills only | `./uninstall.sh` | `~/.cursor/skills/agent-spec-*` | Per-repo files until unregister |
| Full | `./uninstall.sh --full` | All registered harness + skills | `.agent-spec/` in each repo |

Removing `.agent-spec/` is a separate explicit git decision.

---

## Leadership FAQ (short)

**Cost per successfully completed task?** North star: `(LLM cost + engineer time) / tasks merged with zero regression`. Token-only savings without input discipline can **increase** billed cost (cache pricing). Details: [Appendix D](#appendix-d-leadership-faq-expanded).

**New infrastructure?** No — client-side hooks and git-tracked files only.

**Security?** Absolute rules (no `main` commits, no `.env` edits, confirm deletes). `@SECURITY` supports review; hooks are fail-open, not an enforcement boundary.

---

## Appendix A — Six pillars (detail)

| Pillar & components | Role & value | Created / updated | Consumed |
|---------------------|--------------|-------------------|----------|
| **1. Memory & state** — `SESSION-SNAPSHOT.md`, `TECH-DEBT-REGISTER.md`, `.agent-spec/memory/facts/`, `.agent-spec/memory/snapshots/` | Eliminates amnesia across reboots | `install.sh`; compact, snapshot, remember | `agent-spec-digest.py`; PR handoff |
| **2. Identity & guardrails** — `CONSTITUTION.md`, `PROJECT-INDEX.md`, `rules/`, `anti-hallucination/` | Safety and boundaries | install; `/agent-spec-onboard` | `agent-spec.mdc`; `preToolUse` |
| **3. Code intelligence** — `graph/knowledge-graph.json`, cache, `KNOWLEDGE-GRAPH.md` | ~150 B structural queries | `graphify-build.py`; index skill | `graphify-cli.py`; query-graph |
| **4. Local execution** — `.agent-spec/bin/` | Air-gapped tooling | install from package | hooks; CLI audits |
| **5. Standards & personas** — `personas/`, `coding-standards/` | Senior rigor on demand | install | persona / review skills |
| **6. Delivery pipeline** — `pipeline/`, `sdlc/`, `templates/` | Nine-gate SDLC lineage | install; SDLC skills | gate sign-off; `agent-spec-gate.py check` |

---

## Appendix B — Snapshot rotation

```text
[Developer / Agent Session]
          │
          ▼ Writes summary at task boundary
┌──────────────────────────────────────────────┐
│ .agent-spec/SESSION-SNAPSHOT.md              │
│ - Keeps newest 2 sections                    │
│ - When > 12 KB ──► Rotate older sections ───┐│
└───────────────────────┬──────────────────────┘│
                        │                       │
      Hook reads only   │                       │ Archives older
      latest 240 chars  │                       │ history to disk
                        ▼                       ▼
           ┌───────────────────────┐ ┌──────────────────────────────────────┐
           │ Cursor sessionStart   │ │ .agent-spec/memory/snapshots/        │
           │ (1.7 KB total digest) │ │ snapshots-through-YYYYMMDD-HHMMSS.md │
           │ 0 tokens on archives  │ │ auditable via CLI / git              │
           └───────────────────────┘ └──────────────────────────────────────┘
```

---

## Appendix C — Script inventory

### C.1 Deployed to each registered workspace

| Script | Why it exists (Problem solved) | Role / Value |
|--------|--------------------------------|--------------|
| `agent-spec-digest.py` | Eliminates turn-1 "AI Amnesia" without reading the codebase tree | Injects a ~1.7 KB context digest (stack, active gate, memory facts) via Cursor's `sessionStart` hook |
| `graphify-cli.py` | Avoids expensive whole-file reads (35KB+) just to discover dependencies | Queries the structural graph in ~150 bytes: maps blast radius, call flows, service edges, and endpoints |
| `graphify-build.py` | Keeps architecture maps accurate with zero server infrastructure | Incrementally parses repo imports, service boundaries, and messaging topics into `knowledge-graph.json` |
| `agent-spec-gate.py` | Prevents "vibe coding" and un-reviewed code dumps by enforcing engineering lineage | Manages 9 SDLC quality gates and verifies end-to-end traceability of `REQ-` IDs from spec to validation |
| `agent-spec-memory.py` | Prevents engineers from having to repeatedly re-explain team decisions and gotchas | Persists durable constraints, architectural decisions, and rotating session snapshots on disk |
| `agent-spec-tokens.py` | Provides transparent, local cost and context metrics without third-party SaaS | Audits local Cursor JSONL transcripts to measure token buckets, cache hit efficiency, and harness overhead |
| `agent-spec-index` | Provides a single convenient CLI entry point for developers | Shell wrapper to execute incremental Graphify indexing |

**Hook adapters in `.cursor/hooks/`:** `agent-spec-session-start.py`, `agent-spec-pre-tool-use.py`.

### C.2 Package clone only (maintainer)

| Script | Why it exists | Role |
|--------|---------------|------|
| `agent-spec-selftest.sh` | Verifies package health and release readiness | Automated test suite validating package shape, idempotency, and hook schemas |
| `agent-spec-lint-refs.py` | Prevents broken references across skills and rules | Lints internal cross-links and paths |
| `tests/test_gate_status_json.py` | Ensures gate schema reliability | Unit test verifying gate status JSON structure |
| `merge-hooks-json.py`, `unmerge-hooks-json.py` | Guarantees safe, non-destructive IDE hook installation | Idempotently merges/unmerges harness hooks into Cursor's `hooks.json` |
| `manage-git-hooks.py` | Guarantees safe, non-destructive Git hook installation | Injects/uninstalls marker-bounded `post-checkout`, `post-merge` & `post-rewrite` auto-indexing hooks |

---

## 11. Operations

| Concern | Action |
|---------|--------|
| Graph freshness | Automatic via Git hooks on checkout/pull & sessionStart safety net; or `/agent-spec-index-project` |
| Package upgrade | `git pull` + `./install.sh` |
| Coexistence | Do not stack Always Apply `algosec-lean` + `agent-spec.mdc` |
| Hooks disabled | Run `./.agent-spec/bin/agent-spec-digest.py` manually at session start |

---

## Appendix D — Leadership FAQ (expanded)

### Q: Quality & Productivity: Are we maintaining or improving task success rates, code quality, developer time, and security? Cost per successfully completed task should be the primary efficiency metric.

**Answer:**  
We fully adopt **Cost per Successfully Completed Task** as the North Star efficiency metric. Saving API tokens is counterproductive if developers lose engineering hours fixing broken AI code or security vulnerabilities. The harness directly protects all four dimensions:

1. **Task Success Rates (Eliminating Context Rot):**  
   Standard LLM reasoning degrades significantly as conversation history swells past 50,000 tokens ("Lost in the Middle" syndrome). By compacting state into `SESSION-SNAPSHOT.md` and resetting chats at task boundaries, the AI operates in a perpetually focused context window (<15k tokens), maintaining peak reasoning accuracy.

2. **Code Quality (Anti-Abstraction Guardrails):**  
   Standard AI tends to generate speculative abstractions, bloated factories, and gratuitous helpers. Standing `.cursor/rules/agent-spec.mdc` enforces the *Senior Engineer Test*: code must be surgical, strictly scoped to the task, and verified against existing tests. Activating `@REVIEWER` forces a blockers-first review before code is accepted.

3. **Developer Time (Eliminating Repetitive Prompting):**  
   In standard Cursor, developers waste 5–10 minutes per session re-explaining project stack quirks, ports, and team constraints. The harness injects these automatically via `agent-spec-digest.py` in sub-50ms on turn 1. Furthermore, the intelligent router provides an **Asymmetric Fast-Track** for small bug fixes (≤3 files), skipping Gates 0–4 so developers never face unnecessary ceremony.

4. **Security & Governance (Zero-Trust Guardrails):**  
   `rules/ABSOLUTE-RULES.md` permanently forbids committing to `main`, editing `.env` or credentials, and deleting files without confirmation. Activating `@SECURITY` audits code inline for parameterized queries, secret isolation, and least-privilege scoping.

#### Primary Efficiency Metric Formulation (Phase 2 Pilot)

$$\text{Efficiency Metric} = \frac{\text{Billed LLM API Cost} + (\text{Active Developer Chat Minutes} \times \text{Hourly Rate})}{\text{Tasks Merged with 0 Regression Defects}}$$

In the Phase 2 pilot across 10 developers, we measure first-pass PR approval rates and Jira cycle time alongside billed Cursor API costs to prove net organizational ROI.

---

Algosec Cursor AI

