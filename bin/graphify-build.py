#!/usr/bin/env python3
"""Graphify — build the project knowledge graph.

Walks the source tree, extracts imports, and RESOLVES each import to a node in
the graph. Only resolved (internal) imports become edges; everything else is
recorded as an external dependency count. An edge whose target is not a node is
not a dependency the agent can traverse, and a graph full of `import json` is
noise that hides the real structure.
"""
import os
import re
import json
import argparse
from collections import defaultdict, Counter
from datetime import datetime

PROJECT_ROOT = os.getcwd()
OUTPUT_DIR = os.path.join(PROJECT_ROOT, ".agent-spec", "graph")

IMPORT_PATTERNS = [
    r'^\s*from\s+([.\w]+)\s+import',                  # Python
    r'^\s*import\s+([.\w]+)',                          # Python / Java / Go
    r'^\s*import\s+.*?\bfrom\s+[\'"]([^\'"]+)[\'"]',   # ES module
    r'^\s*import\s+[\'"]([^\'"]+)[\'"]',               # ES bare import
    r'^\s*export\s+.*?\bfrom\s+[\'"]([^\'"]+)[\'"]',   # ES re-export
    r'require\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)',        # CommonJS
    r'^\s*#include\s*[<"]([^>"]+)[>"]',                # C / C++
    r'^\s*use\s+([\w:]+)',                             # Rust
]

EXCLUDE_DIRS = {
    '.git', 'node_modules', 'target', 'dist', 'build', 'out', 'obj',
    'venv', '.venv', 'env', '.idea', '.vscode', '__pycache__', '.agent-spec',
    '.next', '.nuxt', 'coverage', '.pytest_cache', '.mypy_cache', '.ruff_cache',
    'vendor', 'Pods', '.gradle', '.tox', 'site-packages',
}

# Extensions we index. Keep in step with IMPORT_PATTERNS.
ALLOWED_EXTS = {
    '.py', '.java', '.kt', '.kts', '.scala', '.go', '.rs', '.rb', '.php', '.cs',
    '.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs', '.vue', '.svelte',
    '.c', '.h', '.cpp', '.hpp', '.cc',
}

LANG_BY_EXT = {
    '.py': 'python', '.java': 'java', '.kt': 'kotlin', '.kts': 'kotlin',
    '.scala': 'scala', '.go': 'go', '.rs': 'rust', '.rb': 'ruby',
    '.php': 'php', '.cs': 'csharp', '.ts': 'typescript', '.tsx': 'typescript',
    '.js': 'javascript', '.jsx': 'javascript', '.mjs': 'javascript',
    '.cjs': 'javascript', '.vue': 'vue', '.svelte': 'svelte',
    '.c': 'c', '.h': 'c', '.cpp': 'cpp', '.hpp': 'cpp', '.cc': 'cpp',
}

TEST_HINTS = ('test', 'spec', '_test.', '.test.', '.spec.')

# Manifests, in probe order. First hit wins.
MANIFESTS = [
    ("pom.xml",         "Java (Maven)",  {"spring-boot": "Java Spring Boot"}),
    ("build.gradle",    "Java (Gradle)", {"org.springframework.boot": "Java Spring Boot"}),
    ("build.gradle.kts","Kotlin (Gradle)", {}),
    ("package.json",    "Node.js",       {"angular": "Node.js + Angular", "next": "Node.js + Next.js",
                                          "react": "Node.js + React", "vue": "Node.js + Vue",
                                          "svelte": "Node.js + Svelte", "express": "Node.js + Express",
                                          "nestjs": "Node.js + NestJS"}),
    ("pyproject.toml",  "Python",        {"django": "Python (Django)", "fastapi": "Python (FastAPI)",
                                          "flask": "Python (Flask)", "pydantic": "Python (Pydantic)"}),
    ("requirements.txt","Python",        {"django": "Python (Django)", "fastapi": "Python (FastAPI)",
                                          "flask": "Python (Flask)"}),
    ("go.mod",          "Go",            {}),
    ("Cargo.toml",      "Rust",          {}),
    ("Gemfile",         "Ruby",          {"rails": "Ruby on Rails"}),
    ("composer.json",   "PHP",           {"laravel": "PHP (Laravel)", "symfony": "PHP (Symfony)"}),
]


def detect_stack():
    """First matching manifest wins; refine by a marker inside it."""
    # Probe the root and one level down — a monorepo keeps its manifests in
    # service directories, and reporting "Unknown" for those is useless.
    roots = [PROJECT_ROOT]
    try:
        roots += [os.path.join(PROJECT_ROOT, d) for d in sorted(os.listdir(PROJECT_ROOT))
                  if os.path.isdir(os.path.join(PROJECT_ROOT, d))
                  and d not in EXCLUDE_DIRS and not d.startswith(".")]
    except OSError:
        pass

    found = []
    for filename, base, markers in MANIFESTS:
        path = next((os.path.join(r, filename) for r in roots
                     if os.path.exists(os.path.join(r, filename))), None)
        if path is None:
            continue
        stack = base
        try:
            content = open(path, "r", encoding="utf-8", errors="ignore").read().lower()
            for marker, refined in markers.items():
                if marker in content:
                    stack = refined
                    break
        except OSError:
            pass
        found.append(stack)
    if not found:
        return "Unknown"
    # Polyglot repos keep every stack — a monorepo with a Java service and an
    # Angular front end is not "Java".
    return " + ".join(dict.fromkeys(found))


def extract_imports(filepath):
    out = set()
    try:
        content = open(filepath, "r", encoding="utf-8", errors="ignore").read()
    except OSError:
        return []
    for pattern in IMPORT_PATTERNS:
        for m in re.finditer(pattern, content, re.MULTILINE):
            token = m.group(1).strip()
            if token:
                out.add(token)
    return sorted(out)


def collect_files():
    files = []
    for root, dirs, names in os.walk(PROJECT_ROOT):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith('.')]
        for name in names:
            ext = os.path.splitext(name)[1]
            if ext not in ALLOWED_EXTS:
                continue
            rel = os.path.relpath(os.path.join(root, name), PROJECT_ROOT)
            files.append(rel.replace(os.sep, "/"))
    return sorted(files)


def build_index(files):
    """Map every way an import could name a file back to its path.

    by_path : 'src/app/utils' (no extension, and the /index form) -> path
    by_dotted: every dotted suffix of the path, longest first  -> [paths]
               'nivesh_engine.contracts.facts', 'contracts.facts', 'facts'
               covers Python packages and Java FQNs without needing to know
               where the source root is.
    """
    by_path = {}
    by_dotted = defaultdict(list)
    for rel in files:
        stem, _ = os.path.splitext(rel)
        stems = [stem]
        # A package entry point also answers to its directory: importing
        # `app.services` must reach `app/services/__init__.py`.
        for entry in ("/__init__", "/index", "/mod"):
            if stem.endswith(entry):
                stems.append(stem[: -len(entry)])
        for s in stems:
            by_path.setdefault(s, rel)
            parts = s.split("/")
            for i in range(len(parts)):
                by_dotted[".".join(parts[i:])].append(rel)
    return by_path, by_dotted


def resolve(token, importer, by_path, by_dotted):
    """Return the node this import names, or None if it is external."""
    importer_dir = os.path.dirname(importer)

    # Relative: ./x, ../x, and Python's .x / ..x
    if token.startswith("."):
        if "/" in token or token.startswith("./") or token.startswith("../"):
            target = os.path.normpath(os.path.join(importer_dir, token)).replace(os.sep, "/")
            return by_path.get(target)
        # Python relative import: leading dots are parent levels.
        up = len(token) - len(token.lstrip("."))
        rest = token.lstrip(".").replace(".", "/")
        base = importer_dir
        for _ in range(up - 1):
            base = os.path.dirname(base)
        target = os.path.normpath(os.path.join(base, rest)).replace(os.sep, "/") if rest else base
        return by_path.get(target)

    if "/" in token:
        target = os.path.normpath(os.path.join(importer_dir, token)).replace(os.sep, "/")
        return by_path.get(target) or by_path.get(token)

    token = token.replace("::", ".")           # Rust paths
    # Longest dotted suffix that names exactly one file. Ambiguity is not a
    # dependency — two candidates means we do not know, so we say nothing.
    parts = token.split(".")
    for i in range(len(parts)):
        candidate = ".".join(parts[i:])
        hits = by_dotted.get(candidate)
        if hits and len(hits) == 1 and hits[0] != importer:
            return hits[0]
    return None


def find_cycles(adjacency, limit=20):
    """Depth-first cycle detection over the resolved graph."""
    cycles, state, stack = [], {}, []

    def walk(node):
        if len(cycles) >= limit:
            return
        state[node] = 1
        stack.append(node)
        for nxt in adjacency.get(node, ()):
            if state.get(nxt) == 1:
                cycles.append(stack[stack.index(nxt):] + [nxt])
                if len(cycles) >= limit:
                    break
            elif state.get(nxt, 0) == 0:
                walk(nxt)
        stack.pop()
        state[node] = 2

    for node in adjacency:
        if state.get(node, 0) == 0:
            walk(node)
    return cycles


def top_modules(files, depth=2):
    """Group files into modules by their first `depth` path segments.

    Top-level directories alone are not modules — `src/` is one folder and
    twelve services. Two segments gets `services/billing`, `src/app`.
    """
    counts = Counter()
    for rel in files:
        parts = rel.split("/")[:-1]
        if not parts:
            continue
        counts["/".join(parts[:depth])] += 1
    return counts


def write_project_index(stack, modules, stats, path):
    rows = "".join(
        f"| `{mod}/` | [TODO] | `{mod}` | {count} files |\n"
        for mod, count in modules.most_common(25)
    ) or "| | [TODO: no modules auto-detected] | | |\n"
    date_str = datetime.now().strftime("%Y-%m-%d")
    content = f"""# Project Index

> Generated by Graphify on {date_str}. Run `/onboard` to fill the [TODO] entries
> from the repository itself.

## Project Overview
**Name**: {os.path.basename(PROJECT_ROOT)}
**Type**: [TODO: web-app, api, library or CLI?]
**Tech Stack**: {stack}
**Status**: active

## Scale
| Metric | Value |
|--------|-------|
| Source files | {stats['files']} |
| Internal dependencies | {stats['internal_edges']} |
| External packages | {stats['external_packages']} |
| Test files | {stats['test_files']} |
| Import cycles | {stats['cycles']} |

## Modules / Services
| Module | Responsibility | Path | Size |
|--------|---------------|------|------|
{rows}
## Key Architectural Decisions
- [TODO: ask the user whether any ADRs exist]

## Known Technical Debt
- [TODO: see .agent-spec/TECH-DEBT-REGISTER.md]

## External Dependencies
{chr(10).join(f'- `{name}` ({count} imports)' for name, count in stats['top_external']) or '- [TODO]'}
"""
    if os.path.exists(path):
        print("PROJECT-INDEX.md exists — left alone to preserve human notes.")
        return
    open(path, "w").write(content)
    print("Wrote PROJECT-INDEX.md")


def write_graph_md(stack, stats, hot, cycles, path):
    lines = [f'  "{a.split("/")[-1]}" --> "{b.split("/")[-1]}"' for a, b in hot[:25]]
    cycle_block = "\n".join(
        "- " + " → ".join(os.path.basename(n) for n in c) for c in cycles[:5]
    ) or "- none detected"
    content = f"""# Knowledge Graph

> Generated by Graphify on {datetime.now().strftime('%Y-%m-%d %H:%M')}.
> Do not read this file to answer a structural question — query it:
> `./.agent-spec/bin/graphify-cli.py query --file <path>`

**Stack**: {stack} · **Files**: {stats['files']} · **Internal edges**: {stats['internal_edges']} · **Cycles**: {stats['cycles']}

## Most depended-upon files
| File | Dependents |
|------|-----------|
{chr(10).join(f'| `{f}` | {n} |' for f, n in stats['most_depended']) or '| | |'}

## Busiest edges

```mermaid
graph TD
{chr(10).join(lines) or '  A[no internal edges resolved]'}
```

## Import cycles
{cycle_block}

## Orphans (no internal imports either way)
{chr(10).join(f'- `{f}`' for f in stats['orphans'][:15]) or '- none'}
"""
    open(path, "w").write(content)
    print("Wrote KNOWLEDGE-GRAPH.md")


def main():
    parser = argparse.ArgumentParser(description="Build the Graphify knowledge graph")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    stack = detect_stack()
    files = collect_files()
    by_path, by_dotted = build_index(files)

    nodes, edges = [], []
    external = Counter()
    lang_counts = Counter()
    test_files = 0
    adjacency = defaultdict(set)

    for rel in files:
        ext = os.path.splitext(rel)[1]
        lang_counts[LANG_BY_EXT.get(ext, "other")] += 1
        lowered = rel.lower()
        is_test = any(h in lowered for h in TEST_HINTS)
        if is_test:
            test_files += 1
        nodes.append({"id": rel, "type": "test" if is_test else "file",
                      "path": rel, "lang": LANG_BY_EXT.get(ext, "other")})

        for token in extract_imports(os.path.join(PROJECT_ROOT, rel)):
            target = resolve(token, rel, by_path, by_dotted)
            if target:
                edges.append({"source": rel, "target": target, "type": "imports"})
                adjacency[rel].add(target)
            else:
                external[token.split(".")[0].split("/")[0]] += 1

    fan_in = Counter(e["target"] for e in edges)
    fan_out = Counter(e["source"] for e in edges)
    connected = set(fan_in) | set(fan_out)
    orphans = [f for f in files if f not in connected]
    cycles = find_cycles(adjacency)
    hot = [(e["source"], e["target"]) for e in edges
           if fan_in[e["target"]] >= 2][:25] or [(e["source"], e["target"]) for e in edges[:25]]

    stats = {
        "files": len(nodes),
        "internal_edges": len(edges),
        "external_packages": len(external),
        "test_files": test_files,
        "cycles": len(cycles),
        "languages": dict(lang_counts.most_common()),
        "most_depended": fan_in.most_common(10),
        "top_external": external.most_common(10),
        "orphans": orphans,
    }

    graph = {
        "version": "3.0",
        "project": os.path.basename(PROJECT_ROOT),
        "generated": datetime.now().isoformat(),
        "generator": "graphify-build",
        "stack": stack,
        "stats": {k: v for k, v in stats.items() if k != "orphans"},
        "orphan_count": len(orphans),
        "nodes": nodes,
        "edges": edges,
        "external": external.most_common(50),
        "note": "Edges are resolved to node ids. External packages are counted, not edged.",
    }
    json.dump(graph, open(os.path.join(OUTPUT_DIR, "knowledge-graph.json"), "w"), indent=2)

    write_project_index(stack, top_modules(files), stats,
                        os.path.join(PROJECT_ROOT, ".agent-spec", "PROJECT-INDEX.md"))
    write_graph_md(stack, stats, hot, cycles,
                   os.path.join(OUTPUT_DIR, "KNOWLEDGE-GRAPH.md"))

    if not args.quiet:
        resolved_pct = 100 * len(edges) / max(len(edges) + sum(external.values()), 1)
        print(f"Stack: {stack}")
        print(f"{len(nodes)} files, {len(edges)} internal edges "
              f"({resolved_pct:.0f}% of imports are internal), "
              f"{len(external)} external packages, {len(cycles)} cycles")


if __name__ == "__main__":
    main()
