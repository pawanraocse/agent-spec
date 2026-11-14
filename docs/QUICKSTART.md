# QUICKSTART — algosec-agent-spec (Cursor)

## Day 1 (target: productive in under 10 minutes)

```bash
cd /path/to/algosec-agent-spec
./install.sh                                  # 1. global skills + harness on this repo
cd /path/to/your/app && /path/to/algosec-agent-spec/install.sh --register-here   # 2. your app repo
./.agent-spec/bin/agent-spec-doctor.py        # 3. doctor: every line OK, or it prints the fix
```

Then in Cursor (new chat in the app folder):

1. **Doctor** — digest ends with `doctor: OK`. Otherwise run the printed `fix:` command.
2. **Onboard** — if the digest says `ONBOARDING NEEDED`, run `/agent-spec-onboard` once.
3. **Work** — for coding sessions, `/agent-spec-raw-code-full`. Skip the SDLC gates for small
   fixes; use `/agent-spec-sdlc` only for features (anything with a "should" or a stakeholder).
   Unsure which skill? `/agent-spec` routes.
4. **Close** — `/agent-spec-snapshot`, then `/agent-spec-compact` → **new Cursor chat**.

Enable **Hooks** in Cursor Settings and set **Customize → Rules → agent-spec = Always Apply**.

## Install

```bash
cd /path/to/algosec-agent-spec
chmod +x install.sh check-install.sh uninstall.sh
./install.sh
./check-install.sh
```

`./install.sh` copies skills to `~/.cursor/skills/` (global, like algosec-lean) and
applies the harness to this package repo. Restart Cursor or start a **new chat**.

Harness on an app workspace (rules / hooks / `.agent-spec/`):

```bash
./install.sh --register "/absolute/path/to/opened/Cursor/folder"
./install.sh --register-here          # from inside the app: git root, else the current folder
./check-install.sh "/absolute/path/to/opened/Cursor/folder"
```

Registering runs the doctor at the end and prints any fix commands.

## Windows

Full harness needs a POSIX shell. Supported paths:

- **Git Bash** (recommended): `.\install.ps1 -Register C:\path\to\app` or `-RegisterHere`.
  The script converts the path to `C:/path/to/app` before calling bash.
- **WSL**: `bash` resolves to WSL; `install.ps1` converts with `wslpath` (`/mnt/c/...`).
  Cursor must be running its hooks in the same environment as the repo.
- `hooks.json` runs `python3`. If Windows only has `python` or `py -3`, edit
  `.cursor/hooks.json` accordingly (the installer does not rewrite foreign choices).
- The graph build lock uses `fcntl` (POSIX); on native Windows it fails open (no lock, builds still work).
- Health check: `python .agent-spec\bin\agent-spec-doctor.py`.

Not provided: a native PowerShell port of the installer or git hooks.

## Keeping the graph fresh

`sessionStart` runs an incremental Graphify build and the digest reports it:

| Digest line | Meaning | Do |
|---|---|---|
| `graph: fresh` | nothing changed since the last build | nothing |
| `graph: incremental (42ms, 3 reparsed)` | rebuilt just now | nothing |
| `graph: stale (lock held …)` | another build (git hook) is running | ignore; next session is current |
| `graph: stale (timeout 3s …)` | large repo or slow disk | `./.agent-spec/bin/agent-spec-index` once; or raise `AGENT_SPEC_BUILD_TIMEOUT` |
| no `graph:` line, doctor says "graph last built N days ago" | Hooks are off or the session is a cloud agent | enable Hooks in Cursor Settings, or run `./.agent-spec/bin/agent-spec-index` |

Git hooks (`post-checkout`, `post-merge`, `post-rewrite`) re-index in the background. A
workspace registered before `post-rewrite` existed gets a doctor WARN — re-run `--register`.

## Team defaults (optional)

```bash
cp .agent-spec/templates/team.yaml .agent-spec/team.yaml   # then uncomment what applies
```

Flat `key: value`: `java_version`, `node_version`, `sdlc_track`
(`fast-track|algorithm|design|full`), `default_branch`. Valid keys appear in the digest as
`team: …`; invalid values are ignored and flagged by the doctor.

## Register the right root

Use the folder shown in Cursor's title bar. Wrong: registering the monorepo parent while
you opened a child package. Multi-root: `--register` each root that needs rules.

## Coexistence

| Situation | Guidance |
|---|---|
| Older agent-spec clone also installed | Last `./install.sh` wins for `agent-spec-*` skills |
| algosec-lean Always Apply also on | Do not stack: both ride in the prefix every turn. Set `alwaysApply: false` on one. The doctor and `agent-spec-tokens.py audit` flag it |
| Cloud agent / no hooks | Manual digest (`./.agent-spec/bin/agent-spec-digest.py`); standing rule still applies |

## Measuring the harness (post-install habit)

Overhead target: **< 5 %** of session cost. After installing (or changing rules or hooks):

```bash
./.agent-spec/bin/agent-spec-tokens.py list                      # pick a before and an after transcript
./.agent-spec/bin/agent-spec-tokens.py compare <before> <after>  # side by side, weighted
./.agent-spec/bin/agent-spec-tokens.py overhead --all            # what the harness re-sends each turn
./.agent-spec/bin/agent-spec-tokens.py audit --scan .            # config defects; exit 1 on findings
```

Optional CI step: `python3 .agent-spec/bin/agent-spec-tokens.py audit --scan .` fails the
job when a hook is duplicated or missing, rules stack, or memory is oversized.
Methodology: [token-efficiency.md](token-efficiency.md).

Context check: when Cursor's own counter shows a chat has grown past the point where a new
chat pays for itself in under five model calls, the `stop` hook suggests `/agent-spec-compact`
once, with the numbers. Coach › Context budget ranks every chat the same way. Turn the
suggestion off with `export AGENT_SPEC_CONTEXT_NUDGE=0`.

Optional guard rail outside Cursor: `export AGENT_SPEC_READ_HARD_CAP_KB=40` denies rangeless
Reads of 40 KB or more every time (default off: one nudge, retry goes through). Under Cursor
the Read and Write nudges and the hard cap do not apply: Cursor strips a Read's offset/limit
and reports a StrReplace as a Write of the whole file before the hook runs, so the hook
cannot tell them apart. Whole-file reads are instead measured after the fact from
`tool_output.content_length` (Coach › Whole-file reads). To see what Cursor
actually sends the hook: `AGENT_SPEC_HOOK_DEBUG=1` (or, without restarting Cursor,
`touch .agent-spec/.hook-debug`) writes payload key names, value types and the hook's
decision (never strings) to `$TMPDIR/algosec-agent-spec-hook-debug.jsonl`.

## Session receipts and ROI (optional)

Each Cursor session writes `.agent-spec/metrics/receipts/<session>.json` (tokens, tool
calls, graph queries, whole-file reads over 20 KB, pipeline gate, facts injected) and a
row in `.agent-spec/metrics/daily.jsonl`. The `sessionEnd` and `stop` hooks do this;
nothing is uploaded and no transcript text is stored. Run it by hand any time:

```bash
./.agent-spec/bin/agent-spec-receipt.py --daily        # latest session
./.agent-spec/bin/agent-spec-roi.py list               # one line per receipt
./.agent-spec/bin/agent-spec-roi.py rollup --days 7    # totals over the window
./.agent-spec/bin/agent-spec-roi.py export --csv -o roi.csv
./.agent-spec/bin/agent-spec-roi.py serve              # http://127.0.0.1:8765, loopback only
```

Cursor transcripts carry no usage data, so token counts are marked `estimated` (text
length / 4). Treat them as a trend, not a bill. The CSV feeds the Phase 2 proof pack (D-014).

## Shared team facts (optional)

Point registration at a repository of fact files (same format as `.agent-spec/memory/facts/`),
either a git URL or a local directory:

```bash
TEAM_FACTS_REPO=git@host:org/team-facts.git ./install.sh --register-here
```

Valid facts (known type, subject and body, under 2 KB, at most 40) are copied to
`.agent-spec/team-facts/`, a read-only namespace: they never count against the local fact
cap or `INDEX.md`. Facts of type `constraint` appear in the digest as `[org]` lines (500 B
cap). A local fact with the same type and subject wins. `agent-spec-memory.py lint` checks
local and team facts together. A git submodule checked out at `.agent-spec/team-facts/` is
used as-is. An unreachable repository only prints a warning; the doctor flags a set that
was never merged or was last synced more than 14 days ago. Re-run `--register` to refresh.

## Upgrade

```bash
cd /path/to/algosec-agent-spec
./install.sh --register "/path/to/workspace"   # refreshes skills + registered projects
```

Preserves constitution, SDLC artifacts, memory, graph (add `--force-reindex` to rebuild).
The doctor warns when a workspace's stamped harness version differs from the package `VERSION`.

## Uninstall

```bash
./uninstall.sh --unregister /path/to/workspace
./uninstall.sh                 # skills only
./uninstall.sh --full          # skills + all registered workspaces' our .cursor bits
```

`.agent-spec/` project history is left intact.

## Adoption checklist (paste into Confluence)

- [ ] Python 3 available (`python3 --version`)
- [ ] `./install.sh` run from the algosec-agent-spec clone; `./check-install.sh` exits 0
- [ ] App repo registered: `./install.sh --register-here` (from the app folder)
- [ ] Cursor: Hooks enabled; Rules → agent-spec = Always Apply; algosec-lean not Always Apply
- [ ] New chat shows the digest (`<agent-spec-digest>`) ending in `doctor: OK`
- [ ] `/agent-spec-onboard` run once; `.agent-spec/.onboarding-needed` gone
- [ ] Optional: `.agent-spec/team.yaml` filled in; doctor shows `team.yaml valid`
- [ ] Team habit: `/agent-spec-snapshot` then `/agent-spec-compact` (new chat) at each task boundary
- [ ] After any harness change: `agent-spec-doctor.py --strict` and one `agent-spec-tokens.py compare`

## Manual QA checklist

Full step-by-step series: [PHASE1-VERIFICATION.md](PHASE1-VERIFICATION.md).

- [ ] `./check-install.sh <workspace>` exits 0
- [ ] Customize → Rules → agent-spec = Always Apply
- [ ] New chat includes digest (or manual digest works)
- [ ] `/agent-spec-onboard` runs
- [ ] Task can start `agent-spec-search` / `agent-spec-verify`
- [ ] Outside Cursor: large rangeless Read gets one preToolUse nudge, retry succeeds
- [ ] Under Cursor: ranged and whole Reads are both allowed; `events.jsonl` marks the whole one `ranged: false`
- [ ] Re-running `--register` does not duplicate hook entries in `hooks.json`
