#!/usr/bin/env python3
"""Tests for agent-spec-memory.py: lint (T-001) and the one-line index (T-002).

Run: python3 tests/test_memory.py
Each test builds a throwaway project; the tool resolves paths from cwd.
"""
import os
import subprocess
import sys
import tempfile

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEMORY = os.path.join(REPO_DIR, "bin", "agent-spec-memory.py")
TOKENS = os.path.join(REPO_DIR, "bin", "agent-spec-tokens.py")


def run(cwd, *args):
    return subprocess.run([sys.executable, MEMORY, *args], cwd=cwd,
                          capture_output=True, text=True)


def write_fact(cwd, fid, ftype, subject, body, created="2026-10-01", extra=""):
    d = os.path.join(cwd, ".agent-spec", "memory", "facts")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, fid + ".md"), "w", encoding="utf-8") as fh:
        fh.write("---\nid: %s\ntype: %s\nsubject: %s\ncreated: %s\nsource: test\n%s---\n%s\n"
                 % (fid, ftype, subject, created, extra, body))


def test_lint_clean():
    with tempfile.TemporaryDirectory() as t:
        write_fact(t, "a", "decision", "database", "We use PostgreSQL 16 for orders storage.")
        write_fact(t, "b", "gotcha", "build", "Gradle daemon must be stopped before the integration run.")
        res = run(t, "lint")
        assert res.returncode == 0, res.stdout + res.stderr
        assert "clean" in res.stdout


def test_lint_duplicate_key():
    with tempfile.TemporaryDirectory() as t:
        write_fact(t, "a", "constraint", "JSON library", "Use Jackson for all serialization.")
        write_fact(t, "b", "constraint", "json-library", "Serialization goes through the ObjectMapper bean.")
        res = run(t, "lint")
        assert res.returncode == 1, res.stdout
        assert "DUP-KEY" in res.stdout and "a" in res.stdout and "b" in res.stdout


def test_lint_duplicate_body():
    with tempfile.TemporaryDirectory() as t:
        write_fact(t, "a", "decision", "retries", "Outbound HTTP calls retry three times with backoff.")
        write_fact(t, "b", "gotcha", "http", "Outbound HTTP calls retry three times with backoff!")
        res = run(t, "lint")
        assert res.returncode == 1, res.stdout
        assert "DUP-BODY" in res.stdout


def test_lint_conflict():
    with tempfile.TemporaryDirectory() as t:
        write_fact(t, "a", "constraint", "dates", "Always use java.time for date handling.")
        write_fact(t, "b", "constraint", "legacy dates", "Never use java.time for date handling in the batch module.")
        res = run(t, "lint")
        assert res.returncode == 1, res.stdout
        assert "CONFLICT" in res.stdout


def test_lint_no_false_conflict_on_different_topics():
    with tempfile.TemporaryDirectory() as t:
        write_fact(t, "a", "constraint", "json", "Always use Jackson for serialization.")
        write_fact(t, "b", "constraint", "logging", "Never log request bodies at INFO level.")
        res = run(t, "lint")
        assert res.returncode == 0, res.stdout


def test_add_warns_on_near_duplicate():
    with tempfile.TemporaryDirectory() as t:
        os.makedirs(os.path.join(t, ".agent-spec", "memory", "facts"))
        r1 = run(t, "add", "--type", "constraint", "--subject", "dates",
                 "Always use java.time for date handling.")
        assert r1.returncode == 0, r1.stderr
        r2 = run(t, "add", "--type", "constraint", "--subject", "dates",
                 "Never use java.time for date handling in batch.")
        assert r2.returncode == 0, r2.stderr
        assert "CONFLICT" in r2.stdout or "DUP" in r2.stdout, r2.stdout


def test_index_one_line_per_fact_and_check():
    with tempfile.TemporaryDirectory() as t:
        write_fact(t, "a", "decision", "database", "We use PostgreSQL 16 for orders storage.")
        write_fact(t, "b", "gotcha", "build", "x" * 400 + " tail")
        res = run(t, "index")
        assert res.returncode == 0, res.stderr
        index = os.path.join(t, ".agent-spec", "memory", "INDEX.md")
        lines = [l for l in open(index, encoding="utf-8").read().splitlines() if l.startswith("- ")]
        assert len(lines) == 2, lines
        assert all(len(l) <= 160 for l in lines), [len(l) for l in lines]
        assert run(t, "index", "--check").returncode == 0
        write_fact(t, "c", "gotcha", "ci", "Jenkins agents have no network access to npm.")
        assert run(t, "index", "--check").returncode == 1, "stale index must be detected"


def test_add_and_prune_regenerate_index():
    with tempfile.TemporaryDirectory() as t:
        os.makedirs(os.path.join(t, ".agent-spec", "memory", "facts"))
        run(t, "add", "--type", "gotcha", "--subject", "ci", "Jenkins agents have no network access to npm.")
        assert run(t, "index", "--check").returncode == 0, "add must refresh INDEX.md"
        write_fact(t, "old", "gotcha", "stale", "An outdated gotcha nobody needs anymore.", created="2020-01-01")
        run(t, "index")
        run(t, "prune", "--older-than", "30")
        assert run(t, "index", "--check").returncode == 0, "prune must refresh INDEX.md"


def test_audit_memory_counts_index_not_bodies():
    """40 facts (bodies ~600 B each = 24 KB) must pass the 8 KB audit via INDEX.md alone."""
    with tempfile.TemporaryDirectory() as t:
        os.makedirs(os.path.join(t, ".cursor", "hooks"))
        for i in range(40):
            write_fact(t, "f%02d" % i, "gotcha", "topic %d" % i, ("word%d " % i) * 80)
        archive = os.path.join(t, ".agent-spec", "memory", "snapshots")
        os.makedirs(archive)
        with open(os.path.join(archive, "old.md"), "w") as fh:
            fh.write("s" * 20000)
        run(t, "index")
        out = subprocess.run([sys.executable, TOKENS, "audit", "--scan", t],
                             capture_output=True, text=True)
        assert "memory tree" not in out.stdout + out.stderr, out.stdout + out.stderr
        index_size = os.path.getsize(os.path.join(t, ".agent-spec", "memory", "INDEX.md"))
        assert index_size < 8000, index_size


def test_audit_memory_flags_oversized_index():
    with tempfile.TemporaryDirectory() as t:
        mem = os.path.join(t, ".agent-spec", "memory")
        os.makedirs(mem)
        with open(os.path.join(mem, "INDEX.md"), "w") as fh:
            fh.write("- x\n" * 4000)
        out = subprocess.run([sys.executable, TOKENS, "audit", "--scan", t],
                             capture_output=True, text=True)
        assert "memory tree" in out.stdout + out.stderr, out.stdout + out.stderr


def _fid(out):
    return out.split("remembered:")[1].split()[0]


def _read_fact(t, fid):
    return open(os.path.join(t, ".agent-spec", "memory", "facts", fid + ".md"),
                encoding="utf-8").read()


# ---- fact schema v2 (L-005): confidence, expires, provenance, version, supersedes, status ----

def test_v2_old_format_fact_still_valid():
    with tempfile.TemporaryDirectory() as t:
        write_fact(t, "old", "gotcha", "build", "Gradle daemon must be stopped before the integration run.")
        assert run(t, "lint").returncode == 0
        listing = run(t, "list").stdout
        assert "build" in listing and "superseded" not in listing and "expired" not in listing, listing
        assert "old" in run(t, "search", "gradle").stdout
        assert "Gradle daemon" in run(t, "digest").stdout


def test_v2_add_writes_optional_fields_only_when_given():
    with tempfile.TemporaryDirectory() as t:
        r = run(t, "add", "--type", "gotcha", "--subject", "plain", "Plain facts keep the v1 frontmatter shape.")
        text = _read_fact(t, _fid(r.stdout))
        for key in ("confidence", "expires", "provenance", "version", "supersedes", "status"):
            assert key + ":" not in text, text
        r = run(t, "add", "--type", "gotcha", "--subject", "rich", "--confidence", "HIGH",
                "--expires", "2099-01-01", "--provenance", "run-42", "Rich facts carry the v2 frontmatter.")
        assert r.returncode == 0, r.stderr
        text = _read_fact(t, _fid(r.stdout))
        assert "confidence: HIGH" in text and "expires: 2099-01-01" in text and "provenance: run-42" in text, text
        assert run(t, "lint").returncode == 0


def test_v2_add_rejects_bad_values():
    with tempfile.TemporaryDirectory() as t:
        assert run(t, "add", "--type", "gotcha", "--subject", "x", "--confidence", "MAYBE",
                   "Bad confidence must be rejected loudly.").returncode != 0
        assert run(t, "add", "--type", "gotcha", "--subject", "x", "--expires", "tomorrow",
                   "Bad expiry must be rejected loudly.").returncode == 2
        assert run(t, "add", "--type", "gotcha", "--subject", "x", "--supersedes", "nope",
                   "Superseding a missing fact must be rejected.").returncode == 2
        assert not os.path.isdir(os.path.join(t, ".agent-spec", "memory", "facts")) or \
            not os.listdir(os.path.join(t, ".agent-spec", "memory", "facts"))


def test_v2_supersedes_marks_old_and_bumps_version():
    with tempfile.TemporaryDirectory() as t:
        write_fact(t, "a", "decision", "database", "We use PostgreSQL 14 for orders storage.")
        r = run(t, "add", "--type", "decision", "--subject", "database", "--supersedes", "a",
                "Orders storage moved to a managed cluster on version sixteen.")
        assert r.returncode == 0, r.stdout + r.stderr
        new = _fid(r.stdout)
        old_text = _read_fact(t, "a")
        assert "status: superseded" in old_text and old_text.count("status:") == 1, old_text
        assert old_text.endswith("We use PostgreSQL 14 for orders storage.\n"), old_text
        new_text = _read_fact(t, new)
        assert "supersedes: a" in new_text and "version: 2" in new_text, new_text
        assert run(t, "lint").returncode == 0, run(t, "lint").stdout
        listing = run(t, "list").stdout
        assert "superseded" in listing, listing
        assert "superseded" in run(t, "search", "PostgreSQL").stdout
        digest = run(t, "digest").stdout
        assert "PostgreSQL 14" not in digest and "managed cluster" in digest, digest
        # chain: superseding the new fact bumps again
        r2 = run(t, "add", "--type", "decision", "--subject", "database", "--supersedes", new,
                 "Orders storage is now sharded across two managed clusters.")
        assert "version: 3" in _read_fact(t, _fid(r2.stdout))
        assert run(t, "lint").returncode == 0


def test_v2_expired_fact_is_reported_and_non_active():
    with tempfile.TemporaryDirectory() as t:
        write_fact(t, "gone", "gotcha", "freeze", "Release freeze applies until the audit completes.",
                   extra="expires: 2020-01-01\n")
        write_fact(t, "fine", "gotcha", "future", "This hotfix workaround is valid for a long while.",
                   extra="expires: 2099-12-31\n")
        res = run(t, "lint")
        assert res.returncode == 1 and "EXPIRED" in res.stdout and "gone" in res.stdout, res.stdout
        assert "fine" not in res.stdout.replace("findings", ""), res.stdout
        digest = run(t, "digest").stdout
        assert "Release freeze" not in digest and "hotfix workaround" in digest, digest
        assert "expired" in run(t, "list").stdout


def test_v2_missing_supersedes_target_flagged():
    with tempfile.TemporaryDirectory() as t:
        write_fact(t, "b", "decision", "database", "Orders storage moved to a managed cluster.",
                   extra="supersedes: ghost\nversion: 2\n")
        res = run(t, "lint")
        assert res.returncode == 1 and "MISSING-SUPERSEDES" in res.stdout and "ghost" in res.stdout, res.stdout


def test_v2_supersede_cycle_flagged():
    with tempfile.TemporaryDirectory() as t:
        write_fact(t, "a", "decision", "alpha", "Alpha decision text about queues.", extra="supersedes: b\n")
        write_fact(t, "b", "decision", "beta", "Beta decision text about caches.", extra="supersedes: a\n")
        write_fact(t, "c", "decision", "gamma", "Gamma decision text about tracing.", extra="supersedes: c\n")
        res = run(t, "lint")
        assert res.returncode == 1 and res.stdout.count("SUPERSEDE-CYCLE") == 2, res.stdout


def test_v2_deprecated_status_excluded_from_digest():
    with tempfile.TemporaryDirectory() as t:
        write_fact(t, "d", "gotcha", "legacy", "Legacy importer quirks are documented elsewhere.",
                   extra="status: deprecated\n")
        write_fact(t, "k", "gotcha", "live", "Live importer must run nightly.")
        digest = run(t, "digest").stdout
        assert "Legacy importer" not in digest and "Live importer" in digest, digest
        assert "deprecated" in run(t, "list").stdout


def test_v2_invalid_field_values_flagged():
    with tempfile.TemporaryDirectory() as t:
        write_fact(t, "x", "gotcha", "odd", "A hand edited fact with odd metadata values.",
                   extra="confidence: SURE\nexpires: soon\nstatus: zombie\nversion: two\n")
        res = run(t, "lint")
        assert res.returncode == 1 and res.stdout.count("BAD-FIELD") == 4, res.stdout


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print("  ok", fn.__name__)
    print("%d memory tests passed" % len(tests))
