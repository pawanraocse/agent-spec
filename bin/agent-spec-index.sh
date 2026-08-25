#!/usr/bin/env bash
# =============================================================================
# agent-spec-index.sh — Graphify project indexer
#
# Usage: ./.agent-spec/bin/agent-spec-index [--quiet]
#
# graphify-build.py writes all three artifacts: knowledge-graph.json,
# KNOWLEDGE-GRAPH.md and PROJECT-INDEX.md. This wrapper only locates it and
# reports where the output went.
# =============================================================================
set -euo pipefail

PROJECT_ROOT="$(pwd)"
AGENT_SPEC_HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

BUILDER="${AGENT_SPEC_HOME}/bin/graphify-build.py"
[ -f "${BUILDER}" ] || BUILDER="${PROJECT_ROOT}/.agent-spec/bin/graphify-build.py"
[ -f "${BUILDER}" ] || { echo "✗ graphify-build.py not found" >&2; exit 1; }

command -v python3 >/dev/null 2>&1 || {
  echo "✗ python3 not found. The graph cannot be built by hand — every skill that" >&2
  echo "  queries it would then be trusting a fabricated map." >&2
  exit 1
}

echo -e "${YELLOW}Indexing...${NC}"
# --graphify is accepted and ignored: it was the old flag and is still in docs.
python3 "${BUILDER}" $([ "${1:-}" = "--quiet" ] && echo --quiet)

echo -e "${GREEN}✓${NC} .agent-spec/graph/knowledge-graph.json"
echo -e "${GREEN}✓${NC} .agent-spec/graph/KNOWLEDGE-GRAPH.md"
echo -e "${GREEN}✓${NC} .agent-spec/PROJECT-INDEX.md (only if absent)"
echo ""
echo "Query it instead of reading it:"
echo "  ./.agent-spec/bin/graphify-cli.py query --file <path>"
