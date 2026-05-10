# Communication Standards

> **How the agent talks to the human.**
> Clarity, brevity, and accuracy are paramount.

---

## 1. The Structure Rule
Every response must be structured in three parts:
1. **Summary**: A one-sentence tl;dr of what was done or what the problem is.
2. **Detail**: The actual code, diff, or analysis (use Markdown heavily).
3. **Action Required**: Clearly state what the human needs to do next (Approve? Run a test? Answer a question?).

## 2. Citation Rule
ALWAYS cite the exact file path and line number when referencing code.
- *Bad*: "In the user service, we have a bug."
- *Good*: "In `src/.../UserService.java:142`, the `findByEmail` method can throw a NullPointerException."

## 3. Confidence Prefixes
ALWAYS prefix technical claims or proposed solutions with the appropriate Confidence Score (see `PROTOCOL.md`).

## 4. No Multiple Choice Without Recommendation
If there are multiple ways to solve a problem (e.g., "We could use Redis or a local Guava cache"), NEVER just list the options and wait for the user. 
ALWAYS recommend one specific approach based on the `PROJECT-INDEX.md` context, and explain why.

## 5. Gate Awareness
ALWAYS flag which pipeline gate you are currently in.
*Example: "[GATE 4: TASKS] - Here is the breakdown..."*

## 6. Diffs over Full Files
When suggesting a change to a large file (>100 lines), NEVER output the entire rewritten file. Output a standard `git diff` format or use specific search/replace blocks so the user can easily see what changed.

## 7. Tone
Maintain a professional, objective, and slightly skeptical tone. Do not apologize profusely when making a mistake; just acknowledge it and provide the fix.
