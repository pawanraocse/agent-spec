#!/usr/bin/env python3
import os
import json

# Define the 15 skills
skills = [
    {
        "name": "requirements",
        "description": "Elicit and structure raw customer needs. Output to sdlc/01-REQUIREMENTS.md",
        "content": "1. Adopt the @WRITER persona.\n2. Read the user's raw input.\n3. Structure it according to .agent-spec/sdlc/01-REQUIREMENTS.md.\n4. Use [NEEDS CLARIFICATION] tags for missing information.\n5. Ask the user questions to fill the gaps."
    },
    {
        "name": "tech-spec",
        "description": "Define feasibility, tech stack, and NFRs. Output to sdlc/02-TECH-SPEC.md",
        "content": "1. Adopt the @ARCHITECT persona.\n2. Read sdlc/01-REQUIREMENTS.md and PROJECT-INDEX.md.\n3. Assess technical feasibility and define NFRs.\n4. Output to .agent-spec/sdlc/02-TECH-SPEC.md following the template."
    },
    {
        "name": "prd",
        "description": "Generate Product Requirements Document with MoSCoW and Validation. Output to sdlc/03-PRD.md",
        "content": "1. Adopt the @WRITER persona.\n2. Read 01-REQUIREMENTS.md and 02-TECH-SPEC.md.\n3. Follow the iterative Discover -> Document -> Review cycle.\n4. Apply MoSCoW prioritization to all features.\n5. Run the 14-point Validation Checklist defined in sdlc/03-PRD.md.\n6. Output to .agent-spec/sdlc/03-PRD.md and provide a Status Report in chat."
    },
    {
        "name": "hld",
        "description": "Generate High Level Design and Architecture. Output to sdlc/04-HLD.md",
        "content": "1. Adopt the @ARCHITECT persona.\n2. Read 03-PRD.md, 02-TECH-SPEC.md, and KNOWLEDGE-GRAPH.md.\n3. Define components, data flow, and API boundaries.\n4. Generate a Mermaid diagram for the architecture.\n5. Output to .agent-spec/sdlc/04-HLD.md."
    },
    {
        "name": "lld",
        "description": "Generate Low Level Design (Classes, DB Schemas, API Contracts). Output to sdlc/05-LLD.md",
        "content": "1. Adopt the @ARCHITECT persona.\n2. Read 04-HLD.md and KNOWLEDGE-GRAPH.md.\n3. Define exact class structures, DB tables, and JSON payloads.\n4. Verify SOLID principles.\n5. Output to .agent-spec/sdlc/05-LLD.md."
    },
    {
        "name": "implement",
        "description": "Trigger the 6-Gate coding pipeline based on the LLD.",
        "content": "1. Acknowledge implementation start.\n2. Begin GATE-1-DISCOVERY.md.\n3. Do not proceed to the next gate until the current gate's checklist is complete and approved."
    },
    {
        "name": "review",
        "description": "Deep skeptical code review.",
        "content": "1. Adopt the @REVIEWER persona.\n2. Review the specified files against coding-standards/CLEAN-CODE.md.\n3. Identify logic flaws, style violations, and missing tests.\n4. Output findings using [BLOCKER], [MINOR], and [NIT] tags."
    },
    {
        "name": "solid-check",
        "description": "Audit a file specifically for SOLID principle violations.",
        "content": "1. Adopt the @ARCHITECT persona.\n2. Read the specified file.\n3. Audit against the 5 principles in coding-standards/SOLID-PRINCIPLES.md.\n4. If a violation is found, suggest a refactor."
    },
    {
        "name": "index-project",
        "description": "Run Graphify to build or update the KNOWLEDGE-GRAPH.md",
        "content": "1. Run the `bin/agent-spec-index.sh` script.\n2. If unable to run scripts, manually scan the `src/` directory and update `.agent-spec/graph/knowledge-graph.json` and `KNOWLEDGE-GRAPH.md`."
    },
    {
        "name": "snapshot",
        "description": "Generate SESSION-SNAPSHOT.md to save current state.",
        "content": "1. Review the chat history for the current session.\n2. Summarize completed tasks, modified files, and next steps.\n3. Overwrite `.agent-spec/SESSION-SNAPSHOT.md` using the template format."
    },
    {
        "name": "debt",
        "description": "Analyze code and log technical debt.",
        "content": "1. Adopt the @REFACTOR persona.\n2. Analyze the specified code for smells or debt.\n3. Append a new entry to the Active Technical Debt table in `.agent-spec/TECH-DEBT-REGISTER.md`."
    },
    {
        "name": "raw-code",
        "description": "Token reduction: Minimal output. Code only.",
        "content": "CRITICAL RULE: From now on, output ONLY code blocks. No pleasantries. No explanations. No markdown outside of the code block. If I ask a question, answer in 5 words or less."
    },
    {
        "name": "trim-noise",
        "description": "Token reduction: Remove conversational filler.",
        "content": "CRITICAL RULE: From now on, do not use conversational filler (e.g., 'Certainly!', 'I can help with that'). Provide direct, concise answers. Reduce output length by 40%."
    },
    {
        "name": "dense",
        "description": "Token reduction: Maximum information density.",
        "content": "CRITICAL RULE: From now on, format all outputs as highly dense tables or bullet point lists. Use abbreviations where obvious. Prioritize data density over readability."
    },
    {
        "name": "verbose",
        "description": "Restore default chatty behavior.",
        "content": "CRITICAL RULE: You may resume normal, helpful, explanatory conversational output. Token reduction mode is disabled."
    }
]

# Directories
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLAUDE_DIR = os.path.join(PROJECT_ROOT, "skills", "claude")
GEMINI_DIR = os.path.join(PROJECT_ROOT, "skills", "gemini")
CURSOR_DIR = os.path.join(PROJECT_ROOT, "skills", "cursor")
GENERIC_DIR = os.path.join(PROJECT_ROOT, "skills", "generic")

for d in [CLAUDE_DIR, GEMINI_DIR, CURSOR_DIR, GENERIC_DIR]:
    os.makedirs(d, exist_ok=True)

# Generate Claude Skills (.md with YAML frontmatter)
for skill in skills:
    content = f"""---
name: {skill['name']}
description: {skill['description']}
---

# {skill['name'].capitalize()} Skill

{skill['content']}
"""
    with open(os.path.join(CLAUDE_DIR, f"{skill['name']}.md"), "w") as f:
        f.write(content)

# Generate Gemini Skills (.toml)
for skill in skills:
    content = f"""[command]
name = "{skill['name']}"
description = "{skill['description']}"

[prompt]
text = \"\"\"
{skill['content']}
\"\"\"
"""
    with open(os.path.join(GEMINI_DIR, f"{skill['name']}.toml"), "w") as f:
        f.write(content)

# Generate Cursor Skills (.md)
for skill in skills:
    content = f"""# Cursor Skill: {skill['name']}

**Description**: {skill['description']}

## Instructions for Cursor
{skill['content']}
"""
    with open(os.path.join(CURSOR_DIR, f"{skill['name']}.md"), "w") as f:
        f.write(content)

# Generate Generic Skills (Directory with SKILL.md)
for skill in skills:
    skill_dir = os.path.join(GENERIC_DIR, skill['name'])
    os.makedirs(skill_dir, exist_ok=True)
    content = f"""---
name: {skill['name']}
description: {skill['description']}
allowed-tools:
  - "Read"
  - "Write"
  - "Bash"
---

# {skill['name'].capitalize()}

## Execution Prompt
{skill['content']}
"""
    with open(os.path.join(skill_dir, "SKILL.md"), "w") as f:
        f.write(content)

print("Generated 60 skill files successfully.")
