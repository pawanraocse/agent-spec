# Changelog

All notable changes to **agent-spec** will be documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

---

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
