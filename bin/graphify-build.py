#!/usr/bin/env python3
import os
import json
import re
from datetime import datetime

PROJECT_ROOT = os.getcwd()
OUTPUT_DIR = os.path.join(PROJECT_ROOT, ".agent-spec", "graph")

# Regex patterns for common import syntax
IMPORT_PATTERNS = [
    r'^import\s+[\'"]([^\'"]+)[\'"]',              # JS/TS/Go
    r'^from\s+([^\s]+)\s+import',                   # Python
    r'^import\s+([^\s]+)',                          # Python/Java
    r'require\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)',     # JS/Node
    r'^#include\s*[<"]([^>"]+)[>"]'                 # C/C++
]

EXCLUDE_DIRS = {'.git', 'node_modules', 'target', 'dist', 'build', 'venv', '.venv', '.idea', '__pycache__', '.agent-spec'}
ALLOWED_EXTS = {'.py', '.java', '.ts', '.js', '.go', '.cpp', '.c', '.h'}

def should_process(filepath):
    ext = os.path.splitext(filepath)[1]
    return ext in ALLOWED_EXTS

def extract_imports(filepath):
    imports = set()
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            for pattern in IMPORT_PATTERNS:
                matches = re.finditer(pattern, content, re.MULTILINE)
                for match in matches:
                    imports.add(match.group(1))
    except Exception:
        pass # Skip unreadable files
    return list(imports)

def build_graph():
    nodes = []
    edges = []
    
    stats = {"java_files": 0, "ts_files": 0, "test_files": 0, "py_files": 0, "go_files": 0}
    
    for root, dirs, files in os.walk(PROJECT_ROOT):
        # Exclude directories
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        
        for file in files:
            filepath = os.path.join(root, file)
            if not should_process(filepath):
                continue
                
            rel_path = os.path.relpath(filepath, PROJECT_ROOT)
            ext = os.path.splitext(file)[1]
            
            # Update stats
            if ext == '.java': stats['java_files'] += 1
            elif ext in ['.ts', '.js']: stats['ts_files'] += 1
            elif ext == '.py': stats['py_files'] += 1
            elif ext == '.go': stats['go_files'] += 1
            
            if 'test' in file.lower() or 'spec' in file.lower():
                stats['test_files'] += 1
                
            imports = extract_imports(filepath)
            
            nodes.append({
                "id": rel_path,
                "type": "file",
                "path": rel_path
            })
            
            for imp in imports:
                edges.append({
                    "source": rel_path,
                    "target": imp,
                    "type": "imports"
                })
                
    return nodes, edges, stats

if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    print("Building knowledge graph dependencies...")
    nodes, edges, stats = build_graph()
    
    graph_data = {
        "version": "2.0",
        "project": os.path.basename(PROJECT_ROOT),
        "generated": datetime.now().isoformat(),
        "generator": "graphify-build-automated",
        "stats": stats,
        "nodes": nodes,
        "edges": edges,
        "note": "Automatically populated via AST/Regex extraction."
    }
    
    out_file = os.path.join(OUTPUT_DIR, "knowledge-graph.json")
    with open(out_file, 'w') as f:
        json.dump(graph_data, f, indent=2)
        
    print(f"Graph built successfully. Found {len(nodes)} files and {len(edges)} dependencies.")
    print(f"Output saved to {out_file}")
