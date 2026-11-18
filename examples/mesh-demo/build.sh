#!/usr/bin/env bash
# Build the mesh-demo mesh into HUB (default: a temp dir) and print its stats.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
MESH="$HERE/../../bin/graphify-mesh.py"
HUB="${1:-$(mktemp -d)}"
mkdir -p "$HUB/.agent-spec"
cat > "$HUB/.agent-spec/mesh-aliases.json" <<JSON
{"orders-api": "orders-api", "orders": "orders-api"}
JSON
cd "$HUB"
for repo in acme-common orders-api orders-worker shop-ui; do
  python3 "$MESH" remove "$repo" >/dev/null 2>&1 || true
  python3 "$MESH" add "$HERE/$repo" --id "$repo"
done
python3 "$MESH" build
python3 "$MESH" stats
