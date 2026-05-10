# GATE 3: ARCHITECTURE

> **Goal: Prevent code rot. Block the creation of God objects, circular dependencies, and tightly-coupled spaghetti code.**

Before any code is modified, the agent must prove the intended design respects the project's architecture. The `@ARCHITECT` persona principles apply here, even if another persona is active.

## The Checklist

- [ ] **SOLID Check**:
    - **S**: Does the new class/method have only *one* reason to change?
    - **O**: Can we extend this behavior without modifying existing code?
    - **L**: (If subclassing) Does this break parent contracts?
    - **I**: (If interface) Is it lean?
    - **D**: Are high-level modules free of low-level implementation details?
- [ ] **Dependency Graph Check**: Will this change introduce a circular dependency? 
- [ ] **New File vs Existing File**: If appending to an existing file makes it exceed 400 lines, explicitly suggest creating a new file/class instead.

## The Output

```markdown
**GATE 3: ARCHITECTURE COMPLETE**
- **SOLID Status**: Passed. `UserService` was getting too large, so we are creating a dedicated `PasswordResetService` to maintain Single Responsibility.
- **Graph Impact**: `AuthController` will now depend on `PasswordResetService`. No circular dependencies detected.
- Please confirm the architectural approach to proceed to GATE 4.
```
