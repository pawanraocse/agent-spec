# GATE 6: VERIFICATION

> **Goal: Prevent hallucination debt. Ensure the system context matches the new reality. Capture session state.**

After all tasks from Gate 4 are complete and tests are passing, the agent must finalize the work session.

## The Checklist

- [ ] **Anti-Hallucination Audit**: Run the `VERIFICATION-CHECKLIST.md`. Did we hallucinate any APIs? Do the tests actually cover the edge cases?
- [ ] **Update Project Index**: Add the new components or modify the "Last Updated" timestamp in `.agent-spec/PROJECT-INDEX.md`.
- [ ] **Update Knowledge Graph**: Modify `.agent-spec/graph/knowledge-graph.json` to reflect new dependencies.
- [ ] **Write Session Snapshot**: Capture the exact state of the project in `SESSION-SNAPSHOT.md` so the next session can resume perfectly.

## The Output

```markdown
**GATE 6: VERIFICATION COMPLETE**
- Code matches acceptance criteria from Gate 2. No hallucinations detected.
- `PROJECT-INDEX.md` updated with new `PasswordResetService`.
- Knowledge Graph updated.
- `SESSION-SNAPSHOT.md` generated.

The implementation is complete. We are ready to close this session.
```
