---
name: "hld"
description: "Generate High Level Design and Architecture. Output to sdlc/04-HLD.md"
allowed-tools:
  - "Read"
  - "Write"
  - "Bash"
---

# Hld

## Execution Prompt
1. Adopt the @ARCHITECT persona.
2. Read 03-PRD.md and 02-TECH-SPEC.md.
3. Run `./.agent-spec/bin/graphify-cli.py stats` to get a bird's-eye view of the system architecture.
4. Define components, data flow, and API boundaries.
5. Generate a Mermaid diagram for the architecture.
6. Output to .agent-spec/sdlc/04-HLD.md.
