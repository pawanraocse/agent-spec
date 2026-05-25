---
name: "implement"
description: "Trigger the 6-Gate coding pipeline based on the LLD."
allowed-tools:
  - "Read"
  - "Write"
  - "Bash"
---

# Implement Skill

1. Acknowledge implementation start.
2. Begin GATE-1-DISCOVERY.md.
3. Run `./.agent-spec/bin/graphify-cli.py query --file <target_file>` to understand the blast radius before modifying any code.
4. Do not proceed to the next gate until the current gate's checklist is complete and approved.
5. Strictly enforce Absolute Rule #9 (Surgical Changes) — modify only what is strictly required for the current task.
