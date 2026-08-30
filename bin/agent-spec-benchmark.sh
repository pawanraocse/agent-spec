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
#   bin/agent-spec-benchmark.sh --arm-b none        # a mode against no mode at all
#   bin/agent-spec-benchmark.sh --arms none,agent-spec-raw-code,agent-spec-raw-code-full
#
# The arm named "none" runs with no skill body injected. It is the control, and
# without it the suite can only rank the two modes against each other — never say
# whether either saves anything against plain Claude Code.
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
ARMS=""                 # comma separated; overrides ARM_A/ARM_B when set
MODEL="sonnet"
BUDGET="5"
REPEATS="3"
TASKS=""
REPORT_ONLY="false"
CONSEC_ERRORS=0
ABORT_AFTER=3

die() { echo -e "${RED}✗${NC} $*" >&2; exit 1; }

while [ $# -gt 0 ]; do
  case "$1" in
    --arm-a)   ARM_A="$2"; shift 2 ;;
    --arm-b)   ARM_B="$2"; shift 2 ;;
    --arms)    ARMS="$2"; shift 2 ;;
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

  case "${label}" in
    [A-Z]) ;;
    *) die "bad arm label '${label}' — it becomes a directory name" ;;
  esac
  rm -rf "${dir}"
  git clone --quiet --no-hardlinks "${REPO}" "${dir}" 2>/dev/null || die "clone failed"
  [ -d "${dir}" ] || die "clone reported success but ${dir} does not exist"

  # The skill body is injected. A leading /skill-name line in a -p prompt is
  # passed through as plain text and the mode never takes effect, which silently
  # turns the whole comparison into one configuration against itself.
  # The arm named "none" is the control: no skill body at all. Without it the
  # suite can only say which mode is cheaper, never whether either one saves
  # anything against plain Claude Code — which is the number the skills claim.
  local body=""
  if [ "${skill}" != "none" ]; then
    body="$(cat "${HOME_DIR}/skills/claude/${skill}/SKILL.md" 2>/dev/null)"
    [ -n "${body}" ] || die "no skill body for ${skill}"
  fi
  local -a sysargs=()
  [ -n "${body}" ] && sysargs=(--append-system-prompt "${body}")

  local started; started="$(date +%s)"
  ( cd "${dir}" && env -u CLAUDECODE -u CLAUDE_CODE_SESSION_ID -u CLAUDE_CODE_ENTRYPOINT \
    claude -p "${prompt}" ${sysargs[@]+"${sysargs[@]}"} \
      --output-format json \
      --session-id "${sid}" \
      --model "${MODEL}" \
      --permission-mode acceptEdits \
      --allowed-tools "Bash Read Write Edit MultiEdit Glob Grep Task" \
      --max-budget-usd "${BUDGET}" \
      > "${dir}/.result.json" 2> "${dir}/.stderr.txt" )
  local elapsed=$(( $(date +%s) - started ))

  # A run that billed nothing never reached the model — a usage limit, an auth
  # expiry, a network error. Its clone is untouched, so the verify script then
  # reports a task failure, which reads exactly like the mode did the work badly.
  # That is how a whole suite can look like a finding about the two modes when
  # it is a finding about the account.
  local errmsg
  errmsg="$(python3 - "${dir}/.result.json" "${dir}/.stderr.txt" <<'PY'
import json, sys
try:
    d = json.load(open(sys.argv[1]))
except Exception:
    d = {}
usage = d.get("usage") or {}
billed = (d.get("total_cost_usd") or 0) > 0 or (usage.get("output_tokens") or 0) > 0
if not billed:
    msg = str(d.get("result") or d.get("error") or "").strip()
    if not msg:
        try:
            msg = open(sys.argv[2]).read().strip()
        except Exception:
            msg = ""
    msg = msg or "the run never reached the model"
    print(msg.splitlines()[0][:160])
PY
)"

  # The verify script is the arbiter, not the model's own report.
  local verdict="FAIL" vout=""
  if [ -n "${errmsg}" ]; then
    verdict="ERROR"
    vout="${errmsg}"
  elif [ -s "${dir}/.result.json" ]; then
    vout="$(cd "${dir}" && bash "${TASK_DIR}/${task}.verify" 2>&1)"
    [ $? -eq 0 ] && verdict="PASS"
  else
    verdict="ERROR"
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
  case "${verdict}" in
    PASS)
      echo -e "    ${GREEN}PASS${NC}  ${label} ${task} #${rep}  \$${cost}  ${elapsed}s"
      CONSEC_ERRORS=0 ;;
    ERROR)
      echo -e "    ${YELLOW}ERROR${NC} ${label} ${task} #${rep}  nothing billed  ${elapsed}s  — $(echo "${vout}" | head -1)"
      CONSEC_ERRORS=$(( CONSEC_ERRORS + 1 )) ;;
    *)
      echo -e "    ${RED}FAIL${NC}  ${label} ${task} #${rep}  \$${cost}  ${elapsed}s  — $(echo "${vout}" | head -1)"
      CONSEC_ERRORS=0 ;;
  esac

  # Keep what a run that did not pass left behind. Deleting it was why the last
  # suite could not say whether the failures were the modes or the account.
  if [ "${verdict}" = "PASS" ]; then
    rm -rf "${dir}"
  else
    local keep="${OUT_DIR}/failed/${label}-${task}-${rep}"
    rm -rf "${keep}"; mkdir -p "${keep}"
    cp "${dir}/.result.json" "${dir}/.stderr.txt" "${keep}/" 2>/dev/null
    rm -rf "${dir}"
  fi
}

# ---------------------------------------------------------------------------

report() {
  python3 - "${OUT_DIR}/results.jsonl" <<'PY'
import json, sys, statistics as st

path = sys.argv[1]
rows = []
for line in open(path):
    try: rows.append(json.loads(line))
    except ValueError: pass
if not rows:
    print("no results"); raise SystemExit(1)

# A run that billed nothing never reached the model. Counting it as a failed task
# turns an account problem into a false finding about a mode, so it is reported
# separately and excluded from every rate and every median below.
def never_ran(r):
    return r.get("verdict") == "ERROR" or (not r.get("cost") and not r.get("out"))

errors = [r for r in rows if never_ran(r)]
rows   = [r for r in rows if not never_ran(r)]
if errors:
    print("\n=== %d run(s) never reached the model — excluded ===" % len(errors))
    print("  " + ", ".join("%s %s #%d" % (r["arm"], r["task"], r["repeat"]) for r in errors[:8])
          + (" …" if len(errors) > 8 else ""))
    print("  Nothing was billed for these. Their clones were untouched, so any")
    print("  verify message they produced describes an empty repository, not a mode.")
if not rows:
    print("\nEvery run billed nothing. There is no comparison to make.")
    raise SystemExit(0)

# Arm order comes from the results themselves, so --report works on its own.
arms = []
for r in rows:
    if r["skill"] not in arms: arms.append(r["skill"])
tasks = sorted({r["task"] for r in rows})
# The control, if it was run, is what every saving is measured against.
base = "none" if "none" in arms else arms[0]
label = lambda a: "plain (no skill)" if a == "none" else "/" + a
W = max(len(label(a)) for a in arms) + 2

def med(v): return st.median(v) if v else 0.0
def ok_rows(a, t=None):
    return [r for r in rows if r["skill"] == a and r["verdict"] == "PASS"
            and (t is None or r["task"] == t)]

print("\n=== completion rate (runs that reached the model) ===")
print("%-*s %8s %10s" % (W, "", "runs", "verified"))
rate = {}
for a in arms:
    runs = [r for r in rows if r["skill"] == a]
    ok = ok_rows(a)
    rate[a] = (len(runs), len(ok))
    print("%-*s %8d %7d (%.0f%%)" % (W, label(a), len(runs), len(ok),
                                     100.0 * len(ok) / len(runs) if runs else 0))

print("\n=== tokens per verified run (median) ===")
print("%-*s %9s %9s %11s %11s %11s" % (W, "", "turns", "output", "cache wr", "cache rd", "total"))
toks = {}
for a in arms:
    v = ok_rows(a)
    if not v:
        print("%-*s %9s" % (W, label(a), "—")); continue
    m = {k: med([r[k] for r in v]) for k in ("turns", "out", "write", "read", "in")}
    total = m["out"] + m["write"] + m["read"] + m["in"]
    toks[a] = total
    print("%-*s %9.1f %9.0f %11.0f %11.0f %11.0f"
          % (W, label(a), m["turns"], m["out"], m["write"], m["read"], total))

print("\n=== cost per VERIFIED task ===")
print("%-*s %11s %11s %11s %12s" % (W, "", "median $", "min $", "max $", "vs " + ("control" if base == "none" else "first")))
cost = {}
for a in arms:
    c = [r["cost"] for r in ok_rows(a)]
    if not c:
        print("%-*s %11s" % (W, label(a), "no verified runs")); continue
    cost[a] = med(c)
    if a == base or base not in cost:
        delta = "—"
    else:
        d = 100.0 * (cost[a] - cost[base]) / cost[base]
        delta = "%+.1f%%" % d
    print("%-*s %11.4f %11.4f %11.4f %12s" % (W, label(a), med(c), min(c), max(c), delta))

print("\n=== per task, median cost of verified runs ===")
hdr = "%-22s" % "task"
for a in arms: hdr += " %13s" % (("plain" if a == "none" else a.replace("agent-spec-", ""))[:13])
print(hdr)
wins = {a: 0 for a in arms}; wins["tie"] = 0
for t in tasks:
    line = "%-22s" % t
    per = {}
    for a in arms:
        c = [r["cost"] for r in ok_rows(a, t)]
        per[a] = c
        line += " %13s" % ("%.4f" % med(c) if c else "—")
    print(line)
    # A delta needs more than one verified run per arm, and ranges that do not
    # overlap. Anything else is the noise this script exists to get above.
    usable = [a for a in arms if len(per[a]) >= 2]
    if base in usable and len(usable) > 1:
        note = []
        for a in usable:
            if a == base: continue
            d = 100.0 * (med(per[a]) - med(per[base])) / med(per[base])
            overlap = not (max(per[a]) < min(per[base]) or max(per[base]) < min(per[a]))
            note.append("%s %+.1f%%%s" % (("plain" if a == "none" else a.replace("agent-spec-", "")),
                                          d, " (overlaps)" if overlap else ""))
            if overlap: wins["tie"] += 1
            elif d < 0: wins[a] += 1
            else: wins[base] += 1
        print("%-22s   vs %s: %s" % ("", "plain" if base == "none" else base.replace("agent-spec-", ""),
                                     ", ".join(note)))
    else:
        counts = "/".join(str(len(per[a])) for a in arms)
        print("%-22s   too few verified runs for a delta (%s)" % ("", counts))
        wins["tie"] += 1

print("\n=== verdict ===")
runs_seen = {rate[a][0] for a in arms}
if len(runs_seen) > 1:
    print("The arms did not get the same number of runs (%s), so this is not a paired"
          % ", ".join(str(rate[a][0]) for a in arms))
    print("comparison. Re-run the suite when it can finish.")
rates = {round(rate[a][1] / rate[a][0], 6) if rate[a][0] else 0 for a in arms}
if len(rates) > 1:
    print("Completion rates differ (%s). Cost per verified task accounts for that, but"
          % ", ".join("%d/%d" % (rate[a][1], rate[a][0]) for a in arms))
    print("a mode that fails more often is worse even when cheaper.")
elif any(rate[a][1] != rate[a][0] for a in arms):
    print("Every arm failed the same runs. A task all arms fail is a broken task or a")
    print("broken verifier, not a finding about any mode — fix it and re-run.")
if base in cost:
    for a in arms:
        if a == base or a not in cost: continue
        d = 100.0 * (cost[a] - cost[base]) / cost[base]
        print("%s: %.1f%% %s than %s, and %+.0f tokens per run"
              % (label(a), abs(d), "cheaper" if d < 0 else "more expensive", label(base),
                 toks.get(a, 0) - toks.get(base, 0)))
decided = sum(v for k, v in wins.items() if k != "tie")
if wins["tie"] >= decided:
    print("\nMost comparisons are inside the noise. Report NO MEASURABLE DIFFERENCE, not")
    print("a percentage — a number smaller than the spread that produced it is not a result.")
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

if [ -n "${ARMS}" ]; then
  ARM_LIST="$(echo "${ARMS}" | tr ',' ' ')"
else
  ARM_LIST="${ARM_A} ${ARM_B}"
fi
ARM_LABELS="A B C D E F G H"
[ "$(echo "${ARM_LIST}" | wc -w)" -le 8 ] || die "at most 8 arms"
for a in ${ARM_LIST}; do
  [ "${a}" = "none" ] && continue
  [ -f "${HOME_DIR}/skills/claude/${a}/SKILL.md" ] || die "no skill body for ${a}"
done

mkdir -p "${OUT_DIR}/work" "${OUT_DIR}/failed"
rm -rf "${OUT_DIR}/failed"/*
ABORTED="false"
: > "${OUT_DIR}/results.jsonl"

TOTAL=$(( $(echo "${SUITE}" | wc -w) * REPEATS * $(echo "${ARM_LIST}" | wc -w) ))
echo "suite:   ${SUITE}"
echo "arms:    $(echo "${ARM_LIST}" | sed 's/ / vs /g')"
echo "repeats: ${REPEATS}   model: ${MODEL}   runs: ${TOTAL}"
echo "base:    $(git rev-parse --short HEAD) on $(git rev-parse --abbrev-ref HEAD)"
echo ""

for t in ${SUITE}; do
  echo -e "${YELLOW}${t}${NC}"
  for rep in $(seq 1 "${REPEATS}"); do
    # Arms are interleaved rather than run in blocks, so drift in service latency
    # or load lands on both equally.
    i=1
    for a in ${ARM_LIST}; do
      # The label ends up in a directory name, so it is a plain letter from a
      # fixed list. Computing it with printf escapes produced the literal string
      # "\000", every arm shared one clone, and claude exited on a path it could
      # not lstat before any run reached the model.
      one_run "$(echo "${ARM_LABELS}" | cut -d' ' -f"${i}")" "${a}" "${t}" "${rep}"
      i=$(( i + 1 ))
    done
    if [ "${CONSEC_ERRORS}" -ge "${ABORT_AFTER}" ]; then
      echo ""
      echo -e "${RED}✗${NC} ${CONSEC_ERRORS} runs in a row billed nothing. Stopping."
      echo "  Usually a usage limit or an expired login, not the suite. Evidence:"
      echo "  ${OUT_DIR}/failed/"
      echo "  Resume when it clears; results so far are kept and --report re-prints them."
      ABORTED="true"
      break 2
    fi
  done
done

report
echo ""
echo "raw results: ${OUT_DIR}/results.jsonl"
echo "re-print:    bin/agent-spec-benchmark.sh --report"
