#!/usr/bin/env bash
# =============================================================================
# agent-spec-init.sh — compatibility shim.
#
# The entry point is now bin/install.sh, which installs skills machine-wide AND
# sets up the current project in one command. This file only exists so links to
# the old curl URL keep working.
#
# Old behaviour was project-only, so that is what this forwards to.
# =============================================================================
set -eo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "note: agent-spec-init.sh is deprecated — use bin/install.sh" >&2
exec "${DIR}/install.sh" --project-only "$@"
