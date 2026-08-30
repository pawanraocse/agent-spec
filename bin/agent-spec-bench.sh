#!/usr/bin/env bash
# =============================================================================
# agent-spec-bench.sh — measure the framework's context cost
#
# "More efficient" is unfalsifiable without a number. This prints the bytes that
# enter a session's context before any work begins, and what each skill adds when
# it is invoked. Token counts are estimated at 4 bytes per token — close enough to
# compare two revisions of this repository, not close enough to quote elsewhere.
#
# Usage: bin/agent-spec-bench.sh [project-dir]
#        bin/agent-spec-bench.sh --session    # measured, from the session transcript
# =============================================================================
set -uo pipefail

HOME_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT="${1:-$(pwd)}"
BOLD='\033[1m'; NC='\033[0m'

bytes() { [ -f "$1" ] && wc -c < "$1" | tr -d ' ' || echo 0; }
tokens() { echo $(( $1 / 4 )); }

# --session hands over to the one thing here that is measured rather than estimated.
# Everything below it is bytes divided by four, which compares two revisions of a file
# and cannot measure a session at all.
if [ "${1:-}" = "--session" ]; then
  exec python3 "${HOME_DIR}/bin/agent-spec-tokens.py" session
fi

echo -e "${BOLD}Always-on context${NC}  (paid every turn — ESTIMATED at 4 bytes per token)"
echo "  For measured numbers from the real session transcript: bin/agent-spec-bench.sh --session"
echo "  One config file loads per agent, not all four. The total below uses CLAUDE.md."
for f in AGENTS.md CLAUDE.md CURSOR.md GEMINI.md; do
  B=$(bytes "${HOME_DIR}/${f}")
  printf "  %-14s %7d B  ~%5d tok\n" "$f" "$B" "$(tokens "$B")"
done
TOTAL=$(bytes "${HOME_DIR}/CLAUDE.md")

DESC=$(python3 - "$HOME_DIR" <<'PY'
import os, re, sys
home = sys.argv[1]
total = 0
for d in sorted(os.listdir(os.path.join(home, "skills", "claude"))):
    p = os.path.join(home, "skills", "claude", d, "SKILL.md")
    if not os.path.exists(p):
        continue
    m = re.search(r"description: >-\n((?:  .*\n)+)", open(p, encoding="utf-8").read())
    if m:
        total += len(" ".join(l.strip() for l in m.group(1).split("\n") if l.strip()))
print(total)
PY
)
printf "  %-14s %7d B  ~%5d tok   (%d skills)\n" "descriptions" "$DESC" "$(tokens "$DESC")" \
  "$(ls -d "${HOME_DIR}/skills/claude"/*/ | wc -l | tr -d ' ')"
TOTAL=$((TOTAL + DESC))

DIGEST=0
if [ -d "${PROJECT}/.agent-spec" ]; then
  DIGEST=$( cd "$PROJECT" && python3 "${HOME_DIR}/bin/agent-spec-digest.py" | wc -c | tr -d ' ' )
fi
printf "  %-14s %7d B  ~%5d tok\n" "digest" "$DIGEST" "$(tokens "$DIGEST")"
TOTAL=$((TOTAL + DIGEST))
printf "  %-14s %7d B  ~%5d tok\n\n" "TOTAL" "$TOTAL" "$(tokens "$TOTAL")"

echo -e "${BOLD}What the digest replaces${NC}  (the old read-four-files protocol)"
OLD=0
for f in PROJECT-INDEX.md graph/KNOWLEDGE-GRAPH.md CONSTITUTION.md SESSION-SNAPSHOT.md; do
  B=$(bytes "${PROJECT}/.agent-spec/${f}")
  OLD=$((OLD + B))
  printf "  %-26s %7d B\n" "$f" "$B"
done
printf "  %-26s %7d B  ~%5d tok\n" "TOTAL" "$OLD" "$(tokens "$OLD")"
if [ "$DIGEST" -gt 0 ] && [ "$OLD" -gt 0 ]; then
  printf "  saved per session: %d B  ~%d tok\n\n" "$((OLD - DIGEST))" "$(tokens "$((OLD - DIGEST))")"
else
  printf "  (run this inside an onboarded project for the comparison)\n\n"
fi

echo -e "${BOLD}Per-skill body${NC}  (paid only when invoked)"
for d in "${HOME_DIR}/skills/claude"/*/; do
  B=$(bytes "${d}SKILL.md")
  printf "  %-16s %6d B  ~%4d tok\n" "$(basename "$d")" "$B" "$(tokens "$B")"
done | sort -k2 -rn | head -12

echo ""
echo -e "${BOLD}Graph query cost${NC}  (versus reading the files those answers come from)"
if [ -f "${PROJECT}/.agent-spec/graph/knowledge-graph.json" ]; then
  for q in "stats" "layers" "services"; do
    B=$( cd "$PROJECT" && python3 "${HOME_DIR}/bin/graphify-cli.py" $q 2>/dev/null | wc -c | tr -d ' ' )
    printf "  %-10s %6d B  ~%4d tok\n" "$q" "$B" "$(tokens "$B")"
  done
  SRC=$(python3 -c "
import json,sys
g=json.load(open(sys.argv[1]))
print(g['stats'].get('files',0))" "${PROJECT}/.agent-spec/graph/knowledge-graph.json")
  echo "  reading all ${SRC} indexed files instead: see the source tree; the point is the ratio."
else
  echo "  no graph — run ./.agent-spec/bin/agent-spec-index"
fi
