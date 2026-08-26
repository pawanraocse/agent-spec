# Agent compatibility

Back-link: [README](../README.md)

One source tree, `skills/claude/<name>/SKILL.md`, serves every agent. Claude Code, Cursor
and the generic agents (Antigravity, Gemini) all read the same `SKILL.md` shape, so the
installer copies it directly. There are no translations and nothing to regenerate.

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
| `.agents/skills/<name>/SKILL.md` | Antigravity and other generic agents (no user-level home) |
| `CLAUDE.md` `AGENTS.md` `CURSOR.md` `GEMINI.md` | root configs |

`--project-skills` additionally copies the skills into `.claude/skills/` and
`.cursor/skills/` — for team repos that want them committed rather than relying on each
machine's install.

## Why Windsurf and Copilot are not supported

They were, until it turned out the support was actively harmful. Both read a single
always-on file, whose entire content sits in context on every turn, and the framework
inlined all 29 skill bodies into it — roughly 15,000 tokens per turn to carry skills of
which a turn uses at most one. Neither file carried the standing rules.

Rather than maintain a second, always-on shape of every skill for agents nobody here
uses, the two formats were dropped. Claude, Cursor and the generic agents all load skills
on demand, which is the behaviour the framework is designed around.

## Why only one file under `.cursor/rules/`

Cursor loads every file in `.cursor/rules/` in every conversation. Earlier versions of
agent-spec dumped every skill there, making them permanently resident context. Skills
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
