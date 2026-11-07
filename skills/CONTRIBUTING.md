# CONTRIBUTING (Cursor-only)

This package targets **Cursor** only. Do not add Claude Code harnesses, `CLAUDE.md`, or
`~/.claude` install paths.

## How to submit a skill

1. Write `skills/<name>/SKILL.md` — YAML frontmatter (`name`, `description`) plus body.
2. Nothing to render. Cursor reads `SKILL.md` directly; `./install.sh` copies to
   `~/.cursor/skills/`.
3. Open a PR against `skills/`.

## Design guidelines

- **No magic**: say what to read and write.
- **Enforce state**: durable decisions go to memory / PROJECT-INDEX / SDLC docs.
- **Fail gracefully**: stop and ask when required context is missing.

## Example

```text
# Security Scan Skill
1. Adopt the @SECURITY persona.
2. Read the currently open file.
3. Identify OWASP Top 10 vulnerabilities.
4. Output findings in a Markdown table.
5. Do NOT provide fixed code unless explicitly asked.
```
