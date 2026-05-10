# GATE 4: TASKS

> **Goal: Break the work into small, atomic chunks. Ensure there is a safe rollback path if a chunk fails.**

Agents fail when asked to write 500 lines of code across 8 files in a single prompt. They succeed when executing 30-minute atomic tasks.

## The Checklist

- [ ] **Atomic Breakdown**: Split the approved architecture into tasks that take no longer than 30 minutes each.
- [ ] **Dependency Ordering**: Order the tasks from leaf to root (e.g., write the DB entity first, then the repository, then the service, then the controller).
- [ ] **Rollback Plan**: State exactly how to undo the change if it fails tests.
- [ ] **Approval**: Present the task list to the developer.

## The Output

```markdown
**GATE 4: TASKS COMPLETE**

1. Create `PasswordResetToken` Entity.
   - *Rollback*: Delete file.
2. Create `TokenRepository` interface.
   - *Rollback*: Delete file.
3. Implement `PasswordResetService` logic and Unit Test.
   - *Rollback*: `git checkout src/main/.../PasswordResetService.java`
4. Update `AuthController` to expose endpoints.
   - *Rollback*: `git checkout` the controller.

Please approve task 1 to proceed to GATE 5.
```
