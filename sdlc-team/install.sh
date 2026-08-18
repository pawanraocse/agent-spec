#!/usr/bin/env bash
# =============================================================================
# sdlc-team installer (bash — WSL, Linux, macOS)
#
#   ./install.sh [TARGET_PROJECT] [--force] [--dev]
#
#   TARGET_PROJECT  Project to install into. Defaults to the current directory.
#   --force         Overwrite an existing install.
#   --dev           Don't copy anything; just print the --plugin-dir command.
# =============================================================================
set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; BLUE='\033[0;34m'; NC='\033[0m'

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="$(pwd)"
FORCE="false"
DEV="false"

for arg in "$@"; do
  case "$arg" in
    --force) FORCE="true" ;;
    --dev)   DEV="true" ;;
    -h|--help) sed -n '2,10p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *)       TARGET="$arg" ;;
  esac
done

# --- sanity: does the source actually look like the plugin? ------------------
if [ ! -f "${SRC}/.claude-plugin/plugin.json" ]; then
  echo -e "${RED}✗ ${SRC} is not an sdlc-team plugin (no .claude-plugin/plugin.json)${NC}"
  exit 1
fi

echo -e "${BLUE}sdlc-team installer${NC}"
echo -e "  source: ${SRC}"

if [ "$DEV" = "true" ]; then
  echo ""
  echo -e "${GREEN}Session-only load — no files copied. Run:${NC}"
  echo ""
  echo "  claude --plugin-dir \"${SRC}\""
  echo ""
  exit 0
fi

if [ ! -d "$TARGET" ]; then
  echo -e "${RED}✗ target directory does not exist: ${TARGET}${NC}"
  exit 1
fi
TARGET="$(cd "$TARGET" && pwd)"
DEST="${TARGET}/.claude/skills/sdlc-team"

echo -e "  target: ${TARGET}"
echo ""

if [ "${SRC}" = "${DEST}" ]; then
  echo -e "${YELLOW}⏭  Already installed at this exact path; nothing to do.${NC}"
  exit 0
fi

if [ -d "$DEST" ] && [ "$FORCE" != "true" ]; then
  echo -e "${YELLOW}⚠  Already installed at ${DEST}${NC}"
  echo -e "   Re-run with --force to overwrite."
  exit 1
fi

# --- install -----------------------------------------------------------------
mkdir -p "${TARGET}/.claude/skills"
rm -rf "$DEST"
mkdir -p "$DEST"
for item in .claude-plugin agents commands skills README.md TESTING.md; do
  [ -e "${SRC}/${item}" ] && cp -R "${SRC}/${item}" "${DEST}/"
done
echo -e "${GREEN}✅ Installed → ${DEST}${NC}"

# --- verify ------------------------------------------------------------------
A=$(find "${DEST}/agents"   -name '*.md'    2>/dev/null | wc -l | tr -d ' ')
S=$(find "${DEST}/skills"   -name 'SKILL.md' 2>/dev/null | wc -l | tr -d ' ')
C=$(find "${DEST}/commands" -name '*.md'    2>/dev/null | wc -l | tr -d ' ')
echo -e "   ${A} agents · ${S} skills · ${C} commands"

if [ "$A" -eq 0 ] || [ "$S" -eq 0 ]; then
  echo -e "${RED}✗ Install looks incomplete — agents or skills are missing.${NC}"
  exit 1
fi

if command -v claude >/dev/null 2>&1; then
  claude plugin validate "$DEST" 2>&1 | grep -qi "passed" \
    && echo -e "${GREEN}✅ claude plugin validate: passed${NC}" \
    || echo -e "${YELLOW}⚠  claude plugin validate did not report success — run it manually.${NC}"
fi

# --- gitignore warning -------------------------------------------------------
if [ -f "${TARGET}/.gitignore" ] && git -C "$TARGET" check-ignore -q "$DEST" 2>/dev/null; then
  echo ""
  echo -e "${YELLOW}⚠  .gitignore excludes ${DEST#$TARGET/}${NC}"
  echo -e "   The plugin still works for you, but teammates won't get it."
  echo -e "   To share it, add this to .gitignore:"
  echo -e "     !/.claude/skills/sdlc-team/"
fi

# --- next steps --------------------------------------------------------------
cat <<EOF

$(echo -e "${YELLOW}1. RESTART Claude Code.${NC}") It only picks up .claude/skills/ that
   existed when the session started. A mid-session install looks broken
   but is not.

2. Try it:   /prd add CSV export
   If that is not found, try the namespaced form:  /sdlc-team:prd

3. Full pipeline:  /new-feature add CSV export
   Verification prompts:  ${DEST}/TESTING.md

EOF
