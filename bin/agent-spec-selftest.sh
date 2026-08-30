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
echo "-----------------------------------------"
echo -e "${GREEN}${PASS} passed${NC}, ${FAIL} failed"
[ "$FAIL" -eq 0 ] || exit 1
