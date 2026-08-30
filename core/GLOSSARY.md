# Glossary

To ensure precise communication between human developers and AI agents, `agent-spec` uses a strict vocabulary. When these terms are used in prompts or agent responses, they carry the specific meanings defined below.

---

## SDLC Artifacts

| Term | Meaning in agent-spec |
|------|------------------------|
| **Requirements** | Raw, unstructured goals or customer needs. The starting point. |
| **Tech Spec** | Feasibility assessment. Defines constraints, non-functional requirements, and tech stack choices. |
| **PRD** | Product Requirements Document. Defines *what* to build and *why*. Must include user stories, MoSCoW priorities, and acceptance criteria. Contains NO technical architecture. |
| **HLD** | High Level Design. Defines the system architecture, component boundaries, and data flow. |
| **LLD** | Low Level Design. Defines specific classes, interfaces, DB schemas, and API contracts. |

## Pipeline & Framework Concepts

| Term | Meaning in agent-spec |
|------|------------------------|
| **Gate** | A mandatory checkpoint in the development pipeline. An agent cannot proceed past a gate without satisfying its exit checklist. |
| **Skill** | An executable slash command (e.g., `/agent-spec-prd`, `/agent-spec-review`) installed in the agent's native directory that triggers a specific workflow. |
| **Rule** | An always-on behavioral constraint (e.g., "Never delete files without confirmation") defined in `AGENTS.md` or persona files. |
| **Persona** | A strict behavioral profile (e.g., `@ARCHITECT`) that the agent adopts, which carries specific rules and responsibilities. |
| **Graphify** | The indexing method that scans a codebase and produces a structured JSON/Mermaid knowledge graph of dependencies. |

## Memory & State

| Term | Meaning in agent-spec |
|------|------------------------|
| **Project Index** | A living narrative document (`PROJECT-INDEX.md`) describing the project's purpose, modules, and known debt. |
| **Knowledge Graph** | The machine-readable map of dependencies (`KNOWLEDGE-GRAPH.md`). |
| **Session Snapshot** | A point-in-time capture (`SESSION-SNAPSHOT.md`) written at the end of a work session so the next session can resume without context loss. |
| **Context Window** | The maximum amount of text the AI can process at once. Treated as a scarce resource to be budgeted. |

## Anti-Hallucination Protocol

| Term | Meaning in agent-spec |
|------|------------------------|
| **[CONFIDENCE: HIGH]** | The agent has directly read the relevant source code file during the current session. |
| **[CONFIDENCE: MEDIUM]** | The agent is relying on established framework patterns, but hasn't read the specific code in this project. |
| **[CONFIDENCE: LOW]** | The agent is inferring or guessing. Explicit human validation is required before taking action. |
| **[CONFIDENCE: UNKNOWN]** | The agent lacks the information to make a claim. Must ask a clarifying question. |
| **Pre-Change Declaration** | A mandatory summary the agent provides *before* modifying code (File, Current State, Intended State, Risk, Test). |
