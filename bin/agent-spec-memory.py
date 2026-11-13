#!/usr/bin/env python3
"""agent-spec project memory.

A session snapshot is a narrative: good for a human catching up, useless for an agent
that needs one fact. This is the other half — one fact per file, typed, dated, sourced,
and small enough that the whole set can be put in front of a session without reading it.

  add     record one fact
  list    what is remembered
  search  find a fact by keyword
  show    one fact in full
  lint    flag duplicate keys, opposing constraints, expired facts, dangling/cyclic supersedes
  index   write memory/INDEX.md — one line per fact; the only memory file audited for size
  digest  the bounded block the SessionStart hook prints
  prune   drop stale facts
  rotate  archive old snapshot sections so SESSION-SNAPSHOT.md stays readable
  merge-team <dir>  import shared team facts into .agent-spec/team-facts/ (read-only namespace)

Bounded on purpose. Memory that grows without limit is the problem it was meant to fix:
past a point every session pays for facts nobody reads. `digest` enforces a byte cap,
and `list` says when the store is over its fact cap so someone prunes it deliberately
rather than discovering it as a truncation.
"""
import argparse
import hashlib
import json
import glob
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


# Fact schema v2 (L-005): every field below is OPTIONAL, so a v1 fact (no such keys) loads
# and behaves exactly as before: status defaults to active, nothing expires.
CONFIDENCES = ("HIGH", "MEDIUM", "LOW")
STATUSES = ("active", "superseded", "expired", "deprecated")
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}$")


def _today():
    return datetime.now().strftime("%Y-%m-%d")


def valid_date(value):
    """True for a real YYYY-MM-DD calendar date."""
    if not _DATE_RE.match(value or ""):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return False
    return True


def fact_status(fact, today=None):
    """Effective status: 'expired' once `expires` is in the past, else the stored status
    (default active). An unknown stored status or an unparseable date never hides a fact;
    lint reports them instead."""
    status = fact.get("status") or "active"
    if status not in STATUSES:
        status = "active"
    expires = fact.get("expires")
    if status == "active" and valid_date(expires) and expires < (today or _today()):
        return "expired"
    return status


def is_active(fact, today=None):
    return fact_status(fact, today) == "active"


def _status_tag(fact):
    status = fact_status(fact)
    return "" if status == "active" else " (%s)" % status


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


# Shared team facts (T-053): same file format as local facts, kept in their own directory so
# they never count against the local fact cap or INDEX.md, and so a sync can replace them
# wholesale. Local facts win on a (type, subject) collision.
TEAM_DIR = os.path.join(SPEC, "team-facts")
TEAM_FACT_CAP = 40
TEAM_FACT_BYTES = 2000
TEAM_DIGEST_BYTES = 500
TEAM_SYNCED = ".synced"


def team_source_files(src):
    """Fact files in a team-facts source: <src>/facts/*.md if that directory exists, else <src>/*.md."""
    base = os.path.join(src, "facts") if os.path.isdir(os.path.join(src, "facts")) else src
    try:
        return [os.path.join(base, n) for n in sorted(os.listdir(base))
                if n.endswith(".md") and n.lower() != "readme.md"]
    except OSError:
        return []


def valid_team_fact(path):
    """(fact, reason). A team fact needs a known type, a subject and a body, within the size cap."""
    try:
        if os.path.getsize(path) > TEAM_FACT_BYTES:
            return None, "over %d B" % TEAM_FACT_BYTES
    except OSError:
        return None, "unreadable"
    fact = parse_fact(path)
    if not fact:
        return None, "no front matter"
    if fact.get("type") not in TYPES:
        return None, "unknown type '%s'" % fact.get("type", "")
    if not fact.get("subject") or not fact["body"]:
        return None, "missing subject or body"
    fact.setdefault("id", os.path.basename(path)[:-3])
    fact["team"] = True
    return fact, ""


def load_team_facts():
    out = []
    for path in team_source_files(TEAM_DIR)[:TEAM_FACT_CAP]:
        fact, _ = valid_team_fact(path)
        if fact:
            out.append(fact)
    out.sort(key=lambda f: f.get("created", ""), reverse=True)
    return out


def _key(fact):
    return (fact.get("type"), slugify(fact.get("subject", ""), 60))


def team_not_overridden(local, team):
    """Team facts minus any whose (type, subject) a local fact already states: local wins."""
    mine = {_key(f) for f in local}
    return [f for f in team if _key(f) not in mine]


INDEX = os.path.join(SPEC, "memory", "INDEX.md")
INDEX_LINE_MAX = 150

# Words that carry no topic. Negations and modals are here too: lint compares what a
# fact is *about*, then separately compares whether it affirms or forbids.
_NEGATIONS = {"never", "not", "no", "dont", "avoid", "forbid", "forbidden", "ban",
              "banned", "disable", "disabled", "without", "stop"}
_STOPWORDS = _NEGATIONS | {
    "the", "a", "an", "to", "of", "in", "on", "for", "and", "or", "is", "are", "be", "must",
    "should", "always", "do", "does", "use", "using", "used", "enable", "enabled", "all",
    "any", "with", "by", "at", "as", "it", "this", "that", "we", "our", "from", "when",
}
DUP_BODY_SIMILARITY = 0.8
CONFLICT_SIMILARITY = 0.5


def _tokens(text):
    cleaned = text.lower().replace("'", "")
    return re.findall(r"[a-z0-9]+(?:[._][a-z0-9]+)*", cleaned)


def _topic(text):
    return {t for t in _tokens(text) if t not in _STOPWORDS}


def _is_negative(text):
    return any(t in _NEGATIONS for t in _tokens(text))


def _jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def lint_facts(facts):
    """Return (kind, id_a, id_b, message) for every duplicate or opposing pair.

    DUP-KEY   same type and same subject once normalized (two facts, one key).
    DUP-BODY  bodies are near-identical, whatever their type or subject.
    CONFLICT  constraints/decisions about the same topic where one affirms and the
              other forbids. Compared on topic words, so "always use Jackson" and
              "never log bodies" are not flagged.
    """
    findings = []
    # Only live facts are compared pairwise: a superseded fact is expected to resemble (or
    # contradict) the one that replaced it.
    live = [f for f in facts if is_active(f)]
    for i, a in enumerate(live):
        for b in live[i + 1:]:
            ida, idb = a.get("id", "?"), b.get("id", "?")
            if (a.get("type") == b.get("type")
                    and slugify(a.get("subject", ""), 60) == slugify(b.get("subject", ""), 60)):
                findings.append(("DUP-KEY", ida, idb,
                                 "same type+subject '%s'" % a.get("subject", "")))
            if _jaccard(set(_tokens(a["body"])), set(_tokens(b["body"]))) >= DUP_BODY_SIMILARITY:
                findings.append(("DUP-BODY", ida, idb, "near-identical bodies"))
            if (a.get("type") in ("constraint", "decision")
                    and b.get("type") in ("constraint", "decision")
                    and _is_negative(a["body"]) != _is_negative(b["body"])
                    and _jaccard(_topic(a["body"]), _topic(b["body"])) >= CONFLICT_SIMILARITY):
                findings.append(("CONFLICT", ida, idb, "opposing statements on the same topic"))
    return findings + lint_v2(facts)


def lint_v2(facts):
    """Schema-v2 findings. Facts without v2 fields produce none.

    EXPIRED             `expires` is before today (the fact is treated as non-active).
    MISSING-SUPERSEDES  `supersedes` names a fact that is not in the store.
    SUPERSEDE-CYCLE     following `supersedes` pointers returns to the starting fact.
    BAD-FIELD           confidence/expires/status/version holds an unusable value.
    """
    findings = []
    ids = {f.get("id") for f in facts}
    today = _today()
    for f in facts:
        fid = f.get("id", "?")
        conf, exp, st, ver = (f.get(k) for k in ("confidence", "expires", "status", "version"))
        if conf is not None and conf not in CONFIDENCES:
            findings.append(("BAD-FIELD", fid, "-", "confidence '%s' not in %s" % (conf, "|".join(CONFIDENCES))))
        if exp is not None and not valid_date(exp):
            findings.append(("BAD-FIELD", fid, "-", "expires '%s' is not a YYYY-MM-DD date" % exp))
        if st is not None and st not in STATUSES:
            findings.append(("BAD-FIELD", fid, "-", "status '%s' not in %s" % (st, "|".join(STATUSES))))
        if ver is not None and not re.match(r"\d+$", ver):
            findings.append(("BAD-FIELD", fid, "-", "version '%s' is not an integer" % ver))
        if valid_date(exp) and exp < today:
            findings.append(("EXPIRED", fid, "-", "expired %s" % exp))
        target = f.get("supersedes")
        if target and target not in ids:
            findings.append(("MISSING-SUPERSEDES", fid, target, "supersedes target not found"))
    by_id = {f.get("id"): f.get("supersedes") for f in facts}
    reported = set()
    for start in by_id:
        seen, cur = [], start
        while cur in by_id and cur not in seen:
            seen.append(cur)
            cur = by_id[cur]
        if cur in seen:
            cycle = seen[seen.index(cur):]
            key = frozenset(cycle)
            if key not in reported:
                reported.add(key)
                findings.append(("SUPERSEDE-CYCLE", cycle[0], cycle[-1],
                                 "cycle: %s" % " -> ".join(cycle + [cycle[0]])))
    return findings


def _print_findings(findings):
    for kind, ida, idb, msg in findings:
        print("%-8s %s <> %s  (%s)" % (kind, ida, idb, msg))


def cmd_lint(args):
    facts = load_facts() + load_team_facts()
    findings = lint_facts(facts)
    if not findings:
        print("lint: clean (%d facts)" % len(facts))
        return 0
    _print_findings(findings)
    print("\n%d finding(s). Resolve by deleting or rewording one fact of each pair." % len(findings))
    return 1


def index_text(facts):
    """One short line per fact. Bodies stay in facts/; this is what is cheap to load."""
    lines = ["# Memory index (generated by agent-spec-memory.py index; do not edit)", ""]
    for f in facts:
        line = "- %s | %s | %s | %s" % (
            f.get("id", "?"), f.get("type", "?"), f.get("subject", "")[:30],
            f["body"].split("\n")[0])
        lines.append(line[:INDEX_LINE_MAX])
    return "\n".join(lines) + "\n"


def write_index():
    os.makedirs(os.path.dirname(INDEX), exist_ok=True)
    with open(INDEX, "w", encoding="utf-8") as fh:
        fh.write(index_text(load_facts()))


def cmd_index(args):
    if args.check:
        facts = load_facts()
        current = open(INDEX, encoding="utf-8").read() if os.path.exists(INDEX) else ""
        if not facts and not current:
            return 0
        if current != index_text(facts):
            print("INDEX.md is stale — run ./.agent-spec/bin/agent-spec-memory.py index")
            return 1
        print("INDEX.md is current (%d facts)" % len(facts))
        return 0
    write_index()
    print("wrote %s (%d B)" % (os.path.relpath(INDEX, ROOT), os.path.getsize(INDEX)))
    return 0


def set_status(path, status):
    """Set `status:` in a fact's frontmatter (replace the line, or add it); body untouched."""
    raw = open(path, encoding="utf-8").read()
    m = re.match(r"(---\n)(.*?)(\n---\n.*)", raw, re.S)
    if not m:
        return
    lines = [l for l in m.group(2).split("\n") if not l.startswith("status:")]
    lines.append("status: %s" % status)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(m.group(1) + "\n".join(lines) + m.group(3))


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

    if args.confidence is not None and args.confidence not in CONFIDENCES:
        print("confidence must be one of: %s" % ", ".join(CONFIDENCES), file=sys.stderr)
        return 2
    if args.expires is not None and not valid_date(args.expires):
        print("expires must be a YYYY-MM-DD date", file=sys.stderr)
        return 2

    existing = load_facts()
    for f in existing:
        if f["body"].strip().lower() == text.lower():
            print("Already recorded as %s — not duplicated." % f.get("id"))
            return 0

    old = None
    if args.supersedes:
        old = next((f for f in existing if f.get("id") == args.supersedes), None)
        if old is None:
            print("--supersedes: no fact with id '%s'" % args.supersedes, file=sys.stderr)
            return 2

    os.makedirs(FACTS, exist_ok=True)
    fid = fact_id(args.subject, text)
    path = os.path.join(FACTS, fid + ".md")
    extra = ""
    if args.confidence:
        extra += "confidence: %s\n" % args.confidence
    if args.expires:
        extra += "expires: %s\n" % args.expires
    if args.provenance:
        extra += "provenance: %s\n" % " ".join(args.provenance.split())
    addresses = [a for a in re.split(r"[,\s]+", (getattr(args, "addresses", None) or "").lower()) if a]
    if addresses:
        # DV-050: which review-finding classes this fact should make rarer. The model picks them
        # at /agent-spec-remember; the dashboard only counts findings before and after `created`.
        extra += "addresses: %s\n" % ", ".join(re.sub(r"[^a-z0-9_]", "_", a) for a in addresses)
    if old is not None:
        old_version = int(old["version"]) if re.match(r"\d+$", old.get("version", "")) else 1
        extra += "version: %d\nsupersedes: %s\n" % (old_version + 1, old["id"])
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("---\nid: %s\ntype: %s\nsubject: %s\ncreated: %s\nsource: %s\n%s---\n%s\n"
                 % (fid, args.type, args.subject, datetime.now().strftime("%Y-%m-%d"),
                    args.source or "conversation", extra, text))
    if old is not None:
        set_status(old["path"], "superseded")
    print("remembered: %s" % fid)
    write_index()
    related = [x for x in lint_facts(load_facts()) if fid in (x[1], x[2])]
    if related:
        print("! this fact overlaps an existing one — review:")
        _print_findings(related)
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
        print("  [%-10s] %-12s %s%s" % (f.get("type", "?"), f.get("created", "?"),
                                       f.get("subject", ""), _status_tag(f)))
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
        print("  %s  [%s]  %s%s" % (f.get("id"), f.get("type"), f.get("subject"), _status_tag(f)))
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
    # Non-active facts (superseded, deprecated, expired, past `expires`) are never injected.
    # team_not_overridden still sees the full local list: a retired local fact keeps
    # shadowing a team fact on the same (type, subject), as before.
    all_local = load_facts()
    facts = [f for f in all_local if is_active(f)]
    org = [f for f in team_not_overridden(all_local, load_team_facts())
           if f.get("type") == "constraint" and is_active(f)]
    lines, org_used = [], 0
    for f in org:
        line = "- [org] %s: %s" % (f.get("subject", ""), f["body"].replace("\n", " "))
        if org_used + len(line) > TEAM_DIGEST_BYTES:
            lines.append("- [org] (more org constraints — see .agent-spec/team-facts/)")
            break
        lines.append(line)
        org_used += len(line)
    if not facts:
        if lines:
            print("\n".join(lines))
        return 0
    ordered = ([f for f in facts if f.get("type") == "constraint"]
               + [f for f in facts if f.get("type") != "constraint"])
    used, org_lines = 0, len(lines)
    for f in ordered:
        line = "- [%s] %s: %s" % (f.get("type", "?"), f.get("subject", ""),
                                  f["body"].replace("\n", " "))
        if used + len(line) > DIGEST_BYTES:
            lines.append("- (%d more facts — ./.agent-spec/bin/agent-spec-memory.py list)"
                         % (len(ordered) - (len(lines) - org_lines)))
            break
        lines.append(line)
        used += len(line)
    print("\n".join(lines))
    return 0


def cmd_merge_team(args):
    """Replace .agent-spec/team-facts/ with the valid facts from <dir>. Invalid, oversized or
    excess files are skipped and named; the previous team facts are removed only after the
    source has been read. A git submodule at team-facts/ is used as-is, never overwritten."""
    src = os.path.abspath(args.source)
    if not os.path.isdir(src):
        print("merge-team: %s is not a directory" % args.source)
        return 1
    if os.path.exists(os.path.join(TEAM_DIR, ".git")) and os.path.realpath(src) != os.path.realpath(TEAM_DIR):
        print("merge-team: %s is a git checkout (submodule); update it with git, not merge-team"
              % os.path.relpath(TEAM_DIR, ROOT))
        return 0
    keep, skipped = [], []
    for path in team_source_files(src):
        fact, reason = valid_team_fact(path)
        if not fact:
            skipped.append("%s (%s)" % (os.path.basename(path), reason))
        elif len(keep) >= TEAM_FACT_CAP:
            skipped.append("%s (over the %d-fact cap)" % (os.path.basename(path), TEAM_FACT_CAP))
        else:
            keep.append((path, fact))
    if os.path.realpath(src) != os.path.realpath(TEAM_DIR):
        os.makedirs(TEAM_DIR, exist_ok=True)
        for name in os.listdir(TEAM_DIR):
            if name.endswith(".md") or name == TEAM_SYNCED:
                os.remove(os.path.join(TEAM_DIR, name))
        for path, _ in keep:
            with open(path, encoding="utf-8") as s, open(
                    os.path.join(TEAM_DIR, os.path.basename(path)), "w", encoding="utf-8") as d:
                d.write(s.read())
        with open(os.path.join(TEAM_DIR, TEAM_SYNCED), "w") as fh:
            fh.write(datetime.now().replace(microsecond=0).isoformat() + "\n")
    team = [f for _, f in keep]
    local = load_facts()
    overridden = len(team) - len(team_not_overridden(local, team))
    print("merge-team: %d team fact(s) from %s; %d skipped; %d overridden by local facts"
          % (len(team), os.path.basename(src), len(skipped), overridden))
    for s in skipped:
        print("  skipped: " + s)
    findings = lint_facts(local + team)
    if findings:
        _print_findings(findings)
        print("  %d lint finding(s) across local + team facts; local facts win in the digest."
              % len(findings))
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
    else:
        write_index()
    return 0


# The snapshot skill has written three heading shapes over time: '# Session Snapshot …',
# '## <date> …' and '## Session <date> …'. All three start a section. '## Archived
# sections' starts the index a rotation leaves behind; later snapshots append after it,
# so it can sit mid-file.
SECTION_RE = re.compile(r"(?m)^(?=# Session Snapshot\b"
                        r"|##[ \t]+(?:Session[ \t]+)?\d{4}-\d{2}-\d{2}"
                        r"|## Archived sections[ \t]*$)")
INDEX_HEADING = "## Archived sections"


def _split_snapshot(text):
    """Split a snapshot file into (preamble, sections, index_lines).

    Each section keeps its heading line and its trailing newlines, so joining the
    preamble and the sections reproduces the file minus the index blocks. Every
    '## Archived sections' block is pulled out, so a rotation rebuilds one index
    instead of stacking a new one after each run.
    """
    chunks = SECTION_RE.split(text)
    preamble, sections, index = chunks[0], [], []
    for chunk in chunks[1:]:
        if chunk.startswith(INDEX_HEADING):
            index.extend(l for l in chunk.split("\n")[1:] if l.strip())
        else:
            sections.append(chunk)
    return preamble, sections, index


def _heading_name(heading):
    return re.sub(r"^#+\s*(?:Session Snapshot|Session)?\s*", "", heading).strip(" —")


def _sections(text):
    """Split a snapshot file into (heading, body) pairs, index blocks excluded."""
    return [sec.partition("\n")[::2] for sec in _split_snapshot(text)[1]]


def _summary_line(body):
    """The first real sentence of a section, for an index line.

    Older sections carry a '## Session Summary'; dated sections start straight into
    '### Done' and a bullet list, so fall back to the first line of content.
    """
    m = re.search(r"(?ms)^## Session Summary\s*\n+(.+?)(?:\n\s*\n|\Z)", body)
    if m:
        return " ".join(m.group(1).split())
    for line in body.split("\n"):
        line = line.strip()
        if line and not line.startswith(("#", ">")):
            return " ".join(line.lstrip("-* ").replace("**", "").split())
    return ""


def cmd_snapshots(args):
    """Every snapshot section, live and archived, so the record can be reviewed
    without opening a 29 KB file to find out what is in it.
    """
    rows = []
    if os.path.exists(SNAPSHOT):
        text = open(SNAPSHOT, encoding="utf-8").read()
        for head, body in _sections(text):
            rows.append(("live", _heading_name(head),
                         len(body.encode("utf-8")), _summary_line(body)))
    for f in sorted(glob.glob(os.path.join(ARCHIVE, "*.md"))):
        text = open(f, encoding="utf-8").read()
        for head, body in _sections(text):
            rows.append((os.path.basename(f)[:28],
                         _heading_name(head),
                         len(body.encode("utf-8")), _summary_line(body)))
    if not rows:
        print("no snapshot sections")
        return 0
    total = sum(r[2] for r in rows)
    print("%-30s %-24s %8s  %s" % ("where", "section", "bytes", "summary"))
    for where, name, size, summary in rows:
        print("%-30s %-24s %8d  %s" % (where, name[:24], size, summary[:70]))
    print("\n%d sections, %d B total. Live file: %d B (rotate above %d B)."
          % (len(rows), total,
             os.path.getsize(SNAPSHOT) if os.path.exists(SNAPSHOT) else 0,
             SNAPSHOT_BYTES))
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

    preamble, sections, old_index = _split_snapshot(text)
    if len(sections) <= SNAPSHOT_KEEP:
        print("only %d sections — nothing to archive." % len(sections))
        return 0

    os.makedirs(ARCHIVE, exist_ok=True)
    archived, kept = sections[:-SNAPSHOT_KEEP], sections[-SNAPSHOT_KEEP:]
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = os.path.join(ARCHIVE, "snapshots-through-%s.md" % stamp)
    with open(target, "w", encoding="utf-8") as fh:
        fh.write("# Archived session snapshots\n\n"
                 "> Rotated out of SESSION-SNAPSHOT.md on %s. Nothing here is deleted;\n"
                 "> it is moved so the live file stays small enough to load in full.\n\n"
                 % datetime.now().strftime("%Y-%m-%d"))
        fh.write("".join(archived))
    # Moving sections out without saying so is how a record quietly stops being
    # one. The live file keeps a one-line index of everything that left, earlier
    # rotations included.
    index = [INDEX_HEADING] + old_index
    index.append("> Moved to `%s`. Nothing is deleted." % os.path.relpath(target, ROOT))
    for sec in archived:
        h, _, body = sec.partition("\n")
        index.append("- **%s** — %s" % (_heading_name(h),
                                         (_summary_line(body) or "no summary")[:110]))
    with open(SNAPSHOT, "w", encoding="utf-8") as fh:
        fh.write(preamble + "".join(kept).rstrip("\n") + "\n\n" + "\n".join(index) + "\n")
    print("archived %d sections to %s; %d kept."
          % (len(archived), os.path.relpath(target, ROOT), SNAPSHOT_KEEP))
    return 0


def main():
    parser = argparse.ArgumentParser(description="agent-spec project memory")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("add", aliases=["remember"])
    p.add_argument("--type", required=True, choices=TYPES)
    p.add_argument("--subject", required=True)
    p.add_argument("--source", default=None, help="file:line, a commit, or a URL")
    p.add_argument("--confidence", default=None, help="HIGH|MEDIUM|LOW (optional)")
    p.add_argument("--expires", default=None, help="YYYY-MM-DD; non-active after this date (optional)")
    p.add_argument("--provenance", default=None, help="session/run id or file this came from (optional)")
    p.add_argument("--addresses", default=None,
                   help="comma-separated review finding categories this fact should prevent (optional)")
    p.add_argument("--supersedes", default=None,
                   help="id of the fact this replaces; it is marked superseded, version bumps")
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

    sub.add_parser("lint", help="flag duplicate keys, near-identical bodies, opposing constraints"
                   ).set_defaults(func=cmd_lint)

    p = sub.add_parser("index", help="write memory/INDEX.md, one line per fact")
    p.add_argument("--check", action="store_true", help="exit 1 if INDEX.md is stale")
    p.set_defaults(func=cmd_index)

    p = sub.add_parser("merge-team", help="import shared team facts into .agent-spec/team-facts/")
    p.add_argument("source", help="directory holding fact files (or a facts/ subdirectory)")
    p.set_defaults(func=cmd_merge_team)

    sub.add_parser("digest").set_defaults(func=cmd_digest)
    sub.add_parser("snapshots").set_defaults(func=cmd_snapshots)

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
