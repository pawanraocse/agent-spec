#!/usr/bin/env bash
# Dashboard / aspec_platform slice — ~15s, not full tests/ (278 cases).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONUNBUFFERED=1
python3 -m pytest \
  tests/test_agent_exec.py \
  tests/test_api.py \
  tests/test_api_security.py \
  tests/test_platform_data.py \
  tests/test_platform_db.py \
  tests/test_platform_guard.py \
  -q "$@"
