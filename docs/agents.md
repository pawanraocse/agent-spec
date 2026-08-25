# Agent compatibility

Back-link: [README](../README.md)

One source tree, `skills/claude/<name>/SKILL.md`, serves every agent. Cursor and the
generic agents read the same `SKILL.md` shape, so the installer copies it directly.
Windsurf and Copilot take a single flat file, rendered by
`bin/agent-spec-render-skills.sh`.

## Where things land

Machine-wide (default — every project on the box):

| Home | Contents |
|---|---|
| `~/.claude/skills/<name>/SKILL.md` | Claude Code |
| `~/.cursor/skills/<name>/SKILL.md` | Cursor |
| `C:\Users\<you>\.claude\skills\` | Claude Code launched from Windows |
| `C:\Users\<you>\.cursor\skills\` | Cursor launched from Windows |

Per project:

| Path | Contents |
|---|---|
| `.agent-spec/` | constitution, graph, SDLC artifacts, personas, standards, `bin/` |
| `.cursor/rules/agent-spec.mdc` | the standing rules, `alwaysApply: true` |
| `.windsurfrules` | every skill, flattened |
| `.github/copilot-instructions.md` | every skill, flattened |
| `CLAUDE.md` `AGENTS.md` `CURSOR.md` `GEMINI.md` `COPILOT.md` | root configs |

`--project-skills` additionally copies the skills into `.claude/skills/`,
`.cursor/skills/` and `.agents/skills/` — for team repos that want them committed.

## Why only one file under `.cursor/rules/`

Cursor loads every file in `.cursor/rules/` in every conversation. Earlier versions of
agent-spec dumped all 26 skills there, making them permanently resident context. Skills
now live in `.cursor/skills/`, which Cursor loads on demand; `.cursor/rules/` holds one
`.mdc` — the standing rules that genuinely should always apply.

## The WSL two-homes problem

Claude Code reads user-level skills from the HOME of the **process**. Inside WSL that is
`~/.claude`. Launched from the Windows app it is `C:\Users\<you>\.claude` — even when the
app has opened a `\\wsl.localhost\...` folder, because it is still a Windows process.

Syncing only one home is why skills appear in some projects and not others. `install.sh`
writes every home it finds. Override the Windows guess with `WIN_CLAUDE_HOME`.

Restart the agent afterwards: skills are enumerated at session start.

## Script naming

Repo `bin/` uses extensions (`agent-spec-index.sh`). The copies installed into a project
drop them (`.agent-spec/bin/agent-spec-index`), because there they are a CLI. The skills
call the extensionless form.
