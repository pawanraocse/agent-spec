---
name: "agent-spec-synthesize-routine"
description: >-
  Synthesize a reusable agent-spec-wf-* workflow from a repeated task pattern (Rule of 3). Requires human approval.
---

# agent-spec-synthesize-routine

Synthesize a repeated task pattern into a parameterized workflow skill (`skills/agent-spec-wf-<slug>/SKILL.md`).
Runs through the **4-Tier Defense System** against skill bloat:
1. **Rule of 3 Gate**: Requires >= 3 successful runs in `.agent-spec/experience.jsonl` (or an explicit override from developer).
2. **Hub-Runner Hierarchy**: Creates a workflow executed via `/agent-spec-hub-runner <slug>`—never a loose global skill.
3. **Proposal & Approval Gate**: Writes to `.agent-spec/skill-proposals/<slug>.md` first; copies to `skills/` only after explicit confirmation.
4. **Token Budget Cap**: Description must be <= 150 characters; prompts use structured inputs and outputs.

## Usage

`/agent-spec-synthesize-routine <task description or session_id>`

## Protocol

1. **Verify Repetition (Rule of 3 Gate)**:
   - Extract 3–5 key search terms from the requested task.
   - Count successful matching entries in `.agent-spec/experience.jsonl`:
     ```bash
     grep -i "<term>" .agent-spec/experience.jsonl | grep '"status": "success"' | wc -l
     ```
   - If count < 3:
     Stop and inform the developer:
     *"This pattern has only succeeded <N> times in experience logs. Under the Rule of 3, a routine requires at least 3 successful repetitions before graduating to a workflow. Proceed anyway with developer override? [Yes / No]"*
     Wait for confirmation before proceeding.

2. **Extract & Abstract Steps**:
   - Inspect the transcript tool calls or run events.
   - Categorize steps:
     - Read-only lookups -> `agent: agent-spec-search`
     - Shell commands -> `ai: false` (run deterministic command)
     - Deep analysis -> `agent: generalPurpose`, `model: deep`
     - MCP calls -> `agent-spec-mcp-filter.py` fetch steps
     - Human decisions -> `gate: human`
   - Abstract concrete identifiers into parameters:
     - Ticket IDs -> `<KEY>`
     - Branch names -> `<BRANCH>`
     - Paths -> `<PATH>`

3. **Format Workflow Proposal**:
   - Create proposal at `.agent-spec/skill-proposals/<slug>.md`.
   - Structure follows standard workflow format:
     ```yaml
     ---
     name: "agent-spec-wf-<slug>"
     description: "<Brief description under 150 chars>"
     ---
     
     # agent-spec-wf-<slug>
     
     Run via `/agent-spec-hub-runner <slug>`.
     
     ```steps
     - id: <step-1>
       ai: true
       ...
     ```
     
     ## Step prompts
     ...
     ```
   - Validate structure using:
     ```bash
     python3 bin/agent-spec-run.py validate .agent-spec/skill-proposals/<slug>.md
     ```

4. **Human Approval & Graduation**:
   - Present the proposal diff in chat with summary of steps.
   - Ask developer:
     *"Drafted workflow proposal `.agent-spec/skill-proposals/<slug>.md`. Graduate to `skills/agent-spec-wf-<slug>/SKILL.md`? [Yes / No]"*
   - Only copy if the developer says yes:
     ```bash
     mkdir -p skills/agent-spec-wf-<slug>
     cp .agent-spec/skill-proposals/<slug>.md skills/agent-spec-wf-<slug>/SKILL.md
     ./install.sh --register "."
     ```

## Hard Stops
- Never auto-publish into `skills/` or `~/.cursor/skills/` without explicit approval.
- Never create a standalone command skill when a workflow (`agent-spec-wf-*`) under `hub-runner` fits.
- Never write descriptions longer than 150 characters (prevents catalog token bloat).
