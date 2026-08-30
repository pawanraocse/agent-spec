# The Skills System

> **Skills are executable workflows for AI agents.**

While personas define *how* an agent behaves (rules and tone), skills define *what* an agent does (workflows and outputs). 

`agent-spec` provides a suite of standard skills that map directly to the SDLC stages and pipeline gates.

---

## The Core Skills

### The SDLC Builders
- `/agent-spec-requirements`: Elicit and structure raw customer needs.
- `/agent-spec-tech-spec`: Define feasibility and constraints.
- `/agent-spec-prd`: Generate the Product Requirements Document (WHAT/WHY).
- `/agent-spec-hld`: Generate the High Level Design (Architecture/Mermaid).
- `/agent-spec-lld`: Generate the Low Level Design (Classes/Schemas).

### The Execution Engine
- `/agent-spec-implement`: Triggers the 6-Gate coding pipeline.
- `/agent-spec-review`: Deep, skeptical code review against SOLID/Security standards.
- `/agent-spec-solid-check`: Specifically audits a file for SOLID violations.

### Memory & State
- `/agent-spec-index-project`: Runs Graphify to build/update `KNOWLEDGE-GRAPH.md`.
- `/agent-spec-snapshot`: Generates `SESSION-SNAPSHOT.md` to save state.
- `/agent-spec-debt`: Analyzes code and logs findings to `TECH-DEBT-REGISTER.md`.

### Context Management (Token Savers)
- `/agent-spec-raw-code`: Minimal output. Code only. No pleasantries.
- `/agent-spec-trim-noise`: Removes conversational filler (reduces output by ~40%).
- `/agent-spec-dense`: Maximum information density (tables, bullet points, abbreviations).
- `/agent-spec-verbose`: Restores default chatty behavior.

---

## How Skills Are Installed

Every skill is authored once, in `skills/claude/<name>/SKILL.md`. Claude Code, Cursor and
the generic agents all read that same shape, so the installer copies it directly. One
tree, no translations, nothing to regenerate.

`bin/install.sh` installs skills **machine-wide** by default, so they are available in
every project without a per-project step:

- **Claude**: `~/.claude/skills/<name>/SKILL.md` (and the Windows home, on WSL)
- **Cursor**: `~/.cursor/skills/<name>/SKILL.md` — on-demand skills, not always-on rules
- **Antigravity / generic**: `.agents/skills/<name>/SKILL.md` per project

`--project-skills` additionally writes `.claude/skills/` and `.cursor/skills/` inside the
repo, for teams that want them committed. See [`docs/agents.md`](../docs/agents.md).
