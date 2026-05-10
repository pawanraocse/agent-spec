# The Full AI-SDLC Pipeline

> **Software Development Life Cycle for AI Agents.**
> Never jump straight from a vague idea to writing code.

Code generation is the *easiest* part for modern LLMs. Reasoning about architecture and intent is the hardest. `agent-spec` enforces a strict, multi-stage pipeline to force the AI to do the reasoning *before* it touches source code.

---

## The 6 SDLC Stages

1. **[01-REQUIREMENTS](01-REQUIREMENTS.md)**: Raw idea → Structured requirements.
2. **[02-TECH-SPEC](02-TECH-SPEC.md)**: Feasibility, constraints, and tech stack choices.
3. **[03-PRD](03-PRD.md)**: Product Requirements Document (WHAT and WHY).
4. **[04-HLD](04-HLD.md)**: High Level Design (System architecture).
5. **[05-LLD](05-LLD.md)**: Low Level Design (Class structures, schemas).
6. **[06-IMPLEMENTATION](06-IMPLEMENTATION.md)**: The 6-Gate coding execution.

---

## How It Works

This directory (`.agent-spec/sdlc/`) stores the output of each stage.

When you trigger a skill (e.g., `/prd`), the agent will:
1. Read the outputs of the previous stages (Requirements, Tech Spec).
2. Generate the artifact for the current stage (PRD).
3. Save it to `.agent-spec/sdlc/03-prd.md`.

This creates a **lineage of intent**. If the agent is implementing code (Stage 6) and gets confused about a business rule, it can read the PRD (Stage 3) to regain context.

## Iterative Cycle

Documents are not carved in stone. If during LLD (Stage 5) you discover that a feature is too expensive to build, you can ask the agent to go back and update the PRD (Stage 3) to descope it, and then regenerate the HLD and LLD.

Always maintain the chain of documents so they reflect reality.
