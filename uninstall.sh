#!/usr/bin/env bash
# algosec-agent-spec — Cursor uninstall
#
#   ./uninstall.sh                  # remove machine-wide agent-spec-* skills only
#   ./uninstall.sh --unregister <ws>  # remove our .cursor harness from one workspace + registry line
#   ./uninstall.sh --full           # skills + unregister every known workspace
#
# Never deletes user source code. Never touches .env.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CURSOR_SKILLS="${HOME}/.cursor/skills"
PROJECTS_FILE="${CURSOR_SKILLS}/.algosec-agent-spec-projects"
ROOT_MARKER="${CURSOR_SKILLS}/.algosec-agent-spec-root"

MODE="skills"
UNREGISTER=""

while [ $# -gt 0 ]; do
  case "$1" in
    --skills-only) MODE="skills"; shift ;;
    --full) MODE="full"; shift ;;
    --unregister)
      shift
      [ $# -gt 0 ] || { echo "ERROR: --unregister requires a path"; exit 1; }
      MODE="unregister"
      UNREGISTER="$1"
      shift
      ;;
    -h|--help)
      sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *) echo "unknown: $1"; exit 1 ;;
  esac
done

remove_skills() {
  echo "Removing agent-spec-* skills from $CURSOR_SKILLS"
  for skill_dir in "$REPO_DIR/skills"/*/; do
    [ -d "$skill_dir" ] || continue
    name="$(basename "$skill_dir")"
    if [ -d "$CURSOR_SKILLS/$name" ]; then
      rm -rf "$CURSOR_SKILLS/$name"
      echo "  removed skill $name"
    fi
  done
  rm -f "$ROOT_MARKER"
}

unregister_workspace() {
  local root="$1"
  root="$(cd "$root" && pwd)"
  echo "Unregister $root"
  rm -f "$root/.cursor/rules/agent-spec.mdc"
  rm -f "$root/.cursor/hooks/agent-spec-session-start.py"
  rm -f "$root/.cursor/hooks/agent-spec-pre-tool-use.py"
  rm -f "$root/.cursor/hooks/agent-spec-session-end.py"
  rm -f "$root/.cursor/hooks/agent-spec-cursor-event.py"
  rm -f "$root/.cursor/hooks/agent-spec-digest.py"
  rm -f "$root/.cursor/agents/agent-spec-search.md"
  rm -f "$root/.cursor/agents/agent-spec-verify.md"
  rm -f "$root/.cursor/agents/agent-spec-reviewer.md"
  rm -f "$root/.cursor/agents/handoffs/agent-spec-"*.json
  rmdir "$root/.cursor/agents/handoffs" 2>/dev/null || true

  if [ -f "$root/.cursor/hooks.json" ]; then
    PY=python3
    [ -x /usr/bin/python3 ] && PY=/usr/bin/python3
    if [ -x /usr/bin/python3 ] || command -v python3 >/dev/null 2>&1; then
      "$PY" "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/hooks/unmerge-hooks-json.py" \
        "$root/.cursor/hooks.json" && echo "  cleaned hooks.json markers"
    fi
  fi

  PY=python3
  [ -x /usr/bin/python3 ] && PY=/usr/bin/python3
  if [ -x /usr/bin/python3 ] || command -v python3 >/dev/null 2>&1; then
    "$PY" "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/hooks/manage-git-hooks.py" uninstall "$root" \
      && echo "  cleaned git auto-index hooks"
  fi

  if [ -f "$PROJECTS_FILE" ]; then
    tmp="$(mktemp)"
    grep -Fxv "$root" "$PROJECTS_FILE" > "$tmp" || true
    mv "$tmp" "$PROJECTS_FILE"
    echo "  removed from registry"
  fi
  echo "  note: left .agent-spec/ (constitution, sdlc, memory) intact"
}

case "$MODE" in
  skills)
    remove_skills
    ;;
  unregister)
    unregister_workspace "$UNREGISTER"
    ;;
  full)
    if [ -f "$PROJECTS_FILE" ]; then
      while IFS= read -r line || [ -n "$line" ]; do
        [ -z "$line" ] && continue
        [ -d "$line" ] && unregister_workspace "$line"
      done < "$PROJECTS_FILE"
    fi
    remove_skills
    rm -f "$PROJECTS_FILE"
    ;;
esac

echo "Done."
