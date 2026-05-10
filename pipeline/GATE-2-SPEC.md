# GATE 2: SPEC

> **Goal: Ensure there is a testable target before code is written. Prevent aimless drifting.**

The agent must review the requirements. If this is part of a larger SDLC, it reads the PRD. If it's a small standalone task, it must define the acceptance criteria here.

## The Checklist

- [ ] **Identify Acceptance Criteria**: What exact behavior proves this task is done? (Given/When/Then format).
- [ ] **Identify Edge Cases**: What happens if input is null? What if the network fails?
- [ ] **Identify Out-of-Scope**: Explicitly state what we are *not* doing in this task.
- [ ] **User Confirmation**: The developer must approve the criteria before the agent proceeds.

## The Output

```markdown
**GATE 2: SPEC COMPLETE**
- **Acceptance Criteria**: When a valid email is submitted, a 202 Accepted is returned and an email is queued.
- **Edge Case**: If email is invalid format, return 400 Bad Request.
- **Out of Scope**: We are not building the actual email sending worker in this task, just the queue publish.
- Please approve these criteria to proceed to GATE 3.
```
