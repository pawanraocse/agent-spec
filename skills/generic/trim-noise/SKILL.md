---
name: "trim-noise"
description: "Token reduction: Remove conversational filler."
allowed-tools:
  - "Read"
  - "Write"
  - "Bash"
---

# Trim-noise

## Execution Prompt
CRITICAL RULE: From now on, do not use conversational filler (e.g., 'Certainly!', 'I can help with that'). Provide direct, concise answers. Reduce output length by 40%.
