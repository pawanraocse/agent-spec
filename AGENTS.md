# AGENTS.md — algosec-agent-spec (thin router)

> **Cursor-only.** Standing rules live in `CURSOR.md` → installed as
> `.cursor/rules/agent-spec.mdc`. Do not duplicate the protocol here.

## Install (when the user asks)

From the **algosec-agent-spec** clone:

```bash
./install.sh
```

Skills go to `~/.cursor/skills/` (global). Verify: `./check-install.sh`.

Optional — project harness on the opened app folder:

```bash
./install.sh --register "<absolute path of the folder opened in Cursor>"
```

After updates: new chat or restart Cursor. Enable **Hooks** in Cursor Settings if
digest/preToolUse do not fire.

## Planning (this package)

- **Strategy:** `docs/MASTER-PLAN.md`
- **Sequenced tasks:** `todo-plan.md` (only place to track slice order)

## While working in a registered project

1. Prefer the `sessionStart` digest already in context; if missing, run
   `./.agent-spec/bin/agent-spec-digest.py`.
2. Follow `.cursor/rules/agent-spec.mdc` (always apply).
3. Skills: `/agent-spec-*` from `~/.cursor/skills/` (on demand).
4. Subagents: Task → `agent-spec-search` / `agent-spec-verify` under `.cursor/agents/`.

## Coexistence

- Re-installing overwrites global `agent-spec-*` skills (**last install wins** vs older
  agent-spec clones).
- Stacking `algosec-lean.mdc` + `agent-spec.mdc` inflates always-on context; prefer one
  style layer. This package does not ship lean.

## Uninstall

```bash
./uninstall.sh                  # skills only
./uninstall.sh --unregister <ws>
./uninstall.sh --full
```

Algosec Cursor AI
