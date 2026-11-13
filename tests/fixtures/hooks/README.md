# Hook payload fixtures

One payload per event the event spine (`hooks/cursor-event.py`) is registered for.

**Provenance: documented, not yet recorded.** Field names and shapes are copied from the
Cursor hooks reference (cursor.com/docs/hooks, "Input (all hooks)" and each event's
section) as read on 2026-11-13. Values are invented. DV-002 replaces each file with a
payload recorded from a live Cursor session:

1. In a registered workspace, start Cursor with `AGENT_SPEC_HOOK_RECORD=1` in its
   environment.
2. Run one prompt that reads a file, runs a failing shell command, delegates to a subagent
   and edits a file.
3. Copy `.agent-spec/metrics/hook-payloads/*.json` over these files, set this paragraph to
   "recorded from Cursor <version> on <date>", and note any field the docs omit (in
   particular any token count, and how a skill invocation appears).
