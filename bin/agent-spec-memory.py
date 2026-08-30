#!/usr/bin/env python3
"""agent-spec project memory.

A session snapshot is a narrative: good for a human catching up, useless for an agent
that needs one fact. This is the other half — one fact per file, typed, dated, sourced,
and small enough that the whole set can be put in front of a session without reading it.

  add     record one fact
  list    what is remembered
  search  find a fact by keyword
  show    one fact in full
  digest  the bounded block the SessionStart hook prints
  prune   drop stale facts
  rotate  archive old snapshot sections so SESSION-SNAPSHOT.md stays readable

Bounded on purpose. Memory that grows without limit is the problem it was meant to fix:
past a point every session pays for facts nobody reads. `digest` enforces a byte cap,
and `list` says when the store is over its fact cap so someone prunes it deliberately
rather than discovering it as a truncation.
"""
import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timedelta

ROOT = os.getcwd()
SPEC = os.path.join(ROOT, ".agent-spec")
FACTS = os.path.join(SPEC, "memory", "facts")
ARCHIVE = os.path.join(SPEC, "memory", "snapshots")
SNAPSHOT = os.path.join(SPEC, "SESSION-SNAPSHOT.md")

TYPES = ("decision", "constraint", "gotcha", "reference")

# A fact the digest prints every session has to earn its place. These caps are what
# stops the store becoming a second file nobody can afford to load.
DIGEST_BYTES = 1200
FACT_CAP = 40
SNAPSHOT_BYTES = 12000     # above this, rotate: keep the newest sections, archive the rest
SNAPSHOT_KEEP = 2          # sections left in the live file after a rotation


def slugify(text, limit=40):
    out = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return out[:limit] or "fact"


def fact_id(subject, text):
    digest = hashlib.sha1((subject + text).encode("utf-8")).hexdigest()[:6]
    return "%s-%s-%s" % (datetime.now().strftime("%Y%m%d"), slugify(subject, 24), digest)


def parse_fact(path):
    try:
        raw = open(path, encoding="utf-8").read()
    except OSError:
        return None
    m = re.match(r"---\n(.*?)\n---\n(.*)", raw, re.S)
    if not m:
        return None
    meta = {}
    for line in m.group(1).split("\n"):
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    meta["body"] = m.group(2).strip()
    meta["path"] = path
    return meta


def load_facts():
    if not os.path.isdir(FACTS):
        return []
    out = []
    for name in sorted(os.listdir(FACTS)):
        if not name.endswith(".md"):
            continue
        fact = parse_fact(os.path.join(FACTS, name))
        if fact:
            out.append(fact)
    out.sort(key=lambda f: f.get("created", ""), reverse=True)
    return out


def cmd_add(args):
    if args.type not in TYPES:
        print("type must be one of: %s" % ", ".join(TYPES), file=sys.stderr)
        return 2
    text = " ".join(args.text).strip()
    if len(text) < 10:
        print("A fact needs to be a sentence. Too short to be worth remembering.", file=sys.stderr)
        return 2
    if len(text) > 600:
        print("Too long for a fact (%d chars, cap 600). That is a snapshot section, "
              "not a fact — split it or put it in the snapshot." % len(text), file=sys.stderr)
        return 2

    existing = load_facts()
    for f in existing:
        if f["body"].strip().lower() == text.lower():
            print("Already recorded as %s — not duplicated." % f.get("id"))
            return 0

    os.makedirs(FACTS, exist_ok=True)
    fid = fact_id(args.subject, text)
    path = os.path.join(FACTS, fid + ".md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("---\nid: %s\ntype: %s\nsubject: %s\ncreated: %s\nsource: %s\n---\n%s\n"
                 % (fid, args.type, args.subject, datetime.now().strftime("%Y-%m-%d"),
                    args.source or "conversation", text))
    print("remembered: %s" % fid)
    if len(existing) + 1 > FACT_CAP:
        print("! %d facts, cap is %d. Run prune — past the cap the digest starts dropping "
              "facts, and it drops them by age, not by importance."
              % (len(existing) + 1, FACT_CAP))
    return 0


def cmd_list(args):
    facts = load_facts()
    if args.type:
        facts = [f for f in facts if f.get("type") == args.type]
    print("=== %d facts ===" % len(facts))
    for f in facts[: args.limit]:
        print("  [%-10s] %-12s %s" % (f.get("type", "?"), f.get("created", "?"), f.get("subject", "")))
        print("      %s" % f["body"].split("\n")[0][:110])
    if len(facts) > FACT_CAP:
        print("\n! over the cap of %d — prune." % FACT_CAP)
    return 0


def cmd_search(args):
    needle = args.keyword.lower()
    hits = [f for f in load_facts()
            if needle in f["body"].lower() or needle in f.get("subject", "").lower()]
    print("=== '%s' — %d facts ===" % (args.keyword, len(hits)))
    for f in hits[:20]:
        print("  %s  [%s]  %s" % (f.get("id"), f.get("type"), f.get("subject")))
        print("      %s" % f["body"].replace("\n", " ")[:200])
    if not hits:
        print("  (none)")
    return 0


def cmd_show(args):
    for f in load_facts():
        if f.get("id") == args.id or args.id in f.get("id", ""):
            print(open(f["path"], encoding="utf-8").read())
            return 0
    print("no fact matching '%s'" % args.id, file=sys.stderr)
    return 1


def cmd_digest(args):
    """The bounded block the SessionStart hook prints.

    Constraints first: they are the facts that make a session's work wrong if it does
    not know them. Everything else by recency, until the byte cap.
    """
    facts = load_facts()
    if not facts:
        return 0
    ordered = ([f for f in facts if f.get("type") == "constraint"]
               + [f for f in facts if f.get("type") != "constraint"])
    lines, used = [], 0
    for f in ordered:
        line = "- [%s] %s: %s" % (f.get("type", "?"), f.get("subject", ""),
                                  f["body"].replace("\n", " "))
        if used + len(line) > DIGEST_BYTES:
            lines.append("- (%d more facts — ./.agent-spec/bin/agent-spec-memory.py list)"
                         % (len(ordered) - len(lines)))
            break
        lines.append(line)
        used += len(line)
    print("\n".join(lines))
    return 0


def cmd_prune(args):
    facts = load_facts()
    cutoff = (datetime.now() - timedelta(days=args.older_than)).strftime("%Y-%m-%d")
    doomed = [f for f in facts
              if f.get("created", "9999") < cutoff and f.get("type") != "constraint"]
    if not doomed:
        print("nothing to prune (constraints are never pruned by age).")
        return 0
    for f in doomed:
        print("%s %s  [%s] %s" % ("would remove" if args.dry_run else "removed",
                                  f.get("id"), f.get("type"), f.get("subject")))
        if not args.dry_run:
            os.remove(f["path"])
    if args.dry_run:
        print("\n--dry-run: nothing was deleted. Re-run without it to apply.")
    return 0


def cmd_rotate(args):
    """Archive old snapshot sections so the live file stays small enough to read.

    The snapshot is append-only by design — the record of reversed decisions is the
    point — but an unbounded file gets truncated by whatever loads it, silently, and the
    oldest entries are the ones that vanish. Rotating moves them somewhere they can still
    be read on purpose.
    """
    if not os.path.exists(SNAPSHOT):
        print("no SESSION-SNAPSHOT.md")
        return 0
    text = open(SNAPSHOT, encoding="utf-8").read()
    size = len(text.encode("utf-8"))
    if size <= SNAPSHOT_BYTES and not args.force:
        print("%d B, under the %d B threshold — nothing to rotate." % (size, SNAPSHOT_BYTES))
        return 0

    parts = re.split(r"(?m)^# Session Snapshot", text)
    head, sections = parts[0], ["# Session Snapshot" + p for p in parts[1:]]
    if len(sections) <= SNAPSHOT_KEEP:
        print("only %d sections — nothing to archive." % len(sections))
        return 0

    os.makedirs(ARCHIVE, exist_ok=True)
    archived = sections[:-SNAPSHOT_KEEP]
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = os.path.join(ARCHIVE, "snapshots-through-%s.md" % stamp)
    with open(target, "w", encoding="utf-8") as fh:
        fh.write("# Archived session snapshots\n\n"
                 "> Rotated out of SESSION-SNAPSHOT.md on %s. Nothing here is deleted;\n"
                 "> it is moved so the live file stays small enough to load in full.\n\n"
                 % datetime.now().strftime("%Y-%m-%d"))
        fh.write("\n".join(archived))
    with open(SNAPSHOT, "w", encoding="utf-8") as fh:
        fh.write(head + "\n".join(sections[-SNAPSHOT_KEEP:]))
    print("archived %d sections to %s; %d kept."
          % (len(archived), os.path.relpath(target, ROOT), SNAPSHOT_KEEP))
    return 0


def main():
    parser = argparse.ArgumentParser(description="agent-spec project memory")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("add")
    p.add_argument("--type", required=True, choices=TYPES)
    p.add_argument("--subject", required=True)
    p.add_argument("--source", default=None, help="file:line, a commit, or a URL")
    p.add_argument("text", nargs="+")
    p.set_defaults(func=cmd_add)

    p = sub.add_parser("list")
    p.add_argument("--type", choices=TYPES)
    p.add_argument("--limit", type=int, default=40)
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("search")
    p.add_argument("keyword")
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("show")
    p.add_argument("id")
    p.set_defaults(func=cmd_show)

    sub.add_parser("digest").set_defaults(func=cmd_digest)

    p = sub.add_parser("prune")
    p.add_argument("--older-than", type=int, default=180, help="days")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_prune)

    p = sub.add_parser("rotate")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_rotate)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
