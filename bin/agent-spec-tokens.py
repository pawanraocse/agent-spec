#!/usr/bin/env python3
"""Measure where a Claude Code session's tokens actually went.

`agent-spec-bench.sh` estimates context cost as bytes divided by four. That is fine for
comparing two revisions of a file and useless for a session, which is where the money
goes. Claude Code already records the truth: every assistant turn in the session
transcript carries a `usage` object with the four token buckets. This reads it.

The reason this exists at all is that the published numbers for token-saving tools do not
survive measurement — one advertised 60-90% savings and benchmarked 7.6% *more* expensive.
Nothing in this framework should claim a saving it has not counted, and until now it had
no way to count.

Read-only. It never writes anything under ~/.claude.

  context   how big the context has grown, and whether a reset now pays for itself
  corpus    the same buckets across every session on this machine
  session   the four buckets, weighted, for one session
  tools     per tool: what was written into it, what came back, the largest results
  compare   two transcripts side by side, for an honest A/B
  overhead  what the harness re-sends every turn that is not the conversation
  audit     configuration that inflates that overhead, on this machine
  list      the transcripts available for this project

Transcripts are read from ~/.claude and, under WSL, from the Windows profile too
(WIN_CLAUDE_HOME, default /mnt/c/Users/<user>): a session started from the Windows app
is recorded there, not under the WSL home.
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


def transcripts(cwd=None):
    names = []
    for d in project_dirs(cwd):
        try:
            names += [os.path.join(d, n) for n in os.listdir(d) if n.endswith(".jsonl")]
        except OSError:
            continue
    return sorted(names, key=lambda p: os.path.getmtime(p), reverse=True)


def resolve(args):
    """The transcript to read, or None with the reason already printed."""
    if getattr(args, "file", None):
        if os.path.exists(args.file):
            return args.file
        print("no such transcript: %s" % args.file, file=sys.stderr)
        return None
    found = transcripts()
    if found:
        return found[0]
    print("No session transcript under %s.\n"
          "Transcripts are written by Claude Code itself: another agent, a piped\n"
          "session, or a different working directory will not have one, and there is\n"
          "nothing to measure without it." % project_dir(), file=sys.stderr)
    return None


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

    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            message = entry.get("message") or {}

            usage = message.get("usage")
            if usage and entry.get("type") == "assistant":
                turns += 1
                if first_usage is None:
                    first_usage = usage
                last_usage = usage
                for key, _ in BUCKETS:
                    totals[key] += usage.get(key, 0) or 0
                per_turn_context.append((usage.get("cache_read_input_tokens", 0) or 0)
                                        + (usage.get("cache_creation_input_tokens", 0) or 0))

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

    biggest.sort(reverse=True)
    first_usage = first_usage or {}
    return {
        "path": path,
        "turns": turns,
        "last_usage": last_usage,
        "first_usage": first_usage,
        "first_creation": first_usage.get("cache_creation_input_tokens", 0) or 0,
        "first_context": ((first_usage.get("cache_read_input_tokens", 0) or 0)
                          + (first_usage.get("cache_creation_input_tokens", 0) or 0)
                          + (first_usage.get("input_tokens", 0) or 0)),
        "totals": totals,
        "avg_context": sum(per_turn_context) // max(turns, 1),
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


def all_transcripts():
    """Every transcript this machine has, across every project and every profile."""
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


def print_corpus(weights, min_turns=5):
    """Aggregate across every session on this machine.

    One session proves nothing about the shape of the bill — it could be an artefact
    of that day's task. Across a corpus the shares are stable, and that is the only
    basis on which the ordering in `agent-spec-raw-code-full` is defensible.
    """
    found = all_transcripts()
    if not found:
        print("No transcripts under any .claude/projects.", file=sys.stderr)
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


def read_overhead(path):
    """Bytes the harness added around the conversation, and how long each stayed in context.

    An attachment that appears before turn N is re-read on every later turn, so its cost
    is its size times the turns remaining. That is why one injection per prompt costs far
    more than the same text once: each copy is carried to the end of the session.
    """
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
        cache_read += read_usage(path)["totals"].get("cache_read_input_tokens", 0)
        for key, (n, b, c) in r.items():
            on, ob, oc = rows.get(key, (0, 0, 0))
            rows[key] = (on + n, ob + b, oc + c)
    if not rows:
        print("no attachments recorded — nothing added around the conversation.")
        return 0
    print("=== overhead: %d session(s), %d assistant turns, %s cache-read tokens ==="
          % (len(paths), turns, "{:,}".format(cache_read)))
    print("%-42s %6s %10s %14s %7s" % ("source", "count", "bytes", "re-read tokens", "of read"))
    for key, (n, b, c) in sorted(rows.items(), key=lambda kv: -kv[1][2])[:14]:
        print("%-42s %6d %10s %14s %6.1f%%"
              % (key[:42], n, "{:,}".format(b), "{:,}".format(c), 100 * c / max(cache_read, 1)))
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


def load_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh), None
    except OSError:
        return None, None
    except ValueError as exc:
        return None, str(exc)


def audit_findings(scan, limits):
    """(where, finding, risk, fix) for each configuration defect that inflates overhead."""
    out = []
    roots = claude_roots()
    home = roots[0]
    projects = find_projects(scan)
    global_skills = {}
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
                            "one line per fact, bodies in their own files; under %d B" % limits["memory_bytes"]))

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
    return out


def print_audit(scan, limits):
    findings = audit_findings(scan, limits)
    if not findings:
        print("audit: no findings.")
        return 0
    for where, finding, risk, fix in findings:
        print("%s\n  Finding. %s.\n  Risk. %s.\n  Fix. %s.\n" % (where, finding, risk, fix))
    print("%d finding(s)." % len(findings))
    return 1


def main():
    parser = argparse.ArgumentParser(description="Measure a Claude Code session's token cost")
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
    p.add_argument("--max-hook-bytes", type=int, default=DEFAULT_LIMITS["hook_bytes"])
    p.add_argument("--max-memory-bytes", type=int, default=DEFAULT_LIMITS["memory_bytes"])
    p.add_argument("--max-local-bytes", type=int, default=DEFAULT_LIMITS["local_bytes"])
    p.add_argument("--max-listing-bytes", type=int, default=DEFAULT_LIMITS["listing_bytes"])

    sub.add_parser("list", help="transcripts available for this project")

    args = parser.parse_args()
    weights = parse_weights(args.weights)

    if args.command == "corpus":
        return print_corpus(weights, args.min_turns)

    if args.command == "audit":
        return print_audit(args.scan or [os.getcwd()], {
            "hook_bytes": args.max_hook_bytes, "memory_bytes": args.max_memory_bytes,
            "local_bytes": args.max_local_bytes, "listing_bytes": args.max_listing_bytes})

    if args.command == "overhead":
        paths = transcripts() if args.all else [resolve(args)]
        if not paths or paths[0] is None:
            return 1
        return print_overhead(paths, weights)

    if args.command == "list":
        found = transcripts()
        print("=== %d transcripts in %s ===" % (len(found), project_dir()))
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
        print("%s has no assistant turns with usage — nothing to measure."
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
