# testing_todo.md — validation backlog for Phase 2 (v2.0.0)

Maintained alongside implementation. Every row says **what was automated** (real result at time of writing)
and **what still needs a human, a live Cursor session, or another host**.
Status: `AUTO-PASS` automated check ran green · `MANUAL` owed · `BLOCKED` needs a host/credential.

## How to run everything automated

```bash
./bin/agent-spec-selftest.sh              # whole harness incl. section [13] platform (needs sandbox-off: it writes temp HOME)
python3 tests/test_<module>.py            # one suite; all are stdlib-only and also run on /usr/bin/python3 (3.9.6)
```

## Decisions that change what must be tested

- **DEC-11** package is `bin/aspec_platform/` (a dir named `platform` shadows the stdlib module).
- **DEC-12 (2026-10-31)** Cursor-native orchestration, minimum code: no Python hub-runner, no Pydantic/PyYAML/FastAPI.
  Workflows are skills run by Cursor Task subagents; deterministic code = DB + ingest, run-dir plumbing
  (`agent-spec-run.py`), S-002 hook, backlog CLI, stdlib dashboard API. **Consequence: every workflow/skill row is
  verified by a live Cursor chat (MANUAL) — unit tests only cover the plumbing.**

## Environment notes

- No git repo (T-056 deferred): git-worktree parallel writers cannot be exercised; fan-out with non-empty `writes` is serialized.
- Full selftest cannot run in the Cursor sandbox (it redirects HOME to a temp dir): run it with sandbox disabled.

## Framework solidification (pre-skill) — three gates

| Step | Goal | Automated proof (2026-11-03) | Still owed |
|------|------|------------------------------|------------|
| **1 — Engine plumbing** | One run dir, one redactor, ingest → SQLite | `test_run_dir`, `test_resume`, `test_ingest_runs`, `test_o020_framework_proof`; `agent-spec-run.py` loads `aspec_platform/redact.py` by path (same as receipt) | Live hub-runner loop (O-003…O-018 `[~]`); `compact` CLI alias optional |
| **2 — Context & tool protection** | Quarantine, digest discipline, doctor | `test_pre_tool_use`, `test_redact`, `test_api_security`, CURSOR tool discipline; S-004 (>80k token nudge), S-005 (MCP schema audit in doctor), O-018.1 (error cap ≤1k chars), B-006.1 (deterministic MCP filter) AUTO-PASS | T-057 hook proof in live Cursor |
| **3 — Reference workflow + dashboard** | O-020 path visible end-to-end | `test_o020_framework_proof` (example → ingest → `/api/runs/{id}`); D-012/D-021/D-022 via `test_insights` + `test_api`; live run `01M6JD36AEKCV8Z95D5DPM1VDA` recorded | **O-020 closed** (`agent-spec-backlog.py set --evidence`); `./bin/agent-spec-platform.py serve` smoke in browser |

**Skills deferred until Step 3 live gate closes:** L-002, B-003, B-006, B-008, B-009 (RCA / PR-review / eval).

Proof commands:

```bash
./bin/agent-spec-selftest.sh
python3 tests/test_o020_framework_proof.py
AGENT_SPEC_DB=./.agent-spec/platform/platform.db ./bin/agent-spec-platform.py ingest runs
./bin/agent-spec-platform.py serve   # loopback + token; Home / Runs / Gaps
./bin/agent-spec-platform.py export --out /tmp/aspec-proof
```

## Wave 1 — Slice 5 data layer

| P# | ID | Automated | Manual / owed |
|----|----|-----------|---------------|
| P2.3 | D-001 | `tests/test_platform_db.py` (7 tests: tables, WAL, FK, idempotent migrate, newer-DB refusal, env override, FTS5, CLI init) + `tests/test_platform_guard.py` (R1 import guard + no `platform` shadowing) — AUTO-PASS on 3.14 and 3.9 | MANUAL: `./bin/agent-spec-platform.py init` in a real registered project; confirm `.agent-spec/platform/platform.db` appears |
| P2.7 | D-004.1 | `tests/test_backlog.py` (7: parses real todo-plan.md = 120 rows, `[x]` refused without `--evidence`, only the target line changes, evidence file written, unknown ID) — AUTO-PASS 3.14 + 3.9. Dogfooded: D-001/D-004.1/S-001 closed through the CLI | MANUAL: `bin/agent-spec-backlog.py json \| python3 -c 'import json,sys;print(len(json.load(sys.stdin)))'` ≥ 120; `tasks` table ingest not yet run (needs ingest agent) |

## Wave 2 — Security + tools

| P# | ID | Automated | Manual / owed |
|----|----|-----------|---------------|
| P2.12 | S-002 | `tests/test_pre_tool_use.py` (19 tests: every rule-id `env-file ssh-private-key pem-file key-file credentials-file secrets-file aws-dir ssh-dir gnupg-dir`, allow-list `.example/.sample/.template`, `secrets_manager.py` allowed, quarantine.jsonl line, malformed payload fail-open) — AUTO-PASS 3.14 + 3.9; ~35 ms/call. **Live evidence:** the hook blocked two agent Shell commands that contained a dotenv path ("quarantine: blocked sensitive path (env-file)") | MANUAL: Read `~/.ssh/id_rsa` and Grep `~/.aws` in a live chat; confirm lines in `.agent-spec/metrics/quarantine.jsonl`. **Known false positive:** any Shell command that merely mentions a dotenv path (e.g. a commit message, an echo) is denied — decide if acceptable. Deny now also fires in folders without `.agent-spec` |
| P2.29 | S-001 | `tests/test_blast_radius.py` (5: grouped output, `--no-color`, NO_COLOR, ANSI under a PTY, unknown file → exit 2) — AUTO-PASS 3.14 + 3.9 (PTY test skips inside the Cursor sandbox, ran outside) | MANUAL: run `bin/agent-spec-blast-radius --file bin/graphify-cli.py` in a real terminal; eyeball colours; run from project root only |

## Wave 3 — Orchestration core (Cursor-native, DEC-12)

| P# | ID | Automated | Manual / owed |
|----|----|-----------|---------------|
| P2.37–P2.39, P2.42, P2.44 | O-001, O-002, O-002.1, O-019, O-017 | `tests/test_run_dir.py` (9), `test_resume.py` (7: crash → resume re-runs only unfinished, drift refusal, idempotent reuse), `test_status.py` (5), `test_workflow_validate.py` (11: cycle / missing need / duplicate id / legacy format rejected) — AUTO-PASS 3.14 + 3.9; lint-refs clean; skills `agent-spec-hub-runner` 2511 B, `agent-spec-wf-example` 1027 B | MANUAL (live Cursor): run the hub-runner skill on workflow `example`; check `.agent-spec/runs/<id>/` has `events.jsonl`, `checkpoint.json`, `result.json` and `finish` = success. Interrupt after `gather`, resume in a new chat → `gather` not re-run. Edit the example SKILL.md mid-run → `resume` refused (exit 3) until `--accept-drift`. `compact --days 0 --dry-run` lists only finished runs. **Gap:** tests were not run red-first. `redact()` in `agent-spec-run.py` is a minimal local copy — unify with `aspec_platform/redact.py` |
| P2.45 (partial) | O-012 | trace id on every event covered by `test_run_dir.py`; Langfuse exporter dropped by DEC-12 | Row stays open until the dashboard shows trace ids |

## Wave 3b — Learning (Slice 7)

| P# | ID | Automated | Manual / owed |
|----|----|-----------|---------------|
| P2.30 | L-005 | `tests/test_memory.py` (19: 7 new v2 cases + v1 compat), `test_digest.py` (12: expired / superseded facts excluded, v1 digest byte-identical), `test_team_facts.py` (8), `test_doctor.py` (16) — AUTO-PASS 3.14 + 3.9. `memory lint` on this repo: clean (13 facts); digest block 1133 B | MANUAL: in a registered project run `agent-spec-memory.py add --supersedes <id>` and `add --expires <past date>`; check digest, `list`, `lint`; doctor "memory lint" WARN appears for an expired fact. Caveats: `INDEX.md` still lists non-active facts (unmarked); `prune` ignores v2 fields; `test_doctor` needs sandbox off |

## Wave 1 — ingest (Slice 5), rows D-002 D-003 D-004 D-005 D-006 (P2.4–P2.6, P2.8, P2.9)

| P# | ID | Automated | Manual / owed |
|----|----|-----------|---------------|
| P2.4–P2.9 | D-002…D-006 | `test_redact` (8), `test_ingest_transcripts` (14; 1,000 lines in 0.024 s), `test_ingest_subagents` (8), `test_ingest_gates` (5), `test_ingest_memory` (5), `test_ingest_graph` (6; includes quarantine ingest and a real `graphify-build` twice) — AUTO-PASS 3.14 + 3.9. Real ingest of this repo: 65 requests, 1,540 steps, 11 subagent runs, 13 facts, 2 quarantine events; **second run = no-op (unchanged=20)**; 0 steps contain "thinking" | MANUAL: (1) `AGENT_SPEC_DB=./.agent-spec/platform/platform.db ./bin/agent-spec-platform.py ingest --rebuild` on a real project, run again → 0 rows added; grep `requests.prompt_redacted` / `steps.detail_json` for secrets and "thinking". (2) `graphify-build.py` writes a line to `.agent-spec/graph/stats-history.jsonl`, then `ingest graph`. (3) Check subagent links + `started` times on real data. **Known limits:** parent transcripts hold no Task calls or timestamps, so children link by order/time (Task steps only tested synthetically); receipts hold only a `facts_injected` count → `fact_injections` gets no rows (counts in meta `receipt:<session>`); real gate file is `.agent-spec/sdlc/STATE.json` (both paths read); `compact` has no CLI command (`ingest compact` only); `ingest.py` was not written red-first; redaction can over-redact `token = tokens.read(path)` and misses passwords < 4 chars; backlog/runs/experiences sources are `unsupported` until their rows land; `S-003` stays open (redactor done, HTTP middleware pending) |

## Wave 1 — ingest (Slice 5), rows D-002 D-003 D-004 D-005 D-006 (P2.4–P2.6, P2.8, P2.9)

| P# | ID | Automated | Manual / owed |
|----|----|-----------|---------------|
| P2.4–P2.9 | D-002…D-006 | `test_redact` (8), `test_ingest_transcripts` (14; 1,000 lines in 0.024 s), `test_ingest_subagents` (8), `test_ingest_gates` (5), `test_ingest_memory` (5), `test_ingest_graph` (6; includes quarantine ingest and a real `graphify-build` twice) — AUTO-PASS 3.14 + 3.9. Real ingest of this repo: 65 requests, 1,540 steps, 11 subagent runs, 13 facts, 2 quarantine events; **second run = no-op (unchanged=20)**; 0 steps contain "thinking" | MANUAL: (1) `AGENT_SPEC_DB=./.agent-spec/platform/platform.db ./bin/agent-spec-platform.py ingest --rebuild` on a real project, run again → 0 rows added; grep `requests.prompt_redacted` / `steps.detail_json` for secrets and "thinking". (2) `graphify-build.py` writes a line to `.agent-spec/graph/stats-history.jsonl`, then `ingest graph`. (3) Check subagent links + `started` times on real data. **Known limits:** parent transcripts hold no Task calls or timestamps, so children link by order/time (Task steps only tested synthetically); receipts hold only a `facts_injected` count → `fact_injections` gets no rows (counts in meta `receipt:<session>`); real gate file is `.agent-spec/sdlc/STATE.json` (both paths read); `compact` has no CLI command (`ingest compact` only); `ingest.py` was not written red-first; redaction can over-redact `token = tokens.read(path)` and misses passwords < 4 chars; backlog/runs/experiences sources are `unsupported` until their rows land; `S-003` stays open (redactor done, HTTP middleware pending) |
