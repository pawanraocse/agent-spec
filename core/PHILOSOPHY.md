# The agent-spec Philosophy

> **AI agents are not junior developers to be micromanaged. They are hyper-fast compilers of structured intent.**

The `agent-spec` framework is built on a specific mental model of how humans and AI should collaborate to build software. If you understand these principles, you will understand every design choice in this framework.

---

## 1. Spec Before Code (Always)

The highest-leverage activity a human can do is write a clear, unambiguous specification. The lowest-leverage activity is trying to "vibe code" an application into existence through endless chat prompts.

- **Vibe coding** leads to hallucination, architectural drift, and technical debt.
- **Spec coding** leads to predictable, testable, and maintainable software.

In `agent-spec`, we use the **6-Gate Pipeline**. The agent is physically blocked from writing code until the specification and architecture are approved.

## 2. Memory is Non-Negotiable

Language models have no memory between sessions. If you don't explicitly feed them the state of the world, they will invent one.

- **Graphify Indexing**: We use `KNOWLEDGE-GRAPH.md` to map dependencies explicitly. Instead of the agent guessing what affects what, it reads the graph.
- **Session Snapshots**: Every working session ends by generating a `SESSION-SNAPSHOT.md`. The next session begins by loading it. Context is preserved with 100% fidelity.

## 3. Personas Create Discipline

A generic "helpful AI assistant" will try to please you, even if that means writing terrible, tightly-coupled code to get a feature out faster.

By forcing the agent into strict personas (`@ARCHITECT`, `@SECURITY`), we impose artificial constraints. The `@ARCHITECT` is instructed to *refuse* to write code if it violates SOLID principles. Discipline is achieved through persona boundaries.

## 4. Confidence or Silence

Agents are prone to hallucinating APIs, library versions, and business logic because they are trained to always provide an answer.

The **Anti-Hallucination Protocol** forces the agent to attach a `[CONFIDENCE]` score to every technical claim. If the confidence is `LOW` or `UNKNOWN`, the agent is instructed to stop and ask the developer, rather than guessing. "I don't know" is the most valuable phrase an AI can learn.

## 5. Token Budgets Matter

Context windows are large, but they are not infinite. Flooding the context window with irrelevant files dilutes the agent's attention (the "needle in a haystack" problem).

We keep the context window dense with actual signal by not loading what we do not need — the graph before the file, a line range before the file, a subagent for a broad sweep. Compressing the assistant's own prose was measured and reaches 8.2% of what accumulates; deciding what enters context reaches the other 92%.

## 6. Full SDLC Lineage

Code does not exist in a vacuum. It is the final artifact of a long chain of reasoning.
In `agent-spec`, we maintain the entire lineage in the `.agent-spec/sdlc/` directory:

`Requirements → Tech Spec → PRD → HLD → LLD → Code`

If a bug is found in the code, the agent can trace the intent all the way back to the raw requirements document to understand *why* the code was written that way.
