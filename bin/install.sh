#!/usr/bin/env bash
# Compatibility shim — use the package-root installer.
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/install.sh" "$@"
