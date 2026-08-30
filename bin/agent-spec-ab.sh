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
  env -u CLAUDECODE -u CLAUDE_CODE_SESSION_ID -u CLAUDE_CODE_ENTRYPOINT \
    claude -p "${prompt}" \
      --output-format json \
      --session-id "${sid}" \
      --model "${model}" \
      --permission-mode acceptEdits \
      --max-budget-usd "${budget}" \
      > "${STATE_DIR}/result-${label}.json" 2> "${STATE_DIR}/stderr-${label}.txt"
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
  echo -e "  ${GREEN}✓${NC} finished in ${elapsed}s"
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

    mkdir -p "${STATE_DIR}"
    printf '%s\n' "${TASK}" > "${STATE_DIR}/task-A.txt"
    printf '%s\n' "${TASK}" > "${STATE_DIR}/task-B.txt"

    echo "task:  ${TASK}"
    echo "base:  $(git rev-parse --short HEAD 2>/dev/null) on $(git rev-parse --abbrev-ref HEAD 2>/dev/null)"
    echo ""
    run_arm A "${ARM_A}" "${TASK}" "${MODEL}" "${BUDGET}" || die "arm A did not complete"
    echo ""
    run_arm B "${ARM_B}" "${TASK}" "${MODEL}" "${BUDGET}" || die "arm B did not complete"

    report_json "${STATE_DIR}/result-A.json" "${STATE_DIR}/result-B.json" \
                "/${ARM_A}" "/${ARM_B}"

    echo ""
    echo "Per-turn detail. Each arm ran in its own clone, so its transcript is filed"
    echo "under that clone's path, not this repository's:"
    for arm in A B; do
      sid="$(cat "${STATE_DIR}/session-${arm}.txt" 2>/dev/null)"
      tdir="${HOME}/.claude/projects/$(echo "${STATE_DIR}/work-${arm}" | tr '/' '-')"
      echo "  arm ${arm}:  ${tdir}/${sid}.jsonl"
    done
    echo ""
    echo "  python3 ${HOME_DIR}/bin/agent-spec-tokens.py compare <A.jsonl> <B.jsonl>"
    echo "  ${STATE_DIR}/result-*.json holds the authoritative totals and the real cost."
    echo ""
    echo "Diffs produced by each arm (they ran in clones; your tree is untouched):"
    for arm in A B; do
      echo "  arm ${arm}: $(cd "${STATE_DIR}/work-${arm}" 2>/dev/null && git diff --stat HEAD | tail -1)"
    done
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
