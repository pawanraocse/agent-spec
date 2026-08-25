# Why this exists

Back-link: [README](../README.md)

Modern coding agents write good code and are terrible engineers on a real codebase:

1. **Vibe coding.** Straight to code with no grip on the architecture — tightly coupled
   spaghetti that passes a demo and fails a change request.
2. **Amnesia.** Every decision from the last chat is gone. The same explanation, the same
   files, the same tokens, every session.
3. **The God Object.** A vague prompt gets 1,000 more lines in the file that was already
   too long, because appending is the path of least resistance.

Spec-driven development is the fix, and it only works if the agent is *blocked* rather
than asked politely. agent-spec makes the design artifacts a precondition of the code,
keeps a queryable map of the architecture so context loading is bounded, and writes the
project's own rules down once so they are not re-derived every session.

All of it lives in your repo. No service, no account, no runtime dependency.
