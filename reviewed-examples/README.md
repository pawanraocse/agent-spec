# reviewed-examples

Governed, human-reviewed root-cause examples the `agent-spec-wf-rca` fetch step may read.
Data only; no code and no customer data.

## Jira label convention

| Label | Meaning |
|---|---|
| `rca-example` | A human confirmed the root cause; eligible for this folder |
| `rca-reviewed` | A second reviewer approved the write-up |
| `rca-do-not-use` | Wrong or disputed; never used as an example |

Only tickets with both `rca-example` and `rca-reviewed` and without `rca-do-not-use` are copied here.

## File format

One file per ticket: `<KEY>.md` with these sections, each one to three lines:
`Symptom`, `Root cause`, `Evidence` (`path:line`), `Fix summary`, `Reviewed by` (initials), `Date`.
Strip customer names, hostnames, secrets and ticket attachments before saving.
The RCA workflow reads at most two examples that match the ticket's components.
