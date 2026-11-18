#!/usr/bin/env bash
# H-051: prepare the 5-minute demo offline. Nothing here needs the network or Cursor.
#
#   bash examples/mesh-demo/demo-setup.sh [DEMO_DIR]     (default: /tmp/agent-spec-demo)
#
# DEMO_DIR receives copies of the four mesh-demo repos. The package's examples are never
# written to. orders-api is the project the demo works in:
#   1. registered with the harness (project only; global skills are not touched),
#   2. a mesh of all four repos, with orders-api as hub and member,
#   3. a past fix recorded in orders-worker, so recall from orders-api cites it (P3-014),
#   4. one recorded Cursor conversation replayed through the real hooks, so the request
#      feed, Impact tab and audit export have a trace,
#   5. one tier-3 edit blocked by the real preToolUse gate (routes.py is called by shop-ui),
#      waiting in Project > Risk,
#   6. one proposed fact waiting in Project > Proposals,
#   7. the platform database ingested.
# Re-running it starts from a clean DEMO_DIR.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PKG="$(cd "$HERE/../.." && pwd)"
DEMO="${1:-/tmp/agent-spec-demo}"
HUB="$DEMO/orders-api"
FIX="$PKG/tests/fixtures/hooks/recorded"

case "$DEMO" in ""|"/"|"$HOME"|"$PKG"*) echo "refusing DEMO_DIR=$DEMO" >&2; exit 2 ;; esac
# Only a directory this script created (it holds the marker) or an empty one is ever cleared.
if [ -d "$DEMO" ] && [ -n "$(ls -A "$DEMO" 2>/dev/null)" ] && [ ! -f "$DEMO/.agent-spec-demo" ]; then
  echo "refusing to clear $DEMO: not empty and not made by demo-setup.sh" >&2; exit 2
fi
rm -rf "$DEMO"
mkdir -p "$DEMO"
: > "$DEMO/.agent-spec-demo"
for repo in acme-common orders-api orders-worker shop-ui; do
  cp -R "$HERE/$repo" "$DEMO/$repo"
  (cd "$DEMO/$repo" && git init -q && git add -A && git -c user.name=demo -c user.email=demo@example.invalid commit -qm "demo: $repo")
done
echo "1/7 repos copied to $DEMO"

bash "$PKG/install.sh" --project-only --register "$HUB" >/dev/null
# Onboarding is an agent action (/agent-spec-onboard) and cannot run offline. Its two outputs for
# this three-file service are written here instead, so the digest on stage is not an onboarding notice.
cat > "$HUB/.agent-spec/PROJECT-INDEX.md" <<'MD'
# orders-api — project index (demo; what /agent-spec-onboard writes for this service)

- Stack: Python, no framework beyond the `app` route decorator.
- `orders_api/routes.py`: `GET /api/orders/<order_id>`, `POST /api/orders`. Called by `shop-ui` over HTTP.
- `orders_api/bus.py`: the `producer` that publishes `orders.created`, consumed by `orders-worker`.
- Depends on `acme-common` (`acme_common.money.to_cents`, `acme_common.events.order_created`).
MD
cat > "$HUB/.agent-spec/CONSTITUTION.md" <<'MD'
# orders-api — constitution (demo)

1. Money is integer cents, converted once with `acme_common.money.to_cents` (routes.py).
2. Events are built with `acme_common.events`, never as ad hoc dicts (routes.py).
3. Routes are a public contract: `shop-ui` calls them.
MD
rm -f "$HUB/.agent-spec/.onboarding-needed"
echo "2/7 orders-api registered (project harness only), onboarding output written"

cd "$HUB"
python3 .agent-spec/bin/graphify-build.py --quiet >/dev/null 2>&1 || python3 .agent-spec/bin/graphify-build.py >/dev/null
for repo in acme-common orders-api orders-worker shop-ui; do
  python3 .agent-spec/bin/graphify-mesh.py add "$DEMO/$repo" --id "$repo" >/dev/null
done
python3 .agent-spec/bin/graphify-mesh.py build | tail -1
echo "3/7 mesh built: $(python3 .agent-spec/bin/graphify-mesh.py stats | head -1)"

mkdir -p "$DEMO/orders-worker/.agent-spec"
cat > "$DEMO/orders-worker/.agent-spec/experience.jsonl" <<'JSON'
{"exp_id": "session:demo-worker-1", "kind": "session", "schema": 1, "status": "success", "retries": 0, "corrections": 1, "gates": 2, "tokens": {"input": 18400, "output": 2100, "cache_read": 0}, "ts": "2026-11-10T14:02:00", "task": "Fix duplicate orders.created handling: the worker re-processed an order when the bus redelivered; make the consumer idempotent on order_id"}
JSON
python3 .agent-spec/bin/agent-spec-memory.py add --type constraint --subject "routes are a public contract" \
  "orders_api/routes.py is called by shop-ui over HTTP; change a route only with the UI change in the same release." >/dev/null
echo "4/7 past fix recorded in orders-worker, one fact remembered in orders-api"

python3 - "$FIX" "$HUB" <<'PY'
import json, os, subprocess, sys
fix, hub = sys.argv[1], sys.argv[2]
hooks = json.load(open(os.path.join(hub, ".cursor", "hooks.json")))["hooks"]
order = ["sessionStart", "beforeSubmitPrompt", "preToolUse", "postToolUse", "postToolUseFailure",
         "subagentStart", "subagentStop", "afterFileEdit", "afterAgentResponse", "stop", "sessionEnd"]
for event in order:
    path = os.path.join(fix, event + ".json")
    if not os.path.isfile(path):
        continue
    payload = json.load(open(path))
    payload["cwd"] = hub
    payload["workspace_roots"] = [hub]
    for h in hooks.get(event, []):
        subprocess.run(h["command"], shell=True, cwd=hub, input=json.dumps(payload).encode(),
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
PY
echo "5/7 recorded conversation replayed through the hooks"

python3 - "$HUB" <<'PY'
import json, os, subprocess, sys
hub = sys.argv[1]
payload = {"hook_event_name": "preToolUse", "conversation_id": "demo-conv-risk", "generation_id": "demo-gen-risk",
           "session_id": "demo-conv-risk", "cwd": hub, "workspace_roots": [hub], "tool_name": "Write",
           "tool_input": {"file_path": os.path.join(hub, "orders_api", "routes.py"),
                          "contents": "# demo: rename GET /api/orders/{id}\n"}}
out = subprocess.run("python3 .cursor/hooks/agent-spec-pre-tool-use.py", shell=True, cwd=hub,
                     input=json.dumps(payload).encode(), capture_output=True, timeout=60).stdout.decode()
print("   gate says:", (out.strip() or "(allowed)")[:160])
PY
echo "6/7 tier-3 edit of orders_api/routes.py sent to the gate"

python3 .agent-spec/bin/agent-spec-memory.py propose --type gotcha --subject "order ids are idempotency keys" \
  --evidence "orders-worker:.agent-spec/experience.jsonl:1 fixed a duplicate orders.created delivery" \
  "The bus can redeliver orders.created; every consumer must treat order_id as an idempotency key." >/dev/null
python3 .agent-spec/bin/agent-spec-platform.py ingest >/dev/null 2>&1 || true
echo "7/7 fact proposed and platform database ingested"

cat <<EOF

Demo ready in $HUB. Start the dashboard:
  cd "$HUB" && python3 .agent-spec/bin/agent-spec-platform.py serve
EOF
