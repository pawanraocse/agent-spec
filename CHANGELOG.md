# Changelog

All notable changes to **agent-spec** will be documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

### Added
- **`bin/agent-spec-tokens.py` — measurement instead of assertion.** Claude Code writes a
  JSONL transcript per session in which every assistant turn carries a `usage` object with
  the four token buckets. This reads it: `session` reports the buckets weighted by price
  ratio, `tools` reports what was written into each tool and what came back, and `compare`
  puts two transcripts side by side for an honest A/B. Read-only; the price ratios are
  overridable with `--weights` because they are an assumption, not a measurement.
  `bin/agent-spec-bench.sh --session` delegates to it, and the byte-based numbers are now
  labelled as the estimates they are.
- **`/agent-spec-raw-code-full`** — the whole token stack, ordered by measured leverage:
  fewer turns, smaller context, cheaper writes, capped tool output, and caveman prose last
  because that is where the evidence puts it. The numbers are in the skill body so nobody
  reorders it on intuition.
- **`docs/token-efficiency.md`** — where the tokens actually went in a real session here,
  with the JetBrains SkillsBench and Hackenberger figures and their links, so the next
  person to read a "60-90% savings" claim finds the measured refutation in the repository.

### Changed
- **`/agent-spec-raw-code` is now honestly scoped to output.** It had carried a reading-
  discipline section that made it look like it covered more than it did; that moved to
  `raw-code-full`. Both skills, and the always-on output style, gained the rule that
  matters more than terseness: lead with the answer, ask for exactly one thing at a time,
  and never answer with a paragraph of questions and possibilities.
- The self-test covers token measurement and the terse-mode set: **38 assertions, all
  passing**, up from 29. Two of the new assertions were wrong on their first run — the
  expected weighted total was miscalculated by hand — and the tool was right.

### Removed
- **`/agent-spec-dense` and `/agent-spec-trim-noise`.** The output style already makes
  dense-with-full-sentences the default, so both toggled toward what was already on. Two
  terse modes remain — `raw-code` for output, `raw-code-full` for everything — plus
  `verbose` as the off switch. The installer prunes both from every `.claude` and
  `.cursor` home on upgrade.

- **`/agent-spec` — the router.** Choosing between 25 skills is itself a decision, and
  choosing wrong is expensive: `/agent-spec-implement` on a defect whose cause is unknown
  burns a session on edit-test-edit. The router reads the pipeline state, matches the
  request against an ordered table whose top rows exist to prevent exactly those mistakes,
  fetches the file list from the graph, and hands off to one skill. It never does the work
  itself and never chains two skills on one request.
- **Project memory** — `.agent-spec/memory/facts/`, one fact per file, typed `constraint`,
  `decision`, `gotcha` or `reference`, each dated and sourced. `bin/agent-spec-memory.py`
  adds, lists, searches, shows and prunes them, and the `SessionStart` hook prints them
  all — constraints first, under a byte cap — so a fact recorded once is known by every
  later session without anyone opening a file. Capped at forty and pruned deliberately;
  memory that grows without limit becomes the problem it was meant to solve. The skill is
  `/agent-spec-remember`, and it is explicit about what does not belong: anything the
  repository already answers.
- **Snapshot rotation.** `SESSION-SNAPSHOT.md` is append-only by design, but append-only
  is not unbounded — past about 12 KB whatever loads it truncates, silently, oldest first.
  `agent-spec-memory.py rotate` moves the older sections into `memory/snapshots/` where
  they stay readable on purpose. Nothing is deleted. `/agent-spec-snapshot` runs it.
- **Legacy skill pruning on upgrade.** An install that only copied the new prefixed names
  would leave the old ones beside them — 22 duplicate commands, two of every pipeline
  gate, no way to tell which ran. The installer now removes them by name, and only when
  the directory carries a `SKILL.md` whose frontmatter matches, so a skill the user wrote
  is never touched.
- **Indexer limits for real repositories** — `.gitignore` directories excluded on top of
  the built-in list, files over 1 MB and minified or generated ones skipped as written by
  a tool rather than a person, symlink loops terminated, and hitting the file ceiling
  reported rather than silently producing a partial graph.

### Changed
- **Every skill is now prefixed `agent-spec-`**, so a transcript shows which tool ran and
  where it came from. `/prd` is `/agent-spec-prd`, and so on throughout.
- **The ten persona skills are one skill.** `/agent-spec-persona <role>` covers architect,
  security, qa, data, devops, perf, refactor, api, writer and reviewer. Each role's
  Absolute Rules live in `.agent-spec/personas/<ROLE>.md`, which was always the source of
  truth — the ten skills were lifting it verbatim, which is a second copy and therefore a
  second thing to drift.
- Persona references across `CLAUDE.md`, `AGENTS.md`, `CURSOR.md`, `GEMINI.md` and
  `core/` pointed at `SECURITY-AUDITOR.md`, `QA-ENGINEER.md` and `CODE-REVIEWER` — three
  filenames that have never existed in `personas/`. All corrected.
- `--lean` now holds back five SDLC-design skills rather than eight; the list it named
  included two skills that no longer exist under those names.
- The self-test covers the skill naming contract, memory, rotation, indexer limits and the
  upgrade path: **29 assertions, all passing**, up from 16.

- **`/sdlc` orchestrator and `bin/agent-spec-gate.py`** — the nine SDLC gates now have state
  on disk (`.agent-spec/sdlc/STATE.json`) instead of in whichever context window is open.
  `status` says where the pipeline is, `check <n>` exits 1 with the missing artifact named,
  `set <n>` records a pass, and `trace` follows every `REQ-`/`NFR-`/`US-` identifier from
  gate 0 through every downstream artifact and exits 1 on a requirement that reached
  nothing. Every existing gate skill now calls `check` instead of its own `test -f`, and
  records itself before stopping.
- **`/testing` (gate 7) and `/validation` (gate 8)** — the two gates the pipeline never had.
  `/testing` runs the whole suite and reports failures verbatim into `07-TEST-REPORT.md`;
  `/validation` gives one verdict per requirement — PASS, FAIL, NOT-TESTED or DEFERRED,
  with evidence — into `08-VALIDATION.md`, and never writes SHIP over a FAIL.
- **Graphify v2: services, integration edges, layers, conventions.** The graph now detects
  one service per manifest below the root, classifies every file into a layer and reports
  the edges that point the wrong way through it, and recovers the coupling no import graph
  can see: HTTP calls matched to service names, and Kafka/Rabbit/SQS topics matched from
  producer to consumer. It also writes `graph/CONVENTIONS.md` — test framework, injection
  style, error handling and logging, counted across the tree rather than inferred from
  whichever files someone happened to open.
- **New graph queries** — `context --task "<description>"` returns the file list a task
  needs and nothing else; `flow --from <file>` follows the call chain; `services` prints the
  service map and what talks to what; `endpoints` prints the HTTP surface; `layers` prints
  the census and every violation.
- **Incremental indexing.** Only files whose mtime or size moved are re-parsed. The cache is
  keyed by parser version, so changing an extraction pattern invalidates it rather than
  silently serving stale results.
- **Harness-level token reduction.** `bin/install.sh` now writes an `agent-spec` output style
  and a `SessionStart` hook into every `.claude` home, merging non-destructively into an
  existing `settings.json`. The hook emits a ~600-byte project digest — stack, graph size,
  current gate, last session — which replaces the old "read these four files" protocol.
  Measured on this repository: 12,093 bytes of file reads become 605 bytes of digest.
- **`bin/agent-spec-selftest.sh`** — builds Python, Java-multiservice and Node fixtures,
  installs into each, and asserts the failures that have actually shipped here before:
  edges resolving to nothing, the wrapper overwriting the builder's output, gate ordering
  that lets a gate run without its predecessor, and a settings merge that stacks duplicates.
  16 assertions, all passing.
- **`bin/agent-spec-bench.sh`** — prints the always-on context cost and per-skill body cost,
  so "more efficient" can be checked rather than asserted.

### Changed
- `AGENTS.md`, `CLAUDE.md`, `CURSOR.md` and `GEMINI.md` no longer repeat the skill list the
  harness already enumerates, and the session-start protocol is now three lines pointing at
  the digest rather than four file reads. Always-on context for Claude: 6,863 → 4,875 bytes.
- `AGENTS.md`'s "6-Gate Pipeline" described a third pipeline matching neither the SDLC gates
  nor `/implement`'s internal gates. Replaced with the real nine-gate table.
- Skill descriptions dropped the repeated "Carries its absolute rules inline." tail.
- `sdlc/` stage documents realigned to the nine gates: `06-IMPLEMENTATION.md` renamed to
  `06-DEVELOPMENT.md`, and `07-REVIEW.md`, `08-TESTING.md` and `09-VALIDATION.md` added.
- `/review`, `/investigate` and `/onboard` now say to send broad "where does this live"
  sweeps to a subagent, so those reads never enter the main conversation.

### Removed
- **`pipeline/GATE-1..6-*.md`** — a third description of the implementation gates, whose
  names matched neither `/implement` nor `AGENTS.md`. `pipeline/README.md` now summarises
  the six gates and defers to the skill, which is the definition that actually runs.
- **`sdlc-team/`** — a second copy of the same pipeline, never loaded by anything, and a
  standing source of drift. The pipeline lives in `skills/claude/` alone. Recoverable from
  git history if the portable-plugin shape is ever wanted again.

### Fixed
- **`/index-project` pointed at a path that never exists in an installed project.** The skill said to
  run `bin/agent-spec-index.sh`, but `agent-spec-init.sh` installs that script as
  `.agent-spec/bin/agent-spec-index` (relocated, `.sh` stripped). The old path only resolved inside
  the agent-spec source repo, so the skill failed on first use in every consuming project. Fixed in
  all three variants (`skills/claude/`, `skills/generic/`, `skills/cursor/`) and expanded with the
  correct graph output locations, a verification step, and the `graphify-build.py` fallback.
- **README documented the wrong install locations.** It listed `.claude/commands/`, `.gemini/commands/`
  and `.cursor/skills/`; the installer actually writes `.claude/skills/`, `.cursor/rules/` and
  `.agents/skills/` (Gemini is served by `.agents/skills/` + `GEMINI.md`, never `.gemini/`). Replaced
  with a table matching what the script does, and corrected the skill count from 60 to 26.
- **The remaining agent config files documented the same wrong install locations.** The README fix
  above missed its siblings: `CLAUDE.md` said `.claude/commands/`, `CURSOR.md` said `.cursor/skills/`,
  `COPILOT.md` said `.github/skills/` (the installer writes only `.github/copilot-instructions.md`;
  Copilot's skills come from `.agents/skills/`), and `skills/README.md` still listed all three plus a
  `.gemini/commands/*.toml` target the installer has never produced. All now match the script.
- **`/caveman` and `/defluffer` do not exist.** `CLAUDE.md`, `CURSOR.md` and `COPILOT.md` advertised
  both; the actual skills are `/raw-code` and `/trim-noise`. Invoking either documented name was a
  guaranteed miss.
- **`CLAUDE.md` was missing 11 of the 26 installed skills** — `/query-graph` and the ten persona
  switches added in `bf5410f` (`/architect`, `/security`, `/qa`, `/reviewer`, `/refactor`, `/api`,
  `/data`, `/devops`, `/perf`, `/writer`) never made it into the slash-command table.
- **Two more stale `bin/agent-spec-index.sh` references**, in `.windsurfrules` and
  `.github/copilot-instructions.md`, plus three in the README that kept the `.sh` the installer
  strips. Same failure as the `/index-project` fix above.

### Changed
- **`agent-spec-init.sh` now tells you to restart your agent CLI first.** Claude Code only watches
  `.claude/skills/` if the directory existed when the session started; when the installer creates it
  mid-session the skills are installed correctly but stay invisible until a restart. This was silent
  and looked like a broken install. Also noted in the README.

## [1.0.0] — 2026-05-09

### Added
- **Full AI-SDLC Pipeline**: `/requirements` → `/tech-spec` → `/prd` → `/hld` → `/lld` → `/implement` → `/review`
- **6-Gate Development Pipeline**: Discovery → Spec → Architecture → Tasks → Implementation → Verification
- **Graphify Indexing**: JSON knowledge graph + auto-generated Mermaid visualization
- **Session Snapshots**: Never lose context between agent sessions
- **10 Expert Personas**: Architect, Security Auditor, Performance Engineer, QA Engineer, Code Reviewer, Tech Writer, Refactor Specialist, API Designer, Data Engineer, DevOps Engineer
- **Anti-Hallucination Protocol**: Confidence scoring, verification checklists, recovery playbook
- **15 Agent Skills** across 4 agent platforms (Claude, Gemini, Cursor, Generic)
- **Token Reduction Skills**: `/caveman`, `/defluffer`, `/dense` — manage context window cost
- **4 Rules Files**: Absolute rules, communication rules, change management, autonomy limits
- **Coding Standards**: SOLID principles, clean code, error handling, testing, API contracts
- **Language Guides**: Java (Spring Boot) + Angular at full depth; Python + Go as templates
- **8 Spec Templates**: Feature, bug, ADR, refactor, API, test plan, constitution, session handoff
- **`agent-spec init`**: Zero-dependency shell script to bootstrap any project
- **`agent-spec index`**: Graphify-powered scanner for existing codebases
- **`agent-spec new`**: New project scaffolder with SDLC kickoff
