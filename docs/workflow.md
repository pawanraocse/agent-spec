# Daily workflow

Back-link: [README](../README.md)

## First session

Type `/onboard`. It fills `PROJECT-INDEX.md` and `CONSTITUTION.md` from the repo and then
never runs again. Resolve any `[NEEDS CLARIFICATION]` tags it leaves — those are the
facts that would otherwise be re-guessed every session.

## Starting a feature

Invoke a persona and a pipeline skill rather than describing the outcome:

> *"Activate: @ARCHITECT. Run `/prd` for a password reset feature."*
>
> *"Activate: @QA. Run `/review` on `AuthService.java`."*

## Managing the token budget

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
