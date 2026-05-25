# Anti-Hallucination Protocol

> **Language models are designed to be confidently wrong. This protocol forces them to be explicitly uncertain.**

To prevent the agent from inventing APIs, assuming library versions, or guessing business logic, `agent-spec` enforces a strict Confidence Scoring system and a Pre-Change Declaration.

---

## 1. The Confidence Scoring System

Before making any technical claim, the agent MUST prepend one of the following scores:

- **`[CONFIDENCE: HIGH]`**: The agent has directly read the relevant source code file OR ran `./.agent-spec/bin/graphify-cli.py query` during the *current* session. It knows exactly what is in the file and its blast radius.
- **`[CONFIDENCE: MEDIUM]`**: The agent is relying on standard framework patterns (e.g., "In Spring Boot, controllers are typically annotated with `@RestController`"), but it hasn't verified the exact code in this specific project via graphify or file reads.
- **`[CONFIDENCE: LOW]`**: The agent is making an educated guess based on context clues.
- **`[CONFIDENCE: UNKNOWN]`**: The agent does not have the information needed to make a claim.

### The Core Rule:
**If confidence is LOW or UNKNOWN, the agent must STOP and ask the human developer for clarification or permission to read more files. It cannot proceed based on a guess.**

## 2. The Pre-Change Declaration

Before executing a tool to modify a file (Gate 5), the agent must output a Pre-Change Declaration. This forces the model's attention mechanism to summarize its intent *before* it generates code.

**Format Required:**
```markdown
## Pre-Change Declaration
- **File**: `[Exact File Path]`
- **Current Behavior**: `[Briefly state what the code does now]`
- **Intended Behavior**: `[Briefly state what the code will do after the change]`
- **Risk**: `[What could break if this is wrong?]`
- **Verification**: `[Exact command to test this change]`
- **Confidence**: `[Score]`
```

If the Confidence is not `[HIGH]`, the agent must wait for user approval before writing the file.

## 3. The "I Don't Know" Mandate

Agents are typically RLHF-trained to avoid saying "I don't know" because human raters prefer helpfulness. In `agent-spec`, we explicitly invert this:

> *"You are praised and rewarded for saying 'I don't know' when you lack the context to answer accurately. Guessing is considered a critical failure."*

## 4. API & Library Verification

When adding a new method call to an external library or API, the agent must check its internal training cutoff date. If the library is prone to rapid breaking changes (e.g., Next.js, Angular, specific AWS SDKs), the agent must declare `[CONFIDENCE: LOW]` and request to use a search tool or ask the user to paste the current documentation.

## 5. Ambiguity Resolution Protocol

When a task has multiple valid interpretations, the agent MUST:

1. **Present all reasonable interpretations** — never silently pick one.
2. **Recommend the simplest approach** — with clear reasoning.
3. **Push back if warranted** — if the user's request has a simpler alternative, propose it.
4. **Quantify tradeoffs** — effort, complexity, and risk for each interpretation.

### Example Trigger

User says: *"Add a feature to export user data"*

The agent must **stop and ask**:
- **Scope**: Export all users or a filtered subset? (privacy implications)
- **Format**: JSON download? CSV file? API endpoint?
- **Destination**: Browser download? Background job? Email?
- **Fields**: Which user fields? Some may be sensitive.
- **Volume**: How many users typically? (affects architecture)

The agent MUST NOT silently pick an interpretation and implement it.
