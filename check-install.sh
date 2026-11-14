#!/usr/bin/env bash
# algosec-agent-spec — verify Cursor install
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CURSOR_SKILLS="${HOME}/.cursor/skills"
PROJECTS_FILE="${CURSOR_SKILLS}/.algosec-agent-spec-projects"
ROOT_MARKER="${CURSOR_SKILLS}/.algosec-agent-spec-root"
missing=0
PKG_VERSION="$(tr -d '[:space:]' < "$REPO_DIR/VERSION" 2>/dev/null || echo unknown)"

# Compare the version stamped into a workspace's agent-spec.mdc with the package VERSION.
version_drift() {
  local ws="$1" stamped
  stamped="$(sed -n 's/^version:[[:space:]]*//p' "$ws/.cursor/rules/agent-spec.mdc" 2>/dev/null | head -1 | tr -d '[:space:]')"
  if [ -z "$stamped" ]; then
    echo "  WARN: no version stamp in agent-spec.mdc: $ws"; return 1
  elif [ "$stamped" != "$PKG_VERSION" ]; then
    echo "  WARN: harness $stamped but package is $PKG_VERSION: $ws — ./install.sh --register \"$ws\""; return 1
  fi
  return 0
}

echo "algosec-agent-spec check-install"
echo "Package: $REPO_DIR"
echo "Skills:  $CURSOR_SKILLS"
echo ""

# Prefer system python3 for checks (asdf shims can 126 on fresh scripts)
PY=python3
[ -x /usr/bin/python3 ] && PY=/usr/bin/python3

if ! command -v python3 >/dev/null 2>&1 && [ ! -x /usr/bin/python3 ]; then
  echo "MISSING: python3 (required for digest, graph, gate, hooks)"
  missing=1
else
  echo "OK: python3 → $PY"
fi

if [ ! -d "$CURSOR_SKILLS" ]; then
  echo "MISSING: $CURSOR_SKILLS — run ./install.sh"
  missing=1
elif [ ! -w "$CURSOR_SKILLS" ]; then
  echo "MISSING: $CURSOR_SKILLS not writable"
  missing=1
else
  echo "OK: writable $CURSOR_SKILLS"
fi

skill_count=0
for skill_dir in "$REPO_DIR/skills"/*/; do
  [ -d "$skill_dir" ] || continue
  name="$(basename "$skill_dir")"
  skill_count=$((skill_count + 1))
  if [ -f "$CURSOR_SKILLS/$name/SKILL.md" ]; then
    echo "OK: skill $name"
  else
    echo "MISSING: skill $name"
    missing=1
  fi
done
echo "Expected skills from package: $skill_count"
if [ -f "$REPO_DIR/bin/agent-spec-tokens.py" ]; then
  echo "OK: bin/agent-spec-tokens.py"
else
  echo "MISSING: bin/agent-spec-tokens.py"
  missing=1
fi


if [ -f "$ROOT_MARKER" ]; then
  echo "OK: root marker → $(cat "$ROOT_MARKER")"
else
  echo "MISSING: $ROOT_MARKER (re-run ./install.sh)"
  missing=1
fi

if [ -n "${PY:-}" ] || [ -x /usr/bin/python3 ]; then
  PY="${PY:-python3}"
  [ -x /usr/bin/python3 ] && PY=/usr/bin/python3
  out="$(cd /tmp && "$PY" "$REPO_DIR/bin/agent-spec-digest.py" --cursor-hook </dev/null 2>/dev/null || true)"
  if echo "$out" | "$PY" -c 'import json,sys; json.load(sys.stdin)' 2>/dev/null; then
    echo "OK: digest --cursor-hook emits JSON"
  else
    echo "WARN: digest --cursor-hook JSON check failed (outside project may be {})"
    if [ -z "$out" ]; then
      missing=1
      echo "MISSING: digest produced no output"
    fi
  fi
fi

echo ""
echo "Registered workspaces ($PROJECTS_FILE):"
if [ -f "$PROJECTS_FILE" ]; then
  found=0
  while IFS= read -r line || [ -n "$line" ]; do
    [ -z "$line" ] && continue
    found=1
    if [ -d "$line" ]; then
      ok=1
      [ -f "$line/.cursor/rules/agent-spec.mdc" ] || { echo "  WARN rule missing: $line"; ok=0; missing=1; }
      [ -f "$line/.cursor/hooks.json" ] || { echo "  WARN hooks.json missing: $line"; ok=0; missing=1; }
      [ -f "$line/.cursor/hooks/agent-spec-session-start.py" ] || { echo "  WARN session hook missing: $line"; ok=0; missing=1; }
      [ -f "$line/.cursor/hooks/agent-spec-pre-tool-use.py" ] || { echo "  WARN preToolUse hook missing: $line"; ok=0; missing=1; }
      [ -f "$line/.cursor/hooks/agent-spec-session-end.py" ] || { echo "  WARN session-end (receipt) hook missing — re-register: $line"; ok=0; missing=1; }
      [ -f "$line/.agent-spec/bin/agent-spec-receipt.py" ] || { echo "  WARN agent-spec-receipt.py missing — re-register: $line"; ok=0; missing=1; }
      [ -d "$line/.cursor/agents" ] || { echo "  WARN agents missing: $line"; ok=0; missing=1; }
      [ -f "$line/.agent-spec/bin/agent-spec-tokens.py" ] || { echo "  WARN agent-spec-tokens.py missing: $line"; ok=0; missing=1; }
      [ -f "$line/.agent-spec/bin/agent-spec-digest.py" ] || { echo "  WARN .agent-spec/bin missing: $line"; ok=0; missing=1; }
      [ -f "$line/.agent-spec/bin/agent-spec-doctor.py" ] || { echo "  WARN agent-spec-doctor.py missing: $line"; ok=0; missing=1; }
      version_drift "$line" || { ok=0; missing=1; }
      if [ -d "$line/.git" ] || [ -f "$line/.git" ]; then
        if ! "$PY" "$REPO_DIR/hooks/manage-git-hooks.py" check "$line" >/dev/null 2>&1; then
          echo "  WARN git hooks missing (workspace may predate post-rewrite): $line — re-run ./install.sh --register \"$line\""; ok=0; missing=1;
        fi
      fi
      if [ "$ok" -eq 1 ]; then
        echo "  OK: $line"
      fi
    else
      echo "  WARN (path missing): $line"
      missing=1
    fi
  done < "$PROJECTS_FILE"
  [ "$found" -eq 0 ] && echo "  (none — ./install.sh --register <workspace-root>)"
else
  echo "  (none — ./install.sh --register <workspace-root>)"
fi

if [ $# -ge 1 ]; then
  check_root="$(cd "$1" && pwd)"
  echo ""
  echo "Check workspace: $check_root"
  if [ -f "$PROJECTS_FILE" ] && grep -Fxq "$check_root" "$PROJECTS_FILE"; then
    echo "  OK: registered"
  else
    echo "  NOT registered — ./install.sh --register $check_root"
    missing=1
  fi
  for f in \
    .cursor/rules/agent-spec.mdc \
    .cursor/hooks.json \
    .cursor/hooks/agent-spec-session-start.py \
    .cursor/hooks/agent-spec-pre-tool-use.py \
    .cursor/hooks/agent-spec-session-end.py \
    .agent-spec/bin/agent-spec-digest.py \
    .agent-spec/bin/agent-spec-tokens.py \
    .agent-spec/bin/agent-spec-doctor.py \
    .agent-spec/bin/agent-spec-receipt.py
  do
    if [ -e "$check_root/$f" ]; then
      echo "  OK: $f"
    else
      echo "  MISSING: $f"
      missing=1
    fi
  done
  if version_drift "$check_root"; then
    echo "  OK: harness version $PKG_VERSION"
  else
    missing=1
  fi
  if [ -d "$check_root/.git" ] || [ -f "$check_root/.git" ]; then
    if "$PY" "$REPO_DIR/hooks/manage-git-hooks.py" check "$check_root" >/dev/null 2>&1; then
      echo "  OK: git auto-index hooks (post-checkout, post-merge, post-rewrite)"
    else
      echo "  WARN: git auto-index hooks missing in $check_root (may predate post-rewrite; re-register)"
      missing=1
    fi
  fi
fi

echo ""
echo "In Cursor: Customize → Rules → agent-spec (Always Apply)."
echo "Enable Hooks in Settings if sessionStart/preToolUse do not fire."
echo "Registration list is not in Cursor UI — use this script or cat $PROJECTS_FILE"

if [ "$missing" -eq 0 ]; then
  echo "All checks passed."
  exit 0
fi
echo "Some checks failed."
exit 1
