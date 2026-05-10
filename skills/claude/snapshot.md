---
name: "snapshot"
description: "Generate SESSION-SNAPSHOT.md to save current state."
allowed-tools:
  - "Read"
  - "Write"
  - "Bash"
---

# Snapshot Skill

1. Review the chat history for the current session.
2. Summarize completed tasks, modified files, and next steps.
3. Overwrite `.agent-spec/SESSION-SNAPSHOT.md` using the template format.
