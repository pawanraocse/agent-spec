# Project Skills & Instructions

## /requirements
**Description**: Elicit and structure raw customer needs. Output to sdlc/01-REQUIREMENTS.md
1. Adopt the @WRITER persona.
2. Read the user's raw input.
3. Structure it according to .agent-spec/sdlc/01-REQUIREMENTS.md.
4. Use [NEEDS CLARIFICATION] tags for missing information.
5. Ask the user questions to fill the gaps.

## /tech-spec
**Description**: Define feasibility, tech stack, and NFRs. Output to sdlc/02-TECH-SPEC.md
1. Adopt the @ARCHITECT persona.
2. Read sdlc/01-REQUIREMENTS.md and PROJECT-INDEX.md.
3. Assess technical feasibility and define NFRs.
4. Output to .agent-spec/sdlc/02-TECH-SPEC.md following the template.

## /prd
**Description**: Generate Product Requirements Document with MoSCoW and Validation. Output to sdlc/03-PRD.md
1. Adopt the @WRITER persona.
2. Read 01-REQUIREMENTS.md and 02-TECH-SPEC.md.
3. Follow the iterative Discover -> Document -> Review cycle.
4. Apply MoSCoW prioritization to all features.
5. Run the 14-point Validation Checklist defined in sdlc/03-PRD.md.
6. Output to .agent-spec/sdlc/03-PRD.md and provide a Status Report in chat.

## /hld
**Description**: Generate High Level Design and Architecture. Output to sdlc/04-HLD.md
1. Adopt the @ARCHITECT persona.
2. Read 03-PRD.md and 02-TECH-SPEC.md.
3. Run `./.agent-spec/bin/graphify-cli.py stats` to get a bird's-eye view of the system architecture.
4. Define components, data flow, and API boundaries.
5. Generate a Mermaid diagram for the architecture.
6. Output to .agent-spec/sdlc/04-HLD.md.

## /lld
**Description**: Generate Low Level Design (Classes, DB Schemas, API Contracts). Output to sdlc/05-LLD.md
1. Adopt the @ARCHITECT persona.
2. Read 04-HLD.md.
3. Run `./.agent-spec/bin/graphify-cli.py search <domain>` to explore existing related classes.
4. Define exact class structures, DB tables, and JSON payloads.
5. Verify SOLID principles AND apply the Simplicity First standard (coding-standards/SIMPLICITY-FIRST.md) to prevent over-engineering.
6. Output to .agent-spec/sdlc/05-LLD.md.

## /implement
**Description**: Trigger the 6-Gate coding pipeline based on the LLD.
1. Acknowledge implementation start.
2. Begin GATE-1-DISCOVERY.md.
3. Run `./.agent-spec/bin/graphify-cli.py query --file <target_file>` to understand the blast radius before modifying any code.
4. Do not proceed to the next gate until the current gate's checklist is complete and approved.
5. Strictly enforce Absolute Rule #9 (Surgical Changes) — modify only what is strictly required for the current task.

## /review
**Description**: Deep skeptical code review.
1. Adopt the @REVIEWER persona.
2. Run `./.agent-spec/bin/graphify-cli.py query --file <target_file>` to understand what depends on the file being reviewed.
3. Review the specified files against coding-standards/CLEAN-CODE.md AND coding-standards/SIMPLICITY-FIRST.md.
4. Identify logic flaws, style violations, and missing tests.
5. Output findings using [BLOCKER], [MINOR], and [NIT] tags.

## /solid-check
**Description**: Audit a file specifically for SOLID principle violations.
1. Adopt the @ARCHITECT persona.
2. Read the specified file.
3. Audit against the 5 principles in coding-standards/SOLID-PRINCIPLES.md.
4. If a violation is found, suggest a refactor.

## /index-project
**Description**: Run Graphify to build or update the KNOWLEDGE-GRAPH.md
1. Run the `bin/agent-spec-index.sh` script.
2. If unable to run scripts, manually scan the `src/` directory and update `.agent-spec/graph/knowledge-graph.json` and `KNOWLEDGE-GRAPH.md`.

## /query-graph
**Description**: Run the Graphify CLI to query the architecture instead of loading the whole graph.
1. Run `./.agent-spec/bin/graphify-cli.py --help` to see available commands.
2. Use `query --file <path>` to see file imports and blast radius.
3. Use `search <keyword>` to find domain components.
4. Use `stats` for an overview.

## /snapshot
**Description**: Generate SESSION-SNAPSHOT.md to save current state.
1. Review the chat history for the current session.
2. Summarize completed tasks, modified files, and next steps.
3. Overwrite `.agent-spec/SESSION-SNAPSHOT.md` using the template format.

## /debt
**Description**: Analyze code and log technical debt.
1. Adopt the @REFACTOR persona.
2. Analyze the specified code for smells or debt.
3. Append a new entry to the Active Technical Debt table in `.agent-spec/TECH-DEBT-REGISTER.md`.

## /raw-code
**Description**: Token reduction: Minimal output. Code only.
CRITICAL RULE: From now on, output ONLY code blocks. No pleasantries. No explanations. No markdown outside of the code block. If I ask a question, answer in 5 words or less.

## /trim-noise
**Description**: Token reduction: Remove conversational filler.
CRITICAL RULE: From now on, do not use conversational filler (e.g., 'Certainly!', 'I can help with that'). Provide direct, concise answers. Reduce output length by 40%.

## /dense
**Description**: Token reduction: Maximum information density.
CRITICAL RULE: From now on, format all outputs as highly dense tables or bullet point lists. Use abbreviations where obvious. Prioritize data density over readability.

## /verbose
**Description**: Restore default chatty behavior.
CRITICAL RULE: You may resume normal, helpful, explanatory conversational output. Token reduction mode is disabled.

## /architect
**Description**: Switch mindset to @ARCHITECT (Principal Software Architect)
1. Adopt the @ARCHITECT persona mindset.
2. Read your full persona specification from .agent-spec/personas/ARCHITECT.md.
3. Acknowledge the mindset switch and wait for instructions.

## /security
**Description**: Switch mindset to @SECURITY (Security Auditor)
1. Adopt the @SECURITY persona mindset.
2. Read your full persona specification from .agent-spec/personas/SECURITY.md.
3. Acknowledge the mindset switch and wait for instructions.

## /perf
**Description**: Switch mindset to @PERF (Performance Engineer)
1. Adopt the @PERF persona mindset.
2. Read your full persona specification from .agent-spec/personas/PERF.md.
3. Acknowledge the mindset switch and wait for instructions.

## /qa
**Description**: Switch mindset to @QA (QA Engineer)
1. Adopt the @QA persona mindset.
2. Read your full persona specification from .agent-spec/personas/QA.md.
3. Acknowledge the mindset switch and wait for instructions.

## /reviewer
**Description**: Switch mindset to @REVIEWER (Code Reviewer)
1. Adopt the @REVIEWER persona mindset.
2. Read your full persona specification from .agent-spec/personas/REVIEWER.md.
3. Acknowledge the mindset switch and wait for instructions.

## /writer
**Description**: Switch mindset to @WRITER (Technical Writer)
1. Adopt the @WRITER persona mindset.
2. Read your full persona specification from .agent-spec/personas/WRITER.md.
3. Acknowledge the mindset switch and wait for instructions.

## /refactor
**Description**: Switch mindset to @REFACTOR (Refactor Specialist)
1. Adopt the @REFACTOR persona mindset.
2. Read your full persona specification from .agent-spec/personas/REFACTOR.md.
3. Acknowledge the mindset switch and wait for instructions.

## /api
**Description**: Switch mindset to @API (API Designer)
1. Adopt the @API persona mindset.
2. Read your full persona specification from .agent-spec/personas/API.md.
3. Acknowledge the mindset switch and wait for instructions.

## /data
**Description**: Switch mindset to @DATA (Data Engineer)
1. Adopt the @DATA persona mindset.
2. Read your full persona specification from .agent-spec/personas/DATA.md.
3. Acknowledge the mindset switch and wait for instructions.

## /devops
**Description**: Switch mindset to @DEVOPS (DevOps Engineer)
1. Adopt the @DEVOPS persona mindset.
2. Read your full persona specification from .agent-spec/personas/DEVOPS.md.
3. Acknowledge the mindset switch and wait for instructions.

