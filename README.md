# 🚀 agent-spec
> **Stop "vibe coding." Start engineering.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Framework: Agnostic](https://img.shields.io/badge/Framework-Agnostic-success.svg)](#)
[![Agents: Claude | Cursor | Gemini | Copilot](https://img.shields.io/badge/Agents-Claude%20|%20Cursor%20|%20Gemini%20|%20Copilot-blueviolet)](#)

**agent-spec** is a framework that installs directly into your repository to turn your hallucination-prone AI coding assistant into a disciplined, context-aware software engineer.

---

## 🔥 The Superpowers (Features)

`agent-spec` doesn't just prompt your AI—it fundamentally changes how it operates by imposing a strict operating system of rules, memory, and pipelines.

### 🕸️ Graphify: Zero-Amnesia Memory
LLMs forget your architecture the moment you start a new chat. `agent-spec` solves this.
- Run `./bin/agent-spec-index.sh` to automatically scan your codebase and build a machine-readable JSON Knowledge Graph and Mermaid diagram.
- The agent reads this map to understand dependencies *before* writing code, preventing circular dependencies and context amnesia.

### 🎭 10 Expert Personas
Default AI agents are "Yes Men" that will write terrible code just to appease you quickly. We fix that with strict personas:
- `Activate: @ARCHITECT` -> Enforces SOLID principles and blocks the creation of God Objects.
- `Activate: @SECURITY` -> Assumes zero-trust. Demands parameterized queries and rejects hardcoded secrets.
- `Activate: @QA` -> Enforces Test-Driven Development (TDD). No code without a failing test first.

### 🛡️ Strict Anti-Hallucination Protocol
Agents love to guess API signatures and library versions. `agent-spec` enforces a strict `[CONFIDENCE]` scoring protocol. 
If the agent hasn't read the actual file in the current session, it is forbidden from claiming `[CONFIDENCE: HIGH]`. It is explicitly trained that saying *"I don't know, let me check the file"* is the correct answer.

### 🚦 The 6-Gate SDLC Pipeline
The agent is physically blocked from writing code until the design is proven.
`Requirements` → `Tech Spec` → `PRD` → `HLD` → `LLD` → `Code Execution`.
Every stage generates a markdown artifact, creating a perfect lineage of intent.

### 📉 Token Reduction Skills
Context windows are expensive, and large chats degrade AI reasoning logic.
- Run `/caveman` -> The agent outputs ONLY code blocks. Zero pleasantries. Zero conversational fluff.
- Run `/defluffer` -> Reduces chatty outputs by 40%.
- Run `/dense` -> Forces the agent to output only tables and bullet points.

### 🌐 Universal Agent Compatibility
When you run the init script, the framework automatically installs **60 native skills** directly into your project:
- `.claude/commands/` (for Claude Code)
- `.gemini/commands/` (for Gemini CLI)
- `.cursor/skills/` (for Cursor)
- `.agents/skills/` (for Generic/Copilot agents)

### 🚨 The Pre-Change Declaration
Tired of AI silently deleting half your file? We fixed that. Before executing a file modification, `agent-spec` forces the AI to output a **Pre-Change Declaration** stating:
1. What it will change.
2. What could break if it is wrong.
3. The exact bash command to verify the change.

### 📝 Auto-Logging Technical Debt
When the AI detects a code smell or a missing index but isn't tasked with fixing it, it doesn't just leave a `// TODO`. The `/debt` skill forces the AI to autonomously log it to a central `.agent-spec/TECH-DEBT-REGISTER.md` file.

### 🎯 Context Budgeting (Needle-in-a-Haystack Protection)
Loading 10,000 files into a 200k context window destroys AI reasoning. `agent-spec` enforces **Distance-Based Loading**. Using the Graphify map, the AI is only allowed to load the target file, its immediate imports (Distance 1), and files that depend on it (Distance -1).

### 📚 Built-in Coding Standards
Out of the box, `agent-spec` injects rigorous templates for Clean Code, SOLID Principles, Java (Spring Boot), and Angular. The agent reviews its own code against these standards *before* presenting it to you.

---

## 🛑 Why Did We Build This?

Modern AI agents are incredible at writing code, but they suffer from fatal flaws when working on real-world codebases:
1. **The "Vibe Coding" Trap**: Jumping straight to writing code without understanding the architecture, resulting in tightly-coupled spaghetti code.
2. **Amnesia**: Forgetting the decisions made in the previous chat session.
3. **The God Object**: Happily appending 1,000 lines to a single file just to satisfy a vague prompt.

`agent-spec` solves all of this locally, right inside your repo.

---

## ⚡ Quickstart

You can install `agent-spec` into **any existing project** in seconds. There are zero python or node dependencies.

```bash
# 1. Navigate to your project
cd my-awesome-project

# 2. Run the init script (downloads framework to .agent-spec/)
curl -sSL https://raw.githubusercontent.com/pawan/agent-spec/main/bin/agent-spec-init.sh | bash

# 3. Build your project's Knowledge Graph
./.agent-spec/bin/agent-spec-index.sh --graphify
```

Now, open your AI agent (Cursor, Claude Code, etc.) and type:
> *"Activate: @ARCHITECT. Run the /tech-spec skill for a new password reset feature."*

---

## 🤝 Contributing
We welcome contributions! Whether it's a new Persona, a specialized Skill (like AWS deployment or Rust standards), or a refinement to the pipeline, please open a PR. See `skills/third-party/README.md` for our curated list of community extensions.

## 📄 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
