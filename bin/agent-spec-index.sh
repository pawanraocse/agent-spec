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

# --- 1. Detect tech stack ---
echo -e "\n${YELLOW}[1/4] Detecting tech stack...${NC}"
STACK_DETAILS="Unknown"

[ -f "${PROJECT_ROOT}/pom.xml" ] && STACK_DETAILS="Java (Maven)"
grep -q "spring-boot" "${PROJECT_ROOT}/pom.xml" 2>/dev/null && STACK_DETAILS="Java Spring Boot"
[ -f "${PROJECT_ROOT}/package.json" ] && {
  grep -q "angular" "${PROJECT_ROOT}/package.json" 2>/dev/null \
    && STACK_DETAILS="${STACK_DETAILS} + Angular" \
    || STACK_DETAILS="${STACK_DETAILS} + Node.js"
}
[ -f "${PROJECT_ROOT}/requirements.txt" ] && STACK_DETAILS="Python"
[ -f "${PROJECT_ROOT}/go.mod" ] && STACK_DETAILS="Go"
echo -e "  ✅ Detected: ${STACK_DETAILS}"

# --- 2. Count files ---
echo -e "\n${YELLOW}[2/4] Scanning project files...${NC}"
JAVA_COUNT=$( (find "${PROJECT_ROOT}" -type f -name "*.java" 2>/dev/null || true) | grep -vE "(/node_modules/|/target/|/dist/|/build/|/\.git/|/\.idea/|/\.venv/)" | wc -l | tr -d ' ' || true )
TS_COUNT=$( (find "${PROJECT_ROOT}" -type f -name "*.ts" 2>/dev/null || true) | grep -vE "(/node_modules/|/target/|/dist/|/build/|/\.git/|/\.idea/|/\.venv/)" | wc -l | tr -d ' ' || true )
TEST_COUNT=$( (find "${PROJECT_ROOT}" -type f \( -name "*Test*.java" -o -name "*.spec.ts" \) 2>/dev/null || true) | grep -vE "(/node_modules/|/target/|/dist/|/build/|/\.git/|/\.idea/|/\.venv/)" | wc -l | tr -d ' ' || true )
echo -e "  Java: ${JAVA_COUNT} | TypeScript: ${TS_COUNT} | Tests: ${TEST_COUNT}"

# --- 3. Write knowledge-graph.json ---
echo -e "\n${YELLOW}[3/4] Writing knowledge-graph.json...${NC}"
cat > "${OUTPUT_DIR}/knowledge-graph.json" << GRAPHEOF
{
  "version": "1.0",
  "project": "$(basename "${PROJECT_ROOT}")",
  "generated": "${DATETIME}",
  "generator": "agent-spec-index v1.0.0",
  "tech_stack": "${STACK_DETAILS}",
  "stats": {
    "java_files": ${JAVA_COUNT},
    "ts_files": ${TS_COUNT},
    "test_files": ${TEST_COUNT}
  },
  "nodes": [],
  "edges": [],
  "note": "Agent should populate nodes/edges via /index-project skill"
}
GRAPHEOF
echo -e "  ✅ Written: knowledge-graph.json"

# --- 4. Write KNOWLEDGE-GRAPH.md ---
echo -e "\n${YELLOW}[4/4] Generating KNOWLEDGE-GRAPH.md...${NC}"
cat > "${OUTPUT_DIR}/KNOWLEDGE-GRAPH.md" << MDEOF
# Knowledge Graph — $(basename "${PROJECT_ROOT}")

**Stack**: ${STACK_DETAILS} | **Indexed**: ${DATE} | **Files**: Java=${JAVA_COUNT} TS=${TS_COUNT} Tests=${TEST_COUNT}

## Architecture Diagram

\`\`\`mermaid
graph TD
  ROOT["$(basename "${PROJECT_ROOT}")<br/>${STACK_DETAILS}"]
\`\`\`

> 💡 Ask your agent: *"Update the knowledge graph based on the project structure"*
> Or run the \`/index-project\` skill to have the agent fill this in.

## Node Inventory
| Node | Type | Path | Updated |
|------|------|------|---------|
| _(run /index-project to populate)_ | | | ${DATE} |

## Arrow Legend
| Notation | Meaning |
|----------|---------|
| \`A --> B\` | A depends on B |
| \`A -->|owns| B\` | A owns B |
| \`A -->|uses| B\` | A uses B at runtime |
| \`A -.->|optional| B\` | A optionally uses B |

*Managed by agent-spec | Last indexed: ${DATE}*
MDEOF
echo -e "  ✅ Written: KNOWLEDGE-GRAPH.md"

echo -e "\n${GREEN}╔══════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     Graphify indexing complete! 🕸️   ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════╝${NC}"
echo -e "\nFiles: .agent-spec/graph/knowledge-graph.json"
echo -e "       .agent-spec/graph/KNOWLEDGE-GRAPH.md"
echo -e "\nNext: Run /index-project in your agent to populate the graph"
