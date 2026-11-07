#!/usr/bin/env python3
"""Cursor preToolUse hook — algosec-agent-spec input discipline.

MARKER: algosec-agent-spec:preToolUse

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
MARKER_TTL = 86400


def nudged_already(session_id, key):
    root = os.path.join(tempfile.gettempdir(), "algosec-agent-spec-nudge")
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
    root = os.path.join(tempfile.gettempdir(), "algosec-agent-spec-tokens")
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
        with open(os.path.join(tempfile.gettempdir(), "algosec-agent-spec-hook-debug.jsonl"), "a") as fh:
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


def _payload_meta(raw):
    """Best-effort (tool name, session id) for the log; never raises."""
    try:
        payload = json.loads(raw)
        tool = (payload.get("tool_name") or payload.get("toolName")
                or (payload.get("tool") or {}).get("name") or "unknown")
        return tool, payload.get("session_id") or payload.get("sessionId")
    except Exception:
        return "unknown", None


def check(tool, args):
    if tool in ("Read", "read_file"):
        path = args.get("file_path") or args.get("path") or args.get("target_file") or ""
        if is_ranged(args):
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
    sys.stdout.write(json.dumps({"permission": "allow"}))
    return 0


def deny(message, user_message="algosec-agent-spec input discipline"):
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
        return deny(
            "Quarantine rule %s (S-002): this tool call touches a secrets/credentials path. "
            "Do not read, edit, list or copy it; ask the user to handle it manually "
            "(use .env.example for templates)." % hit[0],
            "algosec-agent-spec quarantine: blocked sensitive path (%s)" % hit[0],
        )
    if not os.path.isdir("./.agent-spec"):
        return allow()
    try:
        payload = json.loads(raw)
    except (ValueError, OSError):
        return allow()
    if not isinstance(payload, dict):
        return allow()

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
        payload.get("session_id")
        or payload.get("sessionId")
        or "none"
    )

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
                "algosec-agent-spec context threshold nudge (>80k tokens)",
            )

    try:
        hard = hard_cap_hit(tool, args)
    except Exception:
        hard = None
    if hard:
        debug_log(tool, payload, args, "deny-hard-cap")
        return deny(hard)

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
        payload.get("session_id")
        or payload.get("sessionId")
        or "none"
    )
    if nudged_already(session_id, tool + ":" + key):
        debug_log(tool, payload, args, "allow-retry")
        return allow()
    debug_log(tool, payload, args, "deny-nudge")
    return deny(message)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        try:
            sys.stdout.write(json.dumps({"permission": "allow"}))
        except Exception:
            pass
        sys.exit(0)
