#!/usr/bin/env bash
# =============================================================================
# agent-spec install
#
# One command to install. The same command to update.
#
#   curl -sSL https://raw.githubusercontent.com/pawanraocse/agent-spec/main/bin/install.sh | bash
#   ./bin/install.sh
#
# By default it does two things:
#   1. Skills, machine-wide — every project on this box gets them, no per-project
#      step. Written to every Claude and Cursor home that exists (see below).
#   2. Project setup in the current directory — .agent-spec/ (constitution, graph,
#      SDLC docs, personas, standards) plus the root agent config files.
#
# An empty directory is treated as a new project: it also gets a raw-requirements
# stub and a git repo, which is what the old agent-spec-new did.
#
# Flags:
#   --skills-only     machine-wide skills, touch nothing in this directory
#   --project-only    this directory only, leave the machine-wide install alone
#   --project-skills  also copy skills into ./.claude/ and ./.cursor/ (team repos
#                     that want the skills committed alongside the code)
#   --lean            skip the 8 SDLC-design skills (api devops hld lld perf prd
#                     requirements tech-spec)
#   --force           overwrite project files that already exist
#
# WSL note: Claude Code reads user-level skills from the HOME of the *process*.
# Inside WSL that is ~/.claude; launched from the Windows app — even when it opens
# a \\wsl.localhost\... folder — it is C:\Users\<you>\.claude. This script writes
# every home it can find, which is why skills otherwise appear in some projects
# and not others. Override the Windows guess with WIN_CLAUDE_HOME.
#
# Restart your agent afterwards. Skills are enumerated at session start.
# =============================================================================
set -eo pipefail

GREEN='\033[0;32m'; BLUE='\033[0;34m'; YELLOW='\033[1;33m'; NC='\033[0m'

PROJECT_ROOT="$(pwd)"
DATETIME=$(date '+%Y-%m-%dT%H:%M:%S')
DATE=$(date '+%Y-%m-%d')

DO_SKILLS="true"; DO_PROJECT="true"; PROJECT_SKILLS="false"
LEAN="false"; FORCE="false"

for arg in "$@"; do
  case "$arg" in
    --skills-only)    DO_PROJECT="false" ;;
    --project-only)   DO_SKILLS="false" ;;
    --project-skills) PROJECT_SKILLS="true" ;;
    --lean)           LEAN="true" ;;
    --force)          FORCE="true" ;;
    -h|--help)        sed -n '3,30p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown argument: $arg" >&2; exit 1 ;;
  esac
done

# --- resolve the framework: a local clone, or a throwaway download when piped ---
if [ -n "${BASH_SOURCE[0]:-}" ] && [ -f "${BASH_SOURCE[0]}" ]; then
  AGENT_SPEC_HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
else
  AGENT_SPEC_HOME="$(mktemp -d)"
  echo -e "${YELLOW}Downloading agent-spec...${NC}"
  curl -sSL "https://github.com/pawanraocse/agent-spec/archive/refs/heads/main.tar.gz" \
    | tar -xz -C "${AGENT_SPEC_HOME}" --strip-components=1
  trap 'rm -rf "${AGENT_SPEC_HOME}"' EXIT
fi

SKILL_SRC="${AGENT_SPEC_HOME}/skills/claude"
[ -d "${SKILL_SRC}" ] || { echo "✗ not found: ${SKILL_SRC}" >&2; exit 1; }

# The SDLC-design skills, held back only under --lean.
LEAN_EXCLUDE="api devops hld lld perf prd requirements tech-spec"

echo -e "${BLUE}agent-spec${NC}"
echo -e "  project: ${PROJECT_ROOT}"
echo -e "  source:  ${AGENT_SPEC_HOME}"
echo ""

# ---------------------------------------------------------------------------
# copy_skills <dest-dir>
# Cursor and the generic agents read the same SKILL.md shape as Claude, so one
# source tree serves all of them.
# ---------------------------------------------------------------------------
copy_skills() {
  local dest="$1" installed=0 skipped=0 name
  mkdir -p "${dest}"
  for dir in "${SKILL_SRC}"/*/; do
    name="$(basename "${dir}")"
    [ -f "${dir}SKILL.md" ] || continue
    if [ "$LEAN" = "true" ] && [[ " ${LEAN_EXCLUDE} " == *" ${name} "* ]]; then
      skipped=$((skipped + 1)); continue
    fi
    mkdir -p "${dest}/${name}"
    cp -r "${dir}." "${dest}/${name}/"
    installed=$((installed + 1))
  done
  echo -e "  ${GREEN}✓${NC} ${installed} skills → ${dest}$([ "$skipped" -gt 0 ] && echo "   (${skipped} excluded)")"
}

# ---------------------------------------------------------------------------
# 1. Machine-wide skills
# ---------------------------------------------------------------------------
if [ "$DO_SKILLS" = "true" ]; then
  echo -e "${YELLOW}Skills (machine-wide)${NC}"

  HOMES=("${HOME}/.claude" "${HOME}/.cursor")
  WIN_HOME="${WIN_CLAUDE_HOME:-/mnt/c/Users/$(id -un)}"
  if [ -d "${WIN_HOME}" ]; then
    [ "${WIN_HOME}/.claude" != "${HOME}/.claude" ] && HOMES+=("${WIN_HOME}/.claude")
    [ -d "${WIN_HOME}/.cursor" ] && HOMES+=("${WIN_HOME}/.cursor")
  fi

  for h in "${HOMES[@]}"; do
    copy_skills "${h}/skills"
  done
  echo ""
fi

[ "$DO_PROJECT" = "true" ] || { echo "Restart your agent to pick the skills up."; exit 0; }

# ---------------------------------------------------------------------------
# 2. Project setup
# ---------------------------------------------------------------------------
# An empty directory means a brand-new project (what agent-spec-new used to do).
IS_NEW="false"
if [ -z "$(ls -A "${PROJECT_ROOT}" 2>/dev/null)" ]; then IS_NEW="true"; fi

echo -e "${YELLOW}Project${NC}"

mkdir -p "${PROJECT_ROOT}/.agent-spec/graph" "${PROJECT_ROOT}/.agent-spec/sdlc"

[ -f "${PROJECT_ROOT}/.agent-spec/CONSTITUTION.md" ] || \
  cp "${AGENT_SPEC_HOME}/templates/project-constitution.md" "${PROJECT_ROOT}/.agent-spec/CONSTITUTION.md"

[ -f "${PROJECT_ROOT}/.agent-spec/TECH-DEBT-REGISTER.md" ] || \
  cp "${AGENT_SPEC_HOME}/context/TECH-DEBT-REGISTER.md" "${PROJECT_ROOT}/.agent-spec/TECH-DEBT-REGISTER.md"

if [ ! -f "${PROJECT_ROOT}/.agent-spec/SESSION-SNAPSHOT.md" ] || [ "$FORCE" = "true" ]; then
  cat > "${PROJECT_ROOT}/.agent-spec/SESSION-SNAPSHOT.md" <<EOF
# Session Snapshot — ${DATETIME}

> Append a dated section after every working session. Never overwrite: the running
> record of corrections and reversed decisions is the point.

## Session Summary
agent-spec installed.

## Current Pipeline Gate
Gate 0: ONBOARDING

## Open Items
- [ ] Run /onboard so the agent learns this project once, instead of every session.

## Next Session: Load These Files
- .agent-spec/PROJECT-INDEX.md
- .agent-spec/graph/KNOWLEDGE-GRAPH.md
- .agent-spec/CONSTITUTION.md
EOF
fi

for folder in personas pipeline rules coding-standards anti-hallucination memory templates; do
  if [ -d "${AGENT_SPEC_HOME}/${folder}" ]; then
    mkdir -p "${PROJECT_ROOT}/.agent-spec/${folder}"
    cp -R "${AGENT_SPEC_HOME}/${folder}/." "${PROJECT_ROOT}/.agent-spec/${folder}/"
  fi
done
echo -e "  ${GREEN}✓${NC} .agent-spec/ (constitution, standards, personas, pipeline, graph)"

# Root agent config: create when missing, otherwise leave the user's file alone and
# just point it at agent-spec.
install_config() {
  local src="$1" dest="$2"
  if [ -f "${dest}" ]; then
    grep -q "agent-spec" "${dest}" || {
      printf '\n---\n<!-- agent-spec: see AGENTS.md and .agent-spec/ -->\n' >> "${dest}"
    }
  elif [ "${src}" != "${dest}" ]; then
    cp "${src}" "${dest}"
  fi
}
for f in AGENTS.md CLAUDE.md GEMINI.md CURSOR.md COPILOT.md; do
  install_config "${AGENT_SPEC_HOME}/${f}" "${PROJECT_ROOT}/${f}"
done
echo -e "  ${GREEN}✓${NC} agent config files (AGENTS, CLAUDE, GEMINI, CURSOR, COPILOT)"

# Cursor always-on rules. One .mdc, not 27 — everything else is an on-demand skill.
mkdir -p "${PROJECT_ROOT}/.cursor/rules"
if [ ! -f "${PROJECT_ROOT}/.cursor/rules/agent-spec.mdc" ] || [ "$FORCE" = "true" ]; then
  {
    echo "---"
    echo "description: agent-spec standing rules — session protocol, personas, hard stops."
    echo "alwaysApply: true"
    echo "---"
    echo ""
    cat "${AGENT_SPEC_HOME}/CURSOR.md"
  } > "${PROJECT_ROOT}/.cursor/rules/agent-spec.mdc"
fi
echo -e "  ${GREEN}✓${NC} .cursor/rules/agent-spec.mdc"

# Flat single-file formats.
for pair in ".windsurfrules:.windsurfrules" ".github/copilot-instructions.md:.github/copilot-instructions.md"; do
  src="${AGENT_SPEC_HOME}/${pair%%:*}"; dest="${PROJECT_ROOT}/${pair##*:}"
  [ -f "${src}" ] || continue
  [ "${src}" = "${dest}" ] && continue
  if [ ! -f "${dest}" ] || [ "$FORCE" = "true" ]; then
    mkdir -p "$(dirname "${dest}")"; cp "${src}" "${dest}"
  fi
done
echo -e "  ${GREEN}✓${NC} .windsurfrules, .github/copilot-instructions.md"

# Per-project skill copies: off by default — the machine-wide install already
# covers every project. Opt in for repos that want them committed.
if [ "$PROJECT_SKILLS" = "true" ]; then
  copy_skills "${PROJECT_ROOT}/.claude/skills"
  copy_skills "${PROJECT_ROOT}/.cursor/skills"
  copy_skills "${PROJECT_ROOT}/.agents/skills"
fi

# Framework binaries, extensionless — these are the CLI the skills call.
mkdir -p "${PROJECT_ROOT}/.agent-spec/bin"
cp "${AGENT_SPEC_HOME}/bin/agent-spec-index.sh" "${PROJECT_ROOT}/.agent-spec/bin/agent-spec-index"
cp "${AGENT_SPEC_HOME}/bin/graphify-build.py"   "${PROJECT_ROOT}/.agent-spec/bin/graphify-build.py"
cp "${AGENT_SPEC_HOME}/bin/graphify-cli.py"     "${PROJECT_ROOT}/.agent-spec/bin/graphify-cli.py"
chmod +x "${PROJECT_ROOT}/.agent-spec/bin/"*
echo -e "  ${GREEN}✓${NC} .agent-spec/bin/ (agent-spec-index, graphify-cli.py, graphify-build.py)"

# New project: the raw-requirements stub and a git repo.
if [ "$IS_NEW" = "true" ]; then
  cat > "${PROJECT_ROOT}/.agent-spec/sdlc/00-RAW-REQUIREMENTS.md" <<'EOF'
# Raw Requirements

> Rough ideas, meeting notes, customer requests. Anything goes here.
> Then run /requirements to structure it.

## The Idea

## Who It Is For

## Key Features
-
EOF
  if command -v git >/dev/null 2>&1 && [ ! -d "${PROJECT_ROOT}/.git" ]; then
    git init -q "${PROJECT_ROOT}"
    printf 'node_modules/\ndist/\nbuild/\ntarget/\n.env\n.DS_Store\n' > "${PROJECT_ROOT}/.gitignore"
  fi
  echo -e "  ${GREEN}✓${NC} new project: 00-RAW-REQUIREMENTS.md + git"
fi

# Build the dependency graph and PROJECT-INDEX.md.
if command -v python3 >/dev/null 2>&1; then
  python3 "${PROJECT_ROOT}/.agent-spec/bin/graphify-build.py" >/dev/null 2>&1 \
    && echo -e "  ${GREEN}✓${NC} indexed: .agent-spec/graph/ + PROJECT-INDEX.md" \
    || echo -e "  ⚠️  indexer failed — run ./.agent-spec/bin/agent-spec-index later"
else
  echo -e "  ⚠️  python3 not found — run ./.agent-spec/bin/agent-spec-index later"
fi

# Onboarding marker: set while the constitution is still the untouched template,
# so the first session runs /onboard and learns the project once.
if diff -q "${AGENT_SPEC_HOME}/templates/project-constitution.md" \
           "${PROJECT_ROOT}/.agent-spec/CONSTITUTION.md" >/dev/null 2>&1; then
  echo "Created ${DATE}. Delete this once /onboard has run." \
    > "${PROJECT_ROOT}/.agent-spec/.onboarding-needed"
  NEEDS_ONBOARD="true"
else
  rm -f "${PROJECT_ROOT}/.agent-spec/.onboarding-needed"
  NEEDS_ONBOARD="false"
fi

echo ""
echo -e "${GREEN}Done.${NC}"
echo ""
echo "  1. Restart your agent — skills are enumerated at session start."
if [ "$NEEDS_ONBOARD" = "true" ]; then
  echo "  2. Type /onboard. It reads the graph, writes PROJECT-INDEX.md and"
  echo "     CONSTITUTION.md from what is actually in this repo, and never runs again."
else
  echo "  2. Already onboarded — CONSTITUTION.md is customised, so /onboard is skipped."
fi
echo ""
echo "  Update later: re-run this exact command."
echo ""
