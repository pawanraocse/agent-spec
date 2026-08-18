# The Skills System

> **Skills are executable workflows for AI agents.**

While personas define *how* an agent behaves (rules and tone), skills define *what* an agent does (workflows and outputs). 

`agent-spec` provides a suite of standard skills that map directly to the SDLC stages and pipeline gates.

---

## The Core Skills

### The SDLC Builders
- `/requirements`: Elicit and structure raw customer needs.
- `/tech-spec`: Define feasibility and constraints.
- `/prd`: Generate the Product Requirements Document (WHAT/WHY).
- `/hld`: Generate the High Level Design (Architecture/Mermaid).
- `/lld`: Generate the Low Level Design (Classes/Schemas).

### The Execution Engine
- `/implement`: Triggers the 6-Gate coding pipeline.
- `/review`: Deep, skeptical code review against SOLID/Security standards.
- `/solid-check`: Specifically audits a file for SOLID violations.

### Memory & State
- `/index-project`: Runs Graphify to build/update `KNOWLEDGE-GRAPH.md`.
- `/snapshot`: Generates `SESSION-SNAPSHOT.md` to save state.
- `/debt`: Analyzes code and logs findings to `TECH-DEBT-REGISTER.md`.

### Context Management (Token Savers)
- `/raw-code`: Minimal output. Code only. No pleasantries.
- `/trim-noise`: Removes conversational filler (reduces output by ~40%).
- `/dense`: Maximum information density (tables, bullet points, abbreviations).
- `/verbose`: Restores default chatty behavior.

---

## How Skills Are Installed

Because different AI platforms (Claude Code, Gemini CLI, Cursor, GitHub Copilot) expect skills in different formats and locations, `agent-spec` maintains translations for all of them.

When you run `agent-spec init`, the framework copies the correct format into your project root:

- **Claude**: `.claude/skills/<name>/SKILL.md` (Markdown with YAML frontmatter)
- **Cursor**: `.cursor/rules/<name>.md` (Markdown, loaded as rules)
- **Generic**: `.agents/skills/<name>/SKILL.md` (standard markdown for Gemini/Copilot/Antigravity)
- **Copilot**: `.github/copilot-instructions.md` (single always-on instructions file)
- **Windsurf**: `.windsurfrules` (single always-on rules file)
