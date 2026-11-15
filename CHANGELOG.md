# Changelog — algosec-agent-spec

## Unreleased

- **Tokens saved per chat, on the board**: the Impact tab opens with what the raw-code rules saved
  across the whole chat (graph queries, ranged reads, subagents, and now targeted edits against a
  rewrite), plus the re-sends avoided on every later model call. Session rows carry a −N chip
  (⚡ when `/agent-spec-raw-code*` was on), and the Showcase leads with the board total, the top
  chats and a raw-code vs plain comparison that stays hidden until each side has 5+ requests.
- **Local agent token cut**: the Ollama agent now sends a relevance-filtered digest, shorter tool
  descriptions, one search hit per file with its purpose line (no past requests, no test files
  unless asked), shrinks earlier tool results to 280 chars, reads 80 lines by default, and answers
  at the first repeated call. Per-step usage is in each result's `step_usage`. Bench, `qwen2.5-coder:7b`
  at temperature 0: 4/6 correct on 21,646 prompt tokens (bare: 2/6 on 17,058); before the cut it was
  5/6 on 65,568 at temperature 0.2.

- **Local mode on Ollama, no Cursor plan needed**: `bin/agent-spec-ollama-agent.py` speaks the
  `cursor-agent -p` stream-json protocol on a local Ollama model and fires the project's registered
  Cursor hooks, so its requests are traced, measured and reviewed like Cursor chats (origin
  `local`, visible in Live). It reads in ranges, skips repeated calls, answers from its notes when
  the tool budget runs out, and honours preToolUse denials. `bin/agent-spec-live.py` sets
  everything up in one command. Ollama discovery (`aspec_platform/ollama.py`) accepts loopback and,
  under WSL, the Windows host; any other endpoint still needs `AGENT_SPEC_ALLOW_REMOTE_MODELS=1`.
- **Console restored**: `GET /api/agent/jobs/<id>/stream` (removed in 7b9d249) is back, with
  `GET /api/agent/status` and an optional `model`. The Console page is now a streaming chat with
  tool chips, token counts, a trace link and follow-ups. The local backend turns the Console on by
  default; `cursor-agent` still needs `AGENT_SPEC_CONSOLE=1` (DEC-15), and `AGENT_SPEC_CONSOLE=0`
  turns it off.
- **Measured RAG accuracy and self-tuned fusion**: `agent-spec-platform.py rag-eval` scores keyword,
  semantic, hybrid and tuned search (hit@1, hit@k, MRR) on a golden set a local model writes
  without naming the files, keeps a history, and stores the semantic weight with the best MRR,
  which `search()` then uses. `rag-embed` embeds the whole index. nomic embeddings now use their
  task prefixes (vectors are stored under a new name, so old and new are never mixed). On this
  repository (60 cases) keyword search is the strongest single mode; the tuned weight (0.25) gives
  the best MRR (0.496 vs 0.480 keyword, 0.457 plain hybrid).
- **Harness A/B benchmark**: `bin/agent-spec-bench.py` runs the same prompts on the same local model
  with the harness on and off. First run on `qwen2.5-coder:7b`, 6 prompts: 5/6 correct with the
  harness, 3/6 without, at 65,568 vs 28,949 prompt tokens.
- **Showcase page**: `/showcase` puts the A/B result, RAG accuracy and its history, the token ledger,
  efficiency and accuracy tiles, a per-model table and the latest prompts on one screen, each
  figure labelled measured, estimated or AI-judged.

- **Impact tab on every request**: the request page now opens on what the harness changed in that
  request, compared with a plain Cursor chat. It shows estimated tokens kept out of the chat (subagent
  sweeps, graph queries priced as the median indexed file they replaced, ranged reads), a measured check
  of the raw-code-full rules, the remembered facts the session-start digest injected, and the fixed
  prompt cost the harness adds (rules, skills, subagent definitions) from Cursor's own breakdown.
  Shell calls to `graphify-cli.py` and `agent-spec-memory.py` are now named after the query
  ("graphify context") in the Orchestration and Waterfall views instead of "Shell".
- **Injected facts are recorded**: the sessionStart hook appends which facts it injected to
  `.agent-spec/metrics/injections.jsonl`, and ingest joins them to that conversation's requests in
  `fact_injections`, so Learning's "Facts injected per request" chart has data. Recording starts with
  this change; earlier chats have none. Read events now record the read extent for ranged reads too.
- **Skill prune** (43 → 35): removed `agent-spec-doc-coauthoring`, `-mcp-builder`, `-skill-creator`
  and `-webapp-testing` (vendored, never invoked), `-solid-check` (covered by `/agent-spec-review` and
  the `refactor` persona), `-prompt-audit` (never invoked, written around `CLAUDE.md`) and
  `-ai-architect` (duplicate of `/agent-spec-persona ai-architect`). `-synthesize-routine` is folded into
  `/agent-spec-learn propose`, which now drafts and validates an `agent-spec-wf-*` workflow. Skills that
  read project hard rules now point at `AGENTS.md` and `.cursor/rules/` instead of `CLAUDE.md`.
  `./install.sh` removes the dropped skills from `~/.cursor/skills`.
- **CLI runs labelled and hidden** (DV-064): requests made through `cursor-agent` (scripted probes,
  `--print` runs) never appear in Cursor's chat list, so they read as phantom requests. They are now
  tagged "CLI run" by Cursor's date-stamped CLI build string and hidden from Live, chats, the Coach
  latency table, skill usage and the Ask index unless "Show CLI runs" (or the CLI runs source) is chosen.
- **Headless requests named and closed** (DV-063): Cursor CLI runs (`cursor-agent --print`) fire no
  prompt or stop hook, so their requests showed "(prompt not captured)" and stayed RUNNING forever.
  The prompt is now read from Cursor's own transcript (only under `~/.cursor`, redacted, and only when
  the chat's queries map to its requests without guessing), and a request with no `stop` and no event
  for 30 minutes (`AGENT_SPEC_TRACE_IDLE_S`) is `incomplete — no stop event`.
- **Skill drift sync** (HA-007): the preflight (`agent-spec-ensure.py`) now installs any package
  skill that is missing from `~/.cursor/skills` or differs from the clone's copy, so a new or edited
  skill no longer waits for someone to re-run `./install.sh`. Switch it off as `skills-sync` in
  Project › Automations.
- **Indexer symlink guard** (PI-013): the project index never follows a symlink out of the project
  or onto a secret path.
- **Ask the project** (PI-001…PI-005, DEC-17): a local index of the code, docs, rules, memory,
  this workspace's Cursor requests and the AI session reviews, kept current by the dashboard
  every 60 s and by the CLI before each query. The new **Ask** space returns cited sources
  (`path:start-end`, `request <id>`) with highlighted snippets and filters by kind, folder and
  time; Ctrl/⌘-K sends any text there. `/agent-spec-ask` lets Cursor's agent answer the same
  questions with citations. Retrieval is BM25 by default; `AGENT_SPEC_EMBED=ollama:<model>` adds
  local embeddings fused by reciprocal rank, and `AGENT_SPEC_LLM=ollama:<model>` lets the
  dashboard write a labelled answer. Model endpoints must be loopback; secret paths are never
  read; other workspaces' chats are not indexed. CLI: `agent-spec-platform.py search|ask`.
- **Outcome quality** (PI-006…PI-008): each request now has measured outcome signals — tool
  failures, unchanged retries, missing-path errors, files edited and churn, whether a test,
  build or lint command ran after the last edit, and rework of the same files in a later
  request — each with its span ids (`agent-spec-platform.py signals`). The session-review rubric
  (2.1.0) scores eight outcome dimensions from them, or marks a dimension not assessable. Request
  › Outcome shows both side by side. Design and gap analysis: `docs/INTELLIGENCE-PLATFORM.md`.
- **Harness automation** (HA-001…HA-003): three scripts that someone had to remember to run now
  run from hooks. The long-chat `stop` follow-up is `/agent-spec-snapshot` itself rather than a
  sentence asking for it. An agent edit, a new or deleted file, or a shell command marks the
  graph dirty (`.agent-spec/.graph-dirty`), and the next `stop` rebuilds it in the background, so
  graph queries no longer lag a mid-session add, move or rename until the next session start.
  `sessionEnd` runs `agent-spec-memory.py rotate`. Auto-advancing SDLC gates was considered and
  dropped (HA-004): every gate is a separate human approval. Evidence: `docs/evidence/HA-001.md`.
- **Any project is ready in one command** (HA-005): `bin/agent-spec-ensure.py` registers an
  unregistered or outdated project, builds a missing graph, and reports whether
  `/agent-spec-onboard` is due, as one JSON line. The `agent-spec-raw-code-full` preflight, the
  router and `CURSOR.md` run it, so starting a skill in a new folder sets the harness up.
- **Automations panel** (HA-006): Project › Automations lists every step the harness runs on its
  own, with measured run counts, last status, a run log and an on/off switch for each. The
  switches write `.agent-spec/automation.json`, which the hooks read on their next run. Runs are
  logged to `.agent-spec/metrics/automation.jsonl`.
- **Measured context budget** (CB-001…CB-005): reads Cursor's own `contextTokensUsed` and
  `promptTokenBreakdown` and computes when a new chat pays for itself (the `agent-spec-tokens.py`
  break-even). The `stop` hook suggests `/agent-spec-compact` once per chat when it does
  (`AGENT_SPEC_CONTEXT_NUDGE=0` turns it off). The dashboard gains a Context tab on every request,
  a Context budget panel in Coach, and a context chip on each conversation. The sessionStart
  digest carries the last snapshot's title, files to load and open items again (its parser had
  fallen behind the snapshot format). Fixed: the AF-004 snapshot nudge never fired (marker spent on
  the first stop; a dict compared to an int). Evidence: `docs/evidence/CB-001.md`.
- **preToolUse follows Cursor's harness** (T-057, DEBT-005): Cursor strips a Read's offset/limit
  and reports StrReplace as a whole-file Write before the hook runs, so under Cursor the Read and
  Write nudges and the read hard cap are skipped. The event spine now judges each Cursor Read from
  `tool_output.content_length` against the file size, so Coach › Whole-file reads is measured.
  Evidence: `docs/evidence/T-057.md`.

## 2.0.0 — Phase 2 Platform

**Control Plane v2 & AI-First Realignment**
- **Dashboard UI & Platform API** (D-010–D-022, CP-000–CP-050): React 19 SPA bundled to 103.8 kB gzip
  served via stdlib `http.server` on 127.0.0.1; 5 core spaces (Home, Sessions, Runs, Knowledge, Governance);
  status bar with live hook status, doctor health, graph freshness, and session metrics.
- **Hook Event Spine & Ingest** (AF-001–AF-008): `hooks/cursor-event.py` records raw events to `events.jsonl`;
  ingestor builds requests/steps/subagent runs without Python heuristics.
- **AI Session Review** (AF-003): Evidence-backed session evaluation in `agent-spec-session-review` skill.
- **Self-Learning Flywheel** (L-001, L-002, L-005): Experience records in `experience.jsonl` with reuse tracking
  and measured token reduction; Fact schema v2 with expiration and supersession support.
- **Cursor-Native Orchestration** (O-001–O-020, B-003–B-009): Skill-driven workflows executed via
  `agent-spec-hub-runner` and recorded through `agent-spec-run.py`; live execution of `rca`, `pr-review`,
  `fix-plan`, and `eval` against golden tickets with human gate approvals and deterministic MCP output filtering.


- **Dashboard server** (D-020, S-003): `agent-spec-platform.py serve` — stdlib `http.server` on 127.0.0.1,
  read-only JSON over `platform.db` (`/api/health`, `/api/runs`, `/api/runs/{id}`, `/api/tasks`) and one
  static `ui/index.html`. Loopback `Host` check (403), per-launch token via HttpOnly SameSite=Strict cookie
  or header (401), GET only (405), non-loopback bind refused, CSP + nosniff, no request logging.
- **Session receipts** (T-050): `agent-spec-receipt.py` writes one JSON per Cursor session under
  `.agent-spec/metrics/receipts/` — tokens (marked estimated), tool calls, graph queries, whole-file
  reads over 20 KB, pipeline gate, facts injected. Counts only; no transcript text.
- **Session-end hook** (T-051): `sessionEnd` + `stop` handlers write the receipt and upsert a
  `metrics/daily.jsonl` row; fail-open, `stop` debounced to 30 s. `hooks.json` entries now carry explicit
  timeouts (sessionStart 10 s, others 5 s). Doctor WARNs when the receipt hook is not registered.
- **ROI viewer** (T-055): `agent-spec-roi.py list | rollup | export --csv | serve` (loopback only).
- **Auto-harness rule** (T-052): `CURSOR.md` gains a 406 B "Code change" rule — graph first, declaration,
  failing test first, surgical diff, real test output — without invoking `/agent-spec-implement`.
- **Shared team facts** (T-053): `TEAM_FACTS_REPO` (git URL or directory) or a submodule at
  `.agent-spec/team-facts/`; `agent-spec-memory.py merge-team`; org constraints appear as `[org]` in the digest;
  local facts win; lint covers both; doctor flags unmerged or stale sets.
- **preToolUse hardening** (T-057, DEBT-005): tolerant range-key matching, `Write` with `old_string`/`new_string`
  allowed, richer debug log, `.agent-spec/.hook-debug` marker. Root cause of the live ranged-Read nudge is not yet
  confirmed.
- **Docs** (T-059, DEBT-002): all dangling references fixed; selftest [12] fails on any new one.
- **Onboarding:** agent runs `/agent-spec-onboard` automatically when `.onboarding-needed` exists;
  digest no longer instructs the user to run it manually (2026-10-29).

## 1.1.0 — Phase 1 Stabilize

**Trust**
- **`agent-spec-doctor.py`** (T-005): checks skills, hooks.json, digest JSON, graph age, memory
  index size, registry vs cwd, harness version drift, git auto-index hooks, `team.yaml`, token
  audit, stacked always-on rules. Every FAIL/WARN prints its fix. `--json`, `--strict`, `--line`.
  Runs at the end of `install.sh --register` and as one `doctor:` line in the digest (T-054).
- **Memory lint** (T-001): `agent-spec-memory.py lint` flags duplicate keys (DUP-KEY),
  near-identical bodies (DUP-BODY) and opposing constraints (CONFLICT); `add` warns on overlap.
- **Memory index** (T-002): `memory/INDEX.md`, one line per fact, regenerated by `add`/`prune`
  (`index`, `index --check`). `audit` now measures `INDEX.md` only — fact bodies and archived
  snapshots no longer count against the 8 KB budget.
- **Tech debt register** (T-006): real entries; shipped template no longer carries fake rows.

**Demo CLI**
- **Graph freshness in the digest** (T-003): `graph: fresh | incremental (Nms, K reparsed) |
  stale (lock held | timeout | build failed)`. `graphify-build.py` writes `graph/.status.json` and
  exits 3 on `--quiet` lock contention. `AGENT_SPEC_BUILD_TIMEOUT` (default 3 s).
- **Onboarding nudge** (T-004): install creates `.agent-spec/.onboarding-needed` on first install
  (or while the constitution has template placeholders); digest says ``run `/agent-spec-onboard` now``.

**Tokens**
- **Tool discipline** (T-010): 7 rules in `CURSOR.md` (always-on rule).
- **Optional hard cap** (T-011): `AGENT_SPEC_READ_HARD_CAP_KB=<n>` denies rangeless Reads of n KB+
  every time (default off). `AGENT_SPEC_HOOK_DEBUG=1` logs payload key names to diagnose Cursor's
  real payload; alternate range keys and stringified `tool_input` are handled.
- **Measurement habit** (T-012) in QUICKSTART and `token-efficiency.md`; `audit` exits non-zero on
  findings (CI-ready). Doctor reports the always-on footprint and the context size at which it is under 5 %.
- **Coexistence** (T-013): `audit` and doctor flag `algosec-lean` Always Apply next to `agent-spec.mdc`.
- **Router skill** (T-014): `agent-spec` SKILL.md 4,543 B → under 3 KB; points at `agent-spec-gate.py status`.

**Developer experience**
- QUICKSTART Day-1 path, graph-freshness table, Windows section, team defaults, adoption checklist (T-020, T-021, T-033, T-034).
- `check-install.sh` and doctor compare the workspace's stamped harness version with `VERSION` (T-022).
- **`install.sh --register-here`** (T-030); `install.ps1 -Register/-RegisterHere` converts paths for Git Bash/WSL.
- Doctor and check-install warn when a workspace predates the `post-rewrite` hook (T-031).
- Optional **`.agent-spec/team.yaml`** (T-032): `java_version`, `node_version`, `sdlc_track`, `default_branch`; digest `team:` line.

**Tests**: `tests/test_memory.py`, `test_digest.py`, `test_pre_tool_use.py`, `test_audit.py`,
`test_doctor.py`; selftest sections [11]–[12]; section numbering fixed.

**Not in 1.1.0**: Slice 1.5 zero-touch items T-050–T-053 and T-055 (receipt, session-end hook,
auto-harness rule, shared facts, ROI viewer); native PowerShell port; no git tag (workspace has no repository).

## 1.0.3

- **SDLC routing:** `/agent-spec-sdlc` 2×2 tracks (fast-track / algorithm / design / full);
  gate 1 `## Complexity` block in tech-spec skill and [`sdlc/02-TECH-SPEC.md`](sdlc/02-TECH-SPEC.md).
- **Skills:** Ported upstream quality improvements (requirements, tech-spec, prd, solid-check,
  snapshot, verbose, webapp-testing, raw-code-full Complexity Override).
- **`agent-spec-skill-creator`:** Imperative SKILL body + [`docs/full-guide.md`](skills/agent-spec-skill-creator/docs/full-guide.md); Cursor-specific eval notes.
- **Docs:** Nine-gate fixes in [`core/PHILOSOPHY.md`](core/PHILOSOPHY.md) and
  [`core/ANTI-PATTERNS.md`](core/ANTI-PATTERNS.md); README restructured (at-a-glance, grouped skills).

## 1.0.2

- **`agent-spec-tokens.py`** is **Cursor-first**: `list`, `session`, `overhead`, `corpus`, etc.
  read `~/.cursor/projects/<slug>/agent-transcripts/` (slug replaces `/` and `.` with `-`).
  Cursor JSONL without `usage` gets chars÷4 estimates; harness tags in user turns feed `overhead`.
- **`--claude`** / **`audit --include-claude`** for legacy Claude Code JSONL and settings scans.

## 1.0.1

- Shipped **`bin/agent-spec-tokens.py`** (upstream `overhead` / `audit` + Claude JSONL
  readers) with **Cursor `audit`** for `.cursor/hooks.json`, rules, skill twins, memory tree.
- **`install.sh --register`** copies tokens into `.agent-spec/bin/`; **`check-install.sh`** verifies it.
- Docs: [token-efficiency.md](docs/token-efficiency.md) two-track measurement; [QUICKSTART.md](docs/QUICKSTART.md)
  hooks troubleshooting; workflow + checklist updates.
- **Not shipped:** upstream `agent-spec-settings.py` (Claude `settings.json` merger).

## 1.0.0 — Cursor-only

- Package brand: **algosec-agent-spec** for Cursor only.
- Removed Claude Code / Gemini / Antigravity surfaces (`CLAUDE.md`, `GEMINI.md`,
  `.claude`, output-styles, Claude settings/hooks/bench harness).
- Skills live under `skills/` (flat); install → `~/.cursor/skills/`.
- `./install.sh --register`, `./check-install.sh`, `./uninstall.sh`, Windows `.ps1`.
- Canonical always-on: `CURSOR.md` → `.cursor/rules/agent-spec.mdc`.
- Hooks: `sessionStart` digest + `preToolUse` input discipline (fail-open, marked).
- Subagents → `.cursor/agents/` with `model: inherit`.
- Compact skill: snapshot + new Cursor chat (no Claude `/compact`).
- Upgrade vs preserve contract documented; registry
  `~/.cursor/skills/.algosec-agent-spec-projects`.

Upstream measurement docs retained under `docs/token-*.md`.
