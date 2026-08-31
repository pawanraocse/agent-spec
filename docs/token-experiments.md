# Experiment queue

One row per open question. Nothing is marked DONE without a number, and a number
without a method beside it is not evidence. Results land in
`docs/token-checklist.md` once settled.

**Rig legend:** `local` = ollama + litellm + the context recorder, free, measures prompt
bytes on the wire. `anthropic` = metered, the only rig that can answer a cost question.
`transcripts` = already-recorded sessions under `~/.claude/projects/`, free.

| # | Question | Rig | Status | Result |
|---|---|---|---|---|
| EXP-1 | What does each skill body cost per turn, on the wire? | local | **done** | `raw-code` **+1,672 B/turn**, `raw-code-full` **+2,975 B/turn** |
| EXP-2 | How much of the prompt is tool schemas rather than our own instructions? | local | **done** | tool schemas **79,541 B = 83.6%**; everything of ours 15,649 B = 16.4% |
| EXP-3 | How fast does context grow per turn in a real session? | transcripts | **done** | turn 1 32,786 → turn 367 472,178 tokens, 14.4× |
| EXP-4 | Is `/compact` better than a fresh session, once re-reading memory is counted? | transcripts + local | open | — |
| EXP-5 | Does a warm session beat resetting? | anthropic | open | — |
| EXP-6 | Does reading discipline (line ranges, capped output) pay on a long task? | anthropic | open | — |
| EXP-7 | Do cheap subagents pay on a broad sweep? | anthropic | open | — |
| EXP-8 | Does tool-output filtering / RTK move anything here? | local | open | — |
| EXP-10 | What is the tool-schema share against Anthropic, with deferral on? | anthropic | open | — |
| EXP-9 | Does restricting `--allowed-tools` shrink every prompt? | local | **done** | **No. 95,190 B either way, to the byte.** |

## EXP-4 deserves its framing fixed

The earlier advice in `docs/token-efficiency.md` — "reset, do not compact" — compares the
wrong things. A reset does not start from nothing: it re-reads `CLAUDE.md`, the skill
frontmatter, the `SessionStart` digest and whatever memory the next task needs. A compact
keeps the thread and pays once for a summary.

So the real comparison is:

```
compact:  one summary generation (output price, once)
          + a smaller context carried forward

reset:    the always-on prompt again (measured: 101 KB on the wire, turn 1)
          + re-reading whatever the task needs
          + losing anything the digest does not carry
```

Neither side of that has been measured. Until it is, "reset early" is an assertion, and
the practical point stands on its own: **compaction keeps working context that a reset
throws away.**


## EXP-1 and EXP-2, measured

One trivial one-turn prompt per arm, request body captured on the wire.

| arm | request B | system B | tool schemas B |
|---|---|---|---|
| plain (no skill) | 95,190 | 15,649 | 79,541 |
| `/agent-spec-raw-code` | 96,862 | 17,330 | 79,532 |
| `/agent-spec-raw-code-full` | 98,165 | 18,645 | 79,520 |

**EXP-1.** The skill bodies cost **+1,672 B** and **+2,975 B** per turn. The files
themselves are 1,573 B and 2,855 B, so the rest is JSON escaping. Every turn pays it
again. This is the number the earlier cost benchmarks could never resolve, because at
Anthropic's 0.1× cache-read price it disappeared into the noise.

**EXP-2 is the uncomfortable one.** Tool schemas are **83.6% of every request**.
Everything agent-spec contributes — CLAUDE.md, the output style, the digest, the skill
frontmatter and the invoked body — is 16.4%, and the part we have spent days shrinking is
under 3%.

**Caveat, and it is a real one.** These bytes were measured through a proxy, and a proxy
turns Claude Code's tool deferral off — the audit warned about exactly this. So 79,541 B
is what the prompt looks like *with every schema sent*, which overstates what Anthropic
sees when deferral is active. The **difference between arms is unaffected**: all three ran
under identical conditions, so EXP-1 stands as measured. EXP-2's share is an upper bound,
and re-measuring it against Anthropic is EXP-10.


## EXP-9: `--allowed-tools` is not a token lever

| tool set | request B |
|---|---|
| all tools (default) | 95,190 |
| `--allowed-tools "Read"` | 95,190 |

Identical to the byte. The flag gates **execution**, not what is sent. Every schema goes
over the wire whatever it is set to, so the 83.6% measured in EXP-2 cannot be reduced from
the client side this way. The only mechanism that touches it is Claude Code's own tool
deferral, which a proxy disables — which is why EXP-10 has to run against Anthropic.

## The instrument

`bin/agent-spec-wire-recorder.py` is committed because every number above depends on it
and none of them can be reproduced without it.

```bash
# ollama on the Windows host, reachable from WSL
setx OLLAMA_HOST "0.0.0.0"          # PowerShell, then restart ollama from the tray

# a proxy that speaks the Anthropic Messages API to a local model
litellm --config litellm-local.yaml --port 4001

# the recorder, between Claude Code and the proxy
./bin/agent-spec-wire-recorder.py --listen 4002 --upstream http://127.0.0.1:4001 \
                                  --log requests.jsonl

AGENT_SPEC_WIRE_LOG=requests.jsonl \
ANTHROPIC_BASE_URL=http://127.0.0.1:4002 ANTHROPIC_AUTH_TOKEN=sk-1234 \
MAX_THINKING_TOKENS=0 \
  bin/agent-spec-benchmark.sh --metric bytes --model local
```

Three settings are not optional and each cost an afternoon to find:

- **`MAX_THINKING_TOKENS=0`** — Claude Code sends extended-thinking parameters and ollama
  answers `"qwen3:8b does not support thinking"`, failing every run.
- **`num_ctx` well above 32,768** — ollama defaults to 2,048 and **truncates silently**.
  A truncated prompt loses the tool schemas, the model answers in one turn with no tools,
  and every run fails looking exactly like a bad mode. The model must also fit alongside
  that cache: qwen3:8b at 40,960 spilled to CPU and took **11m40s to answer "say ok"**.
  qwen3:4b at 32,768 answers in 4.5s on the same card.
- **The recorder itself** — Claude Code's reported `input_tokens` through a local proxy is
  a constant, 8,194, whether the prompt is 200 tokens or 9,000. It is not a measurement.
