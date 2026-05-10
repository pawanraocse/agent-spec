#!/usr/bin/env bash
# =============================================================================
# agent-spec-new.sh
# Scaffold a new project and kickoff the SDLC pipeline
# Usage: ./bin/agent-spec-new.sh <project-name>
# =============================================================================

set -euo pipefail

if [ -z "${1:-}" ]; then
  echo "Usage: $0 <project-name>"
  exit 1
fi

PROJECT_NAME="$1"
AGENT_SPEC_HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}╔══════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║      agent-spec new project 🚀           ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════╝${NC}"
echo ""

if [ -d "${PROJECT_NAME}" ]; then
  echo -e "${YELLOW}Warning: Directory '${PROJECT_NAME}' already exists.${NC}"
  read -p "Continue anyway? (y/N) " -n 1 -r
  echo ""
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 1
  fi
else
  mkdir -p "${PROJECT_NAME}"
  echo -e "  ✅ Created directory ${PROJECT_NAME}"
fi

cd "${PROJECT_NAME}"

# 1. Initialize agent-spec in the new directory
echo -e "\n${YELLOW}[1/3] Initializing agent-spec framework...${NC}"
"${AGENT_SPEC_HOME}/bin/agent-spec-init.sh" > /dev/null
echo -e "  ✅ Framework initialized"

# 2. Create the SDLC kickoff file
echo -e "\n${YELLOW}[2/3] Preparing SDLC pipeline...${NC}"
cat > .agent-spec/sdlc/00-RAW-REQUIREMENTS.md << EOF
# Raw Requirements Document

> Put your rough ideas, meeting notes, or customer requests here.
> Then ask your agent to run \`/requirements\` to structure them.

## The Idea
[Describe what you want to build here]

## Target Audience
[Who is this for?]

## Key Features
- Feature 1
- Feature 2
EOF
echo -e "  ✅ Created 00-RAW-REQUIREMENTS.md template"

# 3. Create initial git repo
echo -e "\n${YELLOW}[3/3] Initializing git repository...${NC}"
if command -v git &> /dev/null; then
  git init > /dev/null
  
  cat > .gitignore << EOF
node_modules/
dist/
build/
target/
.env
.DS_Store
EOF
  echo -e "  ✅ Git initialized with default .gitignore"
else
  echo -e "  ⚠️ Git not installed, skipping."
fi

# Done
echo -e "\n${GREEN}╔══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     Project '${PROJECT_NAME}' ready!     ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"
echo ""
echo "Next steps:"
echo "  1. cd ${PROJECT_NAME}"
echo "  2. Edit .agent-spec/sdlc/00-RAW-REQUIREMENTS.md with your idea"
echo "  3. Open your agent and type: /requirements"
echo ""
