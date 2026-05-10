# Session Snapshot Template

> **Location**: `.agent-spec/SESSION-SNAPSHOT.md`
> This file must be generated at the end of every working session (Gate 6). It is the primary defense against AI amnesia.

---

# Session Snapshot — [YYYY-MM-DD HH:MM]

## 1. Session Summary
[A 2-3 sentence summary of what was accomplished in the session that just ended.]

## 2. Current Pipeline Gate
**Gate [N]: [GATE-NAME]**
[E.g., "Gate 4: Tasks - We broke down the architecture but haven't started implementation yet."]

## 3. Last Task Completed
[E.g., "Created the `PasswordResetToken` JPA entity and its repository."]

## 4. Files Modified
- `src/main/.../PasswordResetToken.java`
- `src/main/.../TokenRepository.java`

## 5. Known Broken State (If Any)
[E.g., "The tests for `PasswordResetService` are currently failing because we haven't mocked the `EmailAdapter` yet. Do not deploy."]

## 6. Open Items
- [ ] Implement `PasswordResetService` logic.
- [ ] Write integration test for the controller.

## 7. Next Session: Load These Files
[List the exact file paths the agent should load when the next session starts, to immediately regain context without searching.]
- `.agent-spec/sdlc/05-lld.md`
- `src/main/.../PasswordResetService.java`
- `src/test/.../PasswordResetServiceTest.java`

## 8. Decisions Pending Human Approval
- [E.g., "Do we want to use SendGrid or AWS SES for the email adapter? Waiting on developer to decide."]
