---
name: "agent-spec-verbose"
description: >-
  Turn off the terse modes. Reading and turn discipline stay on. Triggers on "normal mode", "stop terse".
---

# agent-spec-verbose

Terse mode off.

Clears whichever of `/agent-spec-raw-code` or `/agent-spec-raw-code-full` is active,
including the level `raw-code` was at.
Resume normal explanatory output: full sentences, prose or tables as the content warrants,
explanation where it earns its place.

Not a licence to pad. The standing project rules still apply — no filler, no unrequested
recaps, no "next steps" nobody asked for, and still one ask at a time rather than a
paragraph of questions. Verbose means *explain when explaining helps*, not *write more*.

## What changes vs. what stays on

| Turns off | Stays on |
|---|---|
| Word-budget caps (15–50 / 40–90 words) | `locate → read minimum → change → verify → stop` |
| Fragments-only output | Never re-read unchanged files or unrelated files |
| Suppressed tool narration | Batch independent tool calls into one turn |
| No-markdown / inline-separator rules | Read a line range, not a whole file |
| Caveman-prose compression | Prefer a targeted `Edit` to a whole-file rewrite |
| "One best next step only" constraint | Cap noisy command output (`| head -50`, `-q`) |

**The token discipline is not cleared.** Those rules govern roughly four fifths of the
bill and are worth keeping at every verbosity level — only the prose style changes here.
