#!/usr/bin/env python3
"""Cursor preToolUse hook — agent-spec input discipline.

MARKER: agent-spec:preToolUse

Fail-open: any parse/logic error returns allow. One nudge per target per session;
retry goes through. Maps Cursor tool names onto the shared check() rules.
"""
import hashlib
import json
import os
import re
import shlex
import sys
import tempfile
import time
import uuid

READ_CAP = 20000
# Optional hard cap: AGENT_SPEC_READ_HARD_CAP_KB=N denies every rangeless Read of N KB or
# more, with no retry-as-is bypass. Unset (default) keeps the one-nudge behaviour.
HARD_CAP_ENV = "AGENT_SPEC_READ_HARD_CAP_KB"
DEBUG_ENV = "AGENT_SPEC_HOOK_DEBUG"
TOKEN_THRESHOLD_ENV = "AGENT_SPEC_TOKEN_THRESHOLD"
DEFAULT_TOKEN_THRESHOLD = 80000
RANGE_KEYS = ("limit", "offset", "start_line", "end_line", "line_start", "line_end", "lines",
              "range", "view_range", "startline", "endline", "line_range")
WRITE_CAP = 2000
EDIT_KEYS = ("old_string", "new_string", "old_str", "new_str", "search", "replace")
FILTERED = ("|", ">", "head", "tail", "grep", "wc", "diffstat")
# Commands whose output is long and mostly passing lines: test runners, builds, linters, type
# checkers. Run in the main chat, all of it stays in context and is re-sent on every later turn;
# the agent-spec-verify subagent runs it in its own context and hands back only the failures.
# Matched in command position only (start, or after ; & ( ), so `grep make` is not a build.
NOISY = re.compile(
    r"(?:^|[;&(])\s*(?:\w+=\S*\s+)*(?:"
    r"(?:python3?|uv run|poetry run)\s+-m\s+(?:pytest|unittest)\b|py\.?test\b|tox\b|nox\b"
    r"|(?:npm|pnpm|yarn|bun)\s+(?:run\s+)?(?:test|build|lint|typecheck|check)\b|npx\s+(?:jest|vitest|tsc|eslint)\b"
    r"|jest\b|vitest\b|mocha\b|tsc\b|eslint\b|mypy\b|ruff\s+check\b"
    r"|go\s+(?:test|build|vet)\b|cargo\s+(?:test|build|clippy)\b|mvn\b|\./?gradlew?\b|make\b)")
MARKER_TTL = 86400


def nudged_already(session_id, key):
    root = os.path.join(tempfile.gettempdir(), "agent-spec-nudge")
    slug = hashlib.sha1(
        ("%s\x00%s\x00%s" % (session_id, os.getcwd(), key)).encode("utf-8")
    ).hexdigest()[:20]
    marker = os.path.join(root, slug)
    try:
        if os.path.getmtime(marker) > time.time() - MARKER_TTL:
            return True
    except OSError:
        pass
    try:
        os.makedirs(root, exist_ok=True)
        open(marker, "w").close()
        _sweep(root)
    except OSError:
        pass
    return False


def _sweep(root):
    cutoff = time.time() - MARKER_TTL
    try:
        for name in os.listdir(root):
            path = os.path.join(root, name)
            try:
                if os.path.getmtime(path) < cutoff:
                    os.remove(path)
            except OSError:
                pass
    except OSError:
        pass


def size_of(path):
    try:
        return os.path.getsize(path)
    except OSError:
        return -1


def is_ranged(args):
    """True when a Read names a slice. Keys are matched case-insensitively and one level
    of nesting is searched (e.g. {"range": {"offset": 1}}); any present, non-empty value
    counts, including offset 0, because the caller chose a window."""
    if not isinstance(args, dict):
        return False
    for k, v in args.items():
        if str(k).lower() in RANGE_KEYS and v not in (None, "", False):
            return True
        if isinstance(v, dict) and is_ranged(v):
            return True
    return False


def token_threshold():
    """Context token threshold above which /agent-spec-compact is nudged (S-004)."""
    try:
        val = int(os.environ.get(TOKEN_THRESHOLD_ENV, DEFAULT_TOKEN_THRESHOLD))
        return val if val > 0 else DEFAULT_TOKEN_THRESHOLD
    except ValueError:
        return DEFAULT_TOKEN_THRESHOLD


def extract_tokens(payload):
    """Extract reported session or total tokens from payload, if present."""
    for key in ("session_tokens", "token_count", "total_tokens", "context_tokens"):
        if key in payload and isinstance(payload[key], (int, float)):
            return int(payload[key])
    tokens_obj = payload.get("tokens")
    if isinstance(tokens_obj, (int, float)):
        return int(tokens_obj)
    if isinstance(tokens_obj, dict):
        total = tokens_obj.get("total")
        if isinstance(total, (int, float)):
            return int(total)
        tin = tokens_obj.get("input") or tokens_obj.get("prompt") or 0
        tout = tokens_obj.get("output") or tokens_obj.get("completion") or 0
        if isinstance(tin, (int, float)) and isinstance(tout, (int, float)) and (tin + tout > 0):
            return int(tin + tout)
    return None


def track_session_tokens(session_id, payload, raw_len):
    """Accumulate and return session tokens footprint (S-004)."""
    direct = extract_tokens(payload)
    if not session_id or session_id == "none":
        return direct if direct is not None else (raw_len + 3) // 4
    root = os.path.join(tempfile.gettempdir(), "agent-spec-tokens")
    slug = hashlib.sha1(("%s\x00%s" % (session_id, os.getcwd())).encode("utf-8")).hexdigest()[:20]
    path = os.path.join(root, slug)
    accum = 0
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as fh:
                accum = json.load(fh).get("tokens", 0)
    except Exception:
        accum = 0
    call_tokens = (raw_len + 3) // 4
    total = max(direct, accum + call_tokens) if direct is not None else (accum + call_tokens)
    try:
        os.makedirs(root, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"tokens": total, "ts": time.time()}, fh)
    except Exception:
        pass
    return total


def hard_cap_bytes():
    """The hard cap in bytes, or None when the env flag is unset or not a positive integer."""
    try:
        kb = int(os.environ.get(HARD_CAP_ENV, ""))
    except ValueError:
        return None
    return kb * 1024 if kb > 0 else None


def hard_cap_hit(tool, args):
    """Deny message for a rangeless Read at or above the hard cap, else None."""
    cap = hard_cap_bytes()
    if cap is None or tool not in ("Read", "read_file") or is_ranged(args):
        return None
    path = args.get("file_path") or args.get("path") or args.get("target_file") or ""
    size = size_of(path)
    if size < cap:
        return None
    return (
        "%s is %d B, over the %d KB hard cap (%s). Query the graph "
        "(./.agent-spec/bin/graphify-cli.py query --file) or grep -n then Read a range "
        "with offset/limit. To lift the cap, unset %s." % (path, size, cap // 1024, HARD_CAP_ENV, HARD_CAP_ENV)
    )


def debug_enabled():
    """Debug is on with AGENT_SPEC_HOOK_DEBUG=1 or a `.agent-spec/.hook-debug` marker file.
    The marker exists because Cursor's environment is fixed when the app starts."""
    return bool(os.environ.get(DEBUG_ENV)) or os.path.exists("./.agent-spec/.hook-debug")


def shape(args):
    """Key -> type name, plus the value itself for numbers and booleans. Never string
    contents, so a debug row cannot leak file text or commands."""
    out = {}
    for k, v in args.items():
        if isinstance(v, (bool, int, float)) or v is None:
            out[k] = v
        else:
            out[k] = type(v).__name__
    return out


def debug_log(tool, payload, args, decision=None):
    """Record payload *shape* (keys and value types, never strings) so a mismatch between
    Cursor's real payload and this hook's assumptions can be diagnosed."""
    if not debug_enabled():
        return
    try:
        row = {"ts": time.time(), "tool": tool, "payload_keys": sorted(payload.keys()),
               "arg_keys": sorted(args.keys()), "arg_shape": shape(args),
               "ranged": is_ranged(args), "decision": decision}
        with open(os.path.join(tempfile.gettempdir(), "agent-spec-hook-debug.jsonl"), "a") as fh:
            fh.write(json.dumps(row) + "\n")
    except OSError:
        pass


# ---- S-002 secrets & sensitive-path quarantine --------------------------------------------
# Hard deny (no retry bypass) for tool calls that touch secret files or key/credential dirs.
# Runs before any other parsing; ordinary errors fail open, but a matchable payload is never
# skipped: if structured extraction fails, the raw payload text is matched instead.
SAFE_SUFFIXES = (".example", ".sample", ".template")
SENSITIVE_DIRS = {".aws": "aws-dir", ".ssh": "ssh-dir", ".gnupg": "gnupg-dir"}
PATH_KEYS = frozenset((
    "path", "paths", "file_path", "filepath", "filename", "file", "files", "target_file",
    "target_directory", "target_notebook", "notebook_path", "directory", "dir", "glob",
    "glob_pattern", "include", "cwd", "working_directory", "relative_workspace_path",
    "old_path", "new_path", "source", "destination", "src", "dst",
))
COMMAND_KEYS = frozenset(("command", "cmd", "script"))
ARG_KEYS = ("tool_input", "arguments", "input")
TOKEN_SPLIT = re.compile(r"[\s\"'`;|&<>=,:()\[\]{}\\]+")


def _name_rule(base):
    """Rule-id for a bare file name, or None. `base` is already lower-cased."""
    if base.endswith(SAFE_SUFFIXES):
        return None
    wild = "*" in base or "?" in base
    if base == ".env" or base.startswith(".env.") or (wild and base.startswith(".env")):
        return "env-file"
    if base.startswith(("id_rsa", "id_ed25519")):
        return "ssh-private-key"
    if base.endswith(".pem"):
        return "pem-file"
    if base.endswith(".key"):
        return "key-file"
    if base == "credentials" or base.startswith("credentials.") or (wild and base.startswith("credentials")):
        return "credentials-file"
    if base.startswith("secrets.") or (wild and base.startswith("secrets")):
        return "secrets-file"
    return None


def _token_rule(token):
    """(rule-id, basename) when one path/command token names a sensitive target."""
    segs = [s for s in token.lower().split("/") if s]
    if not segs:
        return None
    rule = _name_rule(segs[-1])
    if rule:
        return rule, segs[-1]
    for seg in segs:
        if seg in SENSITIVE_DIRS:
            return SENSITIVE_DIRS[seg], segs[-1]
    return None


def _match_text(text):
    for token in TOKEN_SPLIT.split(text):
        hit = _token_rule(token)
        if hit:
            return hit
    return None


def _strings(value, out):
    if isinstance(value, str):
        out.append(value)
    elif isinstance(value, (list, tuple)):
        for v in value:
            _strings(v, out)
    elif isinstance(value, dict):
        for v in value.values():
            _strings(v, out)


def _gather(args, out):
    """Collect path/command strings from a tool-input value. Raises ValueError on a shape
    it cannot interpret so the caller falls back to the raw payload text."""
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except ValueError:
            out.append(args)  # unparseable string: match its text as-is
            return
    if not isinstance(args, dict):
        raise ValueError("unexpected tool input shape")
    for k, v in args.items():
        kl = str(k).lower()
        if kl in PATH_KEYS or kl in COMMAND_KEYS:
            _strings(v, out)
        elif isinstance(v, dict):
            _gather(v, out)
        elif isinstance(v, list):
            for item in v:
                if isinstance(item, dict):
                    _gather(item, out)


def quarantine_hit(raw):
    """(rule-id, basename) when the payload touches a quarantined target, else None."""
    try:
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("payload is not an object")
        strings = []
        for key in ARG_KEYS:
            if key in payload:
                _gather(payload[key], strings)
        tool_obj = payload.get("tool")
        if isinstance(tool_obj, dict):
            for key in ARG_KEYS:
                if key in tool_obj:
                    _gather(tool_obj[key], strings)
        return _match_text("\n".join(strings))
    except Exception:
        return _match_text(raw)


def quarantine_log(project_dir, tool, hit, session_id):
    """Append one redacted JSON line (basename + rule only). Never raises."""
    try:
        agent_dir = os.path.join(project_dir, ".agent-spec")
        if not os.path.isdir(agent_dir):
            return
        metrics = os.path.join(agent_dir, "metrics")
        os.makedirs(metrics, exist_ok=True)
        row = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "tool": str(tool)[:64],
               "pattern": hit[0], "path": hit[1][:120]}
        if session_id:
            row["session_id"] = str(session_id)[:128]
        with open(os.path.join(metrics, "quarantine.jsonl"), "a") as fh:
            fh.write(json.dumps(row) + "\n")
    except Exception:
        pass


def _remember_ctx(payload):
    """Documented common fields (cursor.com/docs/hooks) for guard_event; never raises."""
    try:
        roots = payload.get("workspace_roots")
        if isinstance(roots, list) and roots and isinstance(roots[0], str) and os.path.isdir(roots[0]):
            _GUARD_CTX["root"] = roots[0]
        for key in ("conversation_id", "generation_id", "tool_name", "tool_use_id"):
            if payload.get(key):
                _GUARD_CTX[key] = str(payload[key])[:128]
        # Claude Code (the bench, and a Claude Code user of the package) names the event
        # "PreToolUse" and reads its own verdict shape; Cursor sends "preToolUse".
        _GUARD_CTX["claude"] = payload.get("hook_event_name") == "PreToolUse"
        if _GUARD_CTX["claude"] and payload.get("session_id"):
            _GUARD_CTX.setdefault("conversation_id", str(payload["session_id"])[:128])
    except Exception:
        pass


def _payload_meta(raw):
    """Best-effort (tool name, session id) for the log; never raises."""
    try:
        payload = json.loads(raw)
        tool = (payload.get("tool_name") or payload.get("toolName")
                or (payload.get("tool") or {}).get("name") or "unknown")
        if isinstance(payload, dict):
            _remember_ctx(payload)
        return tool, payload.get("conversation_id") or payload.get("session_id") or payload.get("sessionId")
    except Exception:
        return "unknown", None


# Images and PDFs are not read by line, so offset/limit cannot shrink them: never gate them.
NOT_LINE_READ = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".ico", ".pdf")


def in_subagent(payload):
    """True for a tool call a subagent makes: Cursor tags it with `parent_tool_call_id`
    (3.30), Claude Code with `agent_id`. The verify subagent must run the command itself."""
    return bool(payload.get("parent_tool_call_id") or payload.get("agent_id"))


def delegate_hit(tool, args, payload):
    """(key, message) when the main chat is about to run a noisy command with nothing cutting its
    output down, else None. A pipe into a filter (`| tail -n 4`) or a redirect into a log is left
    alone: either is cheaper than a subagent, which starts cold (about 26k tokens of setup in
    bench run c82667, against a 340 B `pytest -q | tail -n 4`). Nudging a redirect too doubled the
    turn's cost there ($0.0106 against $0.0046)."""
    if tool not in ("Shell", "Bash", "shell", "bash") or in_subagent(payload):
        return None
    cmd = str(args.get("command", ""))
    if any(f in cmd for f in ("|", ">")) or not NOISY.search(cmd):
        return None
    return "delegate:" + " ".join(cmd.split()), (
        "This project runs test suites, builds and linters through the agent-spec-verify "
        "subagent, so their output stays out of this chat (it would be re-sent on every later "
        "turn). Call the Task/Agent tool with subagent_type agent-spec-verify, in the foreground "
        "(run_in_background false: you need its verdict before you go on), and the prompt: "
        "Run `%s` and report. It returns the verdict and only the failures, verbatim with "
        "file:line. Retry as-is only if you need the full output here." % cmd.strip()
    )


def check(tool, args):
    if tool in ("Read", "read_file"):
        path = args.get("file_path") or args.get("path") or args.get("target_file") or ""
        if is_ranged(args) or path.lower().endswith(NOT_LINE_READ):
            return None
        size = size_of(path)
        if size >= READ_CAP:
            return path, (
                "%s is %d B and this Read has no offset/limit. Query the graph "
                "(./.agent-spec/bin/graphify-cli.py query --file), or grep -n then "
                "Read a range. Retry as-is if you truly need all of it."
                % (path, size)
            )
        return None

    if tool in ("Write", "write"):
        # Cursor may report a targeted edit (StrReplace) under the Write tool name; such
        # a call carries old_string/new_string and is exactly what the nudge asks for.
        if any(k in args for k in EDIT_KEYS):
            return None
        path = args.get("file_path") or args.get("path") or ""
        size = size_of(path)
        if size >= WRITE_CAP:
            return path, (
                "%s already exists at %d B. Prefer a targeted edit over a full Write. "
                "Retry as-is if a full rewrite is intended." % (path, size)
            )
        return None

    if tool in ("Shell", "Bash", "shell", "bash"):
        cmd = args.get("command", "")
        low = cmd.lower()
        if any(f in low for f in FILTERED):
            return None
        if "git diff" in low and not any(
            flag in low for flag in ("--stat", "--name-only", "--numstat", "--shortstat")
        ):
            return "git-diff", (
                "git diff without --stat pastes every changed line into context. "
                "Run git diff --stat first. Retry as-is if you need the full diff."
            )
        try:
            parts = shlex.split(cmd)
        except ValueError:
            return None
        if parts and parts[0] == "cat":
            for path in parts[1:]:
                if path.startswith("-"):
                    continue
                size = size_of(path)
                if size >= READ_CAP:
                    return path, (
                        "cat %s is %d B into context. Use grep -n, then a ranged read. "
                        "Retry as-is if you need the whole file." % (path, size)
                    )
        return None

    return None


def allow():
    if not _GUARD_CTX.get("claude"):  # Claude Code: no output leaves its own permission rules in charge
        sys.stdout.write(json.dumps({"permission": "allow"}))
    return 0


_GUARD_CTX = {}


def guard_event(rule, target=""):
    """DV-001 guard span: one row in events.jsonl per deny, keyed like every hook row so the
    dashboard can place it inside its request trace. Never raises."""
    try:
        root = _GUARD_CTX.get("root") or os.getcwd()
        if not os.path.isdir(os.path.join(root, ".agent-spec")):
            return
        metrics = os.path.join(root, ".agent-spec", "metrics")
        os.makedirs(metrics, exist_ok=True)
        now = time.time()
        row = {"id": "g" + uuid.uuid4().hex[:15],
               "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(now)) + ".%03dZ" % int((now % 1) * 1000),
               "event": "guard", "decision": "deny", "rule": str(rule)[:64],
               "conversation_id": _GUARD_CTX.get("conversation_id") or "unknown",
               "generation_id": _GUARD_CTX.get("generation_id"),
               "tool_name": _GUARD_CTX.get("tool_name") or "unknown",
               "target": os.path.basename(str(target))[:120]}
        if _GUARD_CTX.get("tool_use_id"):
            row["tool_use_id"] = _GUARD_CTX["tool_use_id"]
        with open(os.path.join(metrics, "events.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, separators=(",", ":")) + "\n")
    except Exception:
        pass


def deny(message, user_message="agent-spec input discipline", rule="input-discipline", target=""):
    guard_event(rule, target)
    if _GUARD_CTX.get("claude"):
        sys.stdout.write(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "permissionDecision": "deny",
            "permissionDecisionReason": message}}))
        return 0
    sys.stdout.write(
        json.dumps(
            {
                "permission": "deny",
                "user_message": user_message,
                "agent_message": message,
            }
        )
    )
    return 0


def _risk_module():
    """.agent-spec/bin/agent-spec-risk.py, loaded once; None when this project predates it."""
    path = os.path.join(os.getcwd(), ".agent-spec", "bin", "agent-spec-risk.py")
    if not os.path.isfile(path):
        return None
    import importlib.util
    spec = importlib.util.spec_from_file_location("agent_spec_risk", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def risk_gate(tool, args, session_id):
    """True when the call was denied (the verdict is written). P4-012: tier 0-1 pass, tier 2 passes with a recorded warning, tier 3 waits for a
    one-use approval from the dashboard (or `agent-spec-risk.py approve`). Fail-open: a
    classifier error allows the call and is written to metrics/risk.jsonl."""
    project = os.getcwd()
    try:
        risk = _risk_module()
        if risk is None:
            return None
        cfg = risk.config(project)
        if cfg.get("enforce") == "off":
            return None
        result = risk.classify(project, tool, args)
    except Exception as exc:
        try:
            with open(os.path.join(project, ".agent-spec", "metrics", "risk.jsonl"), "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "event": "error",
                                     "tool": str(tool), "error": ("%s: %s" % (type(exc).__name__, exc))[:300]}) + "\n")
        except Exception:
            pass
        return None
    tier = result.get("tier", 0)
    if tier < 2:
        return None
    what = result.get("file") or result.get("target") or tool
    if tier == 2 or cfg.get("enforce") == "warn":
        risk._audit(project, {"event": "warned", "key": risk.action_key(result), "tier": tier, "tool": result["tool"],
                              "target": what, "reasons": result.get("reasons"), "session": session_id})
        return None
    if result.get("protected"):
        # The gate's own approvals, config and code: no approval unlocks these for the agent.
        risk._audit(project, {"event": "blocked", "tier": 3, "tool": result["tool"], "target": what,
                              "reasons": result.get("reasons"), "session": session_id, "protected": True})
        deny("Risk gate (P4-012): %s — %s. The agent may not change the gate or approve its own actions; "
             "tell the user what you need and stop." % (what, "; ".join(result.get("reasons") or [])),
             "agent-spec risk gate: protected path (%s)" % what,
             rule="P4-012-protected", target=what)
        return True
    if risk.consume_approval(project, result, session_id):
        return None
    risk.record_blocked(project, result, session_id)
    deny(
        "Risk tier 3 (P4-012): %s — %s. This change waits for a person: ask the user to approve it in "
        "the dashboard (Project > Risk), then retry the same call. Do not work around it with a "
        "different tool, and do not try to approve it yourself."
        % (what, "; ".join(result.get("reasons") or [])),
        "agent-spec risk gate: tier 3 change needs approval (%s)" % what,
        rule="P4-012-tier3", target=what,
    )
    return True


def main():
    try:
        raw = sys.stdin.buffer.read().decode("utf-8", "replace")
    except Exception:
        raw = ""
    try:
        hit = quarantine_hit(raw)
    except Exception:
        hit = None
    if hit:
        tool_name, session_id = _payload_meta(raw)
        quarantine_log(os.getcwd(), tool_name, hit, session_id)
        _GUARD_CTX.setdefault("tool_name", tool_name)
        return deny(
            "Quarantine rule %s (S-002): this tool call touches a secrets/credentials path. "
            "Do not read, edit, list or copy it; ask the user to handle it manually "
            "(use .env.example for templates)." % hit[0],
            "agent-spec quarantine: blocked sensitive path (%s)" % hit[0],
            rule="S-002-" + str(hit[0]), target=hit[1],
        )
    if not os.path.isdir("./.agent-spec"):
        return allow()
    try:
        payload = json.loads(raw)
    except (ValueError, OSError):
        return allow()
    if not isinstance(payload, dict):
        return allow()
    _remember_ctx(payload)

    tool = (
        payload.get("tool_name")
        or payload.get("toolName")
        or (payload.get("tool") or {}).get("name")
        or ""
    )
    args = (
        payload.get("tool_input")
        or payload.get("arguments")
        or payload.get("input")
        or {}
    )
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except ValueError:
            return allow()
    if not isinstance(args, dict):
        return allow()

    session_id = (
        payload.get("conversation_id")
        or payload.get("session_id")
        or payload.get("sessionId")
        or "none"
    )

    if risk_gate(tool, args, session_id):
        return 0  # the deny verdict is already written

    threshold = token_threshold()
    session_tokens = track_session_tokens(session_id, payload, len(raw))
    if session_tokens > threshold:
        if not nudged_already(session_id, "token-threshold-80k"):
            debug_log(tool, payload, args, "deny-token-threshold")
            quarantine_log(os.getcwd(), tool, ("S-004-threshold", "session_tokens=%d>%d" % (session_tokens, threshold)), session_id)
            return deny(
                "Session token footprint is ~%d tokens, exceeding the %d threshold (S-004). "
                "Proactive context threshold reached: run `/agent-spec-compact` to "
                "prevent needle-in-haystack degradation and preserve state before proceeding. "
                "Retry as-is if you wish to continue without compacting."
                % (session_tokens, threshold),
                "agent-spec context threshold nudge (>80k tokens)",
                rule="S-004-threshold",
            )

    if payload.get("cursor_version") and (
            (tool in ("Read", "read_file") and not is_ranged(args))
            or (tool in ("Write", "write") and "old_string" not in args)):
        # Cursor rewrites tool calls before preToolUse (docs/PHASE1-VERIFICATION.md §F): it
        # strips offset/limit from a Read, and reports a StrReplace as Write with the whole
        # new file as content. A ranged and a whole read, or a targeted edit and a rewrite,
        # look the same here. Follow Cursor's harness: allow, and let the postToolUse and
        # afterFileEdit spine rows judge the call from what actually happened.
        # The hard cap cannot apply either: Cursor's ranged reads of a large file would be
        # denied with advice (read a range) the agent has no way to follow. Record when it
        # would have fired, so a user who set the cap can see it was skipped, not missed.
        try:
            over_cap = hard_cap_hit(tool, args) is not None
        except Exception:
            over_cap = False
        debug_log(tool, payload, args, "allow-unobservable-over-cap" if over_cap else "allow-unobservable")
        return allow()

    try:
        hard = hard_cap_hit(tool, args)
    except Exception:
        hard = None
    if hard:
        debug_log(tool, payload, args, "deny-hard-cap")
        return deny(hard, rule="hard-cap", target=args.get("file_path") or args.get("path") or "")

    try:
        hit = delegate_hit(tool, args, payload)
    except Exception:
        hit = None
    if hit:
        if nudged_already(session_id, hit[0]):
            debug_log(tool, payload, args, "allow-retry")
            return allow()
        debug_log(tool, payload, args, "deny-delegate")
        return deny(hit[1], "agent-spec: delegate to agent-spec-verify", rule="delegate-verify",
                    target=" ".join(str(args.get("command", "")).split()[:3]))

    try:
        hit = check(tool, args)
    except Exception:
        debug_log(tool, payload, args, "allow-error")
        return allow()
    if not hit:
        debug_log(tool, payload, args, "allow")
        return allow()

    key, message = hit
    session_id = (
        payload.get("conversation_id")
        or payload.get("session_id")
        or payload.get("sessionId")
        or "none"
    )
    if nudged_already(session_id, tool + ":" + key):
        debug_log(tool, payload, args, "allow-retry")
        return allow()
    debug_log(tool, payload, args, "deny-nudge")
    return deny(message, rule="whole-file-read", target=key)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        try:
            sys.stdout.write(json.dumps({"permission": "allow"}))
        except Exception:
            pass
        sys.exit(0)
