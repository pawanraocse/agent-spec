# Daily workflow

Back-link: [README](../README.md)

## First session

Type `/onboard`. It fills `PROJECT-INDEX.md` and `CONSTITUTION.md` from the repo and then
never runs again. Resolve any `[NEEDS CLARIFICATION]` tags it leaves — those are the
facts that would otherwise be re-guessed every session.

## Starting a feature

```bash
./.agent-spec/bin/agent-spec-gate.py reset --feature "password-reset"
```

Then `/sdlc`, once per gate. It reads the state, runs the gate that is due and stops —
`/requirements` first, and each gate names its successor rather than running it. Give
every requirement an identifier at gate 0; gate 8 traces those identifiers through every
later document, and a requirement without one cannot be traced at all.

`./.agent-spec/bin/agent-spec-gate.py status` answers "where were we" in a new session.

A change too small for a design pass skips the design gates: say "small-change mode" out
loud, run `/implement` directly, and record no gate you did not run.

You can still drive a single skill by hand, with a persona:

> *"Activate: @ARCHITECT. Run `/prd` for a password reset feature."*
>
> *"Activate: @QA. Run `/review` on `AuthService.java`."*

## Before touching code

```bash
./.agent-spec/bin/graphify-cli.py context --task "add a discount to order pricing"
```

Read what it returns and stop there. Walking the tree anyway is how a small change costs
forty thousand tokens. If the list looks wrong, the task description was vague — sharpen
it and re-run, or raise `--budget`.

On a microservice estate, `services` and `layers` are worth a look before any design
gate: they show what actually talks to what, and where the layering has already given
way.

## Managing the token budget

The default is already dense: the installer sets an `agent-spec` output style and a
`SessionStart` hook, so terse output and the project digest are in place before you type
anything. The skills below are for going further within a session.

Long chats exhaust the window and degrade reasoning.

| Skill | Effect |
|---|---|
| `/trim-noise` | Filler out, normal sentences kept. Lightest. |
| `/dense` | Tables and bullets, no paragraphs. |
| `/raw-code` | Code blocks only, nothing outside them. |
| `/verbose` | Back to normal prose. |

All three terse modes also carry reading discipline: broad searches go to a subagent,
structure questions go to the graph rather than to file reads, and commands get capped
output. That is the larger half of the saving — output style is the smaller one.

## Ending a session

1. `/index-project` — rebuild the dependency map if the architecture moved.
2. `/snapshot` — appends a dated section to `.agent-spec/SESSION-SNAPSHOT.md` with what
   was built, what broke, and what to load next time. It never overwrites; the running
   record of corrections and reversed decisions is the point.

Next session opens with *"read the session snapshot and let's resume."*
