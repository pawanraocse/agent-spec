#!/usr/bin/env bash
# =============================================================================
# agent-spec-benchmark.sh — compare two modes properly, over a task suite
#
# The A/B runner compares one task once per arm. That is not enough to say
# anything: three successive single-task runs of two *identical* configurations
# produced deltas of -47.8%, -19.6% and -0.5%. That spread is the noise floor,
# and any real difference has to be larger than it before it is a difference.
#
# So this runs a fixed suite, several times per arm, and — the part that matters
# most — checks whether each run actually did the job. A mode that is cheap
# because it half-finishes would otherwise win every time. The headline is cost
# per *verified* task, never cost per run.
#
#   bin/agent-spec-benchmark.sh --repeats 3
#   bin/agent-spec-benchmark.sh --repeats 5 --tasks 01-add-cli-flag --model sonnet
#   bin/agent-spec-benchmark.sh --report            # re-print from saved results
#
# Each task is a pair under benchmarks/tasks/:
#   <name>.task     the prompt, given verbatim to both arms
#   <name>.verify   a script run inside the clone; exit 0 means the work was done
#
# Every run happens in its own throwaway clone at the current commit, so no run
# ever sees another's edits and the working tree is never touched.
# =============================================================================
set -uo pipefail

HOME_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO="$(pwd)"
OUT_DIR="${REPO}/.agent-spec/benchmark"
TASK_DIR="${HOME_DIR}/benchmarks/tasks"
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'

ARM_A="agent-spec-raw-code"
ARM_B="agent-spec-raw-code-full"
MODEL="sonnet"
BUDGET="5"
REPEATS="3"
TASKS=""
REPORT_ONLY="false"

die() { echo -e "${RED}✗${NC} $*" >&2; exit 1; }

while [ $# -gt 0 ]; do
  case "$1" in
    --arm-a)   ARM_A="$2"; shift 2 ;;
    --arm-b)   ARM_B="$2"; shift 2 ;;
    --model)   MODEL="$2"; shift 2 ;;
    --budget)  BUDGET="$2"; shift 2 ;;
    --repeats) REPEATS="$2"; shift 2 ;;
    --tasks)   TASKS="$2"; shift 2 ;;
    --report)  REPORT_ONLY="true"; shift ;;
    -h|--help) sed -n '3,26p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "unknown argument: $1" ;;
  esac
done

uuid() {
  if [ -r /proc/sys/kernel/random/uuid ]; then cat /proc/sys/kernel/random/uuid
  else python3 -c "import uuid;print(uuid.uuid4())"; fi
}

# ---------------------------------------------------------------------------
# one_run <arm-label> <skill> <task-name> <repeat-index>
#
# Fresh clone, mode injected into the system prompt, then the task's own verify
# script decides whether the work was done. Appends one JSON line to results.
# ---------------------------------------------------------------------------
one_run() {
  local label="$1" skill="$2" task="$3" rep="$4"
  local dir="${OUT_DIR}/work/${label}-${task}-${rep}"
  local sid; sid="$(uuid)"
  local prompt; prompt="$(cat "${TASK_DIR}/${task}.task")"

  rm -rf "${dir}"
  git clone --quiet --no-hardlinks "${REPO}" "${dir}" 2>/dev/null || die "clone failed"

  # The skill body is injected. A leading /skill-name line in a -p prompt is
  # passed through as plain text and the mode never takes effect, which silently
  # turns the whole comparison into one configuration against itself.
  local body; body="$(cat "${HOME_DIR}/skills/claude/${skill}/SKILL.md" 2>/dev/null)"
  [ -n "${body}" ] || die "no skill body for ${skill}"

  local started; started="$(date +%s)"
  ( cd "${dir}" && env -u CLAUDECODE -u CLAUDE_CODE_SESSION_ID -u CLAUDE_CODE_ENTRYPOINT \
    claude -p "${prompt}" \
      --append-system-prompt "${body}" \
      --output-format json \
      --session-id "${sid}" \
      --model "${MODEL}" \
      --permission-mode acceptEdits \
      --allowed-tools "Bash Read Write Edit MultiEdit Glob Grep" \
      --max-budget-usd "${BUDGET}" \
      > "${dir}/.result.json" 2> "${dir}/.stderr.txt" )
  local elapsed=$(( $(date +%s) - started ))

  # The verify script is the arbiter, not the model's own report.
  local verdict="FAIL" vout=""
  if [ -s "${dir}/.result.json" ]; then
    vout="$(cd "${dir}" && bash "${TASK_DIR}/${task}.verify" 2>&1)"
    [ $? -eq 0 ] && verdict="PASS"
  else
    vout="no result json"
  fi

  python3 - "${dir}/.result.json" "${label}" "${skill}" "${task}" "${rep}" \
             "${verdict}" "${elapsed}" "${sid}" >> "${OUT_DIR}/results.jsonl" <<'PY'
import json, sys
path, label, skill, task, rep, verdict, elapsed, sid = sys.argv[1:9]
try:
    d = json.load(open(path))
except Exception:
    d = {}
u = d.get("usage") or {}
print(json.dumps({
    "arm": label, "skill": skill, "task": task, "repeat": int(rep),
    "verdict": verdict, "seconds": int(elapsed), "session": sid,
    "turns": d.get("num_turns", 0),
    "cost": d.get("total_cost_usd", 0.0) or 0.0,
    "in": u.get("input_tokens", 0) or 0,
    "write": u.get("cache_creation_input_tokens", 0) or 0,
    "read": u.get("cache_read_input_tokens", 0) or 0,
    "out": u.get("output_tokens", 0) or 0,
    "is_error": bool(d.get("is_error")),
}))
PY

  local cost; cost="$(python3 -c "
import json
try: print('%.4f' % (json.load(open('${dir}/.result.json')).get('total_cost_usd') or 0))
except Exception: print('0.0000')")"
  if [ "${verdict}" = "PASS" ]; then
    echo -e "    ${GREEN}PASS${NC}  ${label} ${task} #${rep}  \$${cost}  ${elapsed}s"
  else
    echo -e "    ${RED}FAIL${NC}  ${label} ${task} #${rep}  \$${cost}  ${elapsed}s  — $(echo "${vout}" | head -1)"
  fi
  rm -rf "${dir}"          # keep the results, not the clones
}

# ---------------------------------------------------------------------------

report() {
  python3 - "${OUT_DIR}/results.jsonl" "${ARM_A}" "${ARM_B}" <<'PY'
import json, sys, statistics as st
from collections import defaultdict

path, arm_a, arm_b = sys.argv[1:4]
rows = []
for line in open(path):
    try: rows.append(json.loads(line))
    except ValueError: pass
if not rows:
    print("no results"); raise SystemExit(1)

arms = [arm_a, arm_b]
by = defaultdict(list)
for r in rows:
    by[(r["skill"], r["task"])].append(r)

def med(v): return st.median(v) if v else 0.0

print("\n=== completion rate ===")
print("%-28s %10s %10s" % ("", "runs", "verified"))
overall = {}
for a in arms:
    runs = [r for r in rows if r["skill"] == a]
    ok = [r for r in runs if r["verdict"] == "PASS"]
    overall[a] = (len(runs), len(ok))
    pct = 100.0 * len(ok) / len(runs) if runs else 0
    print("%-28s %10d %7d (%.0f%%)" % ("/" + a, len(runs), len(ok), pct))

print("\n=== cost per VERIFIED task (median, and range) ===")
print("%-28s %12s %12s %12s" % ("", "median $", "min $", "max $"))
medians = {}
for a in arms:
    ok = [r["cost"] for r in rows if r["skill"] == a and r["verdict"] == "PASS"]
    medians[a] = med(ok)
    if ok:
        print("%-28s %12.4f %12.4f %12.4f" % ("/" + a, med(ok), min(ok), max(ok)))
    else:
        print("%-28s %12s" % ("/" + a, "no verified runs"))

print("\n=== per task, verified runs only ===")
tasks = sorted({r["task"] for r in rows})
print("%-24s %14s %14s %10s" % ("task", "/" + arm_a[-14:], "/" + arm_b[-14:], "delta"))
wins = {arm_a: 0, arm_b: 0, "tie": 0}
for t in tasks:
    ca = [r["cost"] for r in rows if r["task"] == t and r["skill"] == arm_a and r["verdict"] == "PASS"]
    cb = [r["cost"] for r in rows if r["task"] == t and r["skill"] == arm_b and r["verdict"] == "PASS"]
    # A "median" of a single verified run is that run, and a delta between two
    # single runs is the noise this whole script exists to get above.
    if len(ca) < 2 or len(cb) < 2:
        print("%-24s %14s %14s %10s" % (t, "%.4f" % med(ca) if ca else "—",
                                        "%.4f" % med(cb) if cb else "—",
                                        "too few (%d/%d)" % (len(ca), len(cb))))
        wins["tie"] += 1
        continue
    ma, mb = med(ca), med(cb)
    delta = 100.0 * (mb - ma) / ma if ma else 0
    # Overlapping ranges mean the difference is inside the noise, and saying so
    # is the point of running more than once.
    overlap = not (max(cb) < min(ca) or max(ca) < min(cb))
    mark = "  (overlaps)" if overlap else ""
    print("%-24s %14.4f %14.4f %9.1f%%%s" % (t, ma, mb, delta, mark))
    if overlap: wins["tie"] += 1
    elif mb < ma: wins[arm_b] += 1
    else: wins[arm_a] += 1

print("\n=== verdict ===")
a_runs, a_ok = overall[arm_a]
b_runs, b_ok = overall[arm_b]
if a_ok == 0 or b_ok == 0:
    print("One arm verified nothing. There is no comparison to make.")
    raise SystemExit(0)
if a_ok != b_ok:
    print("Completion rates differ (%d/%d vs %d/%d). Cost per verified task already"
          % (a_ok, a_runs, b_ok, b_runs))
    print("accounts for that, but a mode that fails more often is worse even when cheaper.")
elif a_ok != a_runs:
    print("Both arms failed the same %d of %d runs. A task both arms fail is a broken"
          % (a_runs - a_ok, a_runs))
    print("task or a broken verifier, not a finding about either mode — fix it and re-run.")
print("tasks won: /%s %d, /%s %d, indistinguishable %d"
      % (arm_a, wins[arm_a], arm_b, wins[arm_b], wins["tie"]))
ma, mb = medians[arm_a], medians[arm_b]
if ma and mb:
    d = 100.0 * (mb - ma) / ma
    print("overall median cost per verified task: %.1f%% %s for /%s"
          % (abs(d), "lower" if d < 0 else "higher", arm_b))
if wins["tie"] * 2 > len(tasks):
    print("\nMost tasks are inside the noise. Report NO MEASURABLE DIFFERENCE, not a\n"
          "percentage — a number smaller than the spread that produced it is not a result.")
PY
}

# ---------------------------------------------------------------------------

[ "${REPORT_ONLY}" = "true" ] && { report; exit 0; }

[ -z "${CLAUDECODE:-}" ] || die "Run this from a plain terminal, not inside a Claude Code
  session. A nested run is not a fresh context, which is the variable under test."
command -v claude >/dev/null 2>&1 || die "claude is not on PATH"
[ -d "${TASK_DIR}" ] || die "no task suite at ${TASK_DIR}"

if [ -n "${TASKS}" ]; then
  SUITE="$(echo "${TASKS}" | tr ',' ' ')"
else
  SUITE="$(cd "${TASK_DIR}" && ls *.task 2>/dev/null | sed 's/\.task$//' | tr '\n' ' ')"
fi
[ -n "${SUITE}" ] || die "no tasks found"

for t in ${SUITE}; do
  [ -f "${TASK_DIR}/${t}.task" ]   || die "missing ${t}.task"
  [ -f "${TASK_DIR}/${t}.verify" ] || die "missing ${t}.verify — a task with no
  verification cannot be scored, and an unscored task rewards not doing the work."
done

mkdir -p "${OUT_DIR}/work"
: > "${OUT_DIR}/results.jsonl"

TOTAL=$(( $(echo "${SUITE}" | wc -w) * REPEATS * 2 ))
echo "suite:   ${SUITE}"
echo "arms:    /${ARM_A}  vs  /${ARM_B}"
echo "repeats: ${REPEATS}   model: ${MODEL}   runs: ${TOTAL}"
echo "base:    $(git rev-parse --short HEAD) on $(git rev-parse --abbrev-ref HEAD)"
echo ""

for t in ${SUITE}; do
  echo -e "${YELLOW}${t}${NC}"
  for rep in $(seq 1 "${REPEATS}"); do
    # Arms are interleaved rather than run in blocks, so drift in service latency
    # or load lands on both equally.
    one_run A "${ARM_A}" "${t}" "${rep}"
    one_run B "${ARM_B}" "${t}" "${rep}"
  done
done

report
echo ""
echo "raw results: ${OUT_DIR}/results.jsonl"
echo "re-print:    bin/agent-spec-benchmark.sh --report"
