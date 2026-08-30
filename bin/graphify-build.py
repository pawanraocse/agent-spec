#!/usr/bin/env python3
"""Graphify — build the project knowledge graph.

Walks the source tree, extracts imports, and RESOLVES each import to a node in
the graph. Only resolved (internal) imports become edges; everything else is
recorded as an external dependency count. An edge whose target is not a node is
not a dependency the agent can traverse, and a graph full of `import json` is
noise that hides the real structure.
"""
import os
import sys
import re
import json
import argparse

# Cycle detection recurses to the depth of the longest import chain.
sys.setrecursionlimit(10000)
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


# Production limits. A real repository contains things that are technically source and
# are not worth indexing: a 4 MB bundle, a minified vendor file, a generated client. Each
# one costs parse time and adds an edge nobody will ever traverse.
MAX_FILE_BYTES = 1024 * 1024      # anything larger is generated, not written
MAX_FILES = 20000                 # past this, say so rather than silently taking a subset
SKIP_SUFFIXES = (".min.js", ".min.css", ".bundle.js", ".chunk.js", "_pb.py", ".pb.go",
                 ".g.dart", ".generated.ts", ".d.ts")


def gitignored_dirs():
    """Directory names .gitignore excludes, on top of the built-in list.

    Deliberately only simple directory patterns — `build/`, `generated`, `/out`. Full
    gitignore semantics (negation, globs, nesting) are not worth reimplementing here, and
    a wrong exclusion silently removes real code from the graph. Anything this does not
    catch still falls to EXCLUDE_DIRS or to the size limit.
    """
    out = set()
    path = os.path.join(PROJECT_ROOT, ".gitignore")
    try:
        lines = open(path, encoding="utf-8", errors="ignore").read().split("\n")
    except OSError:
        return out
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("!"):
            continue
        if any(c in line for c in "*?[]"):
            continue
        name = line.strip("/")
        if name and "/" not in name:
            out.add(name)
    return out


def collect_files():
    excluded = EXCLUDE_DIRS | gitignored_dirs()
    files, skipped_big, truncated = [], 0, False
    seen_dirs = set()
    for root, dirs, names in os.walk(PROJECT_ROOT, followlinks=False):
        # A symlinked directory pointing back up the tree walks forever.
        real = os.path.realpath(root)
        if real in seen_dirs:
            dirs[:] = []
            continue
        seen_dirs.add(real)

        dirs[:] = [d for d in dirs if d not in excluded and not d.startswith('.')]
        for name in names:
            ext = os.path.splitext(name)[1]
            if ext not in ALLOWED_EXTS or name.endswith(SKIP_SUFFIXES):
                continue
            full = os.path.join(root, name)
            try:
                if os.path.getsize(full) > MAX_FILE_BYTES:
                    skipped_big += 1
                    continue
            except OSError:
                continue
            rel = os.path.relpath(full, PROJECT_ROOT)
            files.append(rel.replace(os.sep, "/"))
            if len(files) >= MAX_FILES:
                truncated = True
                break
        if truncated:
            break
    if skipped_big:
        print("skipped %d files over %d KB (generated, not written)"
              % (skipped_big, MAX_FILE_BYTES // 1024), file=sys.stderr)
    if truncated:
        print("! stopped at %d files. The graph covers a subset — raise MAX_FILES or "
              "narrow the tree before trusting a blast-radius answer." % MAX_FILES,
              file=sys.stderr)
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


# ---------------------------------------------------------------------------
# Layers
#
# An import graph answers "who calls whom". It cannot answer "should it". Layer
# classification is what turns the graph into an architecture check: once every
# node has a layer, a controller reaching straight into a repository is a fact
# the graph can state, not a judgement someone has to make by reading code.
#
# Classification is by path and filename, in that order, because both are how
# every convention in the wild actually marks a layer. It is a heuristic; the
# graph records it as `layer` and never fails a build on it.
# ---------------------------------------------------------------------------
LAYER_HINTS = [
    ("controller", ("controller", "controllers", "resource", "resources", "handler",
                    "handlers", "route", "routes", "router", "endpoint", "endpoints",
                    "/api/", "views", "rest")),
    ("service",    ("service", "services", "usecase", "usecases", "interactor",
                    "domain", "business", "logic", "manager")),
    ("data",       ("repository", "repositories", "repo", "dao", "mapper", "mappers",
                    "entity", "entities", "model", "models", "schema", "schemas",
                    "migration", "migrations", "store", "persistence")),
    ("integration",("client", "clients", "gateway", "gateways", "adapter", "adapters",
                    "integration", "external", "provider", "connector")),
    ("contract",   ("dto", "dtos", "contract", "contracts", "proto", "protos",
                    "types", "interface", "interfaces", "payload")),
    ("config",     ("config", "configuration", "settings", "wiring", "bootstrap")),
    ("util",       ("util", "utils", "helper", "helpers", "common", "shared", "lib")),
]

# What each layer is permitted to depend on. Anything else is reported.
LAYER_ALLOWED = {
    "controller":  {"service", "contract", "util", "config", "integration", "unknown"},
    "service":     {"data", "integration", "contract", "util", "config", "service", "unknown"},
    "data":        {"contract", "util", "config", "data", "unknown"},
    "integration": {"contract", "util", "config", "unknown"},
    "contract":    {"contract", "util", "unknown"},
    "util":        {"util", "contract", "config", "unknown"},
    "config":      {"controller", "service", "data", "integration", "contract", "util",
                    "config", "unknown"},
    "test":        set(),          # tests may depend on anything
    "unknown":     set(),
}


def classify_layer(rel, is_test):
    if is_test:
        return "test"
    lowered = "/" + rel.lower()
    for layer, hints in LAYER_HINTS:
        for hint in hints:
            if hint.startswith("/"):
                if hint in lowered:
                    return layer
            elif ("/" + hint + "/") in lowered or ("/" + hint + ".") in lowered:
                return layer
    stem = os.path.splitext(os.path.basename(rel))[0].lower()
    for layer, hints in LAYER_HINTS:
        if any(stem.endswith(h.rstrip("s")) or stem.endswith(h) for h in hints if "/" not in h):
            return layer
    return "unknown"


def layer_violations(edges, layer_of, limit=50):
    """Edges that point the wrong way through the layer stack."""
    out = []
    for e in edges:
        if e.get("type") != "imports":
            continue
        src, dst = layer_of.get(e["source"], "unknown"), layer_of.get(e["target"], "unknown")
        if src in ("test", "unknown") or dst == "unknown":
            continue
        allowed = LAYER_ALLOWED.get(src)
        if allowed and dst not in allowed and dst != src:
            out.append({"source": e["source"], "target": e["target"],
                        "from_layer": src, "to_layer": dst})
        if len(out) >= limit:
            break
    return out


# ---------------------------------------------------------------------------
# Services
#
# A manifest below the repository root marks a deployable unit. Without this the
# graph flattens a twelve-service monorepo into one blob, and "which services does
# this change touch" — the first question anyone asks about a microservice estate —
# has no answer.
# ---------------------------------------------------------------------------
SERVICE_MANIFESTS = ("pom.xml", "build.gradle", "build.gradle.kts", "package.json",
                     "go.mod", "Cargo.toml", "pyproject.toml", "requirements.txt",
                     "composer.json", "Gemfile")


def detect_services():
    """Directory -> service name, for every manifest at depth 1..3 below the root."""
    roots = {}
    for root, dirs, names in os.walk(PROJECT_ROOT):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith(".")]
        rel = os.path.relpath(root, PROJECT_ROOT).replace(os.sep, "/")
        if rel == ".":
            rel = ""
        if rel.count("/") >= 3:
            dirs[:] = []
            continue
        if any(m in names for m in SERVICE_MANIFESTS):
            roots[rel] = os.path.basename(root) if rel else os.path.basename(PROJECT_ROOT)
    return roots


def service_of(rel, service_roots):
    """Longest matching service root owns the file."""
    best, name = -1, None
    for root, svc in service_roots.items():
        if root == "" or rel.startswith(root + "/"):
            if len(root) > best:
                best, name = len(root), svc
    return name


# ---------------------------------------------------------------------------
# Wire signals
#
# Two services that talk over HTTP or a broker share no import, so the import
# graph shows them as unrelated. These patterns recover the edges that actually
# carry the traffic: what each file serves, what it calls, and what it publishes
# or consumes.
# ---------------------------------------------------------------------------
ENDPOINT_PATTERNS = [
    r'@(?:Get|Post|Put|Delete|Patch|Request)Mapping\s*\(\s*(?:(?:value|path)\s*=\s*)?["\']([^"\']*)',
    r'@(?:Get|Post|Put|Delete|Patch)\s*\(\s*["\']([^"\']*)',          # NestJS
    r'@(?:app|router|api)\.(?:get|post|put|delete|patch|route)\s*\(\s*["\']([^"\']+)',
    r'(?:app|router)\.(?:get|post|put|delete|patch|use)\s*\(\s*["\']([/][^"\']*)',
    r'(?:mux|r|http)\.HandleFunc\s*\(\s*["\']([^"\']+)',
]

HTTP_CALL_PATTERNS = [
    r'@FeignClient\s*\(\s*(?:name\s*=\s*)?["\']([^"\']+)',
    r'["\'](https?://[\w.\-]+(?::\d+)?)[/"\']',
    r'(?:restTemplate|webClient|httpClient|http)\.\s*(?:get|post|put|delete|exchange|patch)',
    r'(?:axios|fetch|requests|httpx)\s*\.?\s*(?:get|post|put|delete|patch)?\s*\(',
]

TOPIC_PRODUCE_PATTERNS = [
    r'kafkaTemplate\.send\s*\(\s*["\']([^"\']+)',
    r'(?:producer|publisher)\.(?:send|publish)\s*\(\s*\{?\s*(?:topic\s*:\s*)?["\']([^"\']+)',
    r'rabbitTemplate\.convertAndSend\s*\(\s*["\']([^"\']+)',
    r'(?:sns|sqs)\.(?:publish|send_message)\s*\(',
]

TOPIC_CONSUME_PATTERNS = [
    r'@KafkaListener\s*\([^)]*topics\s*=\s*[{\s]*["\']([^"\']+)',
    r'@RabbitListener\s*\([^)]*queues\s*=\s*[{\s]*["\']([^"\']+)',
    r'@SqsListener\s*\(\s*["\']([^"\']+)',
    r'consumer\.subscribe\s*\(\s*\[?\s*\{?\s*(?:topic\s*:\s*)?["\']([^"\']+)',
]


def extract_signals(content):
    """Endpoints served, hosts called, topics produced and consumed."""
    def hits(patterns):
        out = set()
        for pattern in patterns:
            for m in re.finditer(pattern, content):
                token = (m.group(1).strip() if m.lastindex else "")
                if token:
                    out.add(token[:120])
        return sorted(out)

    calls = set(hits(HTTP_CALL_PATTERNS))
    # A bare client call with no literal URL still proves this file talks outward.
    if not calls and re.search(r'(restTemplate|webClient|axios\.|requests\.(get|post)|fetch\()', content):
        calls.add("[dynamic]")

    return {
        "endpoints": hits(ENDPOINT_PATTERNS),
        "calls": sorted(calls),
        "produces": hits(TOPIC_PRODUCE_PATTERNS),
        "consumes": hits(TOPIC_CONSUME_PATTERNS),
    }


def wire_edges(file_signals, service_by_file, service_roots):
    """Integration edges the import graph cannot see.

    Topic edges are real: a producer and a consumer naming the same topic string
    are connected whether or not they share a line of code. HTTP edges are only
    emitted when the called host matches a known service name, because a URL to a
    third-party API is a dependency on someone else's system, not an internal edge.
    """
    edges, topics = [], defaultdict(lambda: {"producers": [], "consumers": []})
    names = {name.lower(): name for name in service_roots.values()}

    for rel, sig in file_signals.items():
        for topic in sig["produces"]:
            topics[topic]["producers"].append(rel)
        for topic in sig["consumes"]:
            topics[topic]["consumers"].append(rel)
        for call in sig["calls"]:
            host = call.split("//")[-1].split(":")[0].split("/")[0].lower()
            for candidate in (call.lower(), host):
                if candidate in names and names[candidate] != service_by_file.get(rel):
                    edges.append({"source": rel, "target": names[candidate],
                                  "type": "http", "detail": call})
                    break

    for topic, ends in sorted(topics.items()):
        for producer in ends["producers"]:
            for consumer in ends["consumers"]:
                edges.append({"source": producer, "target": consumer,
                              "type": "message", "detail": topic})
    return edges, topics


# ---------------------------------------------------------------------------
# Incremental cache
#
# A full walk on every run is fine at 200 files and painful at 20,000. Files are
# re-parsed only when mtime or size moved; anything else is served from the cache.
# The cache is keyed by the parser version, so changing a pattern above
# invalidates every entry rather than silently serving stale extractions.
# ---------------------------------------------------------------------------
PARSER_VERSION = "4.0"
CACHE_PATH = os.path.join(OUTPUT_DIR, ".cache.json")


def load_cache(rebuild):
    if rebuild:
        return {}
    try:
        with open(CACHE_PATH, encoding="utf-8") as fh:
            cache = json.load(fh)
    except (OSError, ValueError):
        return {}
    if cache.get("parser") != PARSER_VERSION:
        return {}
    return cache.get("files", {})


def save_cache(entries):
    try:
        with open(CACHE_PATH, "w", encoding="utf-8") as fh:
            json.dump({"parser": PARSER_VERSION, "files": entries}, fh)
    except OSError:
        pass


def parse_file(rel, cache):
    """Imports plus wire signals for one file, from cache when it has not changed."""
    full = os.path.join(PROJECT_ROOT, rel)
    try:
        st = os.stat(full)
        stamp = [int(st.st_mtime), st.st_size]
    except OSError:
        stamp = [0, 0]

    hit = cache.get(rel)
    if hit and hit.get("stamp") == stamp:
        return hit, False

    try:
        content = open(full, "r", encoding="utf-8", errors="ignore").read()
    except OSError:
        content = ""

    imports = set()
    for pattern in IMPORT_PATTERNS:
        for m in re.finditer(pattern, content, re.MULTILINE):
            token = m.group(1).strip()
            if token:
                imports.add(token)

    entry = {"stamp": stamp, "imports": sorted(imports), "signals": extract_signals(content)}
    return entry, True


# ---------------------------------------------------------------------------
# Conventions
#
# The constitution used to be written from whatever the agent happened to read.
# Counting the markers across the whole tree is both cheaper and more honest: a
# convention is what most of the code does, not what the one file someone opened
# happened to do.
# ---------------------------------------------------------------------------
CONVENTION_PROBES = [
    ("test framework",     [("pytest", r'\bimport pytest|\bdef test_'), ("JUnit 5", r'org\.junit\.jupiter'),
                            ("JUnit 4", r'org\.junit\.Test'), ("Jest", r'\bdescribe\(|\bit\('),
                            ("Vitest", r'from [\'"]vitest'), ("Go testing", r'func Test\w+\(t \*testing')]),
    ("dependency injection",[("Spring annotations", r'@Autowired|@Component|@Service\b'),
                            ("constructor injection", r'constructor\s*\('), ("manual wiring", r'')]),
    ("error handling",     [("custom exception types", r'class \w*(Exception|Error)\b'),
                            ("Result/Either", r'\bResult<|\bEither<'), ("errors.New", r'errors\.New\(')]),
    ("typing",             [("type hints", r'def \w+\([^)]*:\s*\w+'), ("TypeScript", r'interface \w+\s*\{'),
                            ("generics", r'<[A-Z]\w*>')]),
    ("logging",            [("SLF4J", r'LoggerFactory\.getLogger'), ("Python logging", r'logging\.getLogger'),
                            ("console", r'console\.(log|error)')]),
]


def detect_conventions(files, sample=60):
    """Count marker hits across a sample; report only what the code actually shows."""
    picked = files[:sample] if len(files) <= sample else files[::max(1, len(files) // sample)][:sample]
    blobs = []
    for rel in picked:
        try:
            blobs.append(open(os.path.join(PROJECT_ROOT, rel), encoding="utf-8", errors="ignore").read())
        except OSError:
            pass
    joined = "\n".join(blobs)
    out = {}
    for topic, probes in CONVENTION_PROBES:
        scored = [(name, len(re.findall(pattern, joined))) for name, pattern in probes if pattern]
        scored = [s for s in scored if s[1] > 0]
        if scored:
            scored.sort(key=lambda x: -x[1])
            out[topic] = scored[:2]
    return out


def write_conventions(conventions, services, endpoints, violations, path):
    def rows(items):
        return "\n".join("| %s | %s | %d occurrences |" % (topic, name, count)
                         for topic, scored in items.items() for name, count in scored) \
               or "| | [none detected] | |"

    content = """# Conventions

> Generated by Graphify on %s by counting markers across the source tree.
> These are observations, not rules. `/agent-spec-onboard` promotes the ones that are real
> into CONSTITUTION.md; delete anything here that is an accident of sampling.

## Observed conventions
| Topic | Convention | Evidence |
|-------|-----------|----------|
%s

## Services
%s

## HTTP surface
%s

## Layer violations
%s
""" % (
        datetime.now().strftime("%Y-%m-%d"),
        rows(conventions),
        "\n".join("- `%s/` → **%s**" % (root or ".", name) for root, name in sorted(services.items()))
            or "- single service",
        "\n".join("- `%s` — %s" % (rel, ", ".join(eps[:6])) for rel, eps in endpoints[:20])
            or "- none detected",
        "\n".join("- `%s` (%s) → `%s` (%s)" % (v["source"], v["from_layer"], v["target"], v["to_layer"])
                  for v in violations[:20]) or "- none",
    )
    open(path, "w", encoding="utf-8").write(content)
    print("Wrote CONVENTIONS.md")


def write_project_index(stack, modules, stats, path):
    rows = "".join(
        f"| `{mod}/` | [TODO] | `{mod}` | {count} files |\n"
        for mod, count in modules.most_common(25)
    ) or "| | [TODO: no modules auto-detected] | | |\n"
    date_str = datetime.now().strftime("%Y-%m-%d")
    content = f"""# Project Index

> Generated by Graphify on {date_str}. Run `/agent-spec-onboard` to fill the [TODO] entries
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
**Services**: {stats['services']} · **Integration edges**: {stats['integration_edges']} · **Endpoints**: {stats['endpoints']} · **Topics**: {stats['topics']} · **Layer violations**: {stats['layer_violations']}

## Layers
{chr(10).join(f'- **{name}** — {count} files' for name, count in stats['layers'].items()) or '- unclassified'}

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
    parser.add_argument("--rebuild", action="store_true",
                        help="Ignore the incremental cache and re-parse every file")
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    stack = detect_stack()
    files = collect_files()
    by_path, by_dotted = build_index(files)
    service_roots = detect_services()
    cache = load_cache(args.rebuild)

    nodes, edges = [], []
    external = Counter()
    lang_counts = Counter()
    test_files = 0
    reparsed = 0
    adjacency = defaultdict(set)
    layer_of, service_by_file, file_signals, fresh_cache = {}, {}, {}, {}
    endpoint_index = []

    for rel in files:
        ext = os.path.splitext(rel)[1]
        lang_counts[LANG_BY_EXT.get(ext, "other")] += 1
        lowered = rel.lower()
        is_test = any(h in lowered for h in TEST_HINTS)
        if is_test:
            test_files += 1

        entry, was_parsed = parse_file(rel, cache)
        fresh_cache[rel] = entry
        reparsed += 1 if was_parsed else 0
        signals = entry["signals"]
        file_signals[rel] = signals

        layer = classify_layer(rel, is_test)
        service = service_of(rel, service_roots)
        layer_of[rel] = layer
        service_by_file[rel] = service
        if signals["endpoints"]:
            endpoint_index.append((rel, signals["endpoints"]))

        nodes.append({"id": rel, "type": "test" if is_test else "file",
                      "path": rel, "lang": LANG_BY_EXT.get(ext, "other"),
                      "layer": layer, "service": service,
                      "endpoints": signals["endpoints"],
                      "produces": signals["produces"],
                      "consumes": signals["consumes"]})

        for token in entry["imports"]:
            target = resolve(token, rel, by_path, by_dotted)
            if target:
                edges.append({"source": rel, "target": target, "type": "imports"})
                adjacency[rel].add(target)
            else:
                external[token.split(".")[0].split("/")[0]] += 1

    save_cache(fresh_cache)

    integration_edges, topics = wire_edges(file_signals, service_by_file, service_roots)
    edges.extend(integration_edges)
    violations = layer_violations(edges, layer_of)

    fan_in = Counter(e["target"] for e in edges if e["type"] == "imports")
    fan_out = Counter(e["source"] for e in edges if e["type"] == "imports")
    connected = set(fan_in) | set(fan_out)
    orphans = [f for f in files if f not in connected]
    cycles = find_cycles(adjacency)
    import_edges = [e for e in edges if e["type"] == "imports"]
    hot = [(e["source"], e["target"]) for e in import_edges
           if fan_in[e["target"]] >= 2][:25] or [(e["source"], e["target"]) for e in import_edges[:25]]

    stats = {
        "files": len(nodes),
        "internal_edges": len(import_edges),
        "integration_edges": len(integration_edges),
        "external_packages": len(external),
        "test_files": test_files,
        "cycles": len(cycles),
        "services": len(set(service_roots.values())),
        "endpoints": sum(len(e) for _, e in endpoint_index),
        "topics": len(topics),
        "layer_violations": len(violations),
        "languages": dict(lang_counts.most_common()),
        "layers": dict(Counter(layer_of.values()).most_common()),
        "most_depended": fan_in.most_common(10),
        "top_external": external.most_common(10),
        "orphans": orphans,
    }

    conventions = detect_conventions(files)

    graph = {
        "version": "4.0",
        "project": os.path.basename(PROJECT_ROOT),
        "generated": datetime.now().isoformat(),
        "generator": "graphify-build",
        "stack": stack,
        "stats": {k: v for k, v in stats.items() if k != "orphans"},
        "orphan_count": len(orphans),
        "services": service_roots,
        "layer_violations": violations,
        "topics": {t: ends for t, ends in sorted(topics.items())},
        "conventions": conventions,
        "nodes": nodes,
        "edges": edges,
        "external": external.most_common(50),
        "note": ("Edges are resolved to node ids. type=imports is a source dependency; "
                 "type=http and type=message are integration edges recovered from call "
                 "and broker signals, which no import graph can see."),
    }
    with open(os.path.join(OUTPUT_DIR, "knowledge-graph.json"), "w", encoding="utf-8") as fh:
        json.dump(graph, fh, indent=2)

    write_project_index(stack, top_modules(files), stats,
                        os.path.join(PROJECT_ROOT, ".agent-spec", "PROJECT-INDEX.md"))
    write_graph_md(stack, stats, hot, cycles,
                   os.path.join(OUTPUT_DIR, "KNOWLEDGE-GRAPH.md"))
    write_conventions(conventions, service_roots, endpoint_index, violations,
                      os.path.join(OUTPUT_DIR, "CONVENTIONS.md"))

    if not args.quiet:
        resolved_pct = 100 * len(import_edges) / max(len(import_edges) + sum(external.values()), 1)
        print("Stack: %s" % stack)
        print("%d files (%d re-parsed), %d internal edges (%.0f%% of imports are internal), "
              "%d external packages, %d cycles"
              % (len(nodes), reparsed, len(import_edges), resolved_pct, len(external), len(cycles)))
        print("%d services, %d integration edges, %d endpoints, %d topics, %d layer violations"
              % (stats["services"], len(integration_edges), stats["endpoints"],
                 stats["topics"], len(violations)))


if __name__ == "__main__":
    main()
