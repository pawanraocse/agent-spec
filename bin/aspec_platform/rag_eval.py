"""Retrieval accuracy for the local project index: hit@1, hit@k and MRR per search mode.

A golden set is a JSONL file of `{"q", "expect", "kind", "made_by"}` rows at
`.agent-spec/eval/rag-golden.jsonl`. `build_golden` writes one from the project itself: for
each sampled code or doc file it asks a local Ollama model for the question a developer would
ask that the file answers, without naming the file or its identifiers, so keyword search
cannot win by string matching alone. Without a model it falls back to the file's own first
sentence (`made_by: "docstring"`), which is easier and says so. Edit the file by hand to add
real questions; `run` scores whatever is there.

`run` scores keyword (BM25), semantic (embeddings) and hybrid (reciprocal-rank fusion) search
against the same questions and stores the result in `meta` under `rag:eval`, which the
dashboard Showcase reads. Measured, not estimated: every number is a real search call.
"""
from __future__ import annotations

import json
import os
import re

from . import common, ollama, retrieval

GOLDEN = os.path.join("eval", "rag-golden.jsonl")
META_KEY = "rag:eval"
HISTORY_KEY = "rag:eval:history"
HISTORY_MAX = 20
SWEEP = (0.0, 0.25, 0.5, 1.0)   # semantic RRF weights tried; the best is stored for search()
QUESTION_PROMPT = (
    "Below is the start of a file from a software project. Write ONE short question (max 18 words) "
    "a developer would ask that this file answers. Do not mention the file name, path, or any "
    "identifier in backticks or CamelCase/snake_case. Reply with the question only.\n\n%s")


def golden_path(project: str) -> str:
    return os.path.join(common.agent_spec_dir(project), GOLDEN)


def _first_sentence(body: str) -> str:
    text = re.sub(r"^#!.*$", "", body, flags=re.M)
    text = re.sub(r'"""|\'\'\'|^\s*(#+|//|\*|>)\s?', " ", text, flags=re.M)
    text = re.sub(r"`[^`]*`|\([A-Z]{1,4}-[\d.]+\)", " ", text)
    for line in text.splitlines():
        words = line.split()
        if len(words) >= 5 and not re.search(r"[{};=]|^\s*(import|from|def|class)\b", line):
            return " ".join(words)[:200]
    return ""


def _strip_identity(q: str, source: str) -> str:
    stem = os.path.splitext(os.path.basename(source))[0]
    for part in re.split(r"[-_.]", stem):
        if len(part) > 3:
            q = re.sub(r"\b%s\b" % re.escape(part), " ", q, flags=re.I)
    return " ".join(q.split())


def candidates(conn, n: int) -> list:
    """Code files with a docstring and docs with a lead paragraph, sampled evenly by path."""
    rows = conn.execute(
        "SELECT kind, source, body FROM chunks WHERE kind IN ('code', 'doc') AND start_line = 1 "
        "AND source NOT LIKE '%/dist/%' AND source NOT LIKE 'tests/%' ORDER BY source").fetchall()
    usable = [(r["kind"], r["source"], r["body"]) for r in rows if _first_sentence(r["body"])]
    code = [u for u in usable if u[0] == "code"]
    docs = [u for u in usable if u[0] == "doc"]
    want_code = min(len(code), max(1, n * 2 // 3))
    want_docs = min(len(docs), n - want_code)

    def stride(xs, k):
        return [xs[int(i * len(xs) / k)] for i in range(k)] if k else []
    return stride(code, want_code) + stride(docs, want_docs)


def _ask_model(url: str, model: str, body: str) -> str:
    data = retrieval._post_json(url + "/api/chat", {
        "model": model, "stream": False, "options": {"temperature": 0},
        "messages": [{"role": "user", "content": QUESTION_PROMPT % body[:1500]}]}, timeout=120)
    text = re.sub(r"<think>.*?</think>", "", (data.get("message") or {}).get("content") or "", flags=re.S)
    return " ".join(text.strip().strip('"').split())[:200]


def build_golden(conn, project: str, n: int = 30, model: str | None = None) -> dict:
    found = ollama.probe()
    names = [m["name"] for m in ollama.chat_models(found["models"])] if found["reachable"] else []
    model = model if model in names else next((m for m in ("qwen2.5-coder:7b", "qwen3:4b") if m in names),
                                              names[0] if names else None)
    rows = []
    for kind, source, body in candidates(conn, n):
        q, made_by = "", "docstring"
        if model:
            try:
                q, made_by = _strip_identity(_ask_model(found["url"], model, body), source), "ollama:" + model
            except retrieval.EmbedError:
                q = ""
        if len(q.split()) < 4:
            q, made_by = _strip_identity(_first_sentence(body), source), "docstring"
        if q:
            rows.append({"q": q, "expect": source, "kind": kind, "made_by": made_by})
    path = golden_path(project)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    return {"path": path, "cases": len(rows), "model": model}


def load_golden(project: str) -> list:
    out = []
    try:
        with open(golden_path(project), encoding="utf-8") as fh:
            for line in fh:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict) and row.get("q") and row.get("expect"):
                    out.append(row)
    except OSError:
        pass
    return out


def _rank(hits: list, expect: str) -> int | None:
    seen = []
    for h in hits:
        if h["source"] not in seen:
            seen.append(h["source"])
        if h["source"] == expect:
            return len(seen)
    return None


def _score(ranks: list, k: int) -> dict:
    n = len(ranks) or 1
    return {"hit1": round(sum(1 for r in ranks if r == 1) / n, 3),
            "hitk": round(sum(1 for r in ranks if r and r <= k) / n, 3),
            "mrr": round(sum(1.0 / r for r in ranks if r) / n, 3)}


def run(conn, project: str, k: int = 5, label: str | None = None) -> dict:
    cases = load_golden(project)
    if not cases:
        return {"ok": False, "error": "no golden set; run: agent-spec-platform.py rag-eval --build"}
    embedder = retrieval.get_embedder(conn)
    has_vec = bool(embedder) and conn.execute(
        "SELECT 1 FROM chunk_vectors WHERE model = ? LIMIT 1", (embedder.name,)).fetchone() is not None
    pool = max(k * 4, 40)
    ranks = {"keyword": [], "semantic": []}
    sweep = {w: [] for w in SWEEP}
    examples = []
    for c in cases:
        kw = retrieval.keyword_hits(conn, c["q"], {}, pool)
        ranks["keyword"].append(_rank(retrieval.fuse([("keyword", kw)], pool), c["expect"]))
        if has_vec:
            try:
                sem = retrieval.vector_hits(conn, embedder, c["q"], {}, pool)
            except retrieval.EmbedError:
                sem = []
            ranks["semantic"].append(_rank(retrieval.fuse([("semantic", sem)], pool), c["expect"]))
            for w in SWEEP:
                fused = retrieval.fuse([("keyword", kw), ("semantic", sem)], pool, {"semantic": w})
                sweep[w].append(_rank(fused, c["expect"]))
        if len(examples) < 6:
            examples.append({"q": c["q"], "expect": c["expect"], "keyword_rank": ranks["keyword"][-1]})
    modes = {m: _score(r, k) for m, r in ranks.items() if r}
    tuned = None
    if has_vec:
        scored = {w: _score(r, k) for w, r in sweep.items()}
        # Best MRR, then hit@k; a tie keeps the larger semantic weight (more recall for paraphrases).
        best = max(SWEEP, key=lambda w: (scored[w]["mrr"], scored[w]["hitk"], w))
        modes["hybrid"] = scored[1.0]
        modes["tuned"] = dict(scored[best], semantic_weight=best)
        tuned = {"semantic_weight": best, "tuned_at": common.utc_now(), "cases": len(cases),
                 "sweep": {str(w): scored[w] for w in SWEEP}}
        conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (retrieval.FUSION_KEY, json.dumps(tuned)))
    result = {"ok": True, "ts": common.utc_now(), "k": k, "cases": len(cases), "provenance": "measured",
              "made_by": sorted({c.get("made_by") or "manual" for c in cases}),
              "embedder": embedder.name if has_vec else None, "fusion": tuned,
              "modes": modes, "examples": examples}
    conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (META_KEY, json.dumps(result)))
    hist = history(conn)
    hist.append({"ts": result["ts"], "cases": result["cases"], "embedder": result["embedder"],
                 "label": label or result["embedder"] or "keyword only", "modes": result["modes"]})
    conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
                 (HISTORY_KEY, json.dumps(hist[-HISTORY_MAX:])))
    return result


def history(conn) -> list:
    try:
        row = conn.execute("SELECT value FROM meta WHERE key = ?", (HISTORY_KEY,)).fetchone()
        return json.loads(row[0]) if row else []
    except Exception:  # noqa: BLE001
        return []


def latest(conn) -> dict | None:
    try:
        row = conn.execute("SELECT value FROM meta WHERE key = ?", (META_KEY,)).fetchone()
    except Exception:  # noqa: BLE001 — an old schema has no meta row; the panel shows "not run"
        return None
    return json.loads(row[0]) if row else None
