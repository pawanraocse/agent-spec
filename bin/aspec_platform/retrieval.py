"""Local project intelligence: incremental index + hybrid retrieval (DEC-17, PI-001..PI-004).

Allowed-code reasons (DEC-15): *plumbing* (an index the dashboard, the CLI and the
`agent-spec-ask` skill share) and *exact* (hashing, chunking, BM25, rank fusion). Nothing here
judges or summarises; answers are written by a model, and labelled as such.

Sources, each a `kind`:
  code     tracked source files (git ls-files, else a bounded walk)
  doc      Markdown/text docs, including .agent-spec/ artifacts (SDLC, constitution, snapshot)
  rule     always-on and on-demand instructions: CURSOR.md, AGENTS.md, .cursor/rules, SKILL.md
  memory   remembered facts (.agent-spec/memory/facts, team-facts)
  request  one Cursor request trace: prompt, skills, tools, edited files, responses
  review   AI session reviews (.agent-spec/metrics/reviews/*.json)

Retrieval is BM25 over title + body + split identifiers. When a local embedding provider is
configured (`AGENT_SPEC_EMBED=ollama:<model>`), cosine similarity over stored vectors is fused
with BM25 by reciprocal rank (RRF). Without one, results say `mode: keyword` — no semantic
claim is made. Providers must be loopback unless `AGENT_SPEC_ALLOW_REMOTE_MODELS=1`, so
project source never leaves the machine by default.
"""
from __future__ import annotations

import array
import fnmatch
import json
import math
import os
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request

from . import common, ollama, redact

# ---- configuration --------------------------------------------------------------------------

KINDS = ("code", "doc", "rule", "memory", "request", "review")
MAX_FILE_BYTES = 256 * 1024
MAX_FILES = 20000
CHUNK_MIN, CHUNK_MAX = 40, 80          # lines; split at a boundary once past MIN, always at MAX
REQUEST_BODY_CHARS = 6000
EMBED_BATCH = 32
EMBED_PER_PASS = 512                   # background passes catch up; one pass never stalls
RRF_K = 60

TEXT_EXT = {
    ".py", ".pyi", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".java", ".kt", ".kts", ".go", ".rs",
    ".rb", ".php", ".cs", ".c", ".h", ".cc", ".cpp", ".hpp", ".swift", ".scala", ".sh", ".bash", ".ps1",
    ".sql", ".graphql", ".proto", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".json", ".css", ".scss",
    ".html", ".vue", ".svelte", ".tf", ".gradle", ".xml",
}
DOC_EXT = {".md", ".mdx", ".mdc", ".rst", ".txt", ".adoc"}
SKIP_DIRS = {".git", "node_modules", "dist", "build", "out", "target", ".venv", "venv", "__pycache__",
             ".next", ".cache", ".pytest_cache", ".mypy_cache", "coverage", ".idea", ".vscode"}
# .agent-spec/ holds derived and private data; only its Markdown artifacts are indexed.
AGENT_SPEC_SKIP = ("platform/", "metrics/", "bin/", "graph/knowledge-graph.json", "cache/")
# Secret-shaped paths are never read (mirrors the preToolUse quarantine; core and platform do
# not import each other, so the list is restated here).
SECRET_GLOBS = (".env", ".env.*", "*.pem", "*.key", "*.p12", "*.pfx", "id_rsa*", "id_ed25519*",
                "credentials*", "*.keystore", "*secret*.json", ".npmrc", ".pypirc", ".netrc")
LOCKFILES = ("package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "Cargo.lock", "go.sum")

BOUNDARY = re.compile(r"^(?:\s{0,4})(?:async\s+def |def |class |export |function |interface |type |"
                      r"public |private |protected |func |fn |impl |struct |module |describe\(|it\(|test\()")
HEADING = re.compile(r"^(#{1,4})\s+(.+?)\s*#*\s*$")
SYMBOL = re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?(?:def|class|function|interface|type|func|fn|struct)\s+([A-Za-z_][\w]*)")
WORD = re.compile(r"[A-Za-z0-9_]+")
CAMEL = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+")
STOP = {"a", "an", "and", "are", "as", "at", "be", "by", "can", "did", "do", "does", "for", "from", "how",
        "i", "in", "is", "it", "me", "my", "of", "on", "or", "our", "should", "that", "the", "this", "to",
        "was", "we", "were", "what", "when", "where", "which", "who", "why", "will", "with", "you"}


def _rel(project: str, path: str) -> str:
    return os.path.relpath(path, project).replace(os.sep, "/")


def is_secret_path(rel: str) -> bool:
    base = rel.rsplit("/", 1)[-1].lower()
    return any(fnmatch.fnmatch(base, g) for g in SECRET_GLOBS)


def classify(rel: str) -> str | None:
    """Kind for a project-relative path, or None when the file is not indexed."""
    low = rel.lower()
    base = low.rsplit("/", 1)[-1]
    ext = os.path.splitext(base)[1]
    if is_secret_path(rel) or base in (x.lower() for x in LOCKFILES) or base.endswith(".min.js"):
        return None
    if low.startswith(".agent-spec/"):
        inner = low[len(".agent-spec/"):]
        if any(inner.startswith(p) for p in AGENT_SPEC_SKIP) or ext not in DOC_EXT:
            return None
        if inner.startswith("memory/facts/") or inner.startswith("team-facts/"):
            return "memory"
        return "doc"
    if base in ("cursor.md", "agents.md", "claude.md") or low.startswith(".cursor/rules/") or base == "skill.md":
        return "rule"
    if ext in DOC_EXT:
        return "doc"
    if ext in TEXT_EXT:
        return "code"
    return None


def split_terms(text: str, limit: int = 4000) -> str:
    """`buildFromEvents build_from_events` -> `build from events build from events`, so a
    question in plain words matches identifiers. Only identifiers that actually split are kept."""
    out = []
    for w in WORD.findall(text[:200000]):
        parts = [p.lower() for chunk in w.split("_") for p in CAMEL.findall(chunk)]
        if len(parts) > 1:
            out.extend(parts)
        if len(out) >= limit:
            break
    return " ".join(out)


# ---- collectors -----------------------------------------------------------------------------

def _git_files(project: str):
    try:
        out = subprocess.run(["git", "-C", project, "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                             capture_output=True, timeout=20, check=True).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    return [p for p in out.decode("utf-8", "replace").split("\0") if p]


def _walk_files(root: str, project: str):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".") or d in (".cursor", ".agent-spec")]
        for name in filenames:
            yield _rel(project, os.path.join(dirpath, name))


def project_files(project: str) -> list:
    """Indexable project-relative paths: git's view of the tree (respects .gitignore) plus the
    .agent-spec/ Markdown artifacts, which are often gitignored but are the project's memory."""
    files = _git_files(project)
    if files is None:
        files = list(_walk_files(project, project))
    spec = os.path.join(project, ".agent-spec")
    if os.path.isdir(spec):
        files.extend(_walk_files(spec, project))
    seen, keep = set(), []
    for rel in files:
        rel = rel.replace(os.sep, "/")
        if rel in seen or any(part in SKIP_DIRS for part in rel.split("/")[:-1]):
            continue
        seen.add(rel)
        if classify(rel):
            keep.append(rel)
        if len(keep) >= MAX_FILES:
            break
    return sorted(keep)


def chunk_lines(lines: list, markdown: bool) -> list:
    """[(start_line, end_line, title)] covering `lines`; 1-based inclusive line numbers."""
    spans, start, heading = [], 0, ""
    path_titles = []

    def close(end, title):
        if end > start:
            spans.append((start + 1, end, title))

    for i, line in enumerate(lines):
        size = i - start
        if markdown:
            m = HEADING.match(line)
            if m:
                close(i, heading)
                start = i
                level = len(m.group(1))
                path_titles[:] = path_titles[:level - 1] + [m.group(2).strip()]
                heading = " › ".join(path_titles)
                continue
            if size >= CHUNK_MAX:
                close(i, heading)
                start = i
        elif size >= CHUNK_MAX or (size >= CHUNK_MIN and BOUNDARY.match(line)):
            close(i, heading)
            start = i
    close(len(lines), heading)
    return spans


def _file_docs(project: str, rel: str, kind: str):
    path = os.path.join(project, rel)
    with open(path, "rb") as fh:
        raw = fh.read(MAX_FILE_BYTES + 1)
    if len(raw) > MAX_FILE_BYTES or b"\0" in raw[:4096]:
        return raw, []
    text = raw.decode("utf-8", "replace")
    lines = text.splitlines()
    markdown = os.path.splitext(rel)[1].lower() in DOC_EXT
    docs = []
    for start, end, heading in chunk_lines(lines, markdown):
        body = "\n".join(lines[start - 1:end]).strip()
        if not body:
            continue
        sym = ""
        if not markdown:
            for ln in lines[start - 1:end]:
                m = SYMBOL.match(ln)
                if m:
                    sym = m.group(1)
                    break
        title = rel + (" — " + heading if heading else "") + (" · " + sym if sym else "")
        docs.append({"ref": "%s:%d-%d" % (rel, start, end), "title": title, "start_line": start, "end_line": end,
                     "body": redact.redact(body), "terms": split_terms(rel + " " + body)})
    return raw, docs


def _trace_doc(t: dict, spans: list) -> dict:
    """One retrievable passage per request: what was asked, which skills/tools ran, which files
    changed, what failed and what the agent answered."""
    tools, edits, errors, answers, subs = [], [], [], [], []
    for s in spans:
        a = s.get("attributes") or {}
        if s["kind"] == "edit":
            edits.append(a.get("file_path") or a.get("target") or s.get("name") or "")
        elif s["kind"] == "tool":
            tools.append("%s %s" % (s.get("name") or "", (a.get("target") or "")[:120]))
        elif s["kind"] == "subagent":
            subs.append("%s: %s" % (s.get("name"), (a.get("task") or a.get("description") or "")[:200]))
        elif s["kind"] == "response" and a.get("text"):
            answers.append(str(a["text"]))
        if s.get("status") in ("error", "failed", "blocked"):
            errors.append("%s %s %s" % (s["kind"], s.get("name") or "", (a.get("error_message") or a.get("target") or "")[:160]))
    parts = ["Prompt: %s" % (t.get("prompt") or "(not recorded)"),
             "Status: %s · model %s · source %s" % (t.get("status"), t.get("model") or "unknown", t.get("source"))]
    if t.get("skills"):
        parts.append("Skills: " + ", ".join(t["skills"]))
    if subs:
        parts.append("Subagents: " + "; ".join(subs[:10]))
    if edits:
        parts.append("Files changed: " + ", ".join(dict.fromkeys(e for e in edits if e)))
    if tools:
        parts.append("Tools: " + "; ".join(tools[:40]))
    if errors:
        parts.append("Failures: " + "; ".join(errors[:20]))
    if answers:
        parts.append("Response: " + "\n".join(answers))
    body = redact.redact("\n".join(parts))[:REQUEST_BODY_CHARS]
    title = (t.get("prompt") or "request %s" % t["trace_id"]).strip().splitlines()[0][:140] if (t.get("prompt") or "").strip() else "request %s" % t["trace_id"]
    return {"ref": t["trace_id"], "title": title, "start_line": None, "end_line": None, "body": body,
            "terms": split_terms(" ".join(edits + tools)), "session_id": t.get("session_id"), "ts": t.get("start")}


def _review_docs(path: str, review: dict) -> list:
    parts = ["Grade %s. %s" % (review.get("grade") or "?", review.get("summary") or "")]
    for f in review.get("findings") or []:
        if isinstance(f, dict):
            parts.append("[%s/%s] %s — %s (span %s)" % (f.get("category"), f.get("severity"), f.get("title"),
                                                        f.get("detail"), f.get("span_id")))
    for p in review.get("pros") or []:
        if isinstance(p, dict):
            parts.append("Good: %s (span %s)" % (p.get("text"), p.get("span_id")))
    cid = review.get("conversation_id") or os.path.basename(path)[:-5]
    return [{"ref": cid, "title": "Session review %s" % cid, "start_line": None, "end_line": None,
             "body": redact.redact("\n".join(parts))[:REQUEST_BODY_CHARS], "terms": "",
             "session_id": cid, "ts": review.get("session_started") or review.get("reviewed_at")}]


# ---- index writer ---------------------------------------------------------------------------

def _known(conn, kind_filter):
    q = "SELECT kind, source, stamp, sha FROM index_sources"
    return {(r["kind"], r["source"]): (r["stamp"], r["sha"]) for r in conn.execute(q) if kind_filter(r["kind"])}


def _replace(conn, kind, source, stamp, sha, docs, now, default_ts=None):
    conn.execute("DELETE FROM chunks WHERE kind = ? AND source = ?", (kind, source))
    conn.executemany(
        "INSERT INTO chunks (kind, source, ref, title, start_line, end_line, session_id, ts, body, terms) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        [(kind, source, d["ref"], d["title"], d.get("start_line"), d.get("end_line"), d.get("session_id"),
          d.get("ts") or default_ts, d["body"], d.get("terms") or "") for d in docs])
    conn.execute("INSERT OR REPLACE INTO index_sources (kind, source, stamp, sha, chunks, indexed_at) VALUES (?,?,?,?,?,?)",
                 (kind, source, stamp, sha, len(docs), now))


def _drop(conn, kind, source):
    conn.execute("DELETE FROM chunks WHERE kind = ? AND source = ?", (kind, source))
    conn.execute("DELETE FROM index_sources WHERE kind = ? AND source = ?", (kind, source))


def index_files(conn, project: str, stats: dict, now: str) -> None:
    known = _known(conn, lambda k: k in ("code", "doc", "rule", "memory"))
    present = set()
    root = os.path.realpath(project)
    for rel in project_files(project):
        kind = classify(rel)
        path = os.path.join(project, rel)
        # A tracked symlink can point anywhere (~/.aws/credentials under a harmless name);
        # the secret-path check only sees the link's own name, so never follow it out.
        real = os.path.realpath(path)
        if (real != root and not real.startswith(root + os.sep)) or is_secret_path(_rel(root, real)):
            continue
        present.add((kind, rel))
        try:
            st = os.stat(path)
        except OSError:
            continue
        stamp = "%d:%d" % (st.st_mtime_ns, st.st_size)
        prev = known.get((kind, rel))
        if prev and prev[0] == stamp:
            stats["unchanged"] += 1
            continue
        try:
            raw, docs = _file_docs(project, rel, kind)
        except OSError:
            stats["errors"] += 1
            continue
        sha = common.sha256(raw)
        if prev and prev[1] == sha:
            conn.execute("UPDATE index_sources SET stamp = ? WHERE kind = ? AND source = ?", (stamp, kind, rel))
            stats["unchanged"] += 1
            continue
        mtime = common.iso_from_epoch(st.st_mtime)
        _replace(conn, kind, rel, stamp, sha, docs, now, default_ts=mtime)
        stats["indexed"] += 1
        stats["chunks"] += len(docs)
    for key in set(known) - present:
        _drop(conn, *key)
        stats["removed"] += 1


def index_traces(conn, project: str, stats: dict, now: str) -> None:
    from . import traces as tr  # local import: traces imports handoffs, keep module load light
    known = _known(conn, lambda k: k == "request")
    try:
        all_t, all_s = tr.all_traces(project, conn)
    except Exception:  # noqa: BLE001 — an unreadable store must not stop file indexing
        stats["errors"] += 1
        return
    by_trace = {}
    for s in all_s:
        by_trace.setdefault(s["trace_id"], []).append(s)
    present = set()
    here = os.path.realpath(project)
    all_t = [t for t in all_t if t.get("origin") != "cli"]  # CLI probes are not the user's history
    for t in all_t:
        if t.get("source") == "demo_seed":
            continue
        # Project isolation: Cursor's store holds every workspace's chats. Only this project's
        # (hook and run traces come from this project's own files) are indexed.
        if t.get("source") not in ("hook", "run") and os.path.realpath(t.get("workspace") or "/nonexistent") != here:
            continue
        tid = t["trace_id"]
        present.add(("request", tid))
        spans = by_trace.get(tid, [])
        stamp = "%s:%s:%d:%s" % (t.get("end"), t.get("status"), len(spans), t.get("source"))
        prev = known.get(("request", tid))
        if prev and prev[0] == stamp:
            stats["unchanged"] += 1
            continue
        doc = _trace_doc(t, spans)
        _replace(conn, "request", tid, stamp, common.sha256(doc["body"]), [doc], now)
        stats["indexed"] += 1
        stats["chunks"] += 1
    for key in set(known) - present:
        _drop(conn, *key)
        stats["removed"] += 1


def index_reviews(conn, project: str, stats: dict, now: str) -> None:
    known = _known(conn, lambda k: k == "review")
    folder = os.path.join(common.agent_spec_dir(project), "metrics", "reviews")
    present = set()
    for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
        if not name.endswith(".json"):
            continue
        path = os.path.join(folder, name)
        rel = _rel(project, path)
        present.add(("review", rel))
        try:
            st = os.stat(path)
        except OSError:
            continue
        stamp = "%d:%d" % (st.st_mtime_ns, st.st_size)
        if known.get(("review", rel), ("",))[0] == stamp:
            stats["unchanged"] += 1
            continue
        review = common.read_json(path)
        if not isinstance(review, dict):
            stats["errors"] += 1
            continue
        _replace(conn, "review", rel, stamp, common.sha256(json.dumps(review, sort_keys=True)), _review_docs(path, review), now)
        stats["indexed"] += 1
        stats["chunks"] += 1
    for key in set(known) - present:
        _drop(conn, *key)
        stats["removed"] += 1


def ingest_index(conn, project: str) -> dict:
    """Incremental pass over every source; the `index` ingest source. Caller owns the transaction."""
    stats = {"indexed": 0, "unchanged": 0, "removed": 0, "chunks": 0, "embedded": 0, "errors": 0}
    now = common.utc_now()
    index_files(conn, project, stats, now)
    index_traces(conn, project, stats, now)
    index_reviews(conn, project, stats, now)
    embedder = get_embedder()
    if embedder:
        try:
            stats["embedded"] = embed_pending(conn, embedder)
        except EmbedError:
            stats["errors"] += 1
    conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('index:last', ?)",
                 (json.dumps({"ts": now, **stats, "embedder": embedder.name if embedder else None}),))
    return stats


# ---- embeddings (optional, local) ----------------------------------------------------------

class EmbedError(RuntimeError):
    pass


def _loopback(url: str) -> bool:
    """Loopback, or the Windows host from WSL (same machine); see ollama.is_local."""
    return ollama.is_local(url)


def _post_json(url: str, body: dict, timeout: float) -> dict:
    if not ollama.allowed(url):
        raise EmbedError("refusing non-loopback model endpoint %s (set AGENT_SPEC_ALLOW_REMOTE_MODELS=1 to allow)" % url)
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 — URL checked above
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise EmbedError("%s: %s" % (url, exc)) from exc


class OllamaEmbedder:
    """Ollama's `/api/embed` (local). Vectors are L2-normalised so similarity is a dot product."""

    # Models trained with task prefixes retrieve markedly worse without them (nomic-embed-text,
    # measured by `rag-eval`). The prefix is part of the vector space, so it is part of the name:
    # vectors written before prefixes existed are never mixed with prefixed queries.
    PREFIXES = {"nomic-embed": ("search_document: ", "search_query: ")}

    def __init__(self, model: str, url: str):
        self.model, self.url = model, url.rstrip("/")
        self.prefix = next((p for key, p in self.PREFIXES.items() if key in model), None)
        self.name = "ollama:" + model + ("#task-prefix" if self.prefix else "")

    def embed(self, texts: list, role: str = "document") -> list:
        if self.prefix:
            texts = [(self.prefix[1] if role == "query" else self.prefix[0]) + t for t in texts]
        data = _post_json(self.url + "/api/embed", {"model": self.model, "input": texts}, timeout=120)
        vecs = data.get("embeddings")
        if not isinstance(vecs, list) or len(vecs) != len(texts):
            raise EmbedError("unexpected /api/embed response")
        return [_normalise(v) for v in vecs]


def _normalise(v) -> list:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def ollama_url() -> str:
    return ollama.base_url()


def get_embedder():
    """`AGENT_SPEC_EMBED=ollama:<model>` -> embedder; unset or `none` -> None (keyword mode)."""
    spec = (os.environ.get("AGENT_SPEC_EMBED") or "").strip()
    if not spec or spec == "none":
        return None
    provider, _, model = spec.partition(":")
    if provider == "ollama" and model:
        return OllamaEmbedder(model, ollama_url())
    return None


def _pack(vec) -> bytes:
    return array.array("f", vec).tobytes()


def _unpack(blob: bytes) -> array.array:
    a = array.array("f")
    a.frombytes(blob)
    return a


def embed_pending(conn, embedder, limit: int = EMBED_PER_PASS) -> int:
    rows = conn.execute(
        "SELECT c.chunk_id, c.title, c.body FROM chunks c LEFT JOIN chunk_vectors v "
        "ON v.chunk_id = c.chunk_id AND v.model = ? WHERE v.chunk_id IS NULL LIMIT ?", (embedder.name, limit)).fetchall()
    done = 0
    for i in range(0, len(rows), EMBED_BATCH):
        batch = rows[i:i + EMBED_BATCH]
        vecs = embedder.embed([("%s\n%s" % (r["title"], r["body"]))[:4000] for r in batch])
        conn.executemany("INSERT OR REPLACE INTO chunk_vectors (chunk_id, model, dim, vec) VALUES (?,?,?,?)",
                         [(r["chunk_id"], embedder.name, len(v), _pack(v)) for r, v in zip(batch, vecs)])
        done += len(batch)
    return done


# ---- search ---------------------------------------------------------------------------------

def fts_query(q: str) -> str:
    """Free text -> an FTS5 OR query of quoted terms (identifiers also split), stopwords removed.
    Quoting every term means user input can never be parsed as FTS5 syntax."""
    terms = []
    for w in WORD.findall(q):
        low = w.lower()
        if low not in STOP and len(low) > 1:
            terms.append(low)
        parts = [p.lower() for chunk in w.split("_") for p in CAMEL.findall(chunk)]
        if len(parts) > 1:
            terms.extend(p for p in parts if p not in STOP and len(p) > 1)
    return " OR ".join('"%s"' % t.replace('"', "") for t in dict.fromkeys(terms))


def _where(filters: dict):
    clauses, args = [], []
    kinds = [k for k in (filters.get("kinds") or []) if k in KINDS]
    if kinds:
        clauses.append("c.kind IN (%s)" % ",".join("?" * len(kinds)))
        args.extend(kinds)
    if filters.get("path"):
        clauses.append("c.source LIKE ? ESCAPE '\\'")
        args.append(filters["path"].replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%")
    if filters.get("since"):
        clauses.append("c.ts >= ?")
        args.append(filters["since"])
    if filters.get("session"):
        clauses.append("c.session_id = ?")
        args.append(filters["session"])
    return (" AND " + " AND ".join(clauses)) if clauses else "", args


def _row(r, **extra) -> dict:
    d = {k: r[k] for k in ("chunk_id", "kind", "source", "ref", "title", "start_line", "end_line", "session_id", "ts")}
    d.update(extra)
    return d


def keyword_hits(conn, q: str, filters: dict, limit: int) -> list:
    match = fts_query(q)
    if not match:
        return []
    where, args = _where(filters)
    sql = ("SELECT c.*, bm25(chunks_fts, 4.0, 1.0, 1.5) AS score, "
           "snippet(chunks_fts, 1, '[[', ']]', ' … ', 24) AS snip FROM chunks_fts "
           "JOIN chunks c ON c.chunk_id = chunks_fts.rowid WHERE chunks_fts MATCH ?%s "
           "ORDER BY score LIMIT ?" % where)
    try:
        rows = conn.execute(sql, [match] + args + [limit]).fetchall()
    except Exception:  # noqa: BLE001 — a missing index (pre-v4 DB) reads as no hits
        return []
    return [_row(r, snippet=r["snip"], bm25=round(-r["score"], 4)) for r in rows]


def vector_hits(conn, embedder, q: str, filters: dict, limit: int, scan: int = 50000) -> list:
    qv = (embedder.embed([q], role="query") if getattr(embedder, "prefix", None) else embedder.embed([q]))[0]
    where, args = _where(filters)
    rows = conn.execute(
        "SELECT c.chunk_id, c.kind, c.source, c.ref, c.title, c.start_line, c.end_line, c.session_id, c.ts, "
        "substr(c.body, 1, 320) AS head, v.vec FROM chunk_vectors v JOIN chunks c ON c.chunk_id = v.chunk_id "
        "WHERE v.model = ?%s LIMIT ?" % where, [embedder.name] + args + [scan]).fetchall()
    scored = []
    for r in rows:
        vec = _unpack(r["vec"])
        if len(vec) != len(qv):
            continue
        scored.append((sum(a * b for a, b in zip(qv, vec)), r))
    scored.sort(key=lambda x: -x[0])
    return [_row(r, snippet=r["head"], cosine=round(s, 4)) for s, r in scored[:limit]]


FUSION_KEY = "rag:fusion"


def fusion_weight(conn) -> dict:
    """The semantic list's RRF weight, tuned by `rag-eval` on the project's golden set
    ({"semantic_weight", "tuned_at", "cases"}); 1.0 (plain RRF) until an eval has run."""
    try:
        row = conn.execute("SELECT value FROM meta WHERE key = ?", (FUSION_KEY,)).fetchone()
        tuned = json.loads(row[0]) if row else None
    except Exception:  # noqa: BLE001
        tuned = None
    if isinstance(tuned, dict) and isinstance(tuned.get("semantic_weight"), (int, float)):
        return tuned
    return {"semantic_weight": 1.0, "tuned_at": None, "cases": 0}


def fuse(lists: list, limit: int, weights: dict | None = None) -> list:
    """Weighted reciprocal rank fusion: score = sum w / (k + rank). Deterministic tie-break on chunk id."""
    acc = {}
    weights = weights or {}
    for name, hits in lists:
        w = float(weights.get(name, 1.0))
        for rank, h in enumerate(hits):
            entry = acc.setdefault(h["chunk_id"], dict(h, matched_by=[], rrf=0.0))
            entry["matched_by"].append(name)
            entry["rrf"] += w / (RRF_K + rank + 1)
            for key in ("bm25", "cosine"):
                if key in h:
                    entry[key] = h[key]
            if name == "keyword":
                entry["snippet"] = h["snippet"]
    out = sorted(acc.values(), key=lambda e: (-e["rrf"], e["chunk_id"]))[:limit]
    for e in out:
        e["rrf"] = round(e["rrf"], 5)
    return out


def index_status(conn) -> dict:
    try:
        by_kind = {r["kind"]: {"sources": r["n"], "chunks": r["c"] or 0} for r in conn.execute(
            "SELECT kind, COUNT(*) AS n, SUM(chunks) AS c FROM index_sources GROUP BY kind")}
        vectors = {r["model"]: r["n"] for r in conn.execute("SELECT model, COUNT(*) AS n FROM chunk_vectors GROUP BY model")}
        last = conn.execute("SELECT value FROM meta WHERE key = 'index:last'").fetchone()
    except Exception:  # noqa: BLE001
        return {"ready": False, "by_kind": {}, "vectors": {}, "last": None, "embedder": None, "mode": "keyword"}
    embedder = get_embedder()
    mode = "hybrid" if embedder and vectors.get(embedder.name) else "keyword"
    return {"ready": bool(by_kind), "by_kind": by_kind, "vectors": vectors,
            "last": json.loads(last[0]) if last else None, "embedder": embedder.name if embedder else None, "mode": mode}


def search(conn, q: str, filters: dict | None = None, limit: int = 10, embedder="auto") -> dict:
    """Hybrid search. `filters`: kinds[], path (prefix), since (ISO), session."""
    filters = filters or {}
    limit = max(1, min(int(limit or 10), 50))
    if embedder == "auto":
        embedder = get_embedder()
    pool = max(limit * 4, 40)
    lists = [("keyword", keyword_hits(conn, q, filters, pool))]
    warnings = []
    fusion = fusion_weight(conn)
    if embedder and fusion["semantic_weight"] <= 0:
        embedder = None  # rag-eval measured that semantic hits only hurt here; skip the embed call
    if embedder:
        try:
            has = conn.execute("SELECT 1 FROM chunk_vectors WHERE model = ? LIMIT 1", (embedder.name,)).fetchone()
            if has:
                lists.append(("semantic", vector_hits(conn, embedder, q, filters, pool)))
            else:
                warnings.append("no vectors yet for %s; keyword results only" % embedder.name)
        except EmbedError as exc:
            warnings.append("semantic search unavailable: %s" % exc)
    hits = fuse(lists, limit, {"semantic": fusion["semantic_weight"]})
    mode = "hybrid" if len(lists) > 1 else "keyword"
    return {"query": q, "mode": mode, "filters": filters, "hits": hits, "warnings": warnings,
            "fusion": fusion, "provenance": "measured"}


# ---- related code from the dependency graph -------------------------------------------------

def related_files(project: str, paths: list, limit: int = 8) -> list:
    """Files one import edge away from `paths`, from the Graphify graph (exact, no model)."""
    gpath = os.path.join(common.agent_spec_dir(project), "graph", "knowledge-graph.json")
    graph = common.read_json(gpath)
    if not isinstance(graph, dict):
        return []
    wanted = set(paths)
    out = {}
    for e in graph.get("edges") or []:
        s, t = e.get("source"), e.get("target")
        if s in wanted and t not in wanted:
            out.setdefault(t, {"path": t, "relation": "imported by a match"})
        elif t in wanted and s not in wanted:
            out.setdefault(s, {"path": s, "relation": "imports a match"})
    return list(out.values())[:limit]


# ---- ask: retrieval + citations, answer from a model only when one is configured -----------

ASK_SYSTEM = (
    "You answer questions about one software project using ONLY the numbered sources provided. "
    "Cite every claim with [n]. If the sources do not answer the question, say so and name what "
    "to look at next. Never invent file paths, functions or session events.")


def cite(hit: dict) -> str:
    if hit["kind"] in ("request", "review"):
        return "%s %s" % (hit["kind"], hit["ref"])
    return hit["ref"]


def _sources_block(conn, hits: list, chars: int = 1200) -> str:
    blocks = []
    for i, h in enumerate(hits, 1):
        body = conn.execute("SELECT body FROM chunks WHERE chunk_id = ?", (h["chunk_id"],)).fetchone()
        blocks.append("[%d] %s (%s)\n%s" % (i, cite(h), h["kind"], (body[0] if body else "")[:chars]))
    return "\n\n".join(blocks)


def cursor_prompt(question: str, hits: list) -> str:
    """A prompt for Cursor: the agent re-queries the index itself and answers with citations."""
    lines = ["/agent-spec-ask %s" % question, "", "Sources the project index already retrieved (start here, cite as path:lines or request id):"]
    lines += ["- [%d] %s — %s" % (i, cite(h), h["title"][:100]) for i, h in enumerate(hits, 1)]
    return "\n".join(lines)


def get_llm():
    spec = (os.environ.get("AGENT_SPEC_LLM") or "").strip()
    provider, _, model = spec.partition(":")
    return (provider, model) if provider == "ollama" and model else None


def ask(conn, project: str, question: str, filters: dict | None = None, limit: int = 8) -> dict:
    result = search(conn, question, filters, limit)
    hits = result["hits"]
    code_paths = [h["source"] for h in hits if h["kind"] == "code"][:3]
    out = dict(result, related=related_files(project, code_paths), cursor_prompt=cursor_prompt(question, hits),
               answer=None)
    llm = get_llm()
    if llm and hits:
        _, model = llm
        try:
            data = _post_json(ollama_url() + "/api/chat", {
                "model": model, "stream": False, "options": {"temperature": 0},
                "messages": [{"role": "system", "content": ASK_SYSTEM},
                             {"role": "user", "content": "Question: %s\n\nSources:\n%s" % (question, _sources_block(conn, hits))}]},
                timeout=180)
            text = re.sub(r"<think>.*?</think>", "", (data.get("message") or {}).get("content") or "", flags=re.S).strip()
            if text:
                cited = sorted({int(n) for n in re.findall(r"\[(\d+)\]", text) if 0 < int(n) <= len(hits)})
                out["answer"] = {"text": text, "model": "ollama:" + model, "provenance": "ai_judged",
                                 "cited": cited, "uncited": not cited}
        except EmbedError as exc:
            out["warnings"] = out["warnings"] + ["answer model unavailable: %s" % exc]
    return out
