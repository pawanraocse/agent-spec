#!/usr/bin/env bash
# =============================================================================
# session-start.sh — agent-spec SessionStart hook
#
# Emits the project digest on stdout, which Claude Code adds to the session's
# context. Replaces the old "read these four files first" protocol: the same
# facts, assembled outside the model, for roughly a tenth of the tokens.
#
# Silent and successful in any directory that is not an agent-spec project, so
# it is safe to install machine-wide.
# =============================================================================
set -uo pipefail

[ -d "./.agent-spec" ] || exit 0
command -v python3 >/dev/null 2>&1 || exit 0

# Prefer the project's own copy; fall back to the one installed beside this hook, so a
# project set up by an older installer still gets a digest.
DIGEST="./.agent-spec/bin/agent-spec-digest.py"
[ -f "${DIGEST}" ] || DIGEST="$(dirname "${BASH_SOURCE[0]}")/agent-spec-digest.py"
[ -f "${DIGEST}" ] || exit 0

python3 "${DIGEST}" 2>/dev/null || true
exit 0
