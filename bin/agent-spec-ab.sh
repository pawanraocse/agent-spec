#!/usr/bin/env bash
# =============================================================================
# agent-spec-ab.sh — run an honest A/B between two modes, and report the delta
#
# The framework must not claim a saving it has not counted, and a saving can only
# be counted by giving two fresh sessions the same task and comparing the bill.
#
#   bin/agent-spec-ab.sh run "<the task, in quotes>"
#
# That runs both arms automatically with `claude -p`, each in its own throwaway
# clone of this repository so neither arm ever sees the other's edits, then
# prints the comparison.
#
#   bin/agent-spec-ab.sh run "<task>" --arm-a agent-spec-raw-code \
#                                     --arm-b agent-spec-raw-code-full \
#                                     --model sonnet --budget 5
#
# The manual path is still there for a task you want to drive by hand:
#
#   bin/agent-spec-ab.sh start A "<task>"   # then run it in a NEW session
#   bin/agent-spec-ab.sh end A
#   bin/agent-spec-ab.sh start B "<task>"   # again, NEW session, other mode
#   bin/agent-spec-ab.sh end B
#   bin/agent-spec-ab.sh report
#
# Confounds this controls for, because otherwise the number means nothing:
#   - fresh context per arm      each arm gets its own --session-id, never --resume
#   - identical task             the same string is passed to both, and checked
#   - identical starting tree    each arm runs in its own clone at the same commit
#   - identical model            pinned with --model, so it is not a variable
# =============================================================================
set -uo pipefail

HOME_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO="$(pwd)"
STATE_DIR="${REPO}/.agent-spec/ab"
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'

PROJECTS="${HOME}/.claude/projects/$(pwd | tr '/' '-')"

die() { echo -e "${RED}✗${NC} $*" >&2; exit 1; }

uuid() {
  if command -v uuidgen >/dev/null 2>&1; then uuidgen | tr 'A-Z' 'a-z'
  elif [ -r /proc/sys/kernel/random/uuid ]; then cat /proc/sys/kernel/random/uuid
  else python3 -c "import uuid;print(uuid.uuid4())"
  fi
}

# ---------------------------------------------------------------------------
# run_arm <label> <skill> <task> <model> <budget>
#
# One arm: a throwaway clone at the current commit, a brand-new session id, and
# the mode invoked as the first line of the prompt. Prints the JSON result path.
# ---------------------------------------------------------------------------
run_arm() {
  local label="$1" skill="$2" task="$3" model="$4" budget="$5"
  local dir="${STATE_DIR}/work-${label}"
  local sid; sid="$(uuid)"

  rm -rf "${dir}"
  git clone --quiet --no-hardlinks "${REPO}" "${dir}" 2>/dev/null \
    || die "could not clone ${REPO} — is this a git repository?"

  echo -e "${YELLOW}Arm ${label}${NC}  skill=/${skill}  model=${model}  session=${sid}"
  echo "  working in ${dir}"

  # The mode is a skill, so it is invoked the way a user would invoke it: as the
  # first line of the prompt. Appending it to the system prompt instead would
  # change the cache prefix and make the two arms structurally different.
  local prompt
  prompt="$(printf '/%s\n\n%s' "${skill}" "${task}")"

  local started; started="$(date +%s)"
  # CLAUDECODE is unset because Claude Code refuses to launch inside itself. If
  # you are reading this from inside a session, that guard is why: run this from
  # a plain terminal.
  # The `cd` is the entire point of the clone and was missing from the first two
  # runs: `claude -p` inherits the caller's working directory, so both arms were
  # reading and would have edited the real repository, while `git status` was
  # checked in an untouched clone and therefore always reported zero.
  ( cd "${dir}" && env -u CLAUDECODE -u CLAUDE_CODE_SESSION_ID -u CLAUDE_CODE_ENTRYPOINT \
    claude -p "${prompt}" \
      --output-format json \
      --session-id "${sid}" \
      --model "${model}" \
      --permission-mode acceptEdits \
      --allowed-tools "Bash Read Write Edit MultiEdit Glob Grep" \
      --max-budget-usd "${budget}" \
      > "${STATE_DIR}/result-${label}.json" 2> "${STATE_DIR}/stderr-${label}.txt" )
  local rc=$?
  local elapsed=$(( $(date +%s) - started ))

  if [ ! -s "${STATE_DIR}/result-${label}.json" ]; then
    echo -e "  ${RED}no output${NC} (exit ${rc}). stderr:"
    sed 's/^/    /' "${STATE_DIR}/stderr-${label}.txt" | head -5
    return 1
  fi

  # An arm that errored is not a cheap arm. Saying so is the whole point.
  local is_error; is_error="$(python3 -c "
import json,sys
try: print(json.load(open('${STATE_DIR}/result-${label}.json')).get('is_error'))
except Exception: print('unknown')")"
  if [ "${is_error}" = "True" ]; then
    echo -e "  ${RED}arm reported is_error=true${NC} — its numbers are not comparable:"
    python3 -c "
import json;d=json.load(open('${STATE_DIR}/result-${label}.json'))
print('    ' + str(d.get('result'))[:300])"
    return 1
  fi

  printf '%s\n' "${sid}" > "${STATE_DIR}/session-${label}.txt"

  # Did it actually do the work? `is_error: false` only means the session ended
  # cleanly. An arm that changed nothing and reported success is not a cheap arm,
  # it is a failed one — and it is the cheapest possible arm, so counting it would
  # invert the result. This is the check the first real run needed and did not have.
  local changed
  changed="$(cd "${dir}" && git status --porcelain | wc -l | tr -d ' ')"
  printf '%s\n' "${changed}" > "${STATE_DIR}/changed-${label}.txt"
  ( cd "${dir}" && git status --porcelain > "${STATE_DIR}/changes-${label}.txt" )

  # Locate the transcript and confirm it was filed under the clone. If it is filed
  # under the caller's directory, the arm ran in the wrong tree and every number
  # from it describes the wrong experiment.
  local tpath
  tpath="$(find "${HOME}/.claude/projects" -name "${sid}.jsonl" 2>/dev/null | head -1)"
  if [ -n "${tpath}" ] && ! printf '%s' "${tpath}" | grep -q "work-${label}"; then
    echo -e "  ${RED}!${NC} this arm ran OUTSIDE its clone — transcript filed at:"
    echo "      ${tpath}"
    echo "    Every number from it describes the wrong tree. Treat the run as void."
  fi

  local denials
  denials="$(python3 -c "
import json
d=json.load(open('${STATE_DIR}/result-${label}.json'))
print(len(d.get('permission_denials') or []))" 2>/dev/null || echo 0)"

  echo -e "  ${GREEN}✓${NC} finished in ${elapsed}s   files changed: ${changed}   permission denials: ${denials}"
  if [ "${denials}" != "0" ]; then
    echo -e "  ${YELLOW}!${NC} the arm was blocked from a tool it wanted:"
    python3 -c "
import json
d=json.load(open('${STATE_DIR}/result-${label}.json'))
for x in (d.get('permission_denials') or [])[:3]:
    inp = x.get('tool_input') or {}
    print('      %s: %s' % (x.get('tool_name'), str(inp.get('command') or inp.get('file_path') or inp)[:90]))"
  fi
  if [ "${changed}" = "0" ]; then
    echo -e "  ${RED}!${NC} this arm changed NOTHING. Its cost is not comparable — it is the"
    echo    "    cost of not doing the task."
  fi
  return 0
}

# ---------------------------------------------------------------------------
# One table, both arms, from the JSON results — which carry the authoritative
# usage totals and the real dollar cost.
# ---------------------------------------------------------------------------
report_json() {
  python3 - "$1" "$2" "$3" "$4" <<'PY'
import json, sys

a_path, b_path, a_label, b_label = sys.argv[1:5]

def load(p):
    with open(p) as fh:
        d = json.load(fh)
    u = d.get("usage") or {}
    return {
        "turns": d.get("num_turns", 0),
        "cost": d.get("total_cost_usd", 0.0) or 0.0,
        "ms": d.get("duration_ms", 0),
        "in": u.get("input_tokens", 0) or 0,
        "write": u.get("cache_creation_input_tokens", 0) or 0,
        "read": u.get("cache_read_input_tokens", 0) or 0,
        "out": u.get("output_tokens", 0) or 0,
    }

a, b = load(a_path), load(b_path)

rows = [
    ("assistant turns", "turns", "{:,.0f}"),
    ("input_tokens", "in", "{:,.0f}"),
    ("cache_creation_input_tokens", "write", "{:,.0f}"),
    ("cache_read_input_tokens", "read", "{:,.0f}"),
    ("output_tokens", "out", "{:,.0f}"),
    ("duration (ms)", "ms", "{:,.0f}"),
    ("cost (USD)", "cost", "{:.4f}"),
]

print("\n%-30s %16s %16s %10s" % ("", a_label, b_label, "delta"))
print("-" * 76)
for name, key, fmt in rows:
    va, vb = a[key], b[key]
    delta = (100.0 * (vb - va) / va) if va else 0.0
    print("%-30s %16s %16s %9.1f%%"
          % (name, fmt.format(va), fmt.format(vb), delta))

# total_cost_usd is the one number that already has the price ratios in it, so
# it is the verdict rather than the weighted estimate used elsewhere.
if a["cost"] and b["cost"]:
    delta = 100.0 * (b["cost"] - a["cost"]) / a["cost"]
    verdict = "cheaper" if delta < 0 else "more expensive"
    print("\n%s is %.1f%% %s than %s, on this one task."
          % (b_label, abs(delta), verdict, a_label))
    print("One task is one data point. Run it on three or four before quoting a figure,\n"
          "and never quote a saving measured on a task the two arms did differently.")
else:
    print("\nNo cost reported — quote the token buckets, not a percentage.")
PY
}

newest() { ls -t "${PROJECTS}"/*.jsonl 2>/dev/null | head -1; }

# ---------------------------------------------------------------------------

case "${1:-}" in
  run)
    TASK="${2:?the task, in quotes}"
    shift 2
    ARM_A="agent-spec-raw-code"
    ARM_B="agent-spec-raw-code-full"
    MODEL="sonnet"
    BUDGET="5"
    while [ $# -gt 0 ]; do
      case "$1" in
        --arm-a) ARM_A="$2"; shift 2 ;;
        --arm-b) ARM_B="$2"; shift 2 ;;
        --model) MODEL="$2"; shift 2 ;;
        --budget) BUDGET="$2"; shift 2 ;;
        *) die "unknown argument: $1" ;;
      esac
    done

    [ -z "${CLAUDECODE:-}" ] || die "Run this from a plain terminal, not inside a Claude Code session.
  Claude Code refuses to launch inside itself, and a nested run would not be a
  fresh context anyway — which is the variable under test."
    command -v claude >/dev/null 2>&1 || die "claude is not on PATH"
    command -v git >/dev/null 2>&1 || die "git is not on PATH"

    # Preflight the credentials before cloning anything. `claude -p` reports "Not
    # logged in" as a normal result with is_error set, which otherwise surfaces as
    # "arm A did not complete" and looks like a bug in the experiment. An
    # interactive session can be authenticated by its host process while the
    # on-disk token is an empty stub, so the file existing proves nothing.
    CREDS="${HOME}/.claude/.credentials.json"
    if [ -f "${CREDS}" ] && command -v python3 >/dev/null 2>&1; then
      HAS_TOKEN="$(python3 - "${CREDS}" <<'PY'
import json, sys
try:
    d = json.load(open(sys.argv[1]))
except Exception:
    print("unknown"); raise SystemExit
def any_token(o):
    if isinstance(o, dict):
        for k, v in o.items():
            if "token" in k.lower() and isinstance(v, str) and v.strip():
                return True
            if isinstance(v, (dict, list)) and any_token(v):
                return True
    elif isinstance(o, list):
        return any(any_token(x) for x in o)
    return False
print("yes" if any_token(d) else "no")
PY
)"
      [ "${HAS_TOKEN}" = "no" ] && die "The CLI is not logged in.
  ${CREDS} exists but holds no token, so every arm would come back
  with \"Not logged in\" and the run would prove nothing.

  An interactive Claude Code session can be authenticated by its host process
  while that file stays an empty stub — so being logged in on the desktop app is
  not enough for \`claude -p\`.

  Fix it once, in a plain terminal:
      claude          # then complete /login
  then re-run this command."
    fi

    mkdir -p "${STATE_DIR}"
    printf '%s\n' "${TASK}" > "${STATE_DIR}/task-A.txt"
    printf '%s\n' "${TASK}" > "${STATE_DIR}/task-B.txt"

    echo "task:  ${TASK}"
    echo "base:  $(git rev-parse --short HEAD 2>/dev/null) on $(git rev-parse --abbrev-ref HEAD 2>/dev/null)"
    echo ""
    run_arm A "${ARM_A}" "${TASK}" "${MODEL}" "${BUDGET}" || die "arm A did not complete"
    echo ""
    run_arm B "${ARM_B}" "${TASK}" "${MODEL}" "${BUDGET}" || die "arm B did not complete"

    CHANGED_A="$(cat "${STATE_DIR}/changed-A.txt" 2>/dev/null || echo 0)"
    CHANGED_B="$(cat "${STATE_DIR}/changed-B.txt" 2>/dev/null || echo 0)"

    report_json "${STATE_DIR}/result-A.json" "${STATE_DIR}/result-B.json" \
                "/${ARM_A}" "/${ARM_B}"

    # The comparison is only a comparison if both arms did the work. Refusing here
    # is the entire discipline this repository is built on: a cheaper arm that did
    # less is not a saving, and publishing it as one is the failure being studied.
    if [ "${CHANGED_A}" = "0" ] || [ "${CHANGED_B}" = "0" ]; then
      echo ""
      echo -e "${RED}=== THIS RESULT IS VOID ===${NC}"
      echo "  arm A changed ${CHANGED_A} files, arm B changed ${CHANGED_B}."
      echo "  An arm that changed nothing did not do the task, and doing nothing is"
      echo "  always cheapest. Quote no percentage from this run."
      echo ""
      echo "  Read what each arm claimed it did before assuming it failed honestly:"
      echo "    python3 -c \"import json;print(json.load(open('${STATE_DIR}/result-A.json'))['result'])\""
      echo "    python3 -c \"import json;print(json.load(open('${STATE_DIR}/result-B.json'))['result'])\""
    else
      echo ""
      echo "Both arms changed files, so the delta above is a like-for-like comparison"
      echo "of cost. It is still not a comparison of quality — read both diffs:"
      for arm in A B; do
        echo "  arm ${arm}:"
        sed 's/^/      /' "${STATE_DIR}/changes-${arm}.txt" 2>/dev/null | head -8
      done
    fi

    echo ""
    echo "Transcripts, located rather than predicted:"
    for arm in A B; do
      sid="$(cat "${STATE_DIR}/session-${arm}.txt" 2>/dev/null)"
      found="$(find "${HOME}/.claude/projects" -name "${sid}.jsonl" 2>/dev/null | head -1)"
      echo "  arm ${arm}:  ${found:-not filed under ~/.claude/projects}"
    done
    echo ""
    echo "  ${STATE_DIR}/result-*.json holds the authoritative totals and the real cost."
    ;;

  start)
    ARM="${2:?arm required: A or B}"
    TASK="${3:?the task, in quotes}"
    mkdir -p "${STATE_DIR}"
    printf '%s\n' "${TASK}" > "${STATE_DIR}/task-${ARM}.txt"
    ls "${PROJECTS}"/*.jsonl 2>/dev/null | sort > "${STATE_DIR}/before-${ARM}.txt"
    echo -e "${YELLOW}Arm ${ARM} armed.${NC}"
    echo ""
    echo "  1. Start a NEW Claude Code session in this directory. A fresh context is"
    echo "     the variable under test — resuming or continuing invalidates the run."
    echo "  2. Activate the mode for this arm, then paste the task exactly as written:"
    echo ""
    sed 's/^/       /' "${STATE_DIR}/task-${ARM}.txt"
    echo ""
    echo "  3. When the task is done, come back here and run:"
    echo "       bin/agent-spec-ab.sh end ${ARM}"
    ;;

  end)
    ARM="${2:?arm required: A or B}"
    [ -f "${STATE_DIR}/before-${ARM}.txt" ] || die "arm ${ARM} was never started"
    ls "${PROJECTS}"/*.jsonl 2>/dev/null | sort > "${STATE_DIR}/after-${ARM}.txt"
    NEW="$(comm -13 "${STATE_DIR}/before-${ARM}.txt" "${STATE_DIR}/after-${ARM}.txt" | head -1)"
    if [ -z "${NEW}" ]; then
      die "No new transcript appeared. The run happened in a resumed session, in a
  different directory, or not at all. Nothing recorded — a mislabelled arm is
  worse than no measurement."
    fi
    printf '%s\n' "${NEW}" > "${STATE_DIR}/arm-${ARM}.txt"
    echo -e "${GREEN}✓${NC} arm ${ARM}: $(basename "${NEW}")"
    python3 "${HOME_DIR}/bin/agent-spec-tokens.py" session --file "${NEW}" | head -12
    ;;

  report)
    A="$(cat "${STATE_DIR}/arm-A.txt" 2>/dev/null)"
    B="$(cat "${STATE_DIR}/arm-B.txt" 2>/dev/null)"
    [ -n "${A}" ] && [ -n "${B}" ] || die "both arms must be finished first"
    if ! diff -q "${STATE_DIR}/task-A.txt" "${STATE_DIR}/task-B.txt" >/dev/null 2>&1; then
      echo -e "${YELLOW}! The two arms were given different tasks.${NC}"
      echo "  A lower total on a different task is not a saving. Reporting it as one is"
      echo "  exactly how a 60-90% claim gets made. Fix the tasks and re-run."
      echo ""
    fi
    python3 "${HOME_DIR}/bin/agent-spec-tokens.py" compare "${A}" "${B}"
    ;;

  clean)
    rm -rf "${STATE_DIR}"
    echo "removed ${STATE_DIR}"
    ;;

  *)
    sed -n '3,32p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
    exit 1
    ;;
esac
