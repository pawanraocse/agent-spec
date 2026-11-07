#!/usr/bin/env python3
"""agent-spec-mcp-filter.py — deterministic MCP response filter (B-006.1).

Pre-filters bulky MCP responses (such as Jira issue JSON) down to essential
keys before injecting into LLM context, avoiding 50–100 KB payload dumps.

Usage:
  agent-spec-mcp-filter.py [--kind jira|pr|generic] [--keys k1,k2] [FILE]
  cat response.json | agent-spec-mcp-filter.py
"""
import argparse
import json
import re
import sys


def flatten_adf(node):
    """Extract readable text from Atlassian Document Format (ADF) nodes."""
    if not isinstance(node, dict):
        return str(node) if node is not None else ""
    text_parts = []
    if node.get("type") == "text":
        return node.get("text", "")
    for child in node.get("content", []):
        text_parts.append(flatten_adf(child))
    return " ".join(p for p in text_parts if p).strip()


def extract_terms(text):
    """Extract candidate search terms (identifiers and keywords >= 3 chars)."""
    if not text:
        return []
    words = re.findall(r"[A-Za-z0-9_.-]{3,}", text)
    seen = set()
    terms = []
    for w in words:
        wl = w.lower()
        if wl not in seen and not wl.isdigit():
            seen.add(wl)
            terms.append(w)
    return terms[:25]


def filter_jira(data):
    """Extract essential Jira fields, dropping schemas, avatars, user links, transitions."""
    if not isinstance(data, dict):
        return data

    # Some MCP tools wrap the issue in a top-level key
    issue = data.get("issue", data) if isinstance(data.get("issue"), dict) else data
    fields = issue.get("fields", {}) if isinstance(issue.get("fields"), dict) else {}

    key = issue.get("key") or issue.get("id") or ""
    summary = fields.get("summary") or issue.get("summary") or ""

    desc_raw = fields.get("description") or issue.get("description") or ""
    if isinstance(desc_raw, dict):
        symptom = flatten_adf(desc_raw)
    else:
        symptom = str(desc_raw).strip()

    components = []
    for c in fields.get("components", []):
        if isinstance(c, dict) and "name" in c:
            components.append(c["name"])
        elif isinstance(c, str):
            components.append(c)

    attachments = []
    for a in fields.get("attachment", []):
        if isinstance(a, dict):
            fn = a.get("filename") or a.get("name") or ""
            kind = "log" if fn.endswith((".log", ".txt", ".out", ".gz")) else "attachment"
            attachments.append({"name": fn, "kind": kind, "size": a.get("size", 0)})

    status = fields.get("status")
    status_name = status.get("name") if isinstance(status, dict) else str(status or "")

    issuetype = fields.get("issuetype")
    type_name = issuetype.get("name") if isinstance(issuetype, dict) else str(issuetype or "")

    candidate_terms = extract_terms("%s %s %s %s" % (key, summary, " ".join(components), symptom[:500]))

    return {
        "key": key,
        "summary": summary,
        "symptom": symptom,
        "components": components,
        "status": status_name,
        "issuetype": type_name,
        "attachments": attachments,
        "candidate_terms": candidate_terms,
    }


def filter_pr(data):
    """Extract essential PR / Bitbucket fields."""
    if not isinstance(data, dict):
        return data
    pr = data.get("pullrequest", data) if isinstance(data.get("pullrequest"), dict) else data
    title = pr.get("title", "")
    desc = pr.get("description", "")
    return {
        "id": pr.get("id", ""),
        "title": title,
        "description": desc,
        "state": pr.get("state", ""),
        "source": (pr.get("source") or {}).get("branch", {}).get("name", "") if isinstance(pr.get("source"), dict) else "",
        "destination": (pr.get("destination") or {}).get("branch", {}).get("name", "") if isinstance(pr.get("destination"), dict) else "",
    }


def filter_generic(data, allowed_keys):
    """Whitelist specific top-level keys."""
    if not isinstance(data, dict):
        return data
    return {k: data[k] for k in allowed_keys if k in data}


def main():
    parser = argparse.ArgumentParser(description="Deterministic MCP response filter")
    parser.add_argument("file", nargs="?", help="Input JSON file (defaults to stdin)")
    parser.add_argument("--kind", choices=["jira", "pr", "generic"], default="jira",
                        help="Filtering profile (default: jira)")
    parser.add_argument("--keys", help="Comma-separated keys for generic filtering")
    args = parser.parse_args()

    if args.file and args.file != "-":
        with open(args.file, encoding="utf-8") as fh:
            raw = fh.read()
    else:
        raw = sys.stdin.read()

    try:
        data = json.loads(raw)
    except ValueError as exc:
        sys.stderr.write("mcp-filter: invalid JSON: %s\n" % exc)
        sys.exit(2)

    if args.keys or args.kind == "generic":
        keys = [k.strip() for k in (args.keys or "").split(",") if k.strip()]
        out = filter_generic(data, keys)
    elif args.kind == "pr":
        out = filter_pr(data)
    else:
        out = filter_jira(data)

    sys.stdout.write(json.dumps(out, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
