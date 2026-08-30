# Anti-Patterns

When collaborating with AI agents, certain approaches consistently lead to failure, technical debt, and frustration. `agent-spec` is designed specifically to prevent these anti-patterns.

---

## 1. The "Vibe Coding" Anti-Pattern

**The Pattern**: Providing a vague, one-sentence prompt ("build a login page") and letting the agent write code immediately. Reacting to the output with iterative complaints ("make it blue", "it's not connecting to the DB").

**Why it fails**: The agent has no architectural constraints, no data contracts, and no acceptance criteria. It will write tightly-coupled, untestable "spaghetti code" because that is the fastest way to satisfy the immediate prompt.

**The agent-spec Fix**: The 6-Gate Pipeline. The agent is forbidden from writing code until Gate 2 (Spec) and Gate 3 (Architecture) are complete and approved.

## 2. The "Amnesia" Anti-Pattern

**The Pattern**: Starting a new chat session and saying "continue working on the payment feature."

**Why it fails**: The agent has a blank context window. It doesn't remember the previous session, the architectural decisions made, or the specific library versions in use. It will hallucinate a different reality and write code that breaks the existing implementation.

**The agent-spec Fix**: `SESSION-SNAPSHOT.md`. Every session ends by writing a state file. Every new session begins by reading it.

## 3. The "Silent Failure" Anti-Pattern

**The Pattern**: The agent assumes a library version (e.g., assuming React Router v5 when you use v6) or assumes an API payload structure without checking the source code. It writes the code confidently, and it fails at runtime.

**Why it fails**: LLMs are designed to predict the most likely next token, not to verify facts. They default to confidence, even when wrong.

**The agent-spec Fix**: The Anti-Hallucination Protocol. The agent must attach a `[CONFIDENCE]` score to technical claims. If it hasn't read the file in the current session, it cannot claim HIGH confidence.

## 4. The "God Object" Anti-Pattern

**The Pattern**: Asking the agent to "add a feature" to an existing class. Over several sessions, the agent keeps appending methods to the same file, turning a simple `UserService` into a 2,000-line God Object.

**Why it fails**: Agents naturally prefer modifying existing files over creating new ones because it requires less context reasoning. They will happily violate the Single Responsibility Principle (SRP) to fulfill a prompt.

**The agent-spec Fix**: The `@ARCHITECT` persona and the SOLID Gate. Before writing code, the agent must explicitly verify that the change does not violate SRP or Open/Closed principles.

## 5. The "Context Flood" Anti-Pattern

**The Pattern**: Pasting 20 large files into the prompt "just in case" the agent needs them.

**Why it fails**: "Needle in a haystack" degradation. When the context window is flooded with irrelevant data, the agent's attention mechanism gets diluted. It will miss critical instructions and generate lower-quality logic.

**The agent-spec Fix**: Token-reduction skills (`/caveman`, `/agent-spec-dense`) and Graphify memory. The agent queries `KNOWLEDGE-GRAPH.md` to find *exactly* which files it needs, rather than loading everything.

## 6. The "Yes Man" Anti-Pattern

**The Pattern**: The human suggests a terrible architectural decision ("just save the user passwords in plain text for now to save time"). The agent says "Certainly! Here is the code."

**Why it fails**: Most base models are heavily RLHF-tuned to be helpful and compliant. They will rarely push back against bad ideas unless explicitly instructed to do so.

**The agent-spec Fix**: Strict Persona Rules. The `@SECURITY` persona is given an *Absolute Rule* to refuse implementation of insecure patterns, forcing a conversation about tradeoffs.
