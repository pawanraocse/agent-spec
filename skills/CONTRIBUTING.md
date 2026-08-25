# Contributing Custom Skills

> **Extend agent-spec with your own workflows.**

If you build a workflow that makes your AI agent more effective, we want it in `agent-spec`.

## How to Submit a Skill

1. **Write it once**: `skills/claude/<name>/SKILL.md` — YAML frontmatter (`name`,
   `description`) plus a markdown body. This is the only hand-edited copy.
2. **Render the rest**: run `./bin/agent-spec-render-skills.sh`. Cursor and the generic
   agents read the same `SKILL.md` shape, so the installer copies it directly; the
   script regenerates the two flat formats (`.windsurfrules`,
   `.github/copilot-instructions.md`). Never edit those by hand — they are overwritten.
   `--check` fails if they are stale.
3. **Open a PR** against `skills/claude/`.

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
