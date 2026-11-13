#!/usr/bin/env bash
# algosec-agent-spec Cursor selftest — no Claude Code paths
set -euo pipefail

HOME_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
PY=python3
[ -x /usr/bin/python3 ] && PY=/usr/bin/python3

ok() { echo "  OK: $*"; }
bad() { echo "  FAIL: $*"; FAILS=$((FAILS+1)); }
FAILS=0

echo "[1] package shape"
[ -f "$HOME_DIR/VERSION" ] && ok "VERSION" || bad "VERSION"
[ -f "$HOME_DIR/CURSOR.md" ] && ok "CURSOR.md" || bad "CURSOR.md"
[ -f "$HOME_DIR/AGENTS.md" ] && ok "AGENTS.md" || bad "AGENTS.md"
[ -f "$HOME_DIR/install.sh" ] && ok "install.sh" || bad "install.sh"
[ -f "$HOME_DIR/hooks/cursor-session-start.py" ] && ok "session hook" || bad "session hook"
[ -f "$HOME_DIR/hooks/cursor-pre-tool-use.py" ] && ok "preToolUse hook" || bad "preToolUse hook"
[ ! -f "$HOME_DIR/CLAUDE.md" ] && ok "no CLAUDE.md" || bad "CLAUDE.md still present"
[ ! -d "$HOME_DIR/skills/claude" ] && ok "no skills/claude" || bad "skills/claude remains"
[ ! -d "$HOME_DIR/output-styles" ] && ok "no output-styles" || bad "output-styles remains"

echo "[2] CURSOR.md documents sessionStart (not 'no hook')"
if grep -q 'sessionStart' "$HOME_DIR/CURSOR.md"; then
  ok "CURSOR.md mentions sessionStart"
else
  bad "CURSOR.md missing sessionStart"
fi
if grep -qi 'Cursor has no session hook' "$HOME_DIR/CURSOR.md"; then
  bad "CURSOR.md still claims no session hook"
else
  ok "stale no-hook claim absent"
fi

echo "[3] skills install + register idempotent"
UH="$WORK/home"
P="$WORK/proj"
mkdir -p "$UH" "$P"
export HOME="$UH"
mkdir -p "$HOME/.cursor"

bash "$HOME_DIR/install.sh" --skills-only >/dev/null
SKILLS="$(find "$HOME/.cursor/skills" -mindepth 1 -maxdepth 1 -type d -name 'agent-spec*' 2>/dev/null | wc -l | tr -d ' ')"
[ "$SKILLS" -ge 20 ] && ok "skills installed ($SKILLS)" || bad "too few skills ($SKILLS)"

bash "$HOME_DIR/install.sh" --register "$P" >/dev/null
[ -f "$P/.cursor/rules/agent-spec.mdc" ] && ok "mdc written" || bad "mdc missing"
[ -f "$P/.cursor/hooks.json" ] && ok "hooks.json" || bad "hooks.json"
[ -f "$P/.cursor/hooks/agent-spec-session-start.py" ] && ok "session script" || bad "session script"
[ -f "$P/.cursor/hooks/agent-spec-pre-tool-use.py" ] && ok "preTool script" || bad "preTool script"
[ -f "$P/.cursor/hooks/agent-spec-session-end.py" ] && ok "session-end script" || bad "session-end script"
[ -f "$P/.agent-spec/bin/agent-spec-receipt.py" ] && [ -f "$P/.agent-spec/bin/agent-spec-roi.py" ] && ok "receipt + roi bins" || bad "receipt/roi bins missing"
[ -f "$P/.cursor/agents/agent-spec-search.md" ] && ok "agents" || bad "agents"
[ -f "$P/.agent-spec/bin/agent-spec-platform.py" ] && [ -f "$P/.agent-spec/bin/aspec_platform/ingest.py" ] && [ -f "$P/.agent-spec/bin/agent-spec-run.py" ] && [ -f "$P/.agent-spec/bin/agent-spec-backlog.py" ] && ok "platform bins + package installed" || bad "platform bins missing from register"
[ -f "$P/.agent-spec/bin/agent-spec-platform.py" ] && [ -f "$P/.agent-spec/bin/aspec_platform/ingest.py" ] && [ -f "$P/.agent-spec/bin/agent-spec-run.py" ] && [ -f "$P/.agent-spec/bin/agent-spec-backlog.py" ] && ok "platform bins + package installed" || bad "platform bins missing from register"
[ -f "$P/.agent-spec/bin/agent-spec-digest.py" ] && ok "project bin" || bad "project bin"

bash "$HOME_DIR/install.sh" --register "$P" >/dev/null
COUNT="$($PY -c "import json;d=json.load(open('$P/.cursor/hooks.json'));print(len(d['hooks']['sessionStart']))")"
[ "$COUNT" = "1" ] && ok "sessionStart not duplicated ($COUNT)" || bad "sessionStart count=$COUNT"
COUNT2="$($PY -c "import json;d=json.load(open('$P/.cursor/hooks.json'));print(len(d['hooks']['preToolUse']))")"
[ "$COUNT2" = "1" ] && ok "preToolUse not duplicated ($COUNT2)" || bad "preToolUse count=$COUNT2"

echo "[4] digest --cursor-hook JSON"
OUT="$(cd "$P" && $PY ./.agent-spec/bin/agent-spec-digest.py --cursor-hook < /dev/null)"
$PY -c "import json,sys; json.loads(sys.argv[1])" "$OUT" && ok "digest JSON" || bad "digest JSON"

echo "[5] preToolUse fail-open / nudge"
ALLOW="$(echo '{}' | $PY "$HOME_DIR/hooks/cursor-pre-tool-use.py")"
echo "$ALLOW" | $PY -c "import json,sys; d=json.load(sys.stdin); assert d.get('permission')=='allow'" && ok "allow outside project" || bad "allow outside"

echo "[6] lean exclude"
bash "$HOME_DIR/install.sh" --skills-only --lean >/dev/null
[ ! -d "$HOME/.cursor/skills/agent-spec-hld" ] && ok "lean removed hld" || bad "lean left hld"
# restore full skill set for check-install
bash "$HOME_DIR/install.sh" --skills-only >/dev/null

echo "[7] no Claude install surface in scripts"
if rg -n '~/\.claude|WIN_CLAUDE|CLAUDE\.md|install_harness|\.claude/skills' \
  "$HOME_DIR/install.sh" "$HOME_DIR/check-install.sh" "$HOME_DIR/uninstall.sh" 2>/dev/null; then
  bad "Claude paths still in install scripts"
else
  ok "install scripts Claude-clean"
fi


echo "[8] agent-spec-tokens.py cursor audit"
T="${HOME_DIR}/bin/agent-spec-tokens.py"
BAD="${WORK}/badproj"
CLEAN="${WORK}/cleanproj"
EMPTY="${WORK}/emptyscan"
mkdir -p "${BAD}/.agent-spec" "${BAD}/.cursor/hooks" "${CLEAN}/.agent-spec" "${EMPTY}"
"$PY" -c "import json,sys; r=sys.argv[1]; json.dump({'version':1,'hooks':{'sessionStart':[{'command':'python3 .cursor/hooks/agent-spec-session-start.py'},{'command':'python3 .cursor/hooks/agent-spec-session-start.py'}],'preToolUse':[{'command':'python3 .cursor/hooks/agent-spec-pre-tool-use.py'}]}}, open(r+'/.cursor/hooks.json','w'))" "${BAD}"
AUD="$("$PY" "$T" audit --scan "${BAD}" 2>&1 || true)"
echo "$AUD" | grep -q "2 algosec-agent-spec sessionStart handlers" \
  && ok "audit flags duplicate sessionStart" || bad "audit missed duplicate sessionStart"
echo "$AUD" | grep -q "hook target missing" \
  && ok "audit flags missing hook script" || bad "audit missed missing hook script"
AUD_CLEAN="$("$PY" "$T" audit --scan "${CLEAN}" 2>&1 || true)"
echo "$AUD_CLEAN" | grep -q "no .cursor/hooks.json" \
  && ok "audit flags harness without hooks.json" || bad "audit missed missing hooks.json"
"$PY" "$T" audit --scan "${EMPTY}" >/dev/null 2>&1
[ $? -eq 0 ] && ok "audit exits 0 on empty scan tree" || bad "audit should exit 0 when clean"
[ -f "${HOME_DIR}/bin/agent-spec-tokens.py" ] && ok "package bin/agent-spec-tokens.py" || bad "tokens.py missing"

echo "[9] git auto-indexing lifecycle"
if [ -f "${HOME_DIR}/tests/test_manage_git_hooks.py" ]; then
  "$PY" "${HOME_DIR}/tests/test_manage_git_hooks.py" >/dev/null \
    && ok "git auto-indexing hooks (checkout/merge/rewrite + custom preservation)" \
    || bad "git hooks test failed"
fi

echo "[10] check-install"
bash "$HOME_DIR/check-install.sh" "$P" >/dev/null && ok "check-install" || bad "check-install"


echo "[11] Unit suites (memory, digest, preToolUse, audit, doctor/install, receipt, session-end, roi, team facts)"
for t in test_memory test_digest test_pre_tool_use test_audit test_doctor test_receipt test_session_end test_roi test_team_facts; do
  if [ -f "${HOME_DIR}/tests/${t}.py" ]; then
    # HOME was redirected for the install tests above; suites make their own sandboxes.
    if PYTHONDONTWRITEBYTECODE=1 "$PY" "${HOME_DIR}/tests/${t}.py" >"${WORK}/${t}.log" 2>&1; then
      ok "${t}: $(tail -1 "${WORK}/${t}.log")"
    else
      bad "${t} failed — $(tail -5 "${WORK}/${t}.log" | tr '\n' ' ')"
    fi
  else
    bad "${t}.py missing"
  fi
done

echo "[12] Phase 1 package invariants"
ROUTER_BYTES="$(wc -c < "${HOME_DIR}/skills/agent-spec/SKILL.md" | tr -d ' ')"
[ "$ROUTER_BYTES" -lt 3072 ] && ok "router skill ${ROUTER_BYTES} B (<3072)" || bad "router skill ${ROUTER_BYTES} B (limit 3072)"
grep -q "agent-spec-gate.py status" "${HOME_DIR}/skills/agent-spec/SKILL.md" && ok "router points at gate status" || bad "router lacks gate status pointer"
grep -q "### Tool discipline" "${HOME_DIR}/CURSOR.md" && ok "CURSOR.md tool discipline" || bad "CURSOR.md lacks Tool discipline"
[ -f "${HOME_DIR}/bin/agent-spec-doctor.py" ] && ok "doctor shipped" || bad "doctor missing"
[ -f "${HOME_DIR}/templates/team.yaml" ] && ok "team.yaml template" || bad "team.yaml template missing"
if grep -q "YYYY-MM-DD" "${HOME_DIR}/context/TECH-DEBT-REGISTER.md"; then bad "debt template still has placeholders"; else ok "debt template placeholder-free"; fi
grep -q '^\*\*Code change\*\*' "${HOME_DIR}/CURSOR.md" && ok "CURSOR.md auto-harness rule (T-052)" || bad "CURSOR.md lacks the Code change rule"
CURSOR_BYTES="$(wc -c < "${HOME_DIR}/CURSOR.md" | tr -d ' ')"
[ "$CURSOR_BYTES" -lt 4600 ] && ok "CURSOR.md ${CURSOR_BYTES} B (<4600)" || bad "CURSOR.md ${CURSOR_BYTES} B grew past the 4600 B always-on budget"
LINT="$("$PY" "${HOME_DIR}/bin/agent-spec-lint-refs.py" "${HOME_DIR}" 2>&1 | tail -1 || true)"
[ "$LINT" = "every path and skill name resolves" ] && ok "doc refs: 0 dangling (T-059)" || bad "doc refs: ${LINT}"
echo "[13] platform (Phase 2): data layer, ingest, API, run plumbing (stdlib only, DEC-12)"
while read -r t; do
  case "$t" in ""|\#*) continue;; esac
  [ -f "${HOME_DIR}/tests/${t}.py" ] || { bad "${t}.py missing"; continue; }
  # </dev/null: a suite that reads stdin would otherwise swallow the rest of this list.
  if PYTHONDONTWRITEBYTECODE=1 "$PY" "${HOME_DIR}/tests/${t}.py" >"${WORK}/${t}.log" 2>&1 </dev/null; then
    ok "${t}: $(tail -1 "${WORK}/${t}.log")"
  else
    bad "${t} failed — $(tail -5 "${WORK}/${t}.log" | tr '\n' ' ')"
  fi
done < "${HOME_DIR}/tests/platform-suites.txt"
for wf in "${HOME_DIR}"/skills/agent-spec-wf-*/SKILL.md; do
  name="$(basename "$(dirname "$wf")")"
  if "$PY" "${HOME_DIR}/bin/agent-spec-run.py" validate "$wf" >"${WORK}/${name}.validate" 2>&1; then
    ok "${name}: workflow validates"
  else
    bad "${name} failed validate — $(tail -3 "${WORK}/${name}.validate" | tr '\n' ' ')"
  fi
done
echo ""
if [ "$FAILS" -eq 0 ]; then
  echo "All selftests passed."
  exit 0
fi
echo "$FAILS failure(s)."
exit 1
