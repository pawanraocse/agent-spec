#!/usr/bin/env bash
# =============================================================================
# algosec-agent-spec — Cursor-only installer (algosec-lean style)
#
#   ./install.sh                         # skills → ~/.cursor/skills (+ harness on this repo;
#                                        #   refreshes any previously --register'd workspaces)
#   ./install.sh --register <workspace>  # above + project harness; remember workspace
#   ./install.sh --register-here         # same as --register, using the git root of cwd (or cwd)
#   ./install.sh --project-only          # harness for cwd only (no global skills)
#   ./install.sh --skills-only           # global skills only (no project harness)
#   ./install.sh --lean                  # skip SDLC design skills
#   ./install.sh --force                 # overwrite preserved project files (see docs)
#   ./install.sh --force-reindex         # rebuild graph even if present
#   ./install.sh --project-skills        # also copy skills into <workspace>/.cursor/skills
#
# Upgrade vs preserve: docs/QUICKSTART.md.
# Never modifies .env or secrets. No git init.
# =============================================================================
set -eo pipefail

GREEN='\033[0;32m'; BLUE='\033[0;34m'; YELLOW='\033[1;33m'; NC='\033[0m'

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERSION="$(cat "${REPO_DIR}/VERSION" 2>/dev/null || echo '1.0.0')"
# Prefer system python3 — asdf/pyenv shims can return 126 on freshly written scripts.
if [ -x /usr/bin/python3 ]; then
  PYTHON=/usr/bin/python3
elif command -v python3 >/dev/null 2>&1; then
  PYTHON="$(command -v python3)"
else
  PYTHON=""
fi
SKILL_SRC="${REPO_DIR}/skills"
CURSOR_SKILLS="${HOME}/.cursor/skills"
if [ -n "${WIN_CURSOR_HOME:-}" ] && [ -d "${WIN_CURSOR_HOME}/.cursor" ]; then
  CURSOR_SKILLS="${WIN_CURSOR_HOME}/.cursor/skills"
fi
PROJECTS_FILE="${CURSOR_SKILLS}/.algosec-agent-spec-projects"
ROOT_MARKER="${CURSOR_SKILLS}/.algosec-agent-spec-root"

DO_SKILLS="true"
DO_PROJECT="false"
PROJECT_SKILLS="false"
LEAN="false"
FORCE="false"
FORCE_REINDEX="false"
SKILLS_ONLY="false"
declare -a REGISTER_PROJECTS=()

LEAN_EXCLUDE="agent-spec-intent agent-spec-hld agent-spec-lld agent-spec-prd agent-spec-requirements agent-spec-tech-spec"
LEGACY_SKILLS="api architect data devops hld implement index-project investigate lld \
onboard perf prd qa query-graph raw-code refactor requirements review reviewer sdlc \
security self-review snapshot solid-check tech-spec testing trim-noise dense verbose \
validation writer debt agent-spec-dense agent-spec-trim-noise"

usage() {
  sed -n '3,19p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

while [ $# -gt 0 ]; do
  case "$1" in
    --skills-only)    DO_PROJECT="false"; DO_SKILLS="true"; SKILLS_ONLY="true"; shift ;;
    --project-only)   DO_SKILLS="false"; DO_PROJECT="true"; shift ;;
    --project-skills) PROJECT_SKILLS="true"; shift ;;
    --lean)           LEAN="true"; shift ;;
    --force)          FORCE="true"; shift ;;
    --force-reindex)  FORCE_REINDEX="true"; shift ;;
    --register)
      shift
      [ $# -gt 0 ] || { echo "ERROR: --register requires a workspace path" >&2; exit 1; }
      REGISTER_PROJECTS+=("$1")
      DO_PROJECT="true"
      shift
      ;;
    --register=*)
      REGISTER_PROJECTS+=("${1#--register=}")
      DO_PROJECT="true"
      shift
      ;;
    --register-here)
      # Git root of where you are standing, else the directory itself (works without git).
      REGISTER_PROJECTS+=("$(git -C "$PWD" rev-parse --show-toplevel 2>/dev/null || pwd)")
      DO_PROJECT="true"
      shift
      ;;
    -h|--help) usage; exit 0 ;;
    *)
      if [ -d "$1" ]; then
        REGISTER_PROJECTS+=("$1")
        DO_PROJECT="true"
        shift
      else
        echo "unknown argument: $1" >&2; usage; exit 1
      fi
      ;;
  esac
done

# Default: skills only when no register/project-only
if [ "$DO_PROJECT" = "false" ] && [ ${#REGISTER_PROJECTS[@]} -eq 0 ]; then
  DO_SKILLS="true"
fi

[ -d "${SKILL_SRC}" ] || { echo "✗ not found: ${SKILL_SRC}" >&2; exit 1; }

echo -e "${BLUE}algosec-agent-spec${NC} v${VERSION} (Cursor-only)"
echo -e "  package: ${REPO_DIR}"
echo ""
# Package CLIs (doctor/selftest invoke ./bin/* on the clone)
chmod +x "${REPO_DIR}/bin/"* 2>/dev/null || true


prune_legacy() {
  local dest="$1" removed=0
  [ -d "${dest}" ] || return 0
  for name in ${LEGACY_SKILLS}; do
    if [ -f "${dest}/${name}/SKILL.md" ] \
       && grep -q "^name: \"${name}\"$" "${dest}/${name}/SKILL.md" 2>/dev/null; then
      rm -rf "${dest:?}/${name}"
      removed=$((removed + 1))
    fi
  done
  [ "$removed" -gt 0 ] && echo -e "  ${GREEN}✓${NC} removed ${removed} legacy unprefixed skills from ${dest}"
  return 0
}

copy_skills() {
  local dest="$1" installed=0 skipped=0 name
  mkdir -p "${dest}"
  prune_legacy "${dest}"
  for dir in "${SKILL_SRC}"/*/; do
    [ -d "$dir" ] || continue
    name="$(basename "$dir")"
    case " ${LEAN_EXCLUDE} " in
      *" ${name} "*)
        if [ "$LEAN" = "true" ]; then
          [ -d "${dest}/${name}" ] && rm -rf "${dest:?}/${name}"
          skipped=$((skipped + 1))
          continue
        fi
        ;;
    esac
    mkdir -p "${dest}/${name}"
    # Prefer rsync; fall back to cp
    if command -v rsync >/dev/null 2>&1; then
      rsync -a --delete "${dir}" "${dest}/${name}/"
    else
      rm -rf "${dest:?}/${name}"
      mkdir -p "${dest}/${name}"
      cp -R "${dir}." "${dest}/${name}/"
    fi
    installed=$((installed + 1))
  done
  echo -e "  ${GREEN}✓${NC} ${installed} skills → ${dest}$([ "$skipped" -gt 0 ] && echo "   (${skipped} lean-excluded)")"
}

register_workspace() {
  local root="$1"
  root="$(cd "$root" && pwd)"
  mkdir -p "${CURSOR_SKILLS}"
  touch "${PROJECTS_FILE}"
  if ! grep -Fxq "$root" "${PROJECTS_FILE}" 2>/dev/null; then
    printf '%s\n' "$root" >> "${PROJECTS_FILE}"
    echo -e "  ${GREEN}✓${NC} registered ${root}"
  else
    echo -e "  ${GREEN}✓${NC} already registered ${root}"
  fi
}

# --- merge hooks.json: keep foreign handlers; replace ours by marker ---
merge_hooks_json() {
  local project_root="$1"
  local hooks_dir="${project_root}/.cursor/hooks"
  local hooks_json="${project_root}/.cursor/hooks.json"
  mkdir -p "${hooks_dir}"
  cp "${REPO_DIR}/hooks/cursor-session-start.py" "${hooks_dir}/agent-spec-session-start.py"
  cp "${REPO_DIR}/hooks/cursor-pre-tool-use.py" "${hooks_dir}/agent-spec-pre-tool-use.py"
  cp "${REPO_DIR}/hooks/cursor-session-end.py" "${hooks_dir}/agent-spec-session-end.py"
  cp "${REPO_DIR}/hooks/cursor-event.py" "${hooks_dir}/agent-spec-cursor-event.py"
  cp "${REPO_DIR}/bin/agent-spec-digest.py" "${hooks_dir}/agent-spec-digest.py"
  chmod +x "${hooks_dir}/agent-spec-session-start.py" \
           "${hooks_dir}/agent-spec-pre-tool-use.py" \
           "${hooks_dir}/agent-spec-session-end.py" \
           "${hooks_dir}/agent-spec-cursor-event.py" \
           "${hooks_dir}/agent-spec-digest.py"

  if [ -z "${PYTHON}" ]; then
    echo -e "  ⚠️  python3 missing — wrote hook scripts but not hooks.json"
    return 0
  fi

  if ! "${PYTHON}" "${REPO_DIR}/hooks/merge-hooks-json.py" "${hooks_json}"; then
    echo -e "  ⚠️  failed to merge hooks.json" >&2
    return 1
  fi
  echo -e "  ${GREEN}✓${NC} .cursor/hooks.json (sessionStart + preToolUse + sessionEnd/stop receipt, marked)"
}

write_mdc() {
  local project_root="$1"
  mkdir -p "${project_root}/.cursor/rules"
  {
    echo "---"
    echo "description: algosec-agent-spec standing rules — session protocol, personas, hard stops."
    echo "alwaysApply: true"
    echo "globs: [\"**/*\"]"
    echo "version: ${VERSION}"
    echo "---"
    echo ""
    cat "${REPO_DIR}/CURSOR.md"
  } > "${project_root}/.cursor/rules/agent-spec.mdc"
  echo -e "  ${GREEN}✓${NC} .cursor/rules/agent-spec.mdc (from CURSOR.md v${VERSION})"
}

# --- shared team facts (T-053) ---------------------------------------------------------
# TEAM_FACTS_REPO: a git URL or a local directory of fact files. A submodule already checked
# out at .agent-spec/team-facts/ is used as-is. Fail-open: a bad URL or offline run warns and
# never stops the registration.
sync_team_facts() {
  local project_root="$1"
  local team_dir="${project_root}/.agent-spec/team-facts"
  local src_cache="${project_root}/.agent-spec/.team-facts-src"
  local memory="${project_root}/.agent-spec/bin/agent-spec-memory.py"
  [ -n "${PYTHON}" ] || return 0
  # The package clone is harnessed on every register but is not a team project.
  [ "$(cd "${project_root}" && pwd)" = "$(cd "${REPO_DIR}" && pwd)" ] && return 0

  if [ -e "${team_dir}/.git" ]; then
    echo -e "  ${GREEN}✓${NC} team facts: submodule at .agent-spec/team-facts used as-is"
    return 0
  fi
  [ -n "${TEAM_FACTS_REPO:-}" ] || return 0

  local src="${TEAM_FACTS_REPO}"
  if [ ! -d "${src}" ]; then
    if ! command -v git >/dev/null 2>&1; then
      echo -e "  ⚠️  team facts: git not found — skipped (TEAM_FACTS_REPO=${src})"
      return 0
    fi
    if [ -d "${src_cache}/.git" ]; then
      git -C "${src_cache}" pull --ff-only -q >/dev/null 2>&1 || true
    else
      rm -rf "${src_cache}"
      if ! git clone --depth 1 -q "${src}" "${src_cache}" >/dev/null 2>&1; then
        echo -e "  ⚠️  team facts: could not clone ${src} — skipped"
        return 0
      fi
    fi
    src="${src_cache}"
  fi
  if ( cd "${project_root}" && "${PYTHON}" "${memory}" merge-team "${src}" ); then
    echo -e "  ${GREEN}✓${NC} team facts merged into .agent-spec/team-facts/"
  else
    echo -e "  ⚠️  team facts: merge failed — skipped"
  fi
}

install_agents() {
  local project_root="$1"
  mkdir -p "${project_root}/.cursor/agents"
  if [ -d "${REPO_DIR}/agents" ]; then
    cp "${REPO_DIR}/agents/"*.md "${project_root}/.cursor/agents/" 2>/dev/null || true
    if [ -d "${REPO_DIR}/agents/handoffs" ]; then
      # Typed handoff schemas (DV-057): the dashboard reads them; Cursor ignores them.
      mkdir -p "${project_root}/.cursor/agents/handoffs"
      cp "${REPO_DIR}/agents/handoffs/"*.json "${project_root}/.cursor/agents/handoffs/" 2>/dev/null || true
    fi
    echo -e "  ${GREEN}✓${NC} .cursor/agents/ ($(ls "${REPO_DIR}/agents"/*.md 2>/dev/null | wc -l | tr -d ' ') subagents)"
  fi
}

install_git_hooks() {
  local project_root="$1"
  if [ -n "${PYTHON}" ]; then
    if "${PYTHON}" "${REPO_DIR}/hooks/manage-git-hooks.py" install "${project_root}"; then
      if [ -d "${project_root}/.git" ] || [ -f "${project_root}/.git" ]; then
        echo -e "  ${GREEN}✓${NC} .git/hooks/ (post-checkout + post-merge + post-rewrite auto-indexing)"
      fi
    fi
  fi
}

install_project() {
  local project_root="$1"
  project_root="$(cd "$project_root" && pwd)"
  local DATETIME DATE
  DATETIME=$(date '+%Y-%m-%dT%H:%M:%S')
  DATE=$(date '+%Y-%m-%d')

  echo -e "${YELLOW}Project${NC} ${project_root}"

  # Onboarding is pending until the constitution exists and is no longer the template (the
  # template carries 8 "[e.g.," placeholders; 4+ left means untouched). The digest turns the
  # flag into a "run /agent-spec-onboard now" line. A lightly edited constitution never re-flags.
  local NEEDS_ONBOARDING="false" PLACEHOLDERS=0
  if [ ! -f "${project_root}/.agent-spec/CONSTITUTION.md" ]; then
    NEEDS_ONBOARDING="true"
  else
    PLACEHOLDERS="$(grep -c '\[e\.g\.,' "${project_root}/.agent-spec/CONSTITUTION.md" 2>/dev/null || true)"
    [ "${PLACEHOLDERS:-0}" -ge 4 ] && NEEDS_ONBOARDING="true"
  fi

  mkdir -p "${project_root}/.agent-spec/graph" "${project_root}/.agent-spec/sdlc" \
           "${project_root}/.agent-spec/memory/facts" "${project_root}/.agent-spec/memory/snapshots"

  # Preserve constitution / snapshot / debt unless --force
  if [ ! -f "${project_root}/.agent-spec/CONSTITUTION.md" ] || [ "$FORCE" = "true" ]; then
    if [ ! -f "${project_root}/.agent-spec/CONSTITUTION.md" ] || [ "$FORCE" = "true" ]; then
      [ -f "${project_root}/.agent-spec/CONSTITUTION.md" ] || \
        cp "${REPO_DIR}/templates/project-constitution.md" "${project_root}/.agent-spec/CONSTITUTION.md"
      if [ "$FORCE" = "true" ] && [ -f "${REPO_DIR}/templates/project-constitution.md" ]; then
        cp "${REPO_DIR}/templates/project-constitution.md" "${project_root}/.agent-spec/CONSTITUTION.md"
      fi
    fi
  fi

  if [ ! -f "${project_root}/.agent-spec/TECH-DEBT-REGISTER.md" ]; then
    cp "${REPO_DIR}/context/TECH-DEBT-REGISTER.md" "${project_root}/.agent-spec/TECH-DEBT-REGISTER.md"
  fi

  if [ ! -f "${project_root}/.agent-spec/SESSION-SNAPSHOT.md" ]; then
    cat > "${project_root}/.agent-spec/SESSION-SNAPSHOT.md" <<EOF
# Session Snapshot — ${DATETIME}

> Append a dated section after every working session. Never overwrite.

## Session Summary
algosec-agent-spec installed.

## Current Pipeline Gate
Gate 0: ONBOARDING

## Open Items
- [ ] Run /agent-spec-onboard so the agent learns this project once.

## Next Session: Load These Files
- .agent-spec/PROJECT-INDEX.md
- .agent-spec/graph/KNOWLEDGE-GRAPH.md
- .agent-spec/CONSTITUTION.md
EOF
  fi

  # Framework-owned copies — always refresh
  for folder in personas pipeline rules coding-standards anti-hallucination memory templates; do
    if [ -d "${REPO_DIR}/${folder}" ]; then
      mkdir -p "${project_root}/.agent-spec/${folder}"
      cp -R "${REPO_DIR}/${folder}/." "${project_root}/.agent-spec/${folder}/"
    fi
  done
  echo -e "  ${GREEN}✓${NC} .agent-spec/ framework content (personas, standards, …)"

  # Thin AGENTS.md — create if missing; if present without marker, append pointer
  if [ ! -f "${project_root}/AGENTS.md" ]; then
    cp "${REPO_DIR}/AGENTS.md" "${project_root}/AGENTS.md"
  elif ! grep -q "algosec-agent-spec\|agent-spec" "${project_root}/AGENTS.md" 2>/dev/null; then
    printf '\n---\n<!-- algosec-agent-spec: see .cursor/rules/agent-spec.mdc and .agent-spec/ -->\n' \
      >> "${project_root}/AGENTS.md"
  fi

  write_mdc "${project_root}"
  merge_hooks_json "${project_root}"
  install_agents "${project_root}"
  install_git_hooks "${project_root}"

  # Bins — always refresh
  mkdir -p "${project_root}/.agent-spec/bin"
  cp "${REPO_DIR}/bin/agent-spec-index.sh" "${project_root}/.agent-spec/bin/agent-spec-index"
  cp "${REPO_DIR}/bin/graphify-build.py"   "${project_root}/.agent-spec/bin/graphify-build.py"
  cp "${REPO_DIR}/bin/graphify-cli.py"     "${project_root}/.agent-spec/bin/graphify-cli.py"
  cp "${REPO_DIR}/bin/graphify-mesh.py"    "${project_root}/.agent-spec/bin/graphify-mesh.py"
  cp "${REPO_DIR}/bin/agent-spec-digest.py" "${project_root}/.agent-spec/bin/agent-spec-digest.py"
  cp "${REPO_DIR}/bin/agent-spec-gate.py"   "${project_root}/.agent-spec/bin/agent-spec-gate.py"
  cp "${REPO_DIR}/bin/agent-spec-memory.py" "${project_root}/.agent-spec/bin/agent-spec-memory.py"
  cp "${REPO_DIR}/bin/agent-spec-tokens.py" "${project_root}/.agent-spec/bin/agent-spec-tokens.py"
  cp "${REPO_DIR}/bin/agent-spec-doctor.py" "${project_root}/.agent-spec/bin/agent-spec-doctor.py"
  cp "${REPO_DIR}/bin/agent-spec-receipt.py" "${project_root}/.agent-spec/bin/agent-spec-receipt.py"
  cp "${REPO_DIR}/bin/agent-spec-roi.py"     "${project_root}/.agent-spec/bin/agent-spec-roi.py"
  # Phase 2 platform (stdlib only, DEC-12): backlog/blast-radius/run CLIs + data layer package
  for b in agent-spec-backlog.py agent-spec-blast-radius agent-spec-run.py agent-spec-platform.py agent-spec-mcp-filter.py; do
    cp "${REPO_DIR}/bin/${b}" "${project_root}/.agent-spec/bin/${b}"
  done
  rm -rf "${project_root}/.agent-spec/bin/aspec_platform"
  cp -R "${REPO_DIR}/bin/aspec_platform" "${project_root}/.agent-spec/bin/aspec_platform"
  rm -rf "${project_root}/.agent-spec/bin/aspec_platform/__pycache__"
  chmod +x "${project_root}/.agent-spec/bin/"*
  sync_team_facts "${project_root}"
  echo -e "  ${GREEN}✓${NC} .agent-spec/bin/"

  if [ "$NEEDS_ONBOARDING" = "true" ]; then
    touch "${project_root}/.agent-spec/.onboarding-needed"
    echo -e "  ${GREEN}✓${NC} onboarding pending (.agent-spec/.onboarding-needed) — run /agent-spec-onboard"
  fi

  if [ "$PROJECT_SKILLS" = "true" ]; then
    copy_skills "${project_root}/.cursor/skills"
  fi

  # Index graph unless present (preserve) or --force-reindex
  if command -v python3 >/dev/null 2>&1 || [ -x /usr/bin/python3 ]; then
    PY="${PYTHON:-python3}"
    [ -x /usr/bin/python3 ] && PY=/usr/bin/python3
    if [ "$FORCE_REINDEX" = "true" ] || [ ! -f "${project_root}/.agent-spec/graph/knowledge-graph.json" ]; then
      ( cd "${project_root}" && "${PY}" ./.agent-spec/bin/graphify-build.py >/dev/null 2>&1 ) \
        && echo -e "  ${GREEN}✓${NC} indexed graph + PROJECT-INDEX.md" \
        || echo -e "  ⚠️  indexer failed — run ./.agent-spec/bin/agent-spec-index later"
    else
      echo -e "  ${GREEN}✓${NC} graph preserved (use --force-reindex to rebuild)"
    fi
  else
    echo -e "  ⚠️  python3 not found — skip index"
  fi
}

# ---------------------------------------------------------------------------
# 1. Machine-wide skills → ~/.cursor/skills  (default; same as algosec-lean)
# ---------------------------------------------------------------------------
if [ "$DO_SKILLS" = "true" ]; then
  echo -e "${YELLOW}Skills → ${CURSOR_SKILLS}${NC}"
  mkdir -p "${CURSOR_SKILLS}"
  copy_skills "${CURSOR_SKILLS}"
  printf '%s\n' "${REPO_DIR}" > "${ROOT_MARKER}"
  echo -e "  ${GREEN}✓${NC} ${ROOT_MARKER}"
  echo ""
fi

# ---------------------------------------------------------------------------
# 2. Project harness
#    Bare ./install.sh  → this package repo + every previously registered workspace
#    --register <ws>    → register ws, then same refresh
#    --project-only     → cwd only
#    --skills-only      → skip harness
# ---------------------------------------------------------------------------
declare -a TARGETS=()
SKIP_HARNESS="false"

if [ "${SKILLS_ONLY}" = "true" ]; then
  SKIP_HARNESS="true"
fi

if [ "$SKIP_HARNESS" = "false" ]; then
  if [ "$DO_PROJECT" = "true" ] && [ ${#REGISTER_PROJECTS[@]} -eq 0 ]; then
    # --project-only: cwd
    TARGETS+=("$(pwd)")
  else
    # Default bare install + --register: harness this package (like lean → REPO_DIR)
    TARGETS+=("${REPO_DIR}")
    for p in "${REGISTER_PROJECTS[@]+"${REGISTER_PROJECTS[@]}"}"; do
      register_workspace "$p"
      TARGETS+=("$(cd "$p" && pwd)")
    done
    # Refresh every registered workspace (lean upgrade path)
    if [ -f "${PROJECTS_FILE}" ]; then
      while IFS= read -r registered || [ -n "$registered" ]; do
        [ -z "$registered" ] && continue
        [ -d "$registered" ] || continue
        skip=false
        for t in "${TARGETS[@]+"${TARGETS[@]}"}"; do
          [ "$t" = "$registered" ] && skip=true && break
        done
        [ "$skip" = true ] || TARGETS+=("$registered")
      done < "${PROJECTS_FILE}"
    fi
  fi

  # Dedupe TARGETS
  declare -a UNIQUE=()
  for t in "${TARGETS[@]+"${TARGETS[@]}"}"; do
    seen=false
    for u in "${UNIQUE[@]+"${UNIQUE[@]}"}"; do
      [ "$u" = "$t" ] && seen=true && break
    done
    [ "$seen" = true ] || UNIQUE+=("$t")
  done

  for t in "${UNIQUE[@]+"${UNIQUE[@]}"}"; do
    install_project "$t"
    echo ""
  done
fi

# Doctor on every workspace registered in this run: install problems surface now, with fixes.
if [ "$SKIP_HARNESS" = "false" ] && [ -n "${PYTHON}" ]; then
  for p in "${REGISTER_PROJECTS[@]+"${REGISTER_PROJECTS[@]}"}"; do
    p="$(cd "$p" && pwd)"
    echo -e "${YELLOW}Doctor${NC} ${p}"
    ( cd "$p" && "${PYTHON}" ./.agent-spec/bin/agent-spec-doctor.py --project "$p" ) || true
    echo ""
  done
fi

echo -e "${GREEN}Done.${NC} Skills are in ${CURSOR_SKILLS}"
echo "Restart Cursor or start a new chat after updates."
echo "Verify: ./check-install.sh"
echo "Optional — add a workspace harness: ./install.sh --register \"<opened folder root>\""
