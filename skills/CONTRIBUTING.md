# Contributing Custom Skills

> **Extend agent-spec with your own workflows.**

If you build a workflow that makes your AI agent more effective, we want it in `agent-spec`.

## How to Submit a Skill

1. **Define the Skill**: Create a markdown file describing the prompt, inputs, and expected outputs.
2. **Translate it**: Provide versions for Claude (YAML frontmatter), Gemini (TOML), and Generic (Markdown).
3. **Open a PR**: Submit it to the `skills/` directory of this repository.

## Skill Design Guidelines

When designing a new skill, adhere to the `agent-spec` philosophy:

- **No Magic**: Skills should explicitly tell the agent what to read and what to write.
- **Enforce State**: If a skill generates a decision, it must instruct the agent to log that decision in `PROJECT-INDEX.md` or a similar memory file.
- **Fail Gracefully**: If the skill requires information that is missing, the prompt must instruct the agent to stop and ask the user, rather than hallucinating the missing data.

## Example: Building a `/security-scan` Skill

A good skill prompt looks like this:

```text
# Security Scan Skill
1. Adopt the @SECURITY persona.
2. Read the currently open file.
3. Identify OWASP Top 10 vulnerabilities.
4. Output findings in a Markdown table.
5. Do NOT provide fixed code unless explicitly asked.
```
