# algosec-agent-spec — Final todo (sole sequenced backlog)

> Consolidated 2026-11-16 from the old tracker, `dashboard_overhaul.md`, `testing_todo.md`,
> `.agent-spec/TECH-DEBT-REGISTER.md`, the last session snapshot and the 2026-11-16 review of
> cross-repo indexing. Completed, merged and dropped rows were removed. Their history, evidence
> and reasons are kept in [`docs/archive/todo-plan-history.md`](docs/archive/todo-plan-history.md).
> Row IDs carried over from the old tracker keep their ID, so references in
> `docs/IMPLEMENTATION-GUIDE.md` §14 still resolve. New rows use `H-`.
>
> **Strategy:** [`docs/MASTER-PLAN.md`](docs/MASTER-PLAN.md). **Shipped:** v2.0.0 (tag
> `v2.0.0`), Slices 1–9, 6b–6g.

**Status:** `[ ]` open · `[~]` in progress · `[x]` done · `[-]` dropped (reason in the row)

**Goal:** production-ready, and a hackathon demo where a judge sees value without being told
about it: an agent that knows the code across repositories, stops itself before a risky edit,
shows what it saved, and learns. Ranking rule: automation first, and only if the dashboard
shows it and lets the user control it. New skills only when they serve that.

Work milestones in order. Within a milestone rows can run in parallel unless a row names a
dependency. Close a row only here, with evidence.

---

## Summary

| Milestone | Rows | Estimate | Exit |
|-----------|------|----------|------|
| M0 Baseline truth | 6 | 2d | Selftest and doctor green; no unreviewed code |
| M1 Cross-repo that holds up | 8 | 10d | Blast radius crosses real repos, stays correct across branch switches |
| M2 Dashboard control and transparency | 5 | 4.5d | Every automation visible and controllable from the dashboard |
| M3 Guardrails and orchestration | 8 | 11d | Risky edits blocked by graph tier, approved from the dashboard, audited |
| M4 Production hardening | 7 | 6d | CI, install matrix, retention, scale, security |
| M5 Demo and release | 5 | 3d | Rehearsed 5-minute demo; v3.0.0 tagged |
| **Total to done** | **39** | **≈36.5d** | |
| Later (after the hackathon) | grouped | — | Not required for done |

---

## M0 — Baseline truth

Nothing else is worth demoing on a base that has not been checked.

| Status | ID | Item | Acceptance | Est |
|--------|----|------|------------|-----|
| `[x]` | H-001 | **Review unreviewed code** | `bin/aspec_platform/retrieval.py`, `bin/aspec_platform/signals.py` and `skills/agent-spec-ask/` went in with b59e517 outside the 2026-11-15 review. `/code-review high` run; every finding fixed or logged in the debt register | 0.5d |
| `[x]` | H-002 | **Full selftest green** | `bin/agent-spec-selftest.sh` passes with the sandbox off (the Cursor sandbox redirects HOME). pytest, vitest, tsc and the UI gzip budget green in one run. The project copy `.agent-spec/bin/aspec_platform` matches `bin/` | 0.5d |
| `[x]` | H-003 | **Doctor clean** | Memory `INDEX.md` under the 8,000 B limit (9,737 B on 2026-11-16) via `agent-spec-memory.py prune`; `agent-spec-doctor.py` reports 0 issues | 0.25d |
| `[x]` | H-004 | **Debt register holds only real debt** | Template rows DEBT-001 (`UserService.java`) and DEBT-002 (`orders` table) describe code that does not exist here; removed | 0.1d |
| `[~]` | H-005 | **Live check: injected facts on the Impact tab** | A new Cursor chat shows the digest facts it received on its Impact tab (built 2026-11-15, never seen live). Recorded-hook replay through the real sessionStart hook now shows them, after fixing a lost first-chat record (docs/evidence/H-005.md). Owed: one live Cursor chat | 0.25d |
| `[x]` | H-006 | **Lean installs stay lean** | An existing `--lean` install with no marker keeps lean on the next skill sync without re-running `./install.sh --lean` | 0.25d |

---

## M1 — Cross-repo that holds up

Today: the mesh builds, but 0 cross-repo edges on the 10 local repos because none calls
another, and a member's graph copy goes stale on a branch switch until `build --refresh`.

| Status | ID | Item | Acceptance | Est |
|--------|----|------|------------|-----|
| `[x]` | H-010 | **Demo service mesh fixture** | `examples/mesh-demo/` holds 3 small repos that really depend on each other: a UI calling a REST API, the API publishing a topic a worker consumes, a shared Java/Python library imported by two. `graphify-mesh.py stats` shows at least one `imports`, `http` and `message` edge across repos | 1d |
| `[x]` | P3-001 | **Multi-repo Graphify — close** | Built 2026-11-13 (`bin/graphify-mesh.py`, `docs/evidence/P3-001.md`). Left: precision measured on H-010 and on one real pair of services; ≥ 75% (MASTER-PLAN cross-repo accuracy), recorded in the evidence file | 1d |
| `[x]` | H-011 | **Branch-aware graph** | `knowledge-graph.json` records `branch`, `head_sha` and `dirty`. The digest prints the branch and short SHA the graph reflects. A build during a merge or rebase with conflicts is labelled, not presented as fresh. Test covers a branch switch | 1d |
| `[x]` | H-012 | **Mesh drift detection and partial refresh** | `mesh.json` records each member's `head_sha` at build. `stats`, the digest and the dashboard flag members whose HEAD moved. `build` rebuilds only drifted members, so `--refresh` is no longer needed after a pull or a branch switch. Test: switch branch in one member, next build rebuilds that member only | 1d |
| `[x]` | H-013 | **Next.js file-system API routes** | P3-002 follow-up. `pages/api/**` and `app/**/route.ts` produce routes with verbs, so calls from other repos match them. Test fixture added | 0.5d |
| `[x]` | P3-007 | **Self-service repo onboarding** | Add and remove a mesh member from the CLI and from the dashboard (path picker, progress, result). Every add/remove writes an automation event | 1.5d |
| `[x]` | P3-006 | **Multi-repo home and cross-repo blast radius** | Dashboard page: one row per repo (files, branch, SHA, freshness, drift), a map of cross-repo edges per repo pair, and click a file to see `graphify-mesh.py query --file` as a panel. Token totals rolled up per repo without uploading source (absorbs P3-015) | 2d |
| `[x]` | P3-014 | **Cross-repo experience** | A fix recorded in repo A is returned by recall in repo B, with a citation to repo A. Shown in the H-051 demo | 2d |

---

## M2 — Dashboard control and transparency

| Status | ID | Item | Acceptance | Est |
|--------|----|------|------------|-----|
| `[x]` | H-020 | **Index health panel** | Per repo: graph freshness, branch and SHA, last build time and duration, files reparsed, cache size, and the size of every append-only log. Buttons: Rebuild graph, Refresh mesh; both write automation events. Answers "is my index current?" without a terminal | 1d |
| `[x]` | H-021 | **Background build failures surface** | Git-hook rebuilds run with output sent to `/dev/null`. A failed or timed-out build writes a status the digest and H-020 show, with the last error line | 0.5d |
| `[x]` | PI-009 | **Proposals inbox** | Project › Proposals lists `skill-proposals/` and proposed facts with diff and evidence; approve writes through the existing CLI and logs an audit row; nothing applied without a click. Includes promote and deprecate of experiences (absorbs P3-017) | 1.5d |
| `[x]` | PI-010 | **Session comparison — complete** | Sessions already has Compare (`/api/compare`, tokens only). Add signals, quality dimensions and context side by side; every figure carries provenance | 0.75d |
| `[x]` | PI-011 | **Skill effectiveness** | Per skill: requests, median outcome quality, failure rate, rework rate; "not enough data" below 10 reviewed requests | 0.75d |

---

## M3 — Guardrails and orchestration

The strongest demo moment: the agent tries a change to a shared API, the hook blocks it
because the graph says many files depend on it, the user approves it from the dashboard, and
the audit trail records it.

| Status | ID | Item | Acceptance | Est |
|--------|----|------|------------|-----|
| `[x]` | P4-011 | **Blast-radius risk classifier** | `agent-spec-risk.py` puts a tool action in tier 0 (read, test) to 3 (shared API, migration, core) from graph fan-in, layer and cross-repo edges (M1). Thresholds in `.agent-spec/risk.json`. Unit tests per tier | 2d |
| `[x]` | P4-012 | **Risk tier in `preToolUse`** | Tier 0–1 allowed, tier 2 allowed with a warning, tier 3 blocked until approved. Fail-open on classifier error, with the error recorded | 1.5d |
| `[x]` | H-030 | **Approve from the dashboard** | A blocked tier-3 action appears in the dashboard with its blast radius; Approve or Deny; the agent's retry goes through after approval. Approval expires after one use | 1.5d |
| `[x]` | P4-016 | **Risk panel** | Tier distribution per request and per session; blocked, approved and denied actions with their blast radius. The handoff Sankey half is dropped (Sankey cut by DEC-15) | 1d |
| `[x]` | P3-011 | **Session audit export** | Hash-chained JSONL per session: request, agent, tool actions, risk tier, approvals, outcome. `verify` detects any edited line. Export from the dashboard | 1.5d |
| `[x]` | P3-012 | **Approval trails** | Risk approvals (H-030), proposal approvals (PI-009) and external posts all write one audit row with who, when and what | 0.5d |
| `[x]` | P4-013 | **Typed handoffs** | JSON schemas for search, implement and verify results; `agent-spec-hub-runner` validates every step output and fails the step with an actionable error on a violation (absorbs P4-014) | 2d |
| `[x]` | P4-015 | **Handoff context pruning** | Subagents receive only their typed input. Context reduction measured against the current pass-through on the same workflow run and shown on the run page | 1d |

---

## M4 — Production hardening

| Status | ID | Item | Acceptance | Est |
|--------|----|------|------------|-----|
| `[x]` | H-040 | **CI** | GitHub Actions on push and pull request: pytest, vitest, tsc, UI gzip budget, `agent-spec-lint-refs.py`, selftest. The repository has no `.github/workflows` today. Badge in README | 1d |
| `[x]` | H-041 | **Retention for every append-only file** | Size cap plus dated archives that readers still see, retention days configurable, derived DB rows pruned with them. Covers `metrics/events.jsonl`, `automation.jsonl`, `injections.jsonl`, `daily.jsonl`, `hook-payloads/`, `receipts/` and `graph/stats-history.jsonl` (one line per build, never trimmed). Absorbs PI-012 | 1d |
| `[~]` | H-042 | **Install matrix** | Clean install, register, uninstall on Linux, macOS and WSL in CI; one manual run on real Windows Git Bash (absorbs T-058, DEBT-006, PHASE1-VERIFICATION B21) | 1d |
| `[x]` | H-043 | **Scale check** | Graph build on a 20,000-file repo; session-start incremental build inside the 3 s limit; dashboard pages under 1 s with 10,000 traces. Numbers recorded in a new H-043 evidence file under `docs/evidence/`; anything over budget fixed or logged | 1d |
| `[x]` | H-044 | **Security pass** | `/security-review` over the hooks, dashboard API (token, localhost bind, CSRF on control actions), approval endpoint (H-030) and redaction. Every finding fixed | 1d |
| `[ ]` | H-045 | **Fresh-user test** | Someone new to the project goes from README to the first dashboard view in under 10 minutes on a clean machine; every stumble fixed in README or QUICKSTART | 0.5d |
| `[x]` | H-046 | **Fail-open proof** | Each hook with its helper deleted, with a corrupt graph and with a full disk still lets Cursor proceed; one test per case | 0.5d |

---

## M5 — Demo and release

| Status | ID | Item | Acceptance | Est |
|--------|----|------|------------|-----|
| `[ ]` | H-050 | **Head-to-head benchmark** | The same 3 tasks in plain Cursor and with `/agent-spec-raw-code-full` on the H-010 mesh. Impact tab and Sessions Compare show tokens, turns and outcome. The slide says what "kept out of the chat" means: re-send savings in the parent context, not lower total billing | 0.75d |
| `[~]` | H-051 | **Demo script** | `demo.md` rewritten as one 5-minute story: install → digest → cross-repo blast radius → tier-3 edit blocked → approved in the dashboard → Impact savings → learning proposal approved → audit export. Seeded data so it runs offline; a recorded fallback video | 1d |
| `[x]` | H-052 | **Local mode decision** | Decided 2026-11-18: an optional 30-second slot in H-051, run in the dashboard Agent Console on Ollama (the only live agent with the network off), skipped when the Console reports no backend. Cursor cannot reach a local Ollama without a public tunnel, so the demo never claims it; Ollama in Cursor stays out of the demo | 0.25d |
| `[~]` | H-053 | **Two timed dry runs** | On the demo machine, network off; every failure fixed before the next run. Scripted part done: `examples/mesh-demo/demo-dryrun.py`, two runs offline, 10/10 beats, ~2.9 s each, 3 failures fixed (docs/evidence/H-053.md). Owed: two rehearsals by the presenter | 0.5d |
| `[ ]` | T-042 | **Release v3.0.0** | M0–M4 closed; CHANGELOG; tag `v3.0.0` | 0.5d |

---

## Later — after the hackathon

Not required for done. Re-plan from the archive when picked up.

| Group | IDs | Note |
|-------|-----|------|
| Registry | P3-003, P3-004, P3-005, P3-009 | MCP index aggregator, agent catalog, drift in doctor, gateway audiences |
| Platform reach | P3-008, P3-010, P3-013, P3-016, P3-018 | IDE expansion, AgentCore port, Cedar policy gates, Langfuse stack, compliance walkthrough |
| Cursor CLI spike | CP-001 (R3) | Resume an IDE composer id headless |
| Always-on bots | P4-001…P4-010, T-043 | Daemon, cloud sandbox, routine synthesis, checkpoints (P4-009 digest half done in CB-004), scheduling |
| Marketplace and federation | P5-001…P5-014, T-044 | Templates, connectors, federation, metering |

---

## Open decisions

| Item | When to decide |
|------|----------------|
| Risk thresholds (fan-in and layer per tier) | P4-011 kickoff; tune on the H-010 fixture and this repo |
| Local mode in the demo (H-052) | Decided 2026-11-18: optional Console-on-Ollama slot; see the H-052 row |
| Cloud sandbox: self-hosted vs managed | Later, at P4-003 |

---

*Algosec Cursor AI · Close rows only in this file. Last updated: 2026-11-16 (consolidated final list).*
