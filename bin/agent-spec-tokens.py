#!/usr/bin/env python3
"""Measure session token cost and harness overhead (algosec-agent-spec / Cursor).

By default, `list`, `session`, `overhead`, `corpus`, `context`, `tools`, and `compare`
read **Cursor** agent transcripts under
`~/.cursor/projects/<workspace-slug>/agent-transcripts/<session>/<session>.jsonl`.
Cursor JSONL usually has no `usage` object; those commands then estimate in/out from
message size (chars ÷ 4) and parse harness tags in user turns for `overhead`.

With `--claude`, the same commands use Claude Code JSONL (~/.claude/projects/…) where
assistant `usage` is ground truth for the four token buckets.

`audit` scans Cursor harness config (`.cursor/hooks.json`, rules, skills, memory). Pass
`--include-claude` to also scan Claude settings and `.claude/skills` twins.

Read-only. Never writes under ~/.cursor, ~/.claude, or project trees.

  audit     harness config on this machine (Cursor-first)
  overhead  what the harness re-sends each turn besides the conversation
  session   four buckets, weighted (exact with Claude usage; estimated on Cursor)
  list      transcripts for the cwd workspace root
"""
import argparse
import getpass
import json
import os
import re
import sys
from collections import Counter, defaultdict

# Price ratios relative to a fresh input token. These are an assumption about the model
# being billed, not a measurement, so they are overridable rather than buried: output is
# roughly five times input, a cache write about 1.25x, and a cache read a tenth.
DEFAULT_WEIGHTS = {"out": 5.0, "write": 1.25, "read": 0.1, "in": 1.0}

BUCKETS = [
    ("cache_read_input_tokens", "read"),
    ("cache_creation_input_tokens", "write"),
    ("output_tokens", "out"),
    ("input_tokens", "in"),
]

CURSOR_HARNESS_RE = [
    ("attached_skills", re.compile(
        r"<manually_attached_skills\b[^>]*>(.*?)</manually_attached_skills>", re.I | re.S)),
    ("hooks_context", re.compile(
        r"<hooks_context\b[^>]*>(.*?)</hooks_context>", re.I | re.S)),
    ("agent_spec_digest", re.compile(
        r"<agent-spec-digest\b[^>]*>(.*?)</agent-spec-digest>", re.I | re.S)),
    ("workspace_rules", re.compile(
        r"<always_applied_workspace_rules\b[^>]*>(.*?)</always_applied_workspace_rules>",
        re.I | re.S)),
    ("user_rules", re.compile(
        r"<user_rules\b[^>]*>(.*?)</user_rules>", re.I | re.S)),
]


def cursor_projects_root():
    return os.path.join(os.path.expanduser("~"), ".cursor", "projects")


def cursor_project_slug(cwd=None):
    """Cursor folder under ~/.cursor/projects: drop leading /, then `-` for `/` and `.`."""
    cwd = os.path.abspath(cwd or os.getcwd())
    if cwd.startswith(os.sep):
        cwd = cwd[len(os.sep):]
    return cwd.replace(os.sep, "-").replace(".", "-")


def cursor_transcript_dir(cwd=None):
    return os.path.join(cursor_projects_root(), cursor_project_slug(cwd), "agent-transcripts")


def cursor_transcripts(cwd=None):
    """Main session JSONL files for this workspace (not subagent transcripts)."""
    base = cursor_transcript_dir(cwd)
    names = []
    try:
        sessions = os.listdir(base)
    except OSError:
        return []
    for sid in sessions:
        main = os.path.join(base, sid, sid + ".jsonl")
        if os.path.isfile(main):
            names.append(main)
    return sorted(names, key=lambda p: os.path.getmtime(p), reverse=True)


def transcript_format(path):
    """'cursor' or 'claude' from the first JSONL record."""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                if entry.get("type") == "attachment":
                    return "claude"
                if entry.get("role") in ("user", "assistant"):
                    return "cursor"
                if entry.get("type") == "assistant":
                    return "claude"
                break
    except (OSError, ValueError):
        pass
    return "cursor"


def message_content(entry):
    message = entry.get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts = []
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text":
            parts.append(block.get("text") or "")
        elif block.get("type") == "tool_use":
            parts.append(json.dumps(block.get("input", {})))
    return "".join(parts)


def is_assistant_turn(entry):
    if entry.get("type") == "assistant":
        return True
    return entry.get("role") == "assistant"


def assistant_usage(entry):
    message = entry.get("message") or {}
    return message.get("usage") or entry.get("usage")


def claude_roots():
    """Every .claude directory whose transcripts and settings belong to this user.

    Under WSL the Windows app keeps its own profile, so a machine has two.
    """
    home = os.path.join(os.path.expanduser("~"), ".claude")
    roots = [home]
    win = os.environ.get("WIN_CLAUDE_HOME") or os.path.join("/mnt/c/Users", getpass.getuser())
    win = os.path.join(win, ".claude")
    if os.path.isdir(win) and os.path.realpath(win) != os.path.realpath(home):
        roots.append(win)
    return roots


def project_dir(cwd=None):
    """Claude Code stores transcripts under the working directory with / replaced by -."""
    cwd = os.path.abspath(cwd or os.getcwd())
    return os.path.join(claude_roots()[0], "projects", cwd.replace(os.sep, "-"))


def project_dirs(cwd=None):
    """project_dir on every root. The Windows app names a WSL path by its UNC form."""
    cwd = os.path.abspath(cwd or os.getcwd())
    out = [project_dir(cwd)]
    distro = os.environ.get("WSL_DISTRO_NAME")
    for root in claude_roots()[1:]:
        if distro:
            unc = "\\\\wsl.localhost\\" + distro + cwd.replace(os.sep, "\\")
            out.append(os.path.join(root, "projects", re.sub(r"[^A-Za-z0-9]", "-", unc)))
    return out


def claude_transcripts(cwd=None):
    names = []
    for d in project_dirs(cwd):
        try:
            names += [os.path.join(d, n) for n in os.listdir(d) if n.endswith(".jsonl")]
        except OSError:
            continue
    return sorted(names, key=lambda p: os.path.getmtime(p), reverse=True)


def transcripts(cwd=None, claude_only=False):
    if not claude_only:
        found = cursor_transcripts(cwd)
        if found:
            return found
    return claude_transcripts(cwd)


def resolve(args):
    """The transcript to read, or None with the reason already printed."""
    claude_only = getattr(args, "claude", False)
    if getattr(args, "file", None):
        if os.path.exists(args.file):
            return args.file
        print("no such transcript: %s" % args.file, file=sys.stderr)
        return None
    found = transcripts(claude_only=claude_only)
    if found:
        return found[0]
    explain_no_transcripts(claude_only=claude_only)
    return None


def explain_no_transcripts(claude_only=False):
    """Why session/overhead/corpus may show nothing (stderr)."""
    if claude_only:
        print("No Claude Code session transcripts for this project.", file=sys.stderr)
        print("  looked in: %s" % project_dir(), file=sys.stderr)
        print("  Transcripts exist only after Claude Code sessions in this folder.", file=sys.stderr)
        return
    print("No Cursor agent transcripts for this workspace.", file=sys.stderr)
    print("  looked in: %s" % cursor_transcript_dir(), file=sys.stderr)
    print("  Open this folder in Cursor and run agent chats, then retry.", file=sys.stderr)
    print("  Harness config: python3 bin/agent-spec-tokens.py audit", file=sys.stderr)
    print("  Account spend: Cursor Settings → usage / billing.", file=sys.stderr)
    print("  Claude Code JSONL instead: add --claude", file=sys.stderr)


def read_usage(path):
    """Per-turn usage, tool calls, and tool results from one transcript."""
    totals = Counter()
    turns = 0
    first_usage = None
    last_usage = {}
    per_turn_context = []
    tool_calls = Counter()
    tool_in_bytes = Counter()      # what the assistant wrote INTO a tool — an output cost
    tool_out_bytes = Counter()     # what came back — an input cost
    biggest = []
    pending = {}                   # tool_use id -> tool name, so results can be attributed
    estimated = transcript_format(path) == "cursor"
    running_context = 0

    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            message = entry.get("message") or {}

            usage = assistant_usage(entry)
            if is_assistant_turn(entry):
                turns += 1
                if usage:
                    estimated = False
                    if first_usage is None:
                        first_usage = usage
                    last_usage = usage
                    for key, _ in BUCKETS:
                        totals[key] += usage.get(key, 0) or 0
                    per_turn_context.append((usage.get("cache_read_input_tokens", 0) or 0)
                                            + (usage.get("cache_creation_input_tokens", 0) or 0))
                else:
                    text = message_content(entry)
                    totals["output_tokens"] += len(text) // 4
                    running_context += len(text) // 4
                    per_turn_context.append(running_context)

            elif entry.get("role") == "user":
                text = message_content(entry)
                if text:
                    totals["input_tokens"] += len(text) // 4
                    running_context += len(text) // 4

            content = message.get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_use":
                    name = block.get("name", "?")
                    tool_calls[name] += 1
                    tool_in_bytes[name] += len(json.dumps(block.get("input", {})))
                    pending[block.get("id")] = name
                elif block.get("type") == "tool_result":
                    text = block.get("content")
                    if isinstance(text, list):
                        text = "".join(p.get("text", "") for p in text if isinstance(p, dict))
                    size = len(text or "")
                    name = pending.get(block.get("tool_use_id"), "?")
                    tool_out_bytes[name] += size
                    biggest.append((size, name))
                    if estimated:
                        totals["input_tokens"] += size // 4
                        running_context += size // 4

    biggest.sort(reverse=True)
    first_usage = first_usage or {}
    return {
        "path": path,
        "turns": turns,
        "estimated": estimated,
        "last_usage": last_usage,
        "first_usage": first_usage,
        "first_creation": first_usage.get("cache_creation_input_tokens", 0) or 0,
        "first_context": ((first_usage.get("cache_read_input_tokens", 0) or 0)
                          + (first_usage.get("cache_creation_input_tokens", 0) or 0)
                          + (first_usage.get("input_tokens", 0) or 0))
                          if not estimated else (per_turn_context[0] if per_turn_context else 0),
        "totals": totals,
        "per_turn_context": per_turn_context,
        "avg_context": sum(per_turn_context) // max(len(per_turn_context), 1),
        "tool_calls": tool_calls,
        "tool_in_bytes": tool_in_bytes,
        "tool_out_bytes": tool_out_bytes,
        "biggest": biggest[:10],
    }


def weighted(totals, weights):
    return {key: (totals.get(key, 0) or 0) * weights[short] for key, short in BUCKETS}


def parse_weights(spec):
    weights = dict(DEFAULT_WEIGHTS)
    if not spec:
        return weights
    for part in spec.split(","):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        key = key.strip()
        if key not in weights:
            print("unknown weight '%s' — known: %s"
                  % (key, ", ".join(sorted(weights))), file=sys.stderr)
            continue
        try:
            weights[key] = float(value)
        except ValueError:
            print("weight '%s' is not a number: %s" % (key, value), file=sys.stderr)
    return weights


def print_session(data, weights):
    totals, w = data["totals"], weighted(data["totals"], weights)
    grand = sum(w.values()) or 1

    print("=== %s ===" % os.path.basename(data["path"]))
    if data.get("estimated"):
        print("(Cursor transcript — no usage in JSONL; in/out are chars÷4 estimates.)\n")
    print("%d assistant turns, ~%s tokens of context re-read per turn\n"
          % (data["turns"], "{:,}".format(data["avg_context"])))
    print("%-30s %14s %14s %7s" % ("bucket", "tokens", "weighted", "share"))
    for key, short in sorted(BUCKETS, key=lambda b: -w[b[0]]):
        print("%-30s %14s %14s %6.0f%%"
              % (key, "{:,}".format(totals.get(key, 0)), "{:,.0f}".format(w[key]),
                 100 * w[key] / grand))
    print("%-30s %14s %14s" % ("TOTAL", "", "{:,.0f}".format(grand)))
    print("\nweights: %s   (relative to one fresh input token; override with --weights)"
          % ", ".join("%s=%g" % (k, v) for k, v in sorted(weights.items())))

    written = sum(data["tool_in_bytes"].values())
    out_tokens = totals.get("output_tokens", 0) or 1
    print("\n~%s of %s output tokens (%.0f%%) were tool-call inputs — mostly file bodies."
          % ("{:,}".format(written // 4), "{:,}".format(out_tokens),
             100 * (written // 4) / out_tokens))
    returned = sum(data["tool_out_bytes"].values())
    print("~%s tokens came back from tools, %.1f%% of the weighted total."
          % ("{:,}".format(returned // 4), 100 * (returned // 4) / grand))


def all_transcripts(claude_only=False):
    """Every transcript this machine has (Cursor agent-transcripts or Claude projects)."""
    if claude_only:
        return _all_claude_transcripts()
    out = []
    root = cursor_projects_root()
    try:
        slugs = sorted(os.listdir(root))
    except OSError:
        slugs = []
    for slug in slugs:
        base = os.path.join(root, slug, "agent-transcripts")
        if not os.path.isdir(base):
            continue
        try:
            sessions = os.listdir(base)
        except OSError:
            continue
        for sid in sessions:
            main = os.path.join(base, sid, sid + ".jsonl")
            if os.path.isfile(main):
                out.append((slug, main))
    if out:
        return out
    return _all_claude_transcripts()


def _all_claude_transcripts():
    """Claude Code JSONL only."""
    out = []
    for root in claude_roots():
        base = os.path.join(root, "projects")
        try:
            projects = sorted(os.listdir(base))
        except OSError:
            continue
        for name in projects:
            d = os.path.join(base, name)
            if not os.path.isdir(d):
                continue
            for f in sorted(os.listdir(d)):
                if f.endswith(".jsonl"):
                    out.append((name, os.path.join(d, f)))
    return out


def print_corpus(weights, min_turns=5, claude_only=False):
    """Aggregate across every session on this machine.

    One session proves nothing about the shape of the bill — it could be an artefact
    of that day's task. Across a corpus the shares are stable, and that is the only
    basis on which the ordering in `agent-spec-raw-code-full` is defensible.
    """
    found = all_transcripts(claude_only=claude_only)
    if not found:
        print("No transcripts under Cursor agent-transcripts or Claude projects.", file=sys.stderr)
        return 1

    totals = Counter()
    turns = 0
    sessions = 0
    skipped = 0
    projects = set()
    tool_in = 0
    tool_out = 0
    growth = []

    for project, path in found:
        data = read_usage(path)
        if data["turns"] < min_turns:
            skipped += 1
            continue
        sessions += 1
        projects.add(project)
        turns += data["turns"]
        for key, _ in BUCKETS:
            totals[key] += data["totals"].get(key, 0)
        tool_in += sum(data["tool_in_bytes"].values())
        tool_out += sum(data["tool_out_bytes"].values())
        last = data["last_usage"]
        end = ((last.get("cache_read_input_tokens", 0) or 0)
               + (last.get("cache_creation_input_tokens", 0) or 0))
        if data["first_context"]:
            growth.append((data["first_context"], end, data["turns"]))

    w = weighted(totals, weights)
    grand = sum(w.values()) or 1

    print("=== corpus: %d sessions across %d projects, %d assistant turns ==="
          % (sessions, len(projects), turns))
    print("(%d sessions under %d turns were skipped as too short to be representative)\n"
          % (skipped, min_turns))
    print("%-30s %16s %16s %7s" % ("bucket", "tokens", "weighted", "share"))
    for key, _ in sorted(BUCKETS, key=lambda b: -w[b[0]]):
        print("%-30s %16s %16s %6.1f%%"
              % (key, "{:,}".format(totals.get(key, 0)), "{:,.0f}".format(w[key]),
                 100 * w[key] / grand))
    print("%-30s %16s %16s" % ("TOTAL", "", "{:,.0f}".format(grand)))

    out_tokens = totals.get("output_tokens", 0) or 1
    print("\n%-46s %6.1f%% of output" % ("output spent writing into tools:",
                                         100 * (tool_in // 4) / out_tokens))
    print("%-46s %6.2f%% of the bill" % ("everything tools returned:",
                                         100 * (tool_out // 4) / grand))
    if growth:
        starts = sum(g[0] for g in growth) / len(growth)
        ends = sum(g[1] for g in growth) / len(growth)
        print("\naverage context, first turn: %s   last turn: %s   (%.1fx)"
              % ("{:,.0f}".format(starts), "{:,.0f}".format(ends), ends / max(starts, 1)))
    return 0


def print_context(data, weights):
    """Current context size, what carrying it costs, and when to reset.

    The context is re-read on every turn. It cannot be compressed in place: cache
    reads bill at a tenth precisely *because* the bytes are unchanged, so editing
    them invalidates the prefix and forces a full re-write at cache-write price.
    The only two moves are carry it or start again, and this works out which is
    cheaper at the size the session has actually reached.
    """
    usage = data["last_usage"]
    if data.get("estimated"):
        pts = data.get("per_turn_context") or []
        context = pts[-1] if pts else 0
        first = pts[0] if pts else 0
        carry = context * weights["read"]
        print("=== context — %s (estimated) ===" % os.path.basename(data["path"]))
        print("turn 1:    %14s est. tokens" % "{:,}".format(first))
        print("turn %-4d  %14s est. tokens   (%.1fx growth over %d turns)"
              % (data["turns"], "{:,}".format(context),
                 context / max(first, 1), data["turns"]))
        print("\nCursor JSONL has no cache buckets — use Cursor billing for spend.")
        print("carrying est. context costs ~%s weighted units/turn at read=%g."
              % ("{:,.0f}".format(carry), weights["read"]))
        return 0
    context = ((usage.get("cache_read_input_tokens", 0) or 0)
               + (usage.get("cache_creation_input_tokens", 0) or 0)
               + (usage.get("input_tokens", 0) or 0))
    first = data["first_context"]

    carry = context * weights["read"]
    fresh = data["first_creation"] or 13000        # what a cold session re-writes
    reset_once = fresh * weights["write"]
    after = fresh * weights["read"]
    saving = carry - after

    print("=== context — %s ===" % os.path.basename(data["path"]))
    print("turn 1:    %14s tokens" % "{:,}".format(first))
    print("turn %-4d  %14s tokens   (%.1fx growth over %d turns)"
          % (data["turns"], "{:,}".format(context),
             context / max(first, 1), data["turns"]))
    print("")
    print("carrying it costs      %10s per turn   (context x read weight)"
          % "{:,.0f}".format(carry))
    print("a fresh session costs  %10s once        (re-writing %s tokens of always-on)"
          % ("{:,.0f}".format(reset_once), "{:,}".format(fresh)))
    print("and then               %10s per turn" % "{:,.0f}".format(after))

    if saving <= 0:
        print("\nContext is already small. Carry on.")
        return 0
    breakeven = reset_once / saving
    print("\nsaving after a reset:  %10s per turn" % "{:,.0f}".format(saving))
    print("break-even:            %10.1f turns" % breakeven)
    if breakeven < 5:
        print("\nRESET. Run /agent-spec-snapshot, then start a new session — it pays for\n"
              "itself in %.0f turn%s. Note this is a *reset*, not a compaction: compaction\n"
              "also pays output price to generate the summary, and a snapshot writes the\n"
              "same state to a file you were going to write anyway."
              % (breakeven, "" if breakeven < 1.5 else "s"))
    else:
        print("\nNot yet worth resetting. Re-check after another %.0f turns." % breakeven)
    return 0


def print_tools(data):
    print("=== tools — %s ===" % os.path.basename(data["path"]))
    print("%-16s %6s %12s %12s" % ("tool", "calls", "written in", "returned"))
    names = set(data["tool_calls"]) | set(data["tool_out_bytes"])
    for name in sorted(names, key=lambda n: -(data["tool_in_bytes"][n] + data["tool_out_bytes"][n])):
        print("%-16s %6d %9s B %9s B"
              % (name, data["tool_calls"][name],
                 "{:,}".format(data["tool_in_bytes"][name]),
                 "{:,}".format(data["tool_out_bytes"][name])))
    print("\nlargest single results:")
    for size, name in data["biggest"]:
        print("  %9s B  ~%6s tok  %s"
              % ("{:,}".format(size), "{:,}".format(size // 4), name))
    if not data["biggest"]:
        print("  (none)")
    print("\n'written in' is an output cost — the assistant generated it. 'returned' is an\n"
          "input cost. A large 'written in' on Bash or Write means whole file bodies are\n"
          "being generated; a targeted edit costs a fraction of a rewrite.")


def print_compare(a, b, weights):
    wa, wb = weighted(a["totals"], weights), weighted(b["totals"], weights)
    ta, tb = sum(wa.values()) or 1, sum(wb.values()) or 1
    print("=== %s  vs  %s ===" % (os.path.basename(a["path"]), os.path.basename(b["path"])))
    print("%-30s %14s %14s %10s" % ("bucket", "A", "B", "delta"))
    for key, _ in BUCKETS:
        va, vb = a["totals"].get(key, 0), b["totals"].get(key, 0)
        delta = 100 * (vb - va) / va if va else 0
        print("%-30s %14s %14s %9.1f%%"
              % (key, "{:,}".format(va), "{:,}".format(vb), delta))
    print("%-30s %14s %14s %9.1f%%"
          % ("WEIGHTED TOTAL", "{:,.0f}".format(ta), "{:,.0f}".format(tb),
             100 * (tb - ta) / ta))
    print("%-30s %14d %14d" % ("turns", a["turns"], b["turns"]))
    print("\nTwo sessions are only comparable if they did the same work. A lower total on a\n"
          "shorter task is not a saving, and reporting it as one is how a 60-90% claim gets\n"
          "made.")


# A copy of the system prompt and tool schemas, kept for the transcript. It is the base
# prefix every session has, not something a project added, so it is not overhead to fix.
NOT_OVERHEAD = {"prompt_snapshot"}


def overhead_key(att):
    kind = att.get("type", "?")
    if kind.startswith("hook_"):
        return "%s:%s" % (kind, att.get("hookEvent") or att.get("hookName") or "?")
    return kind


def harness_blocks_in_user_text(text):
    """Byte sizes of Cursor-injected blocks in a user turn."""
    blocks = {}
    for key, rx in CURSOR_HARNESS_RE:
        for m in rx.finditer(text):
            blocks[key] = blocks.get(key, 0) + len(m.group(1))
    return blocks


def read_overhead_cursor(path):
    """Harness tags in Cursor user turns; cost = size x turns remaining."""
    rows = {}
    turn = 0
    entries = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if is_assistant_turn(entry):
                turn += 1
            elif entry.get("role") == "user":
                text = message_content(entry)
                blocks = harness_blocks_in_user_text(text)
                if blocks:
                    entries.append((turn, blocks))

    def add(key, at, size):
        n, b, carried = rows.get(key, (0, 0, 0))
        rows[key] = (n + 1, b + size, carried + (size // 4) * max(turn - at, 0))

    for at, blocks in entries:
        for key, size in blocks.items():
            add("cursor:%s" % key, at, size)
    return turn, rows


def read_overhead(path):
    """Bytes the harness added around the conversation, and how long each stayed in context."""
    if transcript_format(path) == "cursor":
        return read_overhead_cursor(path)

    rows = {}
    turn = 0
    entries = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if entry.get("type") == "assistant" and (entry.get("message") or {}).get("usage"):
                turn += 1
            elif entry.get("type") == "attachment":
                entries.append((turn, entry.get("attachment") or {}))

    def add(key, at, size):
        n, b, carried = rows.get(key, (0, 0, 0))
        rows[key] = (n + 1, b + size, carried + (size // 4) * max(turn - at, 0))

    for at, att in entries:
        if att.get("type") in NOT_OVERHEAD:
            continue
        if att.get("type") == "instructions" and isinstance(att.get("files"), list):
            for f in att["files"]:
                name = os.path.basename(str(f.get("path", "?")).replace("\\", "/"))
                add("instructions:%s" % name, at, len(f.get("content", "") or ""))
            continue
        add(overhead_key(att), at, len(json.dumps(att)))
    return turn, rows


def print_overhead(paths, weights):
    turns, rows, cache_read = 0, {}, 0
    for path in paths:
        t, r = read_overhead(path)
        turns += t
        usage = read_usage(path)
        cache_read += usage["totals"].get("cache_read_input_tokens", 0)
        if usage.get("estimated") and not cache_read:
            cache_read += sum(c for _, _, c in r.values())
        for key, (n, b, c) in r.items():
            on, ob, oc = rows.get(key, (0, 0, 0))
            rows[key] = (on + n, ob + b, oc + c)
    if not rows:
        print("no harness blocks recorded in user turns (Cursor tags or Claude attachments).")
        return 0
    denom = max(cache_read, sum(c for _, _, c in rows.values()), 1)
    print("=== overhead: %d session(s), %d assistant turns, %s re-read tokens (denom) ==="
          % (len(paths), turns, "{:,}".format(denom)))
    print("%-42s %6s %10s %14s %7s" % ("source", "count", "bytes", "re-read tokens", "of denom"))
    for key, (n, b, c) in sorted(rows.items(), key=lambda kv: -kv[1][2])[:14]:
        print("%-42s %6d %10s %14s %6.1f%%"
              % (key[:42], n, "{:,}".format(b), "{:,}".format(c), 100 * c / denom))
    print("\nre-read tokens = bytes/4 x turns the text stayed in context. An estimate, and an\n"
          "upper bound: the harness may fold repeated reminders. Run `audit` for the fixes.")
    return 0


# Findings that cost tokens or leak: limits are opinions, so each is a flag.
DEFAULT_LIMITS = {"hook_bytes": 1000, "memory_bytes": 8000,
                  "local_bytes": 50000, "listing_bytes": 25000}
SECRET_PATTERNS = [
    ("a JWT", re.compile(r"eyJ[\w-]{10,}\.[\w-]{10,}\.[\w-]+")),
    ("an AWS access key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("a private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY")),
    ("an API key", re.compile(r"\bsk-[A-Za-z0-9]{20,}")),
]


def hook_commands(settings):
    for event, groups in (settings.get("hooks") or {}).items():
        for group in groups if isinstance(groups, list) else []:
            for h in (group.get("hooks") or []) if isinstance(group, dict) else []:
                if isinstance(h, dict) and h.get("command"):
                    yield event, h["command"]


def skill_description(path):
    """The frontmatter description of a SKILL.md, folded scalars included."""
    try:
        lines = open(path, encoding="utf-8", errors="replace").read().split("\n")
    except OSError:
        return ""
    if not lines or lines[0].strip() != "---":
        return ""
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            break
        if line.startswith("description:"):
            value = line.split(":", 1)[1].strip()
            if value in (">", ">-", "|", "|-"):
                block = []
                for nxt in lines[i + 1:]:
                    if nxt.strip() == "---" or (nxt and not nxt.startswith(" ")):
                        break
                    block.append(nxt.strip())
                return " ".join(block)
            return value.strip("\"'")
    return ""


def skills_in(directory):
    out = {}
    try:
        names = sorted(os.listdir(directory))
    except OSError:
        return out
    for n in names:
        f = os.path.join(directory, n, "SKILL.md")
        if os.path.isfile(f):
            out[n] = len(n) + len(skill_description(f))
    return out


def _same_file(path, candidates):
    try:
        mine = open(path, "rb").read()
        return any(os.path.isfile(c) and open(c, "rb").read() == mine for c in candidates)
    except OSError:
        return False


def find_projects(scan):
    """Directories that hold a .claude: each scan dir itself, or its children."""
    found = []
    for d in scan:
        d = os.path.abspath(d)
        if os.path.isdir(os.path.join(d, ".claude")):
            found.append(d)
            continue
        try:
            kids = sorted(os.listdir(d))
        except OSError:
            continue
        found += [os.path.join(d, k) for k in kids
                  if os.path.isdir(os.path.join(d, k, ".claude"))]
    return found


def find_cursor_projects(scan):
    """Workspace roots with Cursor harness markers (.agent-spec or .cursor/hooks.json)."""
    found = []

    def is_cursor_root(path):
        return (
            os.path.isfile(os.path.join(path, ".cursor", "hooks.json"))
            or os.path.isdir(os.path.join(path, ".agent-spec"))
        )

    for d in scan:
        d = os.path.abspath(d)
        if is_cursor_root(d):
            found.append(d)
            continue
        try:
            kids = sorted(os.listdir(d))
        except OSError:
            continue
        for k in kids:
            p = os.path.join(d, k)
            if os.path.isdir(p) and is_cursor_root(p):
                found.append(p)
    return found


def cursor_skills_home():
    return skills_in(os.path.join(os.path.expanduser("~"), ".cursor", "skills"))


def cursor_hook_commands(hooks_cfg):
    hooks = (hooks_cfg or {}).get("hooks") or {}
    for event, handlers in hooks.items():
        if not isinstance(handlers, list):
            continue
        for h in handlers:
            if isinstance(h, dict) and h.get("command"):
                yield event, h["command"]


def resolve_hook_script(project_root, cmd):
    parts = cmd.split()
    if not parts:
        return None
    if parts[0] in ("python3", "python", "/usr/bin/python3") and len(parts) > 1:
        target = parts[1]
        if target.startswith("/"):
            return target
        return os.path.normpath(os.path.join(project_root, target))
    if not parts[0].startswith("/"):
        return os.path.normpath(os.path.join(project_root, parts[0]))
    return parts[0]


def audit_cursor_project(proj, limits, global_skills, out):
    """Cursor harness checks for one registered workspace."""
    hooks_path = os.path.join(proj, ".cursor", "hooks.json")
    has_harness = os.path.isdir(os.path.join(proj, ".agent-spec"))

    if has_harness and not os.path.isfile(hooks_path):
        out.append((
            proj,
            "registered .agent-spec but no .cursor/hooks.json",
            "sessionStart digest and preToolUse nudges never run",
            "re-run ./install.sh --register on the Cursor workspace root; enable Hooks in Settings",
        ))

    cfg, err = (None, None)
    if os.path.isfile(hooks_path):
        cfg, err = load_json(hooks_path)
        if err:
            out.append((
                hooks_path,
                "not valid JSON (%s)" % err,
                "Cursor ignores broken hooks.json",
                "fix the syntax or re-run ./install.sh --register",
            ))
        try:
            text = open(hooks_path, encoding="utf-8", errors="replace").read()
        except OSError:
            text = ""
        for label, rx in SECRET_PATTERNS:
            hits = len(rx.findall(text))
            if hits:
                out.append((
                    hooks_path,
                    "%d value(s) that look like %s" % (hits, label),
                    "credentials at rest in a file that is copied and synced",
                    "delete the entry and rotate the credential if it has not expired",
                ))

    if cfg:
        hooks = cfg.get("hooks") or {}
        for event in ("sessionStart", "preToolUse"):
            handlers = hooks.get(event) or []
            if not isinstance(handlers, list):
                continue
            ours = [
                h for h in handlers
                if isinstance(h, dict) and "agent-spec" in (h.get("command") or "")
            ]
            if has_harness and not ours:
                out.append((
                    hooks_path,
                    "no algosec-agent-spec handler wired for %s" % event,
                    "standing protocol and digest rely on these hooks",
                    "re-run ./install.sh --register",
                ))
            if len(ours) > 1:
                out.append((
                    hooks_path,
                    "%d algosec-agent-spec %s handlers (expected 1)" % (len(ours), event),
                    "duplicate hook output is re-read every turn",
                    "run hooks/merge-hooks-json.py or reinstall; keep one handler per event",
                ))
        for event, cmd in cursor_hook_commands(cfg):
            token = cmd.split()[0]
            if token.startswith("/mnt/"):
                out.append((
                    hooks_path,
                    "%s hook uses %s" % (event, token),
                    "paths under /mnt/c fail in some Windows shells (exit 127)",
                    "use project-relative commands: python3 .cursor/hooks/agent-spec-*.py",
                ))
            resolved = resolve_hook_script(proj, cmd)
            if resolved and not os.path.isfile(resolved):
                out.append((
                    hooks_path,
                    "%s hook target missing: %s" % (event, resolved),
                    "a failing hook adds errors to every session",
                    "reinstall hooks or fix the command path",
                ))

    rules_dir = os.path.join(proj, ".cursor", "rules")
    if os.path.isdir(rules_dir):
        try:
            rule_files = [f for f in os.listdir(rules_dir) if f.endswith((".mdc", ".md"))]
        except OSError:
            rule_files = []
        lean = [f for f in rule_files if f.startswith("algosec-lean")]
        for f in lean:
            try:
                always = re.search(r"(?m)^alwaysApply:\s*true",
                                   open(os.path.join(rules_dir, f), encoding="utf-8").read())
            except OSError:
                always = None
            if always and "agent-spec.mdc" in rule_files:
                out.append((
                    os.path.join(rules_dir, f),
                    "algosec-lean is Always Apply next to agent-spec.mdc (stacked always-on style rules)",
                    "both rules ride in the cached prefix every turn and can contradict each other on reply shape",
                    "set alwaysApply: false in %s and invoke it on demand; keep one always-on style rule" % f,
                ))
        if len(rule_files) > 1:
            out.append((
                rules_dir,
                "%d always-on rule files (Cursor loads all of them every chat)" % len(rule_files),
                "each file sits in the cached prefix for the whole session",
                "keep one standing rules file (agent-spec.mdc); move the rest to skills on demand",
            ))

    mine = skills_in(os.path.join(proj, ".cursor", "skills"))
    for n in mine:
        for g in (n, "agent-spec-" + n):
            if g not in global_skills:
                continue
            same = _same_file(
                os.path.join(proj, ".cursor", "skills", n, "SKILL.md"),
                [os.path.join(os.path.expanduser("~"), ".cursor", "skills", g, "SKILL.md")],
            )
            out.append((
                os.path.join(proj, ".cursor", "skills", n),
                "%s the global skill %s (%s)"
                % ("same name as" if g == n else "an unprefixed twin of", g,
                   "byte-identical" if same else "content differs"),
                "both descriptions may appear in the skill listing each turn"
                + ("" if same else ", and they may give different instructions"),
                "delete the project copy" if same else
                "diff them, keep one, delete the other",
            ))
            break
    total_listing = sum(mine.values()) + sum(global_skills.values())
    if total_listing > limits["listing_bytes"]:
        out.append((
            proj,
            "Cursor skill listing is ~%d B (%d project + %d global skills)"
            % (total_listing, len(mine), len(global_skills)),
            "name and description of every skill ride in the prefix each turn",
            "shorten descriptions or remove skills the project never uses",
        ))

    mem_dir = os.path.join(proj, ".agent-spec", "memory")
    if os.path.isdir(mem_dir):
        # Only INDEX.md is pulled into sessions. Fact bodies (facts/) and archived
        # snapshots are read on demand, so counting them flagged healthy stores.
        mem_bytes = 0
        try:
            mem_bytes = os.path.getsize(os.path.join(mem_dir, "INDEX.md"))
        except OSError:
            pass
        if mem_bytes > limits["memory_bytes"]:
            out.append((
                mem_dir,
                "memory tree is %d B" % mem_bytes,
                "facts and index text can be pulled into session context",
                "one line per fact in the index; bodies in separate files; under %d B"
                % limits["memory_bytes"],
            ))


def load_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh), None
    except OSError:
        return None, None
    except ValueError as exc:
        return None, str(exc)


def audit_findings(scan, limits, include_claude=False):
    """(where, finding, risk, fix) for each configuration defect that inflates overhead."""
    out = []
    roots = claude_roots()
    home = roots[0]
    projects = find_projects(scan) if include_claude else []
    global_skills = {}
    if include_claude:
        for root in roots:
            global_skills.update(skills_in(os.path.join(root, "skills")))

    def check_settings(path, is_windows):
        settings, err = load_json(path)
        if err:
            out.append((path, "not valid JSON (%s)" % err, "the harness ignores the whole file",
                        "fix the syntax"))
        for event, cmd in hook_commands(settings or {}):
            token = cmd.split()[0]
            if is_windows and token.startswith("/mnt/"):
                out.append((path, "%s hook path %s" % (event, token),
                            "the Windows app runs hooks in Git Bash, where /mnt/ does not exist: exit 127 on every call",
                            "register ~/.claude/hooks/... — re-run bin/install.sh"))
            elif token.startswith("/") and not os.path.exists(token):
                out.append((path, "%s hook %s does not exist" % (event, token),
                            "a failing hook adds an error to the transcript on every call",
                            "reinstall the hook or remove the entry"))
            if event == "UserPromptSubmit" and len(cmd) > limits["hook_bytes"]:
                out.append((path, "UserPromptSubmit injects %d B inline" % len(cmd),
                            "every copy stays in context to the end of the session, so N prompts cost N copies",
                            "inject once from SessionStart, or trim under %d B" % limits["hook_bytes"]))
        try:
            text = open(path, encoding="utf-8", errors="replace").read()
        except OSError:
            return
        for label, rx in SECRET_PATTERNS:
            hits = len(rx.findall(text))
            if hits:
                out.append((path, "%d value(s) that look like %s" % (hits, label),
                            "credentials at rest in a file that is copied and synced",
                            "delete the entry and rotate the credential if it has not expired"))
        if path.endswith("settings.local.json") and len(text) > limits["local_bytes"]:
            out.append((path, "%d B of accumulated allow rules" % len(text),
                        "one-off commands pile up and hide the rules that matter",
                        "prune to wildcard rules (see /fewer-permission-prompts)"))

    if include_claude:
        for root in roots:
            check_settings(os.path.join(root, "settings.json"), root != home)
            base = os.path.join(root, "projects")
            try:
                names = sorted(os.listdir(base))
            except OSError:
                names = []
            for n in names:
                mem = os.path.join(base, n, "memory", "MEMORY.md")
                if os.path.isfile(mem) and os.path.getsize(mem) > limits["memory_bytes"]:
                    out.append((mem, "memory index is %d B" % os.path.getsize(mem),
                                "loaded into every turn of every session in that project",
                                "one line per fact, bodies in their own files; under %d B"
                                % limits["memory_bytes"]))

        for proj in projects:
            for name in ("settings.json", "settings.local.json"):
                check_settings(os.path.join(proj, ".claude", name), False)
            mine = skills_in(os.path.join(proj, ".claude", "skills"))
            for n in mine:
                for g in (n, "agent-spec-" + n):
                    if g not in global_skills:
                        continue
                    same = _same_file(os.path.join(proj, ".claude", "skills", n, "SKILL.md"),
                                      [os.path.join(r, "skills", g, "SKILL.md") for r in roots])
                    out.append((os.path.join(proj, ".claude", "skills", n),
                                "%s the global skill %s (%s)"
                                % ("same name as" if g == n else "an unprefixed twin of", g,
                                   "byte-identical" if same else "content differs"),
                                "both descriptions are listed on every turn"
                                + ("" if same else ", and they may give different instructions"),
                                "delete the project copy" if same else
                                "diff them, keep the one you want, delete the other"))
                    break
            total = sum(mine.values()) + sum(global_skills.values())
            if total > limits["listing_bytes"]:
                out.append((proj, "skill listing is ~%d B (%d project + %d global skills)"
                            % (total, len(mine), len(global_skills)),
                            "name and description of every skill ride in the prefix each turn",
                            "shorten descriptions or remove skills the project never uses"))

    cursor_global = cursor_skills_home()
    seen = set()
    for proj in find_cursor_projects(scan):
        if proj in seen:
            continue
        seen.add(proj)
        audit_cursor_project(proj, limits, cursor_global, out)
    return out


def print_audit(scan, limits, include_claude=False):
    findings = audit_findings(scan, limits, include_claude=include_claude)
    if not findings:
        print("audit: no findings.")
        return 0
    for where, finding, risk, fix in findings:
        print("%s\n  Finding. %s.\n  Risk. %s.\n  Fix. %s.\n" % (where, finding, risk, fix))
    print("%d finding(s)." % len(findings))
    return 1


def main():
    parser = argparse.ArgumentParser(
        description="Measure Cursor agent transcripts and harness overhead (audit)")
    parser.add_argument("--claude", action="store_true",
                        help="use Claude Code JSONL only (skip Cursor agent-transcripts)")
    parser.add_argument("--weights", default=None,
                        help="price ratios, e.g. out=5,write=1.25,read=0.1,in=1")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("session", help="the four token buckets, weighted")
    p.add_argument("--file", default=None, help="transcript path (default: most recent)")

    p = sub.add_parser("context", help="context size, cost per turn, and the reset break-even")
    p.add_argument("--file", default=None)

    p = sub.add_parser("tools", help="per-tool cost, and the largest results")
    p.add_argument("--file", default=None)

    p = sub.add_parser("compare", help="two transcripts side by side")
    p.add_argument("a")
    p.add_argument("b")

    p = sub.add_parser("corpus", help="aggregate across every session on this machine")
    p.add_argument("--min-turns", type=int, default=5)

    p = sub.add_parser("overhead", help="what the harness re-sends each turn besides the conversation")
    p.add_argument("--file", default=None)
    p.add_argument("--all", action="store_true", help="every transcript of this project")

    p = sub.add_parser("audit", help="configuration on this machine that inflates that overhead")
    p.add_argument("--scan", action="append", default=None,
                   help="directory holding projects, or a project (default: cwd); repeatable")
    p.add_argument("--include-claude", action="store_true",
                   help="also scan Claude settings and .claude/skills (legacy twins)")
    p.add_argument("--max-hook-bytes", type=int, default=DEFAULT_LIMITS["hook_bytes"])
    p.add_argument("--max-memory-bytes", type=int, default=DEFAULT_LIMITS["memory_bytes"])
    p.add_argument("--max-local-bytes", type=int, default=DEFAULT_LIMITS["local_bytes"])
    p.add_argument("--max-listing-bytes", type=int, default=DEFAULT_LIMITS["listing_bytes"])

    sub.add_parser("list", help="transcripts available for this workspace (Cursor-first)")

    args = parser.parse_args()
    weights = parse_weights(args.weights)

    if args.command == "corpus":
        return print_corpus(weights, args.min_turns, claude_only=args.claude)

    if args.command == "audit":
        return print_audit(args.scan or [os.getcwd()], {
            "hook_bytes": args.max_hook_bytes, "memory_bytes": args.max_memory_bytes,
            "local_bytes": args.max_local_bytes, "listing_bytes": args.max_listing_bytes},
            include_claude=getattr(args, "include_claude", False))

    if args.command == "overhead":
        if args.all:
            paths = transcripts(claude_only=args.claude)
            if not paths:
                explain_no_transcripts(claude_only=args.claude)
                return 1
        else:
            path = resolve(args)
            if not path:
                return 1
            paths = [path]
        return print_overhead(paths, weights)

    if args.command == "list":
        found = transcripts(claude_only=args.claude)
        if args.claude:
            print("=== %d Claude transcripts in %s ===" % (len(found), project_dir()))
        else:
            print("=== %d Cursor transcripts in %s ===" % (len(found), cursor_transcript_dir()))
        for path in found:
            print("  %s  %8d B" % (os.path.basename(path), os.path.getsize(path)))
        if not found:
            print("  (none)")
        return 0

    if args.command == "compare":
        for path in (args.a, args.b):
            if not os.path.exists(path):
                print("no such transcript: %s" % path, file=sys.stderr)
                return 1
        print_compare(read_usage(args.a), read_usage(args.b), weights)
        return 0

    path = resolve(args)
    if not path:
        return 1
    data = read_usage(path)
    if data["turns"] == 0:
        print("%s has no assistant turns — nothing to measure."
              % os.path.basename(path), file=sys.stderr)
        return 1
    if args.command == "session":
        print_session(data, weights)
    elif args.command == "context":
        return print_context(data, weights)
    else:
        print_tools(data)
    return 0


if __name__ == "__main__":
    sys.exit(main())
