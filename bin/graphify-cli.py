#!/usr/bin/env python3
import os
import sys
import json
import argparse

PROJECT_ROOT = os.getcwd()
GRAPH_FILE = os.path.join(PROJECT_ROOT, ".agent-spec", "graph", "knowledge-graph.json")

def load_graph():
    if not os.path.exists(GRAPH_FILE):
        print(f"Error: {GRAPH_FILE} not found. Run agent-spec-index first.")
        sys.exit(1)
    with open(GRAPH_FILE, 'r') as f:
        return json.load(f)

def query_dependencies(graph, target_file):
    print(f"=== Dependencies for: {target_file} ===")
    
    # What does this file import?
    imports = [e['target'] for e in graph.get('edges', []) if target_file in e['source']]
    print("\n[IMPORTS] (This file depends on):")
    if imports:
        for imp in set(imports):
            print(f"  -> {imp}")
    else:
        print("  (None found)")
        
    # What imports this file?
    imported_by = [e['source'] for e in graph.get('edges', []) if target_file in e['target'] or any(target_file.endswith(t) for t in e['target'].split('.'))]
    print("\n[BLAST RADIUS] (These files depend on this file):")
    if imported_by:
        for imp in set(imported_by):
            print(f"  <- {imp}")
    else:
        print("  (None found)")

def search_nodes(graph, keyword):
    print(f"=== Search Results for: '{keyword}' ===")
    results = [n['path'] for n in graph.get('nodes', []) if keyword.lower() in n['path'].lower()]
    if results:
        for r in results:
            print(f"  - {r}")
    else:
        print("  (No files found matching keyword)")

def show_stats(graph):
    print("=== Graphify Statistics ===")
    stats = graph.get('stats', {})
    for k, v in stats.items():
        print(f"  {k}: {v}")
    print(f"  Total Nodes: {len(graph.get('nodes', []))}")
    print(f"  Total Edges: {len(graph.get('edges', []))}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Graphify AI Query Engine")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    parser_query = subparsers.add_parser("query", help="Find imports and blast radius for a file")
    parser_query.add_argument("--file", required=True, help="Path or partial path to the file")
    
    parser_search = subparsers.add_parser("search", help="Search for files matching a keyword")
    parser_search.add_argument("keyword", help="Keyword to search for")
    
    parser_stats = subparsers.add_parser("stats", help="Show project architecture statistics")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
        
    graph = load_graph()
    
    if args.command == "query":
        # Find exact node if partial path provided
        matches = [n['path'] for n in graph.get('nodes', []) if args.file in n['path']]
        if not matches:
            print(f"Could not find exact file matching: {args.file}")
            sys.exit(1)
        target = matches[0]
        query_dependencies(graph, target)
    elif args.command == "search":
        search_nodes(graph, args.keyword)
    elif args.command == "stats":
        show_stats(graph)
