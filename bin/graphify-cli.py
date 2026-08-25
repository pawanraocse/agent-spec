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
from collections import Counter, defaultdict

GRAPH_PATH = os.path.join(os.getcwd(), ".agent-spec", "graph", "knowledge-graph.json")


def load_graph():
    if not os.path.exists(GRAPH_PATH):
        sys.exit(f"No graph at {GRAPH_PATH}. Run ./.agent-spec/bin/agent-spec-index first.")
    with open(GRAPH_PATH) as f:
        graph = json.load(f)
    if graph.get("version", "0") < "3.0":
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
    imports = sorted({e["target"] for e in edges if e["source"] == node})
    dependents = sorted({e["source"] for e in edges if e["target"] == node})

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

    if args.depth > 1:
        seen, frontier = set(dependents) | {node}, set(dependents)
        for level in range(2, args.depth + 1):
            frontier = {e["source"] for e in edges if e["target"] in frontier} - seen
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

    args = parser.parse_args()
    sys.exit(args.func(load_graph(), args))


if __name__ == "__main__":
    main()
