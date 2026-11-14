# Hook payload fixtures

One payload per event the event spine (`hooks/cursor-event.py`) is registered for.

**Provenance: documented.** The files in this directory are the synthetic payloads the hook
tests assert against. Their field names and shapes come from the Cursor hooks reference
(cursor.com/docs/hooks), read on 2026-11-13, and their values are invented so the tests can
exercise redaction, token fields and truncation.

**Recorded payloads live in `recorded/`.** They come from Cursor's own hook log, which records
the full INPUT of every hook invocation, whether or not the hook could start:

```bash
python3 bin/agent-spec-platform.py hooks --fixtures tests/fixtures/hooks/recorded
```

The command masks email addresses, the local project path and the conversation and
generation ids before it writes anything. `tests/test_hook_logs.py` fails if a recorded file
leaks any of them. Once you have used Cursor in a registered workspace, a rerun refreshes the
directory. The dashboard server backfills the same log into `events.jsonl` every 60 s.

Recorded from Cursor 3.6.21 on 2026-11-13, through Remote-WSL with the Auto model:
`beforeSubmitPrompt`, `preToolUse`, `postToolUse`, `afterAgentResponse`, `stop`,
`sessionStart` and `sessionEnd`. Fields the docs omit:

- `afterAgentResponse` carries `input_tokens`, `output_tokens`, `cache_read_tokens` and
  `cache_write_tokens`. These are measured counts, and the event spine now keeps them.
- `postToolUse` reports `duration` as a decimal string in ms (for example `"2438.671"`), not
  `duration_ms`.
- Every event carries `session_id` (equal to `conversation_id`). `beforeSubmitPrompt` adds
  `composer_mode` and `attachments[]` of `{type, file_path}`. `sessionEnd` adds `reason`,
  `final_status` and `is_background_agent`.
- `model_id` and `model_params` are absent. `model` is `"default"` when Auto is selected.

`afterFileEdit` and `postToolUseFailure` were recorded from the Cursor CLI
(`cursor-agent 2026.11.11-b912975`, `--print --model auto`) with `AGENT_SPEC_HOOK_RECORD=1`,
then scrubbed with `hook_logs.scrub(..., fixture=True)`. `postToolUseFailure` adds
`failure_type`, `is_interrupt` and `duration`. `afterFileEdit` carries
`edits[] {old_string, new_string}`.

The CLI in `--print` mode fires `postToolUse`, `postToolUseFailure` and `afterFileEdit`. It does
not fire `beforeSubmitPrompt`, `afterAgentResponse`, `stop`, `subagentStart` or
`subagentStop`, even when a subagent runs. A subagent shows up only as a `postToolUse` with
`tool_name: Task` and `subagent_type`.

`subagentStart`, `subagentStop`, `afterFileEdit` and `postToolUseFailure` were recorded from
the Cursor IDE (3.30.8, Remote-WSL) by `/agent-spec-hook-probe` on 2026-11-13:

- `subagent_id` is the Task tool-call id (`call-...\nfc_..._0`), not a conversation id.
  `subagentStop` adds `child_conversation_id`, `duration_ms`, `tool_call_count`,
  `message_count`, `loop_count` and `agent_transcript_path`.
- The subagent's own tool calls arrive under `child_conversation_id` and carry
  `parent_tool_call_id` equal to the parent's `subagent_id`; the trace builder nests them by it.
- `sessionEnd` on `window_close` fails with `Error: MainThreadShellExec not initialized`:
  Cursor closes its shell first. The `stop` hook writes the same receipt, so nothing is lost.

Not yet recorded: `preCompact` (it needs a chat long enough to compact).
`agent-spec-platform.py hooks` prints which registered events have not fired yet.
