#!/usr/bin/env bash
# =============================================================================
# agent-spec-index.sh — Graphify-powered project indexer
# Usage: ./bin/agent-spec-index.sh [--graphify]
# =============================================================================
set -euo pipefail

PROJECT_ROOT="$(pwd)"
OUTPUT_DIR="${PROJECT_ROOT}/.agent-spec/graph"
DATE=$(date '+%Y-%m-%d')
DATETIME=$(date '+%Y-%m-%dT%H:%M:%S')
AGENT_SPEC_HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'

echo -e "${BLUE}╔══════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   agent-spec index (Graphify) 🕸️     ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════╝${NC}"

mkdir -p "${OUTPUT_DIR}"

# --- 1. Run Automated Graphify Builder ---
echo -e "\n${YELLOW}[1/2] Running automated AST/Regex indexer...${NC}"
python3 "${AGENT_SPEC_HOME}/bin/graphify-build.py"

# --- 2. Write KNOWLEDGE-GRAPH.md ---
echo -e "\n${YELLOW}[2/2] Generating KNOWLEDGE-GRAPH.md...${NC}"
cat > "${OUTPUT_DIR}/KNOWLEDGE-GRAPH.md" << MDEOF
# Knowledge Graph — $(basename "${PROJECT_ROOT}")

> 💡 **Max Graphify Mode Active**
> The knowledge-graph.json is populated automatically.
> Agents: Do NOT read this file. Use \`./.agent-spec/bin/graphify-cli.py query --file <target>\` to get blast-radius context instantly.

## Arrow Legend
| Notation | Meaning |
|----------|---------|
| \`A --> B\` | A depends on B |
| \`A -->|owns| B\` | A owns B |
| \`A -.->|optional| B\` | A optionally uses B |

*Managed by agent-spec | Last indexed: ${DATE}*
MDEOF
echo -e "  ✅ Written: KNOWLEDGE-GRAPH.md"

echo -e "\n${GREEN}╔══════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     Graphify indexing complete! 🕸️   ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════╝${NC}"
echo -e "\nFiles: .agent-spec/graph/knowledge-graph.json"
echo -e "       .agent-spec/graph/KNOWLEDGE-GRAPH.md"
echo -e "\nNext: Your AI agent will automatically use the graphify-cli tool to navigate the architecture."
