# Stage 9: Validation

> **Skill**: `/validation`
> **Input**: `07-TEST-REPORT.md` and `01-REQUIREMENTS.md`
> **Output**: `.agent-spec/sdlc/08-VALIDATION.md`

## The Goal

The only stage that looks all the way back to the first. Every other gate checks its own
document against the one immediately before it, which is exactly how a requirement
disappears: each handoff is locally consistent and the chain still drops something.

## What the gate covers

Start mechanically, because prose is easy to fool and a grep is not:

```bash
./.agent-spec/bin/agent-spec-gate.py trace
```

Then one verdict per requirement, each with evidence:

| Verdict | Means | Evidence required |
|---|---|---|
| **PASS** | implemented and a test proves it | the test name |
| **FAIL** | implemented wrongly, or not at all | what is wrong, with `file:line` |
| **NOT-TESTED** | implemented, nothing proves it | where the code is, why no test |
| **DEFERRED** | consciously out of scope | who decided, and where it is recorded |

There is no fifth verdict and no partial credit. Deferred means someone decided; dropped
means nobody noticed — conflating them destroys the only signal this stage produces.

## Exit criteria

`SHIP` or `DO NOT SHIP`, with the reason. One FAIL is DO NOT SHIP; a user may overrule
that, and the overrule goes in the document under their name.

```bash
./.agent-spec/bin/agent-spec-gate.py set 8
```
