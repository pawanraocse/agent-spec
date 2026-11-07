#!/usr/bin/env python3
"""Tests for the sessionStart digest: graph freshness (T-003), onboarding nudge (T-004),
team defaults (T-032) and doctor line (T-054).

Run: python3 tests/test_digest.py
"""
import fcntl
import json
import os
import shutil
import subprocess
import sys
import tempfile

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(REPO_DIR, "bin")


def make_project():
    t = tempfile.mkdtemp()
    spec = os.path.join(t, ".agent-spec")
    os.makedirs(os.path.join(spec, "bin"))
    os.makedirs(os.path.join(spec, "graph"))
    for name in ("agent-spec-digest.py", "graphify-build.py", "agent-spec-memory.py",
                 "agent-spec-doctor.py"):
        src = os.path.join(BIN, name)
        if os.path.exists(src):
            shutil.copy(src, os.path.join(spec, "bin", name))
    with open(os.path.join(t, "app.py"), "w") as fh:
        fh.write("import os\n\ndef main():\n    return os.getcwd()\n")
    return t


def digest(project, env=None):
    e = dict(os.environ)
    e.update(env or {})
    res = subprocess.run([sys.executable, os.path.join(project, ".agent-spec", "bin",
                                                       "agent-spec-digest.py")],
                         cwd=project, capture_output=True, text=True, env=e)
    assert res.returncode == 0, res.stderr
    return res.stdout


def test_graph_freshness_incremental_then_fresh():
    t = make_project()
    try:
        first = digest(t)
        assert "graph: incremental (" in first, first
        second = digest(t)
        assert "graph: fresh" in second, second
        with open(os.path.join(t, "app.py"), "a") as fh:
            fh.write("\n# touched\n")
        third = digest(t)
        assert "graph: incremental (" in third and "1 reparsed" in third, third
    finally:
        shutil.rmtree(t)


def test_graph_stale_lock_held():
    t = make_project()
    try:
        digest(t)  # build once so a graph exists
        lock = open(os.path.join(t, ".agent-spec", "graph", ".build.lock"), "w")
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        out = digest(t)
        assert "graph: stale (lock held" in out, out
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
        lock.close()
    finally:
        shutil.rmtree(t)


def test_graph_stale_timeout_names_manual_rebuild():
    t = make_project()
    try:
        out = digest(t, {"AGENT_SPEC_BUILD_TIMEOUT": "0.001"})
        assert "stale (timeout" in out, out
        assert "agent-spec-index" in out, "must name the manual rebuild path"
    finally:
        shutil.rmtree(t)


def test_graph_not_built_when_builder_missing():
    t = make_project()
    try:
        os.remove(os.path.join(t, ".agent-spec", "bin", "graphify-build.py"))
        out = digest(t)
        assert "graph: not built" in out and "agent-spec-index" in out, out
    finally:
        shutil.rmtree(t)


def test_onboarding_nudge():
    t = make_project()
    try:
        flag = os.path.join(t, ".agent-spec", ".onboarding-needed")
        assert "/agent-spec-onboard" not in digest(t)
        open(flag, "w").close()
        out = digest(t)
        assert "run `/agent-spec-onboard` now" in out, out
        os.remove(flag)
        assert "/agent-spec-onboard" not in digest(t)
    finally:
        shutil.rmtree(t)


def test_team_yaml_line():
    t = make_project()
    try:
        with open(os.path.join(t, ".agent-spec", "team.yaml"), "w") as fh:
            fh.write("# team defaults\njava_version: 17\nsdlc_track: fast-track\n")
        out = digest(t)
        assert "team: java_version=17 sdlc_track=fast-track" in out, out
    finally:
        shutil.rmtree(t)


def test_team_yaml_bad_value_is_ignored_not_fatal():
    t = make_project()
    try:
        with open(os.path.join(t, ".agent-spec", "team.yaml"), "w") as fh:
            fh.write("sdlc_track: warp-speed\n::: not yaml\n")
        out = digest(t)
        assert "<agent-spec-digest>" in out
        assert "warp-speed" not in out, "invalid enum values must not be injected"
    finally:
        shutil.rmtree(t)


def test_digest_size_cap():
    t = make_project()
    try:
        open(os.path.join(t, ".agent-spec", ".onboarding-needed"), "w").close()
        with open(os.path.join(t, ".agent-spec", "team.yaml"), "w") as fh:
            fh.write("java_version: 17\nsdlc_track: full\n")
        out = digest(t)
        assert len(out.encode()) <= 2700, len(out.encode())
    finally:
        shutil.rmtree(t)


def test_doctor_line_present():
    t = make_project()
    try:
        out = digest(t)
        assert "doctor:" in out, out
    finally:
        shutil.rmtree(t)


def _put_fact(t, fid, ftype, subject, body, extra=""):
    d = os.path.join(t, ".agent-spec", "memory", "facts")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, fid + ".md"), "w") as fh:
        fh.write("---\nid: %s\ntype: %s\nsubject: %s\ncreated: 2026-10-01\nsource: test\n%s---\n%s\n"
                 % (fid, ftype, subject, extra, body))


def _remembered(out):
    return out.split("remembered:")[1].split("Do NOT open")[0]


def test_digest_skips_expired_and_superseded_facts():
    t = make_project()
    try:
        _put_fact(t, "keep", "constraint", "keeper", "Always keep this active constraint visible.")
        _put_fact(t, "exp", "constraint", "expiring", "Stale expired constraint text here.",
                  "expires: 2020-01-01\n")
        _put_fact(t, "old", "decision", "queue", "Old superseded queue decision text.", "status: superseded\n")
        _put_fact(t, "new", "decision", "queue", "New queue decision replaces the old one.",
                  "supersedes: old\nversion: 2\n")
        mem = _remembered(digest(t))
        assert "active constraint" in mem and "New queue decision" in mem, mem
        assert "Stale expired" not in mem and "Old superseded" not in mem, mem
    finally:
        shutil.rmtree(t)


def test_digest_unchanged_for_v1_only_facts():
    t = make_project()
    try:
        _put_fact(t, "one", "gotcha", "ci", "Jenkins agents have no network access to npm.")
        _put_fact(t, "two", "constraint", "json", "Always use Jackson for serialization.")
        before = _remembered(digest(t))
        # the same facts with explicit v2 'active' metadata must render byte-identically
        _put_fact(t, "one", "gotcha", "ci", "Jenkins agents have no network access to npm.",
                  "status: active\nconfidence: HIGH\n")
        assert _remembered(digest(t)) == before
        assert "- [constraint] json: Always use Jackson for serialization." in before
        assert before.index("[constraint]") < before.index("[gotcha]")
    finally:
        shutil.rmtree(t)


def test_digest_expired_fact_only_does_not_print_remembered_header():
    t = make_project()
    try:
        _put_fact(t, "exp", "gotcha", "ci", "Expired gotcha is the only fact stored.", "expires: 2020-01-01\n")
        assert "remembered:" not in digest(t)
    finally:
        shutil.rmtree(t)


def test_digest_surfaces_staged_learning_candidate():
    t = make_project()
    try:
        mem_dir = os.path.join(t, ".agent-spec", "memory")
        os.makedirs(mem_dir, exist_ok=True)
        staged_file = os.path.join(mem_dir, "staged-candidates.jsonl")
        with open(staged_file, "w") as fh:
            fh.write(json.dumps({
                "session_id": "test-sid",
                "ts": "2026-11-07T20:00:00Z",
                "task": "fix export",
                "candidate": "no, that is wrong - use csv",
                "status": "pending"
            }) + "\n")
        out = digest(t)
        assert 'learning candidate: "no, that is wrong - use csv"' in out, out
    finally:
        shutil.rmtree(t)


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print("  ok", fn.__name__)
    print("%d digest tests passed" % len(tests))
