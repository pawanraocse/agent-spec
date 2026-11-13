# algosec-agent-spec

**Cursor-only** agent framework for AlgoSec — disciplined engineering on real codebases,
with measured context discipline instead of vibe-coding.

Version **2.0.0** (see [`VERSION`](VERSION)). Forked from
[agent-spec](https://github.com/pawanraocse/agent-spec); Claude Code, Gemini, and
Antigravity surfaces are not shipped here. Commands stay `/agent-spec-*`.

**Requires:** `python3` (digest, graph, gate, hooks) and Cursor with **Skills** and
**Hooks** enabled.

Feature detail: [docs/features.md](docs/features.md).

**Planning:** [docs/MASTER-PLAN.md](docs/MASTER-PLAN.md) (strategy) · [todo-plan.md](todo-plan.md) (sequenced tasks).

---

## At a glance

| | |
|---|---|
| **Router** | `/agent-spec` reads pipeline state and hands off to one skill |
| **Graph** | Services, layers, HTTP/broker edges — query via `graphify-cli.py`, not tree walks |
| **Pipeline** | Nine gates on disk; **asymmetric tracks** (fast-track / algorithm / design / full) via `/agent-spec-sdlc` |
| **Memory** | Bounded facts + rotating `SESSION-SNAPSHOT.md`; digest on new chat |
| **Hooks** | `sessionStart` digest (~1.7 KB); `preToolUse` input discipline (fail-open) |
| **Measurement** | `agent-spec-tokens.py` on Cursor agent JSONL ([usage](#measuring-usage)) |
| **Skills** | 41 commands → `~/.cursor/skills/` via `./install.sh` |
| **Self-test** | `./bin/agent-spec-selftest.sh` — package shape, install idempotency, no Claude paths |

---

## Install

Two layers: machine-wide skills, plus a per-project harness.

### 1. Global skills (once per machine)

```bash
cd /path/to/algosec-agent-spec
chmod +x install.sh check-install.sh uninstall.sh
./install.sh
./check-install.sh
```

Copies `agent-spec-*` → `~/.cursor/skills/`, harnesses this package repo, refreshes
previously `--register`'d workspaces. **Restart Cursor or open a new chat.**

Windows (skills): `.\install.ps1` · full harness: Git Bash / WSL `./install.sh …`

### 2. Project harness (once per app repo)

Register the folder Cursor actually opened (title-bar root):

```bash
./install.sh --register "/absolute/path/of/the/folder/you/opened/in/Cursor"
./check-install.sh "/absolute/path/of/the/folder/you/opened/in/Cursor"
```

Enable **Hooks** in Cursor Settings. Confirm **Customize → Rules → agent-spec** is
**Always Apply**.

| | Global (`./install.sh`) | Per project (`--register`) |
|---|---|---|
| Lands in | `~/.cursor/skills/agent-spec-*` | `.agent-spec/`, `.cursor/rules/`, hooks, agents |
| How often | Once per machine; re-run to upgrade | Once per app repo |
| Needed for | Commands to exist | State those commands read/write |

Flags: `--skills-only` · `--lean` · `--force-reindex` · `--project-skills` · `--force` ·
`--register-here` (git root of the current folder, else the folder itself).
Registering runs `agent-spec-doctor.py`, which prints a fix command for anything broken.
Day-1 path, Windows (Git Bash/WSL), team defaults, adoption checklist and QA checklist:
[docs/QUICKSTART.md](docs/QUICKSTART.md). Verification series: [docs/PHASE1-VERIFICATION.md](docs/PHASE1-VERIFICATION.md).

**Adoption checklist:** install → register → Hooks on + Always Apply → digest ends
`doctor: OK` → `/agent-spec-onboard` once → snapshot + compact (new chat) at task boundaries.
Full checkbox list: [QUICKSTART › Adoption checklist](docs/QUICKSTART.md#adoption-checklist-paste-into-confluence).

**What lands in a registered project:** `agent-spec.mdc` (from `CURSOR.md`), hooks,
`agent-spec-search` / `agent-spec-verify` subagents, graph, gate, memory, `bin/`.

---

## Skills

Every command is prefixed `agent-spec-` so transcripts show which workflow ran.

### Daily use

| Skill | When |
|---|---|
| `/agent-spec-sdlc` | Route a feature through the right gate track |
| `/agent-spec-implement` | Declare, test-first, surgical diff, self-review |
| `/agent-spec-query-graph` | Structure without opening large files |
| `/agent-spec-raw-code-full` | Tool-traffic discipline (batch, graph, Edit, cap output) |
| `/agent-spec-investigate` | Diagnose before editing — evidence first |
| `/agent-spec-snapshot` | Append session state (end of block, ~70% context) |
| `/agent-spec-compact` | Snapshot, then **new Cursor chat** at task boundaries |

### Session boundaries

| Skill | When |
|---|---|
| `/agent-spec-onboard` | First session — writes `PROJECT-INDEX` + `CONSTITUTION` once |
| `/agent-spec-index-project` | After big moves / renames |
| `/agent-spec-remember` | Durable constraint, decision, or gotcha |
| `/agent-spec-verbose` | Turn off terse modes |

### SDLC pipeline (one gate per approval)

`/agent-spec-intent` (optional, pre-gate) → `/agent-spec-requirements` →
`/agent-spec-tech-spec` → `/agent-spec-prd` → `/agent-spec-hld` → `/agent-spec-lld` →
`/agent-spec-implement` → `/agent-spec-review` → `/agent-spec-testing` →
`/agent-spec-webapp-testing` (Playwright, under gate 7) → `/agent-spec-validation`

Gate 1's `## Complexity` block (scope × algorithm) selects **fast-track**, **algorithm**,
**design**, or **full** — see `/agent-spec-sdlc`.

### Specialists

| Skill | What |
|---|---|
| `/agent-spec` | Router when unsure |
| `/agent-spec-persona <role>` | architect, security, qa, … — Absolute Rules bind |
| `/agent-spec-review` · `-self-review` · `-solid-check` · `-debt` | Review, repair loop, SOLID, debt register |
| `/agent-spec-doc-coauthoring` | Specs and proposals with a zero-context reader check |
| `/agent-spec-prompt-audit` · `-skill-creator` · `-mcp-builder` | Audit prompts; author skills; MCP servers |

Maintainer index: [skills/README.md](skills/README.md).

---

## Token discipline (measured)

~**92%** of a long session is tool traffic; **~8%** is assistant prose. Optimizing what
enters context matters more than shortening replies.

| Lever | Before → After | Saving |
|---|---:|---:|
| `/agent-spec-compact` → new chat | 480,083 → 53,191 tok | **−88.9%** |
| Session digest (`sessionStart`) | ~30,560 B → ~1.7 KB | **−94.8%** |
| Graph query vs whole-file read | 35,966 B → 152 B | **−99.6%** |
| Batch independent tools in one turn | extra turn tax | **−100% of that turn** |

`/agent-spec-raw-code` and `-full` enforce **fit and tool discipline**, not magic savings.
Full methodology: [docs/token-efficiency.md](docs/token-efficiency.md) ·
[docs/token-checklist.md](docs/token-checklist.md) ·
[docs/token-experiments.md](docs/token-experiments.md).

### Measuring usage

Run from the **folder you opened in Cursor**. Transcripts:
`~/.cursor/projects/<slug>/agent-transcripts/`.

| Command | Purpose |
|---|---|
| `list` | Sessions for this workspace |
| `overhead --all` | Harness blocks re-sent in user turns |
| `session` | Latest session: turns, char estimates, tool share |
| `audit` | Hooks, rules, skills config (`--scan` from package clone) |

`./bin/agent-spec-tokens.py` in this clone, or `./.agent-spec/bin/agent-spec-tokens.py`
in a registered app. Account spend: Cursor **Settings → usage**. Optional legacy Claude
JSONL: `--claude` on the same commands.

---

## How a session works

Enable **Hooks** or run `./.agent-spec/bin/agent-spec-digest.py` manually.

| Piece | Role |
|---|---|
| **Digest** (`sessionStart`) | Stack, graph size, gate, last session, memory facts — do not re-read INDEX/graph for those |
| **preToolUse** | One nudge on expensive reads/diffs/rewrites, then allow retry |
| **Snapshot** | Append narrative to `SESSION-SNAPSHOT.md`; keep working in this chat |
| **Compact** | Snapshot first, then open a **new chat** (no in-thread compression) |
| **Remember** | Facts promoted into the next digest |

| Prefer | Avoid |
|---|---|
| `graphify-cli.py context --task "…"` | Walking the tree to orient |
| `grep -n` + ranged Read | Whole large files |
| `git diff --stat` first | Unfiltered diffs in chat |
| Task → `agent-spec-search` / `agent-spec-verify` | Noisy output in main thread |

### Working cases

**A — New repo:** Install + `--register` → new chat → digest → `/agent-spec-onboard` if
needed → spot-check `graphify-cli.py services` → `/agent-spec-raw-code-full`.

**B — Daily coding:** Trust digest · query graph before explore · `/agent-spec-investigate`
before implement · snapshot + compact at task boundaries.

**C — Feature (SDLC):**

```bash
./.agent-spec/bin/agent-spec-gate.py reset --feature "short-name"
```

`/agent-spec-sdlc` once per gate. Pick a track (fast-track / algorithm / design / full) or
read `## Complexity` from gate 1. `./.agent-spec/bin/agent-spec-gate.py status` for resume.

**D — Memory:** `/agent-spec-remember` for still-true constraints; `/agent-spec-snapshot`
for narrative; `/agent-spec-index-project` when architecture moved.

**E — End of session:** index if needed → snapshot → remember → compact → new chat.

More flow: [docs/QUICKSTART.md](docs/QUICKSTART.md).

---

## Upgrade

```bash
cd /path/to/algosec-agent-spec
git pull
./install.sh
```

Refreshes skills, rules, hooks, `bin/`. Preserves constitution, SDLC artifacts, memory,
graph (unless `--force-reindex`). [docs/QUICKSTART.md](docs/QUICKSTART.md).

## Coexistence

Re-install overwrites global `agent-spec-*` (**last install wins**). Avoid stacking
**algosec-lean** Always Apply with `agent-spec.mdc`. Install never touches `.env`.

## Uninstall

```bash
./uninstall.sh                             # global skills only
./uninstall.sh --unregister <workspace>    # one project harness
./uninstall.sh --full                      # skills + all registered workspaces
```

---

## Docs

| Doc | Topic |
|---|---|
| [docs/QUICKSTART.md](docs/QUICKSTART.md) | Install QA, first session |
| [docs/HLD.md](docs/HLD.md) | Architecture, components, install/rollback |
| [docs/features.md](docs/features.md) | Graph, SDLC, personas |
| [docs/token-efficiency.md](docs/token-efficiency.md) | Where tokens go |
| [docs/QUICKSTART.md](docs/QUICKSTART.md) | Paths, upgrade contract |

## Develop this package

Edit `skills/`, `CURSOR.md`, re-run `./install.sh` (and `--register` for app workspaces).
Cursor-only — no Claude harness in this tree.

---

Algosec Cursor AI
