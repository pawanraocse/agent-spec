# algosec-agent-spec — Master Plan

> **One repo. One product.** `algosec-agent-hub` archived Oct 2026.
> All platform capabilities built into `algosec-agent-spec`.

| Current version | Architecture | IDE support |
|-----------------|-------------|-------------|
| **v1.1.0** | Client-side harness, local-first | Cursor only (Phase 1) |

---

## Document authority

| Document | Role |
|----------|------|
| **[This file](MASTER-PLAN.md)** | **Why, what, when** — phases, exit gates, locked decisions, adoption model, metrics |
| **[`todo-plan.md`](../todo-plan.md)** | **How, in order** — sole sequenced backlog (Slices 1→16b); task IDs and acceptance criteria |

Do not maintain a second roadmap or sprint list elsewhere. Supporting docs (`demo.md`, `DASHBOARD.md`, `platform-design/*`) describe pitch, UI panels, or deep design — they **link here + `todo-plan.md`** for sequence and status.

**Execution rule:** Work slices top to bottom in `todo-plan.md`. **Slice 9 (O-\*)** starts only after **Slice 1** closes.

---

## Locked decisions

| Topic | Decision |
|-------|----------|
| Product | Single repo; agent-hub archived here |
| Local-first | SQLite dashboard on localhost; no default transcript upload |
| Hooks | `sessionStart` + `preToolUse` fail-open |
| Indexing | Git post-checkout/merge/rewrite + sessionStart incremental Graphify |
| Automation | Hooks + always-on rules run the harness; skills are agent instructions, not commands users memorize |
| **AI-first (DEC-15)** | Build order: **rule/skill → hook (command or `prompt` type) → subagent/AI judgement writing a typed artifact → thin deterministic code**. Code only where it must be exact, fast, or secret-safe (see §AI-first principle). Supersedes DEC-14's Console scope |
| UI | **Observe and verify.** Cursor is the console: the UI reads receipts, hook events and AI reviews; it does not re-implement chat, diff review or job running. Headless runs use Cursor Automations / cloud agents, not a custom daemon |
| Demo | Dashboard showcases harness features (`demo.md` §1–8 built today; §9–10 Phase 2) |
| BrandFactory | Pattern: nearest reference → delta → gated verify; not 39-agent port |
| JIRA RCA | Beat 666 BugBot (AUTO-3807 ~50% strict) via orchestration + graph + eval |
| Orchestrator | DEC-12: Cursor-native. Workflows are `agent-spec-wf-*` skills run by `agent-spec-hub-runner` with Task subagents; code only for run-dir plumbing (`agent-spec-run.py`). ADR-001 kept as history |
| 666 tools | Reuse deterministic tools; add graph, eval, governed examples |
| Cursor-only in Phase 1 | Deepest AI IDE integration; expand after platform proven |
| No external servers (default) | Zero infra overhead; everything runs on developer machine |
| Git-backed memory | Decisions persist across sessions via `.agent-spec/` on disk |

---

## AI-first principle (DEC-15)

The product is **instructions and events that the model acts on**, not a Python platform
around the model. Manual logic is a cost: it is exact but brittle, it must be maintained,
and it is the first thing to look fake in a demo.

**Build ladder — stop at the first rung that works:**

| Rung | Mechanism | Use for | Example |
|------|-----------|---------|---------|
| 1 | Rule / skill (markdown the model follows) | Procedure, judgement, rubrics, review, coaching, triage | `agent-spec-implement`, `agent-spec-wf-*`, session review rubric |
| 2 | **Hook** — command or `prompt` type | Reacting to an agent event; injecting context; follow-up turns | `sessionStart` digest, `stop` follow-up to snapshot, `subagentStop` verify |
| 3 | Subagent / AI judgement → **typed JSON artifact on disk** | Anything a human would "grade", summarise or classify | `.agent-spec/metrics/reviews/<session>.json` |
| 4 | Thin deterministic code | **Only** the allowed cases below | graph build, secret guard, redaction, SQLite read-only aggregation |

**Deterministic code is allowed only when one of these holds** (cite it in the task row):
1. *Security/safety floor* — must not depend on a model (S-002 quarantine, redaction, loopback/token guards).
2. *Exact computation* — parsing, hashing, counting, graph build, token arithmetic.
3. *Latency or cost* — runs every tool call, so a model call is unaffordable.
4. *Plumbing* — read-only storage/aggregation that skills and the UI share.

**Not allowed as code:** scoring rubrics, coaching text, "is this good/bad" thresholds, risk
classification beyond a hard deny-list, re-implementing a Cursor feature (chat, diff review,
background agents, marketplace).

**AI-judged output is labelled as such.** A grade or finding produced by a model carries a
*AI-judged* badge with the model, rubric version and evidence links; it is never presented
as *Measured*. Deterministic facts (counts, bytes, exit codes) stay *Measured*.

Tracked as **Slice 6c** in [`todo-plan.md`](../todo-plan.md) (AF-001…AF-008). Review basis:
[`dashboard_overhaul.md`](../dashboard_overhaul.md) §13.

---

## Zero-touch loop (hackathon + adoption)

Humans use natural language in Cursor. The harness runs without slash commands.

```
install/register → sessionStart → work (hooks steer) → session end → receipt + metrics row
                         ↑                                    ↓
              shared facts lite + doctor line          UI ingests (verify only)
```

| Track | Automate | Prove |
|-------|----------|-------|
| **Hackathon** | Graph-first + 6-gate implement via rules; session receipt | Gate + graph + receipt + localhost proof viewer |
| **Adoption** | Doctor on register + digest; ROI export from receipts; shared facts lite on install | Manager CSV; S-002 quarantine; team constraints without `/remember` |

Mapped to **Slice 1.5** in [`todo-plan.md`](../todo-plan.md) (T-050…T-055), after Slice 1.

---

## Architecture Evolution

```
Phase 1 (v1.1.0)            Phase 2 (v2.0.0)            Phase 3 (v3.0.0)            Phase 4 (v4.0.0)            Phase 5 (v5.0.0)
┌──────────────────┐        ┌──────────────────┐        ┌──────────────────┐        ┌──────────────────┐        ┌──────────────────┐
│ Developer Harness│        │ Harness+Platform │        │ Enterprise Mesh  │        │ Autonomous Bots  │        │ Agent Marketplace│
│                  │        │                  │        │                  │        │                  │        │                  │
│ • Graphify       │        │ Everything P1 +  │        │ Everything P2 +  │        │ Everything P3 +  │        │ Everything P4 +  │
│ • Hooks          │──────► │ • Orchestration  │──────► │ • Multi-repo     │──────► │ • Always-on bots │──────► │ • Bot marketplace│
│ • Memory         │Stabil. │ • Self-learning  │ Scale  │ • Registry       │ Auto-  │ • Cloud sandbox  │  Open  │ • 3P integrations│
│ • Personas       │        │ • Dashboard UI   │        │ • Audit+comply   │ nomous │ • Routine synth  │  Eco-  │ • Community bots │
│ • SDLC gates     │        │ • Data+DB        │        │ • Cross-org      │        │ • Env checkpoint │ system │ • Revenue model  │
│ • 33 skills      │        │ • CI/CD headless │        │ • IDE-agnostic   │        │ • Risk-tier gate │        │ • Federation     │
└──────────────────┘        │ • JIRA RCA       │        └──────────────────┘        │ • Handoff schema │        └──────────────────┘
                            └──────────────────┘                                    └──────────────────┘
```

---

## Phase 1 — Stabilize (v1.1.0) — **COMPLETE (2026-10-28)**

**Objective:** Make the existing harness production-grade — tested, measured, frictionless.

**Delivered:** Slices 1–4 (T-001…T-034), T-054 and T-040 — see [CHANGELOG](../CHANGELOG.md) 1.1.0.
**Deferred (not required by the exit gate):** T-050–T-053, T-055 (receipt, session-end hook,
auto-harness rule, shared facts, ROI viewer); native PowerShell port. **Waived:** git tag — the
workspace has no repository yet. **Evidence and manual checks:** [PHASE1-VERIFICATION.md](PHASE1-VERIFICATION.md).

**Timeline:** ~3 weeks

| Track | Key Capabilities |
|-------|-----------------|
| Trust & correctness | Memory dedup & conflict detection, graph freshness signal, doctor command |
| Token efficiency | Tool discipline rules, hard caps, measurement tooling |
| Developer experience | Reduced install friction, quickstart path, team config defaults |
| Release gate | Expanded selftest coverage, CI integration, v1.1.0 tag |

**Exit Gate:** (status at 2026-10-28)
- `agent-spec-selftest.sh` green — **met** (sections [1]–[12])
- `agent-spec-doctor` green — **met** (`--strict`, 0 FAIL / 0 WARN on a registered workspace)
- Token overhead < 5% — **met by construction, measured as footprint**: always-on ≈ 1.2k tokens/turn
  (rule + digest), under 5% once per-turn context exceeds ≈ 24k tokens. Cursor transcripts carry no
  usage data, so a before/after `compare` is chars÷4 only; see PHASE1-VERIFICATION §C.
- v1.1.0 with CHANGELOG — **met**; git tag **waived** (no repo)

**Enterprise Value:** Reliable AI harness that teams can adopt without worrying about stale context, wasted tokens, or broken installs. Foundation trust for everything that follows.

---

## Phase 2 — Platform (v2.0.0)

**Objective:** Transform the harness into an observable, self-learning platform with autonomous workflow execution.

**Timeline:** ~2 months  
**Entry:** Phase 1 v1.1.0 released (tag waived, no git repo). Carry-over scheduled first: todo-plan Slice 4c.

| Track | Key Capabilities |
|-------|-----------------|
| Data layer | Typed contracts, local SQLite, experience store with TTL |
| Dashboard | Read-only observer: sessions, token waterfall, subagent health, savings proof. Fed by **hook events**; grades/coaching come from an **AI session-review skill**, not Python scoring (Slice 6c) |
| Self-learning flywheel | Experience records, promotion tiers, retrieval on similar signals; promotion judged by the model (`/agent-spec-learn`), stored as JSON |
| Orchestration engine | Skill-driven (`agent-spec-hub-runner` + `agent-spec-wf-*`); model decides routing and fan-out, `agent-spec-run.py` only records state. Risk gates = AI classification above a hard deny-list floor |
| JIRA RCA workflow | Vendor BugBot tools, golden eval set, graph-backed triage |
| CI/CD parity | Headless runner, sandboxed execution from Jenkins/GitHub Actions |

**Exit Gate:**
- Dashboard live on localhost showing sessions, traces, and quality trends
- **AI-first gate (DEC-15):** hook events are the primary data source; every grade or finding shown is *AI-judged* with evidence links; no scoring rubric lives in Python; the custom Console is off by default
- ≥ 3 workflows running end-to-end (RCA, review, custom)
- Learning loop proven: Run N retrieves experience from Run N-1 with measured token savings
- Trend data showing confidence and cost trajectories over ≥ 2 weeks

**Enterprise Value:** Quantifiable ROI — token savings dashboards, quality trend tracking, and self-improving agents that get faster on repeated problem patterns. Engineering leadership can see exactly what AI is doing and whether it's getting better.

---

## Phase 3 — Enterprise (v3.0.0)

**Objective:** Scale to multi-repo organizations with centralized governance, cross-project intelligence, and audit compliance.

**Timeline:** ~3 months  
**Entry:** Phase 2 v2.0.0 tagged

| Track | Key Capabilities |
|-------|-----------------|
| Knowledge mesh | Multi-repo Graphify — query blast radius across repo boundaries |
| Agent registry | Centralized catalog of available agents, versions, and capabilities |
| Audit & compliance | Enterprise dashboard with session history, approval trails, policy gates |
| Cross-org learning | Bug fixed in Repo A prevents same bug in Repo B via shared experience |
| IDE expansion | Architecture supports Gemini CLI, VS Code, and other IDE agents |

**Exit Gate:**
- ≥ 3 repos indexed in a connected knowledge graph
- Registry serving agent catalog with version management
- Audit trail complete — every AI action traceable to session, agent, and outcome
- Cross-repo experience retrieval demonstrated

**Enterprise Value:** Organization-wide AI governance. Security and compliance teams get audit trails. Knowledge compounds across teams — every repo benefits from every other repo's learnings.

---

## Phase 4 — Autonomous Bots (v4.0.0) — *Inspired by Cursor Grok Bot*

**Objective:** Transform agent-spec from a session-bound IDE harness into an always-on autonomous agent platform with persistent cloud execution, routine synthesis, and structured inter-agent handoffs.

**Timeline:** ~3 months  
**Entry:** Phase 3 v3.0.0 tagged

> **Design influence:** Cursor's Grok Bot model — always-on cloud agents with persistent
> environments, learned routines, tiered safety boundaries, and structured bot-to-bot handoffs.
> We adopt the patterns that compound on agent-spec's existing strengths (graph, gates, memory)
> while staying local-first where it matters.

| Track | Key Capabilities |
|-------|-----------------|
| Always-on execution | **Use Cursor Automations / cloud agents** (and the Cursor SDK where scripted) to run `agent-spec-wf-*` skills on schedule or event — tasks continue with the IDE closed. A custom daemon is built only if a spike proves Cursor's runtime cannot run the skills + hooks + MCP |
| Routine synthesis | "Demonstrate once, automate forever" — after a successful SDLC pass (RCA → graph → test-first → verified diff), synthesize a reusable, parameterized recipe skill into `.agent-spec/skills/` |
| Environment checkpointing | Machine-readable session checkpoints (git SHA, graph hash, test pass/fail map, active gate track) that allow warm resumption of any session in < 2 seconds |
| Risk-tiered gating | Deterministic **floor** in `preToolUse` (secrets, destructive ops, blast-radius count from the graph) plus a **`prompt` hook / reviewer subagent** that classifies the rest (new files, migrations, shared APIs) with the project's written policy in markdown — no hand-coded tier rule engine |
| Structured handoff contracts | Replace narrative context passing between subagents with typed JSON schemas: `SearchAgent → {rca, facts}`, `Implementer → {diff, tests}`, `Verifier → {result, evidence}` |
| Headless background runner | Cursor Automation / cloud agent for heavyweight tasks (Jira RCA batch, regression review); local git-hook reindex stays as is. Results land as hook events + JSON artifacts the dashboard already reads |

**Exit Gate:**
- ≥ 1 workflow running end-to-end in headless/daemon mode without IDE open
- Routine synthesis demonstrated: manual task → auto-generated skill → successful replay
- Environment checkpoint proven: cold resume reconstructs full session state from checkpoint file
- Risk-tier gating active on ≥ 1 registered project with ≥ 3 tier rules
- Subagent handoffs use typed schemas — zero narrative pass-through in orchestrated workflows

**Enterprise Value:** Developers gain an always-available AI teammate that learns from every successful engineering session and operates autonomously on routine tasks — freeing human engineers for design, architecture, and novel problem-solving. Teams get configurable safety boundaries that scale trust without sacrificing speed.

---

## Phase 5 — Agent Marketplace & Ecosystem (v5.0.0)

**Objective:** Open agent-spec to a broader ecosystem — shareable bot templates, third-party integrations, community-contributed routines, and cross-organization agent federation.

**Timeline:** ~4 months  
**Entry:** Phase 4 v4.0.0 tagged

| Track | Key Capabilities |
|-------|-----------------|
| Bot marketplace | Distribute templates (RCA specialist, security reviewer, migration assistant, onboarding bot) as **Cursor plugins / a team marketplace** (skills + hooks + agents bundles) — not a custom catalog and installer |
| Third-party integrations | Connectors beyond Jira/Bitbucket: Slack, email, vendor portals, CI/CD webhooks, monitoring systems — agents can react to external events |
| Community routines | Publish/subscribe model for synthesized routines — a team's proven recipe can be shared org-wide or publicly with attribution |
| Agent federation | Cross-organization agent mesh: bots from different teams/orgs can negotiate handoffs, share knowledge graphs (with access control), and compose workflows |
| Revenue model framework | **Deferred — not planned.** Revisit only on a named commercial customer; metering/billing is manual platform scope with no AI leverage |
| Ecosystem governance | Trust levels for third-party bots, sandboxed execution, review/approval for community contributions |

**Exit Gate:**
- Marketplace serving ≥ 10 bot templates with install/configure UX
- ≥ 2 third-party integrations live (beyond Jira/Bitbucket)
- Community routine sharing demonstrated across ≥ 2 organizations
- Federation protocol documented and demonstrated between ≥ 2 independent agent-spec deployments

**Enterprise Value:** Agent-spec becomes a platform, not just a tool. Organizations can build, share, and monetize AI engineering expertise as composable agents. The ecosystem effect — more contributors, more routines, more integrations — creates a compounding advantage that no single-team tool can match.

---

## Success Metrics

| Metric | Phase 1 Target | Phase 2 Target | Phase 3 Target | Phase 4 Target | Phase 5 Target |
|--------|---------------|----------------|----------------|----------------|----------------|
| **Token overhead** | < 5% per session | Tracked per agent, trending down | Org-wide cost dashboard | Per-bot cost attribution | Marketplace metering |
| **Install-to-productive** | < 10 minutes (Day-1 path in QUICKSTART) | < 5 min (team.yaml defaults) | Self-service from registry | Bot template: < 2 min deploy | 1-click marketplace install |
| **Selftest pass rate** | 100% on every PR | 100% + workflow integration tests | 100% across all repos | 100% + daemon health checks | 100% + ecosystem integration tests |
| **Context accuracy** | No stale/conflicting memory | Experience retrieval precision ≥ 80% | Cross-repo accuracy ≥ 75% | Checkpoint resume fidelity ≥ 95% | Federated knowledge accuracy ≥ 80% |
| **Confidence distribution** | Baseline measured | HIGH ≥ 70% of sessions | HIGH ≥ 80% org-wide | HIGH ≥ 85% autonomous runs | HIGH ≥ 85% across ecosystem |
| **Flywheel savings** | N/A | Measurable token reduction on repeat patterns | Cross-repo savings tracked | Routine replay: ≥ 50% faster than manual | Community routine reuse rate ≥ 30% |
| **Adoption** | 1 team, 1 repo | 3+ workflows, daily dashboard use | 3+ repos, 3+ teams | ≥ 5 always-on bots | ≥ 10 marketplace templates, ≥ 2 orgs |
| **AI-first ratio** (DEC-15) | ≥ 60% of new tasks ship as skill / hook / prompt, each code task cites its allowed-code reason | ≥ 70% | ≥ 70% | ≥ 80% | ≥ 80% |
| **Autonomy** | N/A | N/A | N/A | ≥ 1 workflow completes without human input | ≥ 3 cross-org federated workflows |

---

## Timeline Summary

```
Week  1 ── 3     4 ──────── 11    12 ──────── 23    24 ──────── 35    36 ──────── 51
┌────────────┐   ┌────────────┐   ┌────────────┐   ┌────────────┐   ┌─────────────┐
│  Phase 1   │   │  Phase 2   │   │  Phase 3   │   │  Phase 4   │   │  Phase 5    │
│  Stabilize │──►│  Platform  │──►│  Enterprise│──►│  Autonomous│──►│  Marketplace│
│  v1.1.0    │   │  v2.0.0    │   │  v3.0.0    │   │  v4.0.0    │   │  v5.0.0     │
└────────────┘   └────────────┘   └────────────┘   └────────────┘   └─────────────┘
   ~3 weeks        ~2 months        ~3 months        ~3 months        ~4 months
```

| Phase | Duration | Depends On |
|-------|----------|-----------|
| Phase 1 — Stabilize | ~3 weeks | Nothing (**done**) |
| Phase 2 — Platform | ~2 months | Phase 1 v1.1.0 (**met**) |
| Phase 3 — Enterprise | ~3 months | Phase 2 v2.0.0 |
| Phase 4 — Autonomous Bots | ~3 months | Phase 3 v3.0.0 |
| Phase 5 — Agent Marketplace | ~4 months | Phase 4 v4.0.0 |

**Total estimated runway: ~15 months**

---

## Graduation Gates

| Gate | Criteria | What It Proves |
|------|----------|---------------|
| **P1 → P2** | Selftest green, doctor green, overhead < 5%, v1.1.0 | Foundation is reliable |
| **P2 → P3** | Dashboard live, 3 workflows, learning loop with trend data | Platform delivers value |
| **P3 → P4** | 3+ repos, registry serving, audit complete, cross-repo learning | Enterprise-ready |
| **P4 → P5** | ≥ 1 headless workflow, routine synthesis proven, checkpoint resume, risk-tier gating active | Autonomous agents are viable |
| **P5 → GA** | Marketplace serving ≥ 10 templates, ≥ 2 third-party integrations, federation demonstrated | Ecosystem is self-sustaining |

---

## Supporting documents (not sequenced backlogs)

| Document | Purpose |
|----------|---------|
| [IMPLEMENTATION-GUIDE.md](IMPLEMENTATION-GUIDE.md) | Unified HLD + LLD for all pending tasks; P2.n / P3.n execution order (§14); decision log |
| [DASHBOARD.md](DASHBOARD.md) | Feature → panel map; Phase 2 UI architecture |
| [HLD.md](HLD.md) | Technical architecture — system context, lifecycle, security |
| [demo.md](../demo.md) | Pitch script (built vs planned labeled in §Roadmap) |
| [token-efficiency.md](token-efficiency.md) | Token measurement methodology |
| [platform-design/AGENT-HUB-PLAN.md](platform-design/AGENT-HUB-PLAN.md) | O-021…O-054 / AgentCore detail beyond P2 minimum O-001…O-020 |

---

*Last updated: 2026-11-07 · Planning doc version: 3.1.0 (adds DEC-15, AI-first)*

Algosec Cursor AI
