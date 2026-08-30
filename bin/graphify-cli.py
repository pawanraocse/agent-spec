#!/usr/bin/env python3
"""Graphify query engine.

Answer structural questions from the graph instead of reading the tree. Every
answer here costs a few hundred tokens; the equivalent file reads cost tens of
thousands.
"""
import os
import sys
import json
import argparse
import re

# Cycle detection recurses to the depth of the longest import chain.
sys.setrecursionlimit(10000)
from collections import Counter, defaultdict

GRAPH_PATH = os.path.join(os.getcwd(), ".agent-spec", "graph", "knowledge-graph.json")


def load_graph():
    if not os.path.exists(GRAPH_PATH):
        sys.exit(f"No graph at {GRAPH_PATH}. Run ./.agent-spec/bin/agent-spec-index first.")
    with open(GRAPH_PATH) as f:
        graph = json.load(f)
    try:
        version = float(str(graph.get("version", "0")).split(".")[0])
    except ValueError:
        version = 0.0
    if version < 3:
        print("! graph was built by an older Graphify and has unresolved edges.\n"
              "  Rebuild it: ./.agent-spec/bin/agent-spec-index\n", file=sys.stderr)
    return graph


def match_node(graph, target):
    """Resolve a user-typed path to exactly one node id."""
    ids = [n["id"] for n in graph.get("nodes", [])]
    if target in ids:
        return target
    needle = target.replace(os.sep, "/").lstrip("./")
    hits = [i for i in ids if i.endswith(needle)]
    if not hits:
        hits = [i for i in ids if needle in i]
    if not hits:
        print(f"No file matching '{target}'.")
        return None
    if len(hits) > 1:
        print(f"'{target}' is ambiguous — {len(hits)} matches:")
        for h in hits[:10]:
            print(f"  {h}")
        return None
    return hits[0]


def cmd_query(graph, args):
    """Imports and blast radius, both from resolved edges only."""
    node = match_node(graph, args.file)
    if not node:
        return 1
    edges = graph.get("edges", [])
    src_edges = [e for e in edges if e.get("type", "imports") == "imports"]
    imports = sorted({e["target"] for e in src_edges if e["source"] == node})
    dependents = sorted({e["source"] for e in src_edges if e["target"] == node})
    wires = [e for e in edges if e.get("type") != "imports"
             and node in (e["source"], e["target"])]

    print(f"=== {node} ===")
    print(f"\n[IMPORTS] {len(imports)} internal")
    for i in imports:
        print(f"  -> {i}")
    if not imports:
        print("  (none)")
    print(f"\n[BLAST RADIUS] {len(dependents)} files import this")
    for d in dependents:
        print(f"  <- {d}")
    if not dependents:
        print("  (none — safe to change in isolation, or dead code)")

    if wires:
        print(f"\n[INTEGRATION] {len(wires)} edges no import graph can see")
        for e in wires:
            arrow = "->" if e["source"] == node else "<-"
            other = e["target"] if e["source"] == node else e["source"]
            print(f"  {arrow} {other}  ({e['type']}: {e.get('detail', '')})")

    if args.depth > 1:
        seen, frontier = set(dependents) | {node}, set(dependents)
        for level in range(2, args.depth + 1):
            frontier = {e["source"] for e in src_edges if e["target"] in frontier} - seen
            if not frontier:
                break
            seen |= frontier
            print(f"\n[BLAST RADIUS depth {level}] {len(frontier)} files")
            for d in sorted(frontier):
                print(f"  <- {d}")
    return 0


def cmd_search(graph, args):
    keyword = args.keyword.lower()
    hits = [n for n in graph.get("nodes", []) if keyword in n["path"].lower()]
    fan_in = Counter(e["target"] for e in graph.get("edges", []))
    print(f"=== '{args.keyword}' — {len(hits)} files ===")
    for n in sorted(hits, key=lambda x: -fan_in[x["id"]])[:40]:
        print(f"  {n['id']}  ({fan_in[n['id']]} dependents)")
    if not hits:
        print("  (none)")
    return 0


def cmd_stats(graph, args):
    stats = graph.get("stats", {})
    print(f"=== {graph.get('project')} ===")
    print(f"Stack: {graph.get('stack', 'Unknown')}")
    print(f"Files: {stats.get('files')}   Internal edges: {stats.get('internal_edges')}   "
          f"Tests: {stats.get('test_files')}   Cycles: {stats.get('cycles')}")
    langs = stats.get("languages", {})
    if langs:
        print("Languages: " + ", ".join(f"{k} {v}" for k, v in langs.items()))
    print("\nMost depended-upon (change these carefully):")
    for path, count in stats.get("most_depended", [])[:10]:
        print(f"  {count:4d}  {path}")
    print("\nTop external packages:")
    for name, count in stats.get("top_external", [])[:10]:
        print(f"  {count:4d}  {name}")
    return 0


def cmd_cycles(graph, args):
    """Import cycles, recomputed from the resolved edges."""
    adjacency = defaultdict(set)
    for e in graph.get("edges", []):
        if e.get("type", "imports") == "imports":
            adjacency[e["source"]].add(e["target"])
    cycles, state, stack = [], {}, []

    def walk(node):
        state[node] = 1
        stack.append(node)
        for nxt in adjacency.get(node, ()):
            if state.get(nxt) == 1:
                cycles.append(stack[stack.index(nxt):] + [nxt])
            elif state.get(nxt, 0) == 0:
                walk(nxt)
        stack.pop()
        state[node] = 2

    for node in list(adjacency):
        if state.get(node, 0) == 0:
            walk(node)

    print(f"=== {len(cycles)} import cycles ===")
    for c in cycles[:20]:
        print("  " + " -> ".join(os.path.basename(x) for x in c))
    if not cycles:
        print("  (none)")
    return 0


def cmd_module(graph, args):
    """What a directory owns, and how it couples to the rest."""
    prefix = args.path.rstrip("/") + "/"
    inside = {n["id"] for n in graph.get("nodes", []) if n["id"].startswith(prefix)}
    if not inside:
        print(f"No files under '{prefix}'.")
        return 1
    out_edges = [e for e in graph.get("edges", []) if e["source"] in inside and e["target"] not in inside]
    in_edges = [e for e in graph.get("edges", []) if e["target"] in inside and e["source"] not in inside]
    print(f"=== {prefix} — {len(inside)} files ===")
    print(f"\n[DEPENDS ON] {len(out_edges)} edges leaving the module")
    for target, count in Counter(e["target"] for e in out_edges).most_common(15):
        print(f"  {count:3d}  -> {target}")
    print(f"\n[USED BY] {len(in_edges)} edges entering the module")
    for source, count in Counter(e["source"] for e in in_edges).most_common(15):
        print(f"  {count:3d}  <- {source}")
    return 0



def cmd_flow(graph, args):
    """Follow the call chain outward from one file.

    `query` answers one hop. A code review needs the path: entry point, the service
    it calls, the repository under that. Depth-first, deduplicated, depth-capped —
    an unbounded flow on a real codebase prints the whole repository.
    """
    node = match_node(graph, args.start)
    if not node:
        return 1
    out = defaultdict(list)
    for e in graph.get("edges", []):
        out[e["source"]].append(e)
    layers = {n["id"]: n.get("layer", "?") for n in graph.get("nodes", [])}

    print(f"=== flow from {node} (depth {args.depth}) ===")
    seen = set()

    def walk(current, level, prefix):
        if level > args.depth or current in seen:
            return
        seen.add(current)
        for e in sorted(out.get(current, []), key=lambda x: x["target"]):
            kind = "" if e.get("type", "imports") == "imports" else f"  [{e['type']}: {e.get('detail', '')}]"
            print(f"{prefix}-> {e['target']}  ({layers.get(e['target'], 'external')}){kind}")
            walk(e["target"], level + 1, prefix + "  ")

    walk(node, 1, "  ")
    if not seen - {node}:
        print("  (leaf — this file calls nothing internal)")
    return 0


def cmd_services(graph, args):
    """Service inventory and the traffic between services."""
    services = graph.get("services", {})
    nodes = graph.get("nodes", [])
    if not services:
        print("No service manifests below the root — this is a single deployable.")
        return 0

    owner = {n["id"]: n.get("service") for n in nodes}
    counts = Counter(s for s in owner.values() if s)
    print(f"=== {len(set(services.values()))} services ===")
    for root, name in sorted(services.items()):
        eps = sum(len(n.get("endpoints") or []) for n in nodes if n.get("service") == name)
        print(f"  {name:20s} {counts[name]:4d} files  {eps:3d} endpoints   ({root or '.'}/)")

    wires = [e for e in graph.get("edges", []) if e.get("type") != "imports"]
    pairs = Counter()
    for e in wires:
        src = owner.get(e["source"]) or "?"
        dst = owner.get(e["target"], e["target"])
        pairs[(src, dst, e["type"])] += 1
    print(f"\n[INTEGRATION] {len(wires)} edges")
    for (src, dst, kind), count in pairs.most_common(30):
        print(f"  {src} -{kind}-> {dst}   ({count})")
    if not wires:
        print("  (none detected)")

    topics = graph.get("topics", {})
    if topics:
        print(f"\n[TOPICS] {len(topics)}")
        for topic, ends in list(topics.items())[:20]:
            print(f"  {topic}: {len(ends['producers'])} producers, {len(ends['consumers'])} consumers")
    return 0


def cmd_endpoints(graph, args):
    """The HTTP surface, which is the contract other teams actually depend on."""
    nodes = [n for n in graph.get("nodes", []) if n.get("endpoints")]
    if args.service:
        nodes = [n for n in nodes if n.get("service") == args.service]
    total = sum(len(n["endpoints"]) for n in nodes)
    print(f"=== {total} endpoints in {len(nodes)} files ===")
    for n in sorted(nodes, key=lambda x: (x.get("service") or "", x["id"])):
        print(f"  [{n.get('service') or '-'}] {n['id']}")
        for ep in n["endpoints"]:
            print(f"      {ep}")
    if not nodes:
        print("  (none detected)")
    return 0


def cmd_layers(graph, args):
    """Layer census, and every edge that points the wrong way through it."""
    counts = Counter(n.get("layer", "unknown") for n in graph.get("nodes", []))
    print("=== layers ===")
    for layer, count in counts.most_common():
        print(f"  {layer:14s} {count:5d}")

    violations = graph.get("layer_violations", [])
    print(f"\n=== {len(violations)} layer violations ===")
    for v in violations[:40]:
        print(f"  {v['source']} ({v['from_layer']})")
        print(f"    -> {v['target']} ({v['to_layer']})")
    if not violations:
        print("  (none)")
    return 0


def cmd_context(graph, args):
    """The file list a task needs — nothing else.

    This is the token lever. Left to itself an agent greps, opens twenty files and
    keeps three. Here the graph scores candidates by name match, then pulls in one
    hop of neighbours, and returns a capped list. Reading the answer costs a few
    hundred tokens; finding it by hand costs tens of thousands.
    """
    words = [w.lower() for w in re.findall(r"[A-Za-z][A-Za-z0-9_]{2,}", args.task)]
    stop = {"the", "and", "for", "with", "add", "fix", "make", "should", "when", "that",
            "this", "from", "into", "use", "using", "does", "not", "why", "how"}
    words = [w for w in words if w not in stop]
    if not words:
        print("No searchable terms in the task description.")
        return 1

    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    fan_in = Counter(e["target"] for e in edges if e.get("type", "imports") == "imports")

    scores = Counter()
    for n in nodes:
        lowered = n["id"].lower()
        hit = sum(3 if w in os.path.basename(lowered) else 1 for w in words if w in lowered)
        if hit:
            scores[n["id"]] = hit

    if not scores:
        print(f"Nothing matches {words}. Widen the task description, or run "
              f"./.agent-spec/bin/graphify-cli.py search <term>.")
        return 1

    seeds = [nid for nid, _ in scores.most_common(max(3, args.budget // 3))]
    neighbours = Counter()
    for e in edges:
        if e["source"] in seeds:
            neighbours[e["target"]] += 1
        if e["target"] in seeds:
            neighbours[e["source"]] += 1

    meta = {n["id"]: n for n in nodes}
    picked, seen = [], set()
    for nid in seeds:
        if nid in meta and nid not in seen:
            seen.add(nid)
            picked.append((nid, "match"))
    for nid, _ in neighbours.most_common():
        if len(picked) >= args.budget:
            break
        if nid in meta and nid not in seen:
            seen.add(nid)
            picked.append((nid, "neighbour"))

    print(f"=== context for: {args.task} ===")
    print(f"terms: {' '.join(words)}   files: {len(picked)} of {len(nodes)}\n")
    for nid, why in picked[: args.budget]:
        n = meta[nid]
        print(f"  {nid}")
        print(f"      {why} | layer={n.get('layer', '?')} | service={n.get('service') or '-'} "
              f"| dependents={fan_in[nid]}")
    print("\nRead these. Do not walk the tree for more — re-run with a sharper task "
          "description, or widen --budget.")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Graphify query engine")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("query", help="Imports and blast radius for one file")
    p.add_argument("--file", required=True)
    p.add_argument("--depth", type=int, default=1, help="Transitive dependent levels")
    p.set_defaults(func=cmd_query)

    p = sub.add_parser("search", help="Find files by keyword, ranked by dependents")
    p.add_argument("keyword")
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("stats", help="Architecture overview")
    p.set_defaults(func=cmd_stats)

    p = sub.add_parser("cycles", help="List import cycles")
    p.set_defaults(func=cmd_cycles)

    p = sub.add_parser("module", help="Coupling for a directory")
    p.add_argument("path")
    p.set_defaults(func=cmd_module)

    p = sub.add_parser("flow", help="Follow the call chain outward from one file")
    p.add_argument("--from", dest="start", required=True)
    p.add_argument("--depth", type=int, default=3)
    p.set_defaults(func=cmd_flow)

    p = sub.add_parser("services", help="Service inventory and integration edges")
    p.set_defaults(func=cmd_services)

    p = sub.add_parser("endpoints", help="HTTP surface")
    p.add_argument("--service", default=None)
    p.set_defaults(func=cmd_endpoints)

    p = sub.add_parser("layers", help="Layer census and violations")
    p.set_defaults(func=cmd_layers)

    p = sub.add_parser("context", help="The file list a task needs, and nothing else")
    p.add_argument("--task", required=True)
    p.add_argument("--budget", type=int, default=12, help="Maximum files to return")
    p.set_defaults(func=cmd_context)

    args = parser.parse_args()
    sys.exit(args.func(load_graph(), args))


if __name__ == "__main__":
    main()
