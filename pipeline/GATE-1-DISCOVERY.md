# GATE 1: DISCOVERY

> **Goal: Re-establish full project context and align on the persona. Prevent context loss amnesia.**

When an implementation task begins, the agent must stop and perform Discovery before doing anything else.

## The Checklist

- [ ] **Load `SESSION-SNAPSHOT.md`**: What was the last thing we were doing?
- [ ] **Load `PROJECT-INDEX.md`**: What is the overall tech stack and module structure?
- [ ] **Query Graph**: Use `./.agent-spec/bin/graphify-cli.py search <target>` to locate the exact files you need without loading the full graph.
- [ ] **Activate Persona**: Confirm which persona is active (e.g., `@ARCHITECT`, `@SECURITY-AUDITOR`).
- [ ] **Confirm Scope**: Explicitly state to the developer what files are in scope, and ask for confirmation.

## The Output

The agent must output a message summarizing its discovery:

```markdown
**GATE 1: DISCOVERY COMPLETE**
- Loaded session snapshot from [Date].
- Loaded project index. Target files: `UserService.java`, `User.java`.
- Persona: @CODE-REVIEWER active.
- Please confirm we are ready to proceed to GATE 2.
```
