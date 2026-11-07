---
name: "agent-spec-wf-eval"
description: >-
  Golden-ticket eval for the RCA workflow: score each RCA result strict or directional against a golden CSV and gate on the BugBot baseline. Run via /agent-spec-hub-runner.
---

# agent-spec-wf-eval

`/agent-spec-hub-runner eval` with the request `golden=evals/golden-tickets.csv baseline=<strict>/<directional>`
(percentages; default `evals/baseline.txt`; `unset` means ask the developer, never assume 0). Read-only.

Precondition: every key in the CSV has a finished `agent-spec-wf-rca` run
(`/agent-spec-hub-runner rca <KEY>`; independent keys may run in parallel chats). The `collect` step reports
missing keys and the workflow stops there rather than scoring a partial set.

```steps
- id: collect
  ai: true
  agent: agent-spec-search
  writes: []
  retries: 1
- id: judge
  needs: [collect]
  ai: true
  agent: generalPurpose
  model: deep
  writes: []
  retries: 1
- id: gate
  needs: [judge]
  ai: true
  agent: generalPurpose
  writes: []
```

## Golden CSV (`evals/golden-tickets.csv`)

Header: `key,expected_root_cause,expected_files,notes`. `expected_files` is `;`-separated paths.
One row per ticket the team has already root-caused by hand. No customer data.

## Step prompts

**collect** — Parse the CSV. For each `key`, find the newest `.agent-spec/runs/*/result.json` whose
`workflow_id` is `rca` and whose run request equals the key (`run.json` `request`), and take the `rca`
step `output`. Return JSON `{"rows": [{"key": "", "expected_root_cause": "", "expected_files": [],
"actual": {"root_cause": "", "evidence": ["path:line"]}}], "missing": ["KEY"]}`. If `missing` is not
empty, return it and flag the step failed with `--error "missing RCA runs: ..."`.

**judge** — Score each row without seeing the other rows:
- `strict`: the actual root cause names the same mechanism as expected AND cites at least one expected file.
- `directional`: same component or file area, mechanism not fully matched.
- `miss`: neither.
Return JSON `{"scores": [{"key": "", "verdict": "strict|directional|miss", "why": "<one sentence>"}]}`.
Judge on the root cause, not on how confident it sounds.

**gate** — Compute `strict% = strict/total` and `directional% = (strict+directional)/total`, rounded to
whole percents. Compare with `baseline`. Return JSON `{"total": 0, "strict_pct": 0,
"directional_pct": 0, "baseline": {"strict": 0, "directional": 0}, "pass": true,
"regressions": ["KEY"]}`. `pass` is true only when both percentages are at or above the baseline.
Answer with the verdict first, then the misses.

## Rules

- The judge never edits the CSV or the RCA output.
- A row with `confidence: LOW` in the RCA still counts; low confidence is not a free pass.
- Fewer than 5 rows: say the sample is too small to gate and report the numbers without `pass`.
