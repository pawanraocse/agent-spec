# Changelog

All notable changes to **agent-spec** will be documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

### Added
- **`sdlc-team/` — a standalone Claude Code plugin** providing a gated SDLC pipeline: 9 subagents
  (PRD → HLD → LLD → implementation → review → test → QA → deployment), 11 skills and 10 slash
  commands. Drops into any repo with no other setup. Orchestration runs in the main conversation
  rather than a subagent, because subagents cannot pause to ask the user anything — putting the
  pipeline inside one would silently discard the confirmation gates. Stages hand off through files
  in `docs/sdlc/<slug>/`, and every stage reconciles its output against the previous artifact,
  halting on anything `MISSING` or `CONTRADICTS`.

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
