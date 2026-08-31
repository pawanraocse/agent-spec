# Memory

Two kinds, deliberately separate.

## Facts — `.agent-spec/memory/facts/`

One fact per file, typed `constraint`, `decision`, `gotcha` or `reference`, each with a
date and a source. The `SessionStart` hook prints them all — constraints first, then by
recency, under a byte cap — so a fact recorded once is known by every later session
without anyone opening a file.

```bash
./.agent-spec/bin/agent-spec-memory.py add --type gotcha --subject "..." --source "..." "..."
./.agent-spec/bin/agent-spec-memory.py list
./.agent-spec/bin/agent-spec-memory.py search <keyword>
./.agent-spec/bin/agent-spec-memory.py prune --older-than 180 --dry-run
```

Forty facts is the cap. Bounded on purpose: memory that grows without limit becomes the
problem it was meant to solve, because past a point every session pays for facts nobody
reads. Constraints are never pruned by age.

The skill is `/agent-spec-remember`, and it says what does **not** belong here — anything
the repository already answers. A copy of something the graph knows goes stale silently.

## Narrative — `.agent-spec/SESSION-SNAPSHOT.md`

Append-only, one dated section per session: what was built, what broke, what was decided,
and what was corrected. Written by `/agent-spec-snapshot`.

Append-only is not unbounded. Past about 12 KB the file stops being loadable in full and
whatever loads it truncates, oldest first, silently. `agent-spec-memory.py rotate` moves
the older sections into `.agent-spec/memory/snapshots/`, where they are still readable on purpose.
Nothing is ever deleted.

## Context budget

See [CONTEXT-BUDGET.md](CONTEXT-BUDGET.md) for what a session is allowed to load, and
[RAG-SPEC.md](RAG-SPEC.md) for how the graph decides what is relevant.
