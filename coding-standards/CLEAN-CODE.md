# Clean Code Standards

> **The `@REVIEWER` persona enforces these rules during code generation.**

## 1. Naming
- **Intention-Revealing**: Variables must describe their contents. `List<User> activeUsers` instead of `List<User> list`.
- **Pronounceable**: No `genymdhms` (generation year, month, day, hour, minute, second). Use `generationTimestamp`.
- **No Magic Numbers**: Extract raw numbers into named constants (e.g., `MAX_LOGIN_ATTEMPTS = 3` instead of checking `if (attempts > 3)`).

## 2. Functions
- **Small**: Functions should rarely exceed 20 lines.
- **Do One Thing**: If a function has sections (e.g., "Step 1: Validate", "Step 2: Save"), those sections should be extracted into separate functions.
- **Arguments**: Aim for 0-2 arguments. If a function requires 3+ arguments, they should likely be wrapped in an object/DTO.
- **No Flag Arguments**: Passing a boolean `isPremium` into a function implies it does two different things. Split it into two functions.

## 3. Comments
- **Explain WHY, not WHAT**: The code explains what is happening. The comment explains *why* the business required it to happen that way.
- **No Commented-Out Code**: Delete it. That is what Git is for.
- **No Redundant Javadocs**: Do not write `@param name the name` on a method called `setName(String name)`.

## 4. Error Handling
- **Exceptions, not Return Codes**: Throw an exception rather than returning `-1` or `null` to indicate failure.
- **Provide Context**: Exceptions must include the context of why they failed (e.g., `new UserNotFoundException("User not found with ID: " + id)`).
- **Don't Catch and Ignore**: An empty `catch` block is a critical failure.

## 5. Boundaries
- **Wrap Third-Party APIs**: Never let a third-party library's classes bleed through your application. Wrap them in your own interfaces so they can be easily swapped or mocked.
