#!/usr/bin/env bash
# H-002: every gate in one run — pytest, the selftest, reference lint, tsc, vitest and the
# UI gzip budget. CI runs the same script, so a green local run means a green CI run.
#   bin/agent-spec-check-all.sh            all gates
#   SKIP_UI=1 bin/agent-spec-check-all.sh  Python gates only (no Node on this machine)
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
fail=0
step() {
  local name="$1"; shift
  local log
  log="$(mktemp)"
  if "$@" >"$log" 2>&1; then
    echo "  ok   $name"
  else
    echo "  FAIL $name"
    tail -40 "$log" | sed 's/^/       /'
    fail=$((fail + 1))
  fi
  rm -f "$log"
}

echo "== agent-spec check-all"
step "pytest"        python3 -m pytest -q tests
step "selftest"      bash bin/agent-spec-selftest.sh
step "lint-refs"     python3 bin/agent-spec-lint-refs.py
step "project copy"  bash -c 'diff -rq --exclude=__pycache__ bin/aspec_platform .agent-spec/bin/aspec_platform 2>/dev/null || [ ! -d .agent-spec/bin/aspec_platform ]'
if [ "${SKIP_UI:-0}" != "1" ]; then
  if [ ! -d ui-src/node_modules ]; then
    step "npm ci"    bash -c 'cd ui-src && npm ci --no-audit --no-fund'
  fi
  step "tsc"           bash -c 'cd ui-src && npx tsc --noEmit -p .'
  step "vitest"        bash -c 'cd ui-src && npx vitest run'
  step "build+budget"  bash -c 'cd ui-src && npm run -s build'
fi
if [ "$fail" -eq 0 ]; then
  echo "All gates green."
else
  echo "$fail gate(s) failed."
fi
exit "$fail"
