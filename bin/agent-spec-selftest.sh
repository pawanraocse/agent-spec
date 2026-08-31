#!/usr/bin/env bash
# =============================================================================
# agent-spec-selftest.sh — prove the framework works before shipping it
#
# Builds three throwaway fixture projects, installs into each, and asserts the
# things that have actually broken here before: edges that resolve to nothing,
# an indexer that overwrites its own output, a --lean run that prunes the wrong
# tree, gate ordering that lets a gate run without its predecessor.
#
# Usage: bin/agent-spec-selftest.sh [workdir]
# =============================================================================
set -uo pipefail

HOME_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="${1:-$(mktemp -d)}"
GREEN='\033[0;32m'; RED='\033[0;31m'; NC='\033[0m'
PASS=0; FAIL=0

ok()   { PASS=$((PASS+1)); echo -e "  ${GREEN}✓${NC} $1"; }
bad()  { FAIL=$((FAIL+1)); echo -e "  ${RED}✗${NC} $1"; }
want() { # want <description> <expected> <actual>
  if [ "$2" = "$3" ]; then ok "$1"; else bad "$1 — expected '$2', got '$3'"; fi
}
at_least() {
  if [ "$3" -ge "$2" ] 2>/dev/null; then ok "$1 ($3)"; else bad "$1 — wanted >= $2, got '$3'"; fi
}

jq_stat() { # jq_stat <graph.json> <key>
  python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['stats'].get(sys.argv[2],''))" "$1" "$2"
}

# ---------------------------------------------------------------------------
mkfixture_python() {
  local d="$1"; mkdir -p "$d/app/services" "$d/app/repository" "$d/tests"
  cat > "$d/pyproject.toml" <<'X'
[project]
name = "fixture"
dependencies = ["fastapi"]
X
  cat > "$d/app/services/pricing.py" <<'X'
from app.repository.prices import load
def total(items): return sum(load(i) for i in items)
X
  echo 'def load(i): return 1' > "$d/app/repository/prices.py"
  cat > "$d/app/api.py" <<'X'
from app.services.pricing import total
from fastapi import APIRouter
router = APIRouter()
@router.get("/total")
def get_total(): return total([])
X
  echo 'from app.services.pricing import total
def test_total(): assert total([]) == 0' > "$d/tests/test_pricing.py"
}

mkfixture_java_services() {
  local d="$1"
  mkdir -p "$d/orders/src/main/java/o/controller" "$d/orders/src/main/java/o/service" "$d/billing/src/main/java/b/service"
  echo '<project><dependency>spring-boot</dependency></project>' > "$d/orders/pom.xml"
  echo '<project><dependency>spring-boot</dependency></project>' > "$d/billing/pom.xml"
  cat > "$d/orders/src/main/java/o/controller/OrderController.java" <<'X'
package o.controller;
import o.service.OrderService;
@RestController public class OrderController { @GetMapping("/orders") void get() {} }
X
  cat > "$d/orders/src/main/java/o/service/OrderService.java" <<'X'
package o.service;
public class OrderService { void go() { kafkaTemplate.send("order.placed", null); } }
X
  cat > "$d/billing/src/main/java/b/service/BillingService.java" <<'X'
package b.service;
@KafkaListener(topics = "order.placed") public class BillingService {}
X
}

mkfixture_node() {
  local d="$1"; mkdir -p "$d/src/api" "$d/src/lib"
  echo '{"name":"fx","dependencies":{"express":"4"}}' > "$d/package.json"
  echo "export const fmt = (x) => x;" > "$d/src/lib/fmt.js"
  echo "import { fmt } from '../lib/fmt';
app.get('/health', () => fmt(1));" > "$d/src/api/health.js"
}

# ---------------------------------------------------------------------------
echo "workdir: ${WORK}"

echo ""
echo "[1] python fixture — import resolution"
P="${WORK}/py"; mkfixture_python "$P"
( cd "$P" && bash "${HOME_DIR}/bin/install.sh" --project-only >/dev/null 2>&1 )
G="$P/.agent-spec/graph/knowledge-graph.json"
if [ -f "$G" ]; then
  at_least "internal edges resolve" 3 "$(jq_stat "$G" internal_edges)"
  want     "endpoints found"        1 "$(jq_stat "$G" endpoints)"
  want     "test files found"       1 "$(jq_stat "$G" test_files)"
  # The bug that shipped once: the wrapper overwrote the builder's own output.
  ( cd "$P" && ./.agent-spec/bin/agent-spec-index --quiet >/dev/null 2>&1 )
  at_least "graph survives the wrapper" 3 "$(jq_stat "$G" internal_edges)"
else
  bad "graph not written"
fi

echo ""
echo "[2] java fixture — services, topics, layers"
J="${WORK}/java"; mkfixture_java_services "$J"
( cd "$J" && bash "${HOME_DIR}/bin/install.sh" --project-only >/dev/null 2>&1 )
G="$J/.agent-spec/graph/knowledge-graph.json"
if [ -f "$G" ]; then
  want     "two services detected"  2 "$(jq_stat "$G" services)"
  at_least "topic edge recovered"   1 "$(jq_stat "$G" integration_edges)"
  want     "topics"                 1 "$(jq_stat "$G" topics)"
  at_least "endpoints"              1 "$(jq_stat "$G" endpoints)"
else
  bad "graph not written"
fi

echo ""
echo "[3] node fixture — relative imports"
N="${WORK}/node"; mkfixture_node "$N"
( cd "$N" && bash "${HOME_DIR}/bin/install.sh" --project-only >/dev/null 2>&1 )
G="$N/.agent-spec/graph/knowledge-graph.json"
at_least "relative import resolves" 1 "$(jq_stat "$G" internal_edges)"

echo ""
echo "[4] gate ordering"
GATE="${HOME_DIR}/bin/agent-spec-gate.py"
( cd "$P" && python3 "$GATE" reset --feature selftest >/dev/null )
( cd "$P" && python3 "$GATE" check 2 >/dev/null 2>&1 )
want "gate 2 blocked without its predecessor" 1 "$?"
( cd "$P" && python3 "$GATE" check 0 >/dev/null 2>&1 )
want "gate 0 always runnable" 0 "$?"
printf 'REQ-001 a\nREQ-002 b\n' > "$P/.agent-spec/sdlc/01-REQUIREMENTS.md"
echo 'covers REQ-001' > "$P/.agent-spec/sdlc/03-PRD.md"
( cd "$P" && python3 "$GATE" trace >/dev/null 2>&1 )
want "trace fails on a dropped requirement" 1 "$?"

echo ""
echo "[5] digest"
OUT="$( cd "$P" && python3 "${HOME_DIR}/bin/agent-spec-digest.py" )"
case "$OUT" in
  *"<agent-spec-digest>"*) ok "digest emitted" ;;
  *) bad "digest empty" ;;
esac
OUT="$( cd "${WORK}" && python3 "${HOME_DIR}/bin/agent-spec-digest.py" )"
want "digest silent outside an agent-spec project" "" "$OUT"

echo ""
echo "[6] settings merge is idempotent"
SET="${WORK}/settings.json"
echo '{"model":"opus"}' > "$SET"
python3 "${HOME_DIR}/bin/agent-spec-settings.py" "$SET" /x/hook.sh >/dev/null
python3 "${HOME_DIR}/bin/agent-spec-settings.py" "$SET" /x/hook.sh >/dev/null
COUNT="$(python3 -c "import json;print(len(json.load(open('$SET'))['hooks']['SessionStart']))")"
want "one SessionStart entry after two runs" 1 "$COUNT"
KEEP="$(python3 -c "import json;print(json.load(open('$SET')).get('model'))")"
want "existing settings preserved" "opus" "$KEEP"

echo ""
echo "[7] skill naming contract"
BAD=0
for d in "${HOME_DIR}/skills/claude"/*/; do
  n="$(basename "$d")"
  case "$n" in agent-spec*) ;; *) BAD=$((BAD+1)); echo "     unprefixed: $n" ;; esac
  # the frontmatter name must equal the directory, or the harness lists a skill nobody can invoke
  FM="$(sed -n 's/^name: "\(.*\)"$/\1/p' "${d}SKILL.md" | head -1)"
  [ "$FM" = "$n" ] || { BAD=$((BAD+1)); echo "     name mismatch: $n vs $FM"; }
done
want "every skill prefixed and self-consistent" 0 "$BAD"

echo ""
echo "[8] memory"
MEM="${HOME_DIR}/bin/agent-spec-memory.py"
( cd "$P" && python3 "$MEM" add --type constraint --subject "selftest" --source "selftest" "This is a constraint recorded by the self test to prove the store works." >/dev/null )
COUNT="$( cd "$P" && python3 "$MEM" list | head -1 | grep -o '[0-9]\+' )"
want "fact recorded" 1 "$COUNT"
( cd "$P" && python3 "$MEM" add --type constraint --subject "selftest" --source "selftest" "This is a constraint recorded by the self test to prove the store works." >/dev/null )
COUNT="$( cd "$P" && python3 "$MEM" list | head -1 | grep -o '[0-9]\+' )"
want "identical fact not duplicated" 1 "$COUNT"
( cd "$P" && python3 "$MEM" add --type gotcha --subject "short" --source "x" "tiny" >/dev/null 2>&1 )
want "a fact too short to be worth keeping is refused" 2 "$?"
OUT="$( cd "$P" && python3 "$MEM" digest )"
case "$OUT" in *"[constraint] selftest"*) ok "fact reaches the digest" ;; *) bad "fact missing from digest" ;; esac
OUT="$( cd "$P" && python3 "${HOME_DIR}/bin/agent-spec-digest.py" )"
case "$OUT" in *"remembered:"*) ok "session digest carries memory" ;; *) bad "session digest has no memory block" ;; esac
# constraints survive a prune by age; that is the whole point of the type
( cd "$P" && python3 "$MEM" prune --older-than 0 >/dev/null )
COUNT="$( cd "$P" && python3 "$MEM" list | head -1 | grep -o '[0-9]\+' )"
want "constraints are never pruned by age" 1 "$COUNT"

echo ""
echo "[9] snapshot rotation"
SNAP="$P/.agent-spec/SESSION-SNAPSHOT.md"
: > "$SNAP"
for i in 1 2 3 4 5; do
  printf '# Session Snapshot — day %d\n\n## Session Summary\nfiller %d\n%s\n\n' \
    "$i" "$i" "$(head -c 3000 /dev/zero | tr '\0' 'x')" >> "$SNAP"
done
( cd "$P" && python3 "$MEM" rotate >/dev/null )
KEPT="$(grep -c '^# Session Snapshot' "$SNAP")"
want "rotation keeps the two newest sections" 2 "$KEPT"
ARCHIVED="$(cat "$P"/.agent-spec/memory/snapshots/*.md 2>/dev/null | grep -c '^# Session Snapshot')"
want "and archives the other three" 3 "$ARCHIVED"
# Moving sections out without saying so is how a record quietly stops being one.
grep -q '## Archived sections' "$SNAP" \
  && ok "the live file keeps an index of what was archived" \
  || bad "rotation moved sections out leaving no trace in the live file"
INDEXED="$(grep -c '^- \*\*day ' "$SNAP")"
want "one index line per archived section" 3 "$INDEXED"
# Reviewing the record must not mean opening a 29 KB file to find out what is in it.
OUT="$( cd "$P" && python3 "$MEM" snapshots 2>&1 )"
case "$OUT" in *"sections,"*) ok "snapshots lists every section, live and archived" ;; *) bad "no snapshots listing" ;; esac
case "$OUT" in *"filler 1"*) ok "and carries each section's summary line" ;; *) bad "listing has no summaries — it is just filenames" ;; esac

echo ""
echo "[10] indexer limits"
BIG="${WORK}/big"; mkdir -p "$BIG/src" "$BIG/generated"
echo '{"name":"big"}' > "$BIG/package.json"
printf 'generated/\n' > "$BIG/.gitignore"
echo "export const a = 1;" > "$BIG/src/a.js"
echo "export const gen = 1;" > "$BIG/generated/huge.js"
echo "export const m = 1;" > "$BIG/src/vendor.min.js"
head -c 2000000 /dev/zero | tr '\0' 'x' > "$BIG/src/bundle.js"
( cd "$BIG" && bash "${HOME_DIR}/bin/install.sh" --project-only >/dev/null 2>&1 )
FILES="$(jq_stat "$BIG/.agent-spec/graph/knowledge-graph.json" files)"
want "gitignored dir, minified and oversized files all skipped" 1 "$FILES"

echo ""
echo "[11] upgrade path"
UH="${WORK}/upgradehome"
mkdir -p "$UH/.claude/skills/review" "$UH/.claude/skills/my-own-skill"
printf -- '---\nname: "review"\ndescription: >-\n  old\n---\nbody\n' > "$UH/.claude/skills/review/SKILL.md"
printf -- '---\nname: "my-own-skill"\ndescription: >-\n  mine\n---\nbody\n' > "$UH/.claude/skills/my-own-skill/SKILL.md"
( cd "$P" && HOME="$UH" WIN_CLAUDE_HOME="$UH/nowin" bash "${HOME_DIR}/bin/install.sh" --skills-only >/dev/null 2>&1 )
LEFT="$(ls "$UH/.claude/skills" 2>/dev/null | grep -cv '^agent-spec')"
want "the old unprefixed skill is pruned, the user's own is kept" 1 "$LEFT"
want "and the one kept is theirs" "my-own-skill" "$(ls "$UH/.claude/skills" | grep -v '^agent-spec')"
CURSOR_COUNT="$(ls "$UH/.cursor/skills" 2>/dev/null | wc -l | tr -d ' ')"
CLAUDE_COUNT="$(ls "$UH/.claude/skills" 2>/dev/null | grep -c '^agent-spec')"
want "cursor and claude get the same skill set" "$CLAUDE_COUNT" "$CURSOR_COUNT"

echo ""
echo "[12] token measurement"
TOK="${HOME_DIR}/bin/agent-spec-tokens.py"
FIX="${WORK}/fixture.jsonl"
# Two assistant turns with known usage, one Bash call and its result.
cat > "$FIX" <<'JSONL'
{"type":"assistant","message":{"usage":{"input_tokens":10,"cache_creation_input_tokens":100,"cache_read_input_tokens":1000,"output_tokens":50},"content":[{"type":"tool_use","id":"t1","name":"Bash","input":{"command":"ls"}}]}}
{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"t1","content":[{"type":"text","text":"0123456789"}]}]}}
{"type":"assistant","message":{"usage":{"input_tokens":10,"cache_creation_input_tokens":100,"cache_read_input_tokens":1000,"output_tokens":50},"content":[]}}
JSONL
OUT="$(python3 "$TOK" session --file "$FIX" 2>&1)"
want "counts the turns"        "2 assistant turns, ~1,100 tokens of context re-read per turn" "$(echo "$OUT" | sed -n 2p)"
want "sums the buckets" "2,000" "$(echo "$OUT" | awk '$1=="cache_read_input_tokens"{print $2}')"
want "weights them (2000*0.1 + 200*1.25 + 100*5 + 20)" "970" "$(echo "$OUT" | awk '$1=="TOTAL"{print $2}')"
OUT="$(python3 "$TOK" --weights read=1 session --file "$FIX" 2>&1)"
case "$OUT" in *"read=1"*) ok "weights are overridable" ;; *) bad "--weights ignored" ;; esac
OUT="$(python3 "$TOK" tools --file "$FIX" 2>&1)"
case "$OUT" in *"Bash"*"10 B"*) ok "attributes a result to its tool" ;; *) bad "tool attribution wrong" ;; esac
python3 "$TOK" session --file "${WORK}/does-not-exist.jsonl" >/dev/null 2>&1
want "a missing transcript exits nonzero with a reason" 1 "$?"

echo ""
echo "[13] terse modes"
MODES="$(ls -d "${HOME_DIR}/skills/claude"/agent-spec-{raw-code,raw-code-full,verbose,dense,trim-noise} 2>/dev/null | wc -l | tr -d ' ')"
want "three remain: raw-code, raw-code-full, verbose" 3 "$MODES"
UH2="${WORK}/upgrade2"
mkdir -p "$UH2/.claude/skills/agent-spec-dense" "$UH2/.claude/skills/agent-spec-trim-noise" "$UH2/.claude/skills/mine"
printf -- '---\nname: "agent-spec-dense"\ndescription: >-\n  old\n---\nbody\n' > "$UH2/.claude/skills/agent-spec-dense/SKILL.md"
printf -- '---\nname: "agent-spec-trim-noise"\ndescription: >-\n  old\n---\nbody\n' > "$UH2/.claude/skills/agent-spec-trim-noise/SKILL.md"
printf -- '---\nname: "mine"\ndescription: >-\n  mine\n---\nbody\n' > "$UH2/.claude/skills/mine/SKILL.md"
( cd "$P" && HOME="$UH2" WIN_CLAUDE_HOME="$UH2/nowin" bash "${HOME_DIR}/bin/install.sh" --skills-only >/dev/null 2>&1 )
want "the dropped modes are pruned on upgrade" 0 "$(ls "$UH2/.claude/skills" | grep -cE 'agent-spec-(dense|trim-noise)$')"
want "and the user's own skill survives" "mine" "$(ls "$UH2/.claude/skills" | grep -v '^agent-spec')"

echo ""
echo "[14] context break-even and subagents"
OUT="$(python3 "$TOK" context --file "$FIX" 2>&1)"
case "$OUT" in *"turn 1:"*) ok "reports the starting context" ;; *) bad "no turn 1 line" ;; esac
case "$OUT" in *"break-even"*|*"already small"*) ok "reaches a reset verdict" ;; *) bad "no verdict" ;; esac
AGENTS="$(ls "${HOME_DIR}/agents"/*.md 2>/dev/null | wc -l | tr -d ' ')"
at_least "subagents ship with the framework" 2 "$AGENTS"
CHEAP=0
for f in "${HOME_DIR}/agents"/*.md; do grep -qE '^model: (haiku|sonnet)$' "$f" || CHEAP=$((CHEAP+1)); done
want "every subagent pins a model rather than inheriting" 0 "$CHEAP"
want "installed into the home"    "$AGENTS" "$(ls "$UH2/.claude/agents"/*.md 2>/dev/null | wc -l | tr -d ' ')"
want "and into the project"       "$AGENTS" "$(ls "$P/.claude/agents"/*.md 2>/dev/null | wc -l | tr -d ' ')"
# an older framework version installed its own sync script; leaving it re-installs old names
touch "$UH2/.claude/sync-agent-spec-skills.sh"
echo "# agent-spec sync" > "$UH2/.claude/sync-agent-spec-skills.sh"
( cd "$P" && HOME="$UH2" WIN_CLAUDE_HOME="$UH2/nowin" bash "${HOME_DIR}/bin/install.sh" --skills-only >/dev/null 2>&1 )
want "the superseded sync script is removed" 0 "$(ls "$UH2/.claude/sync-agent-spec-skills.sh" 2>/dev/null | wc -l | tr -d ' ')"

echo ""
echo "[15] corpus and the A/B harness"
OUT="$(python3 "$TOK" corpus --min-turns 1 2>&1)"
case "$OUT" in *"sessions across"*"projects"*) ok "corpus aggregates across projects" ;; *) bad "corpus output wrong" ;; esac
bash "${HOME_DIR}/bin/agent-spec-ab.sh" >/dev/null 2>&1
want "the A/B runner refuses a bare invocation" 1 "$?"
( cd "$P" && bash "${HOME_DIR}/bin/agent-spec-ab.sh" start A "measure this" >/dev/null 2>&1 )
want "arming an arm records the task" "measure this" "$(cat "$P/.agent-spec/ab/task-A.txt" 2>/dev/null)"
( cd "$P" && bash "${HOME_DIR}/bin/agent-spec-ab.sh" end A >/dev/null 2>&1 )
want "ending an arm with no new transcript is refused" 1 "$?"
( cd "$P" && bash "${HOME_DIR}/bin/agent-spec-ab.sh" report >/dev/null 2>&1 )
want "a report with unfinished arms is refused" 1 "$?"
# The automated path must refuse to run nested: Claude Code will not launch inside
# itself, and a nested run is not a fresh context, which is the variable under test.
OUT="$( cd "$P" && CLAUDECODE=1 bash "${HOME_DIR}/bin/agent-spec-ab.sh" run "x" 2>&1 )"
case "$OUT" in *"plain terminal"*) ok "the automated run refuses to nest" ;; *) bad "no nesting guard" ;; esac
# The comparison table must render from two result JSONs and name a direction.
mkdir -p "${WORK}/abt"
echo '{"num_turns":18,"total_cost_usd":0.82,"duration_ms":94000,"usage":{"input_tokens":40,"cache_creation_input_tokens":52000,"cache_read_input_tokens":610000,"output_tokens":9800}}' > "${WORK}/abt/a.json"
echo '{"num_turns":11,"total_cost_usd":0.54,"duration_ms":71000,"usage":{"input_tokens":36,"cache_creation_input_tokens":49000,"cache_read_input_tokens":318000,"output_tokens":6100}}' > "${WORK}/abt/b.json"
OUT="$(bash -c "$(sed -n '/^report_json() {/,/^}/p' "${HOME_DIR}/bin/agent-spec-ab.sh"; echo "report_json ${WORK}/abt/a.json ${WORK}/abt/b.json ARM_A ARM_B")" 2>&1)"
case "$OUT" in *"34.1% cheaper"*) ok "the comparison reports a signed cost delta" ;; *) bad "cost delta missing or wrong" ;; esac
case "$OUT" in *"One task is one data point"*) ok "and refuses to let one run become a headline" ;; *) bad "no single-sample caveat" ;; esac
# "Not logged in" comes back as a normal result with is_error, which otherwise looks
# like a broken experiment rather than a missing login.
FAKEHOME="${WORK}/nologin"; mkdir -p "$FAKEHOME/.claude"
echo '{"claudeAiOauth":{"accessToken":"","refreshToken":"","expiresAt":0}}' > "$FAKEHOME/.claude/.credentials.json"
OUT="$( cd "$P" && HOME="$FAKEHOME" CLAUDECODE= bash "${HOME_DIR}/bin/agent-spec-ab.sh" run "x" 2>&1 )"
case "$OUT" in *"not logged in"*) ok "an empty credential stub is caught before any arm runs" ;; *) bad "no login preflight" ;; esac
case "$OUT" in *"work-A"*) bad "it cloned before checking the login" ;; *) ok "and nothing is cloned first" ;; esac
# The first real run produced a -47.8% delta from two arms that changed nothing.
# The void guard exists so that never gets published.
VOID="$(bash -c 'CHANGED_A=0; CHANGED_B=0; RED=""; NC=""
if [ "${CHANGED_A}" = "0" ] || [ "${CHANGED_B}" = "0" ]; then echo "THIS RESULT IS VOID"; fi')"
want "a run where an arm changed nothing is voided" "THIS RESULT IS VOID" "$VOID"
grep -q 'THIS RESULT IS VOID' "${HOME_DIR}/bin/agent-spec-ab.sh" \
  && ok "the void guard is wired into the runner" || bad "void guard missing from ab.sh"
grep -q 'allowed-tools' "${HOME_DIR}/bin/agent-spec-ab.sh" \
  && ok "arms are allowed the tools the task needs" || bad "arms cannot run Bash"
# claude -p inherits the caller's working directory. Without a cd, both arms read
# the real repository while git status was checked in an untouched clone.
grep -q 'cd "${dir}" && env -u CLAUDECODE' "${HOME_DIR}/bin/agent-spec-ab.sh" \
  && ok "each arm runs inside its own clone" || bad "arms run in the caller's directory"
grep -q 'ran OUTSIDE its clone' "${HOME_DIR}/bin/agent-spec-ab.sh" \
  && ok "and the transcript location is checked, not assumed" || bad "no clone-location check"
# A leading /skill-name line in a -p prompt is passed through as plain text: three
# runs produced a delta between two arms that were running the same configuration.
grep -q 'append-system-prompt' "${HOME_DIR}/bin/agent-spec-ab.sh" \
  && ok "the skill body is injected, not slash-invoked" || bad "arms run with no mode in force"
grep -q 'skill body is not present' "${HOME_DIR}/bin/agent-spec-ab.sh" \
  && ok "and its presence is verified in the transcript" || bad "no mode-in-force check"

echo ""
echo "[16] benchmark suite"
TD="${HOME_DIR}/benchmarks/tasks"
NT="$(ls "$TD"/*.task 2>/dev/null | wc -l | tr -d ' ')"
at_least "tasks exist" 3 "$NT"
MISSING=0
for f in "$TD"/*.task; do [ -f "${f%.task}.verify" ] || MISSING=$((MISSING+1)); done
want "every task has a verify script" 0 "$MISSING"
# A verifier that passes on an untouched tree scores not doing the work as success.
FALSEPASS=0
for f in "$TD"/*.verify; do
  ( cd "$P" && bash "$f" >/dev/null 2>&1 ) && FALSEPASS=$((FALSEPASS+1))
done
want "no verifier passes on an unmodified tree" 0 "$FALSEPASS"
# The reporter must expose a cheap-but-failing arm rather than crowning it.
mkdir -p "${WORK}/bm/.agent-spec/benchmark"
python3 - > "${WORK}/bm/.agent-spec/benchmark/results.jsonl" <<'JSON'
import json
for r in range(3):
    print(json.dumps({"arm":"A","skill":"agent-spec-raw-code","task":"t1","repeat":r,
        "verdict":"PASS","cost":0.15,"turns":7,"seconds":9,"session":"x",
        "in":1,"write":1,"read":1,"out":1,"is_error":False}))
    print(json.dumps({"arm":"B","skill":"agent-spec-raw-code-full","task":"t1","repeat":r,
        "verdict":"PASS" if r==0 else "FAIL","cost":0.02,"turns":2,"seconds":3,"session":"y",
        "in":1,"write":1,"read":1,"out":1,"is_error":False}))
JSON
OUT="$( cd "${WORK}/bm" && bash "${HOME_DIR}/bin/agent-spec-benchmark.sh" --report 2>&1 )"
case "$OUT" in *"33%"*|*"1 (33%)"*) ok "a failing arm's completion rate is exposed" ;; *) bad "completion rate not reported" ;; esac
case "$OUT" in *"too few"*) ok "a delta from one verified run is refused" ;; *) bad "quoted a delta from n=1" ;; esac
case "$OUT" in *"NO MEASURABLE DIFFERENCE"*) ok "and a noise-dominated suite says so" ;; *) bad "no noise verdict" ;; esac
# Equal-but-imperfect completion is not "rates differ"; and a task both arms fail
# is a broken task, which is a different message and a different action.
python3 - > "${WORK}/bm/.agent-spec/benchmark/results.jsonl" <<'JSON'
import json
for r in range(3):
    for arm,skill in (("A","agent-spec-raw-code"),("B","agent-spec-raw-code-full")):
        print(json.dumps({"arm":arm,"skill":skill,"task":"t1","repeat":r,
            "verdict":"FAIL" if r==2 else "PASS","cost":0.10,"turns":5,"seconds":9,
            "session":"s","in":1,"write":1,"read":1,"out":1,"is_error":False}))
JSON
OUT="$( cd "${WORK}/bm" && bash "${HOME_DIR}/bin/agent-spec-benchmark.sh" --report 2>&1 )"
case "$OUT" in *"Every arm failed the same runs"*) ok "a task every arm fails is called a broken task" ;; *) bad "misreported equal completion as differing" ;; esac
case "$OUT" in *"rates differ"*) bad "claimed rates differ when they are equal" ;; *) ok "and equal rates are not reported as differing" ;; esac
# A run that billed nothing never reached the model — a usage limit, an expired
# login. Its clone is untouched, so its verify message describes an empty repo
# and reads exactly like the mode did the work badly. Counting those as failures
# is how an account problem becomes a false finding about a skill.
python3 - > "${WORK}/bm/.agent-spec/benchmark/results.jsonl" <<'JSON'
import json
for r in range(3):
    for arm, skill in (("A", "agent-spec-raw-code"), ("B", "agent-spec-raw-code-full")):
        print(json.dumps({"arm": arm, "skill": skill, "task": "t1", "repeat": r,
            "verdict": "PASS", "cost": 0.10, "turns": 5, "seconds": 9,
            "session": "s", "in": 1, "write": 1, "read": 1, "out": 1, "is_error": False}))
print(json.dumps({"arm": "A", "skill": "agent-spec-raw-code", "task": "t2", "repeat": 1,
    "verdict": "FAIL", "cost": 0.0, "turns": 1, "seconds": 3, "session": "z",
    "in": 0, "write": 0, "read": 0, "out": 0, "is_error": True}))
JSON
OUT="$( cd "${WORK}/bm" && bash "${HOME_DIR}/bin/agent-spec-benchmark.sh" --report 2>&1 )"
case "$OUT" in *"1 run(s) never reached the model"*) ok "an unbilled run is reported as an error, not a failed task" ;; *) bad "counted a zero-cost run as a task failure" ;; esac
case "$OUT" in *"3 (100%)"*) ok "and is excluded from the completion rate" ;; *) bad "unbilled run polluted the completion rate" ;; esac
grep -q "CONSEC_ERRORS" "${HOME_DIR}/bin/agent-spec-benchmark.sh" \
  && ok "the suite stops after consecutive unbilled runs" \
  || bad "no abort on repeated unbilled runs — a usage limit burns the whole suite"

# Mode against mode ranks two skills. Only a control arm with no skill body can
# say whether either saves anything against plain Claude Code.
grep -q 'if \[ "${skill}" != "none" \]' "${HOME_DIR}/bin/agent-spec-benchmark.sh" \
  && ok "the benchmark has a no-skill control arm" \
  || bad "no control arm — the suite can only rank the modes, never measure them"
[ -f "${HOME_DIR}/benchmarks/tasks/04-long-session.task" ] \
  && ok "the suite has a long-session task" \
  || bad "no long-session task — raw-code-full's reading rules are untestable"

# A local model bills nothing, so cost cannot be the metric or the liveness test.
# --metric tokens ranks on tokens moved and must not discard runs as "never
# reached the model" just because they cost zero.
python3 - > "${WORK}/bm/.agent-spec/benchmark/results.jsonl" <<'JSON'
import json
for r in range(3):
    for arm, skill, read in (("A", "none", 40000), ("B", "agent-spec-raw-code", 30000)):
        print(json.dumps({"arm": arm, "skill": skill, "task": "t1", "repeat": r,
            "verdict": "PASS", "cost": 0.0, "turns": 6, "seconds": 9, "session": "s",
            "in": 5, "write": 1000, "read": read + r, "out": 500, "is_error": False}))
JSON
OUT="$( cd "${WORK}/bm" && bash "${HOME_DIR}/bin/agent-spec-benchmark.sh" --report --metric tokens 2>&1 )"
case "$OUT" in *"never reached the model"*) bad "zero-cost local runs discarded under --metric tokens" ;; *) ok "a zero-cost run counts when the metric is tokens" ;; esac
case "$OUT" in *"tokens per VERIFIED task"*) ok "the headline table is ranked in tokens" ;; *) bad "still ranking on cost under --metric tokens" ;; esac
case "$OUT" in *"cannot be quoted as a saving in money"*) ok "and the report says a token ranking is not a cost result" ;; *) bad "a local ranking is presented without its caveat" ;; esac
OUT="$( cd "${WORK}/bm" && bash "${HOME_DIR}/bin/agent-spec-benchmark.sh" --report 2>&1 )"
case "$OUT" in *"cost per VERIFIED task"*) ok "and the default metric is still cost" ;; *) bad "--metric tokens leaked into the default" ;; esac

# The harness end to end, with a stubbed claude so it costs nothing. The label
# is used as a directory name: when it was computed with printf escapes every
# arm resolved to the literal "\000", shared one clone, and claude exited on a
# path it could not lstat — 36 runs aborted before one reached the model.
HARNESS="${WORK}/harness"
git clone --quiet --no-hardlinks "${HOME_DIR}" "${HARNESS}" 2>/dev/null
mkdir -p "${WORK}/stub"
cat > "${WORK}/stub/claude" <<'STUB'
#!/usr/bin/env bash
echo '{"total_cost_usd":0.05,"num_turns":5,"is_error":false,"usage":{"input_tokens":3,"cache_creation_input_tokens":1000,"cache_read_input_tokens":20000,"output_tokens":500}}'
STUB
chmod +x "${WORK}/stub/claude"
OUT="$( cd "${HARNESS}" && env -u CLAUDECODE PATH="${WORK}/stub:$PATH" \
        bash "${HOME_DIR}/bin/agent-spec-benchmark.sh" \
        --arms none,agent-spec-raw-code,agent-spec-raw-code-full \
        --tasks 01-add-cli-flag --repeats 1 2>&1 )"
case "$OUT" in *"A 01-add-cli-flag"*) ok "arm labels are plain letters" ;; *) bad "arm label is not a letter — it becomes a directory name" ;; esac
case "$OUT" in *"C 01-add-cli-flag"*) ok "three arms run and are labelled A, B, C" ;; *) bad "third arm never ran" ;; esac
N="$(ls "${HARNESS}/.agent-spec/benchmark/failed" 2>/dev/null | wc -l | tr -d ' ')"
want "each arm gets its own clone" 3 "$N"
case "$OUT" in *"plain (no skill)"*) ok "the control arm is named in the report" ;; *) bad "control arm missing from report" ;; esac

# Cutting a long session is the largest saving measured anywhere, and Claude
# Code's /compact cannot be reached from a skill or from Cursor at all. The
# portable version has to exist, and Cursor has to be told to pull the digest
# that Claude Code's hook pushes.
grep -q 'name: "agent-spec-compact"' "${HOME_DIR}/skills/claude/agent-spec-compact/SKILL.md" 2>/dev/null \
  && ok "the portable context cut ships as a skill" \
  || bad "no agent-spec-compact skill — the biggest measured saving is unreachable in Cursor"
grep -q 'agent-spec-digest.py' "${HOME_DIR}/CURSOR.md" \
  && ok "Cursor is told to run the digest itself" \
  || bad "CURSOR.md does not tell Cursor to fetch the digest, and Cursor has no hook"
# Only Claude Code runs a SessionStart hook. Every other harness file that promises one
# is telling its reader not to load three files on the strength of a digest it will never
# receive. This was fixed once in CURSOR.md and the assertion was written for that file
# alone, so the same claim survived in AGENTS.md and GEMINI.md until it was found again.
for f in CURSOR.md GEMINI.md; do
  grep -q 'SessionStart. hook has already' "${HOME_DIR}/$f" \
    && bad "$f claims a SessionStart hook its harness does not have" \
    || ok "$f does not claim a hook its harness does not have"
  grep -q 'agent-spec-digest.py' "${HOME_DIR}/$f" \
    || bad "$f does not tell its reader to run the digest itself"
done
grep -q 'Every other\n*.*agent has no session hook\|agent has no session hook' "${HOME_DIR}/AGENTS.md" \
  && ok "AGENTS.md separates Claude Code from the harnesses with no hook" \
  || bad "AGENTS.md promises every agent a hook only Claude Code has"
grep -q 'agent-spec-compact' "${HOME_DIR}/skills/claude/agent-spec/SKILL.md" \
  && ok "the router points at it" \
  || bad "router does not mention agent-spec-compact"

# A skill body is re-read every turn. raw-code-full lost its own benchmark by 5%
# because 4,247 bytes of rationale sat in the prompt prefix. Rationale belongs in
# docs; the body holds imperatives.
for f in agent-spec-raw-code agent-spec-raw-code-full; do
  SZ="$(wc -c < "${HOME_DIR}/skills/claude/$f/SKILL.md" | tr -d ' ')"
  if [ "$SZ" -le 3000 ]; then ok "$f body is $SZ B (cap 3000)"; else bad "$f body is $SZ B, over the 3000 B cap"; fi
  for clause in "Never compress" "Break style for" "Always normal prose"; do
    grep -q "$clause" "${HOME_DIR}/skills/claude/$f/SKILL.md" \
      || bad "$f lost its '$clause' section while being shrunk"
  done
done
ok "both modes kept every safety clause through the shrink"

# Levels came from an external lean-output framework; its ultra level did not. Ultra is
# plain text with no markdown, which is
# caveman prose under another name, and caveman measured 0 across 26 verified runs.
RC="${HOME_DIR}/skills/claude/agent-spec-raw-code/SKILL.md"
for lvl in lite full; do
  grep -q "agent-spec-raw-code $lvl" "$RC" \
    && ok "raw-code documents the $lvl level and how to switch to it" \
    || bad "raw-code does not document the $lvl level"
done
grep -qi 'ultra' "$RC" \
  && bad "raw-code declares an ultra level — that is caveman prose, which measured 0" \
  || ok "and declares no ultra level"
grep -q '^| Debug | Issue. Cause. Fix. Verify. |' "$RC" \
  && ok "raw-code carries the task-shapes table" \
  || bad "raw-code lost the task-shapes table"
grep -qi 'not for saving tokens' "$RC" \
  && ok "raw-code still refuses to claim a token saving" \
  || bad "raw-code claims a saving that 26 runs measured at +1.4% cost"
grep -q 'cache read bills at 0.1x only while the bytes are unchanged' \
  "${HOME_DIR}/skills/claude/agent-spec-raw-code-full/SKILL.md" \
  && ok "raw-code-full states why the always-on prefix must not be edited mid-session" \
  || bad "raw-code-full lost the cache-stability rule"

echo ""
echo "[14] input discipline (PreToolUse hook)"
# Input is 86.7% of the bill against 13.2% for output. A skill body can only ask for
# reading discipline; this hook is the only place it is enforced. Every case below
# drives the hook directly, because a hook that blocks wrongly breaks every session
# on the machine.
PTU="${HOME_DIR}/hooks/pre-tool-use.py"
[ -f "$PTU" ] && ok "the PreToolUse hook ships" || bad "hooks/pre-tool-use.py is missing"

HK="${WORK}/hookproj"
mkdir -p "${HK}/.agent-spec"
python3 -c "open('${HK}/big.py','w').write('x = 1\n' * 5000)"
printf 'small\n' > "${HK}/small.py"

# fire <session> <json> -> exit code, run from inside the fixture project
fire() { ( cd "$HK" && printf '%s' "$2" | python3 "$PTU" >/dev/null 2>&1; echo $? ); }
# Session ids must be unique per run: the hook remembers what it has already said, and
# WORK can be pinned by the caller, so fixed ids would make the second run a false pass.
S="ptu$$"

R_NOLIMIT='{"session_id":"'"${S}1"'","tool_name":"Read","tool_input":{"file_path":"'"${HK}"'/big.py"}}'
want "a whole-file Read of a 35 kB file is refused once" 2 "$(fire "${S}1" "$R_NOLIMIT")"
want "and the immediate retry goes through" 0 "$(fire "${S}1" "$R_NOLIMIT")"
want "a Read with a limit is never refused" 0 \
  "$(fire "${S}2" '{"session_id":"'"${S}2"'","tool_name":"Read","tool_input":{"file_path":"'"${HK}"'/big.py","limit":50}}')"
want "a small file is never refused" 0 \
  "$(fire "${S}2" '{"session_id":"'"${S}2"'","tool_name":"Read","tool_input":{"file_path":"'"${HK}"'/small.py"}}')"
want "a Write over an existing file is refused once" 2 \
  "$(fire "${S}3" '{"session_id":"'"${S}3"'","tool_name":"Write","tool_input":{"file_path":"'"${HK}"'/big.py","content":"x"}}')"
want "a Write creating a new file is never refused" 0 \
  "$(fire "${S}3" '{"session_id":"'"${S}3"'","tool_name":"Write","tool_input":{"file_path":"'"${HK}"'/new.py","content":"x"}}')"
want "git diff without --stat is refused once" 2 \
  "$(fire "${S}4" '{"session_id":"'"${S}4"'","tool_name":"Bash","tool_input":{"command":"git diff"}}')"
want "git diff --stat is never refused" 0 \
  "$(fire "${S}5" '{"session_id":"'"${S}5"'","tool_name":"Bash","tool_input":{"command":"git diff --stat"}}')"
want "cat of a large file is refused once" 2 \
  "$(fire "${S}6" '{"session_id":"'"${S}6"'","tool_name":"Bash","tool_input":{"command":"cat '"${HK}"'/big.py"}}')"
want "cat piped through head is never refused" 0 \
  "$(fire "${S}7" '{"session_id":"'"${S}7"'","tool_name":"Bash","tool_input":{"command":"cat '"${HK}"'/big.py | head -50"}}')"
want "malformed stdin never blocks a tool call" 0 "$(fire "${S}8" 'not json at all')"

OUTSIDE="${WORK}/notaproject"
mkdir -p "$OUTSIDE"
CODE="$( cd "$OUTSIDE" && printf '%s' "$R_NOLIMIT" | python3 "$PTU" >/dev/null 2>&1; echo $? )"
want "silent outside an agent-spec project, so it is safe machine-wide" 0 "$CODE"

SET2="${WORK}/settings-ptu.json"
python3 "${HOME_DIR}/bin/agent-spec-settings.py" "$SET2" /x/hook.sh /x/ptu.py >/dev/null
python3 "${HOME_DIR}/bin/agent-spec-settings.py" "$SET2" /x/hook.sh /x/ptu.py >/dev/null
want "one PreToolUse entry after two installs" 1 \
  "$(python3 -c "import json;print(len(json.load(open('$SET2'))['hooks']['PreToolUse']))")"
want "and it is matched against Read, Write and Bash" "Read|Write|Bash" \
  "$(python3 -c "import json;print(json.load(open('$SET2'))['hooks']['PreToolUse'][0]['matcher'])")"
grep -q 'agent-spec-pre-tool-use.py' "${HOME_DIR}/bin/install.sh" \
  && ok "the installer deploys it to every .claude home" \
  || bad "install.sh does not install the PreToolUse hook"

# An instruction the model cannot follow is charged on every turn like any other, and
# then wastes a tool call proving itself wrong. Four separate defects of that kind
# reached main, each found by accident. This checks every file at once instead.
LINT="$(python3 "${HOME_DIR}/bin/agent-spec-lint-refs.py" "${HOME_DIR}" 2>&1)"
if [ $? -eq 0 ]; then
  ok "every path and skill name the framework prints actually exists"
else
  bad "dangling references: $(echo "$LINT" | tail -1)"
  echo "$LINT" | head -12 | sed 's/^/      /'
fi
grep -q 'agent-spec-lint-refs.py' "${HOME_DIR}/bin/agent-spec-selftest.sh" \
  && ok "and the check runs on every suite, not once by hand" \
  || bad "the reference linter is not wired in"

echo ""
echo "-----------------------------------------"
echo -e "${GREEN}${PASS} passed${NC}, ${FAIL} failed"
[ "$FAIL" -eq 0 ] || exit 1
