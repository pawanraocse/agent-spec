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

  session   the four buckets, weighted, for one session
  tools     per tool: what was written into it, what came back, the largest results
  compare   two transcripts side by side, for an honest A/B
  list      the transcripts available for this project
"""
import argparse
import json
import os
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


def project_dir(cwd=None):
    """Claude Code stores transcripts under the working directory with / replaced by -."""
    cwd = os.path.abspath(cwd or os.getcwd())
    return os.path.join(os.path.expanduser("~"), ".claude", "projects",
                        cwd.replace(os.sep, "-"))


def transcripts(cwd=None):
    d = project_dir(cwd)
    try:
        names = [os.path.join(d, n) for n in os.listdir(d) if n.endswith(".jsonl")]
    except OSError:
        return []
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
    return {
        "path": path,
        "turns": turns,
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


def main():
    parser = argparse.ArgumentParser(description="Measure a Claude Code session's token cost")
    parser.add_argument("--weights", default=None,
                        help="price ratios, e.g. out=5,write=1.25,read=0.1,in=1")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("session", help="the four token buckets, weighted")
    p.add_argument("--file", default=None, help="transcript path (default: most recent)")

    p = sub.add_parser("tools", help="per-tool cost, and the largest results")
    p.add_argument("--file", default=None)

    p = sub.add_parser("compare", help="two transcripts side by side")
    p.add_argument("a")
    p.add_argument("b")

    sub.add_parser("list", help="transcripts available for this project")

    args = parser.parse_args()
    weights = parse_weights(args.weights)

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
    else:
        print_tools(data)
    return 0


if __name__ == "__main__":
    sys.exit(main())
