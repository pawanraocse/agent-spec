#!/usr/bin/env bash
# =============================================================================
# agent-spec-ab.sh — set up an honest A/B between two modes
#
# The framework must not claim a saving it has not counted, and a saving can
# only be counted by running the same task twice. This script cannot run the
# sessions for you — Claude Code sessions are interactive and each one has to be
# a genuinely fresh context, which is the whole variable under test. What it
# does is record the boundary before and after each run, then hand the two
# transcripts to `agent-spec-tokens.py compare`.
#
#   bin/agent-spec-ab.sh start A "<the task, verbatim>"
#   ... run that task in a NEW Claude Code session, in mode A ...
#   bin/agent-spec-ab.sh end A
#
#   bin/agent-spec-ab.sh start B "<the same task, verbatim>"
#   ... run it again in a NEW session, in mode B ...
#   bin/agent-spec-ab.sh end B
#
#   bin/agent-spec-ab.sh report
# =============================================================================
set -uo pipefail

HOME_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_DIR="$(pwd)/.agent-spec/ab"
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

PROJECTS="${HOME}/.claude/projects/$(pwd | tr '/' '-')"

newest() { ls -t "${PROJECTS}"/*.jsonl 2>/dev/null | head -1; }

case "${1:-}" in
  start)
    ARM="${2:?arm required: A or B}"
    TASK="${3:?the task, in quotes}"
    mkdir -p "${STATE_DIR}"
    printf '%s\n' "${TASK}" > "${STATE_DIR}/task-${ARM}.txt"
    ls "${PROJECTS}"/*.jsonl 2>/dev/null | sort > "${STATE_DIR}/before-${ARM}.txt"
    echo -e "${YELLOW}Arm ${ARM} armed.${NC}"
    echo ""
    echo "  1. Start a NEW Claude Code session in this directory. A fresh context is"
    echo "     the variable under test — resuming or continuing invalidates the run."
    echo "  2. Activate the mode for this arm, then paste the task exactly as written:"
    echo ""
    sed 's/^/       /' "${STATE_DIR}/task-${ARM}.txt"
    echo ""
    echo "  3. When the task is done, come back here and run:"
    echo "       bin/agent-spec-ab.sh end ${ARM}"
    ;;

  end)
    ARM="${2:?arm required: A or B}"
    [ -f "${STATE_DIR}/before-${ARM}.txt" ] || { echo "✗ arm ${ARM} was never started" >&2; exit 1; }
    ls "${PROJECTS}"/*.jsonl 2>/dev/null | sort > "${STATE_DIR}/after-${ARM}.txt"
    NEW="$(comm -13 "${STATE_DIR}/before-${ARM}.txt" "${STATE_DIR}/after-${ARM}.txt" | head -1)"
    if [ -z "${NEW}" ]; then
      echo "✗ No new transcript appeared. The run happened in a resumed session, in a" >&2
      echo "  different directory, or not at all. Nothing recorded — a mislabelled arm" >&2
      echo "  is worse than no measurement." >&2
      exit 1
    fi
    printf '%s\n' "${NEW}" > "${STATE_DIR}/arm-${ARM}.txt"
    echo -e "${GREEN}✓${NC} arm ${ARM}: $(basename "${NEW}")"
    python3 "${HOME_DIR}/bin/agent-spec-tokens.py" session --file "${NEW}" | head -12
    ;;

  report)
    A="$(cat "${STATE_DIR}/arm-A.txt" 2>/dev/null)"
    B="$(cat "${STATE_DIR}/arm-B.txt" 2>/dev/null)"
    [ -n "${A}" ] && [ -n "${B}" ] || { echo "✗ both arms must be finished first" >&2; exit 1; }
    if ! diff -q "${STATE_DIR}/task-A.txt" "${STATE_DIR}/task-B.txt" >/dev/null 2>&1; then
      echo -e "${YELLOW}! The two arms were given different tasks.${NC}"
      echo "  A lower total on a different task is not a saving. Reporting it as one is"
      echo "  exactly how a 60-90% claim gets made. Fix the tasks and re-run."
      echo ""
    fi
    python3 "${HOME_DIR}/bin/agent-spec-tokens.py" compare "${A}" "${B}"
    ;;

  *)
    sed -n '3,24p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
    exit 1
    ;;
esac
