---
name: "debt"
description: >-
  Log technical debt to TECH-DEBT-REGISTER.md. Use for a real defect risk found outside the current task's scope.
---

# debt

A `// TODO` is debt that has been hidden, not recorded. This puts it somewhere with a
date, an owner and a cost.

## When to log rather than fix

Log it when **all** of these hold:

- Fixing it is outside the scope of the task in hand.
- It is a real defect risk, not a style preference.
- It would survive the current change — a smell in code you are about to delete is not debt.

Otherwise fix it now, or say nothing.

## What to record

Append one row per item. Never rewrite existing rows — the register is a ledger.

| Field | Rule |
|---|---|
| Date | today, absolute |
| Location | `path/to/file.ext:line` — exact, from the graph or a read, never guessed |
| Category | correctness · security · performance · test-gap · coupling · dependency |
| Description | the defect, in one sentence. Not "improve X" — what is wrong and what it causes |
| Impact | what breaks, and under what conditions. If you cannot name a trigger, it is a preference, not debt |
| Effort | S / M / L, with the reason in four words |
| Blast radius | from `./.agent-spec/bin/graphify-cli.py query --file <path>` |

## Rules

- **Evidence or nothing.** Every entry points at a line you have read. No speculative debt.
- **No duplicates.** Grep the register first; if the item is already there, update its date
  rather than adding a row.
- Security items are logged **and** raised in the chat immediately. They are not a
  backlog item you mention next quarter.
- Report the count added and nothing else.
