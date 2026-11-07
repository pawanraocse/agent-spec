#!/usr/bin/env python3
"""Tests for shared team facts (T-053): merge-team, local-wins, org constraints in the digest,
install --register sync from TEAM_FACTS_REPO, and the doctor check.

Run: python3 tests/test_team_facts.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEMORY = os.path.join(REPO_DIR, "bin", "agent-spec-memory.py")
INSTALL = os.path.join(REPO_DIR, "install.sh")


def fact(directory, fid, ftype, subject, body, created="2026-10-01"):
    os.makedirs(directory, exist_ok=True)
    with open(os.path.join(directory, fid + ".md"), "w", encoding="utf-8") as fh:
        fh.write("---\nid: %s\ntype: %s\nsubject: %s\ncreated: %s\nsource: test\n---\n%s\n"
                 % (fid, ftype, subject, created, body))


def mem(cwd, *args, **env):
    return subprocess.run([sys.executable, MEMORY, *args], cwd=cwd, capture_output=True, text=True,
                          env=dict(os.environ, **env))


def project():
    p = tempfile.mkdtemp()
    os.makedirs(os.path.join(p, ".agent-spec", "memory", "facts"))
    return p


def team_source():
    src = tempfile.mkdtemp()
    fact(src, "org-pii", "constraint", "pii logging", "Never log customer PII or request bodies.")
    fact(src, "org-java", "decision", "java version", "Services build on Java 17.")
    fact(src, "org-gotcha", "gotcha", "ci cache", "The CI cache key includes the Gradle wrapper hash.")
    with open(os.path.join(src, "bad.md"), "w") as fh:
        fh.write("no front matter here")
    fact(src, "huge", "gotcha", "huge", "x" * 3000)
    fact(src, "weird", "opinion", "weird type", "unknown type is skipped")
    return src


def test_merge_team_imports_valid_and_names_skips():
    p, src = project(), team_source()
    res = mem(p, "merge-team", src)
    assert res.returncode == 0, res.stdout + res.stderr
    assert "3 team fact(s)" in res.stdout and "3 skipped" in res.stdout, res.stdout
    assert "bad.md (no front matter)" in res.stdout and "huge.md (over 2000 B)" in res.stdout
    assert "weird.md (unknown type 'opinion')" in res.stdout
    team = os.path.join(p, ".agent-spec", "team-facts")
    assert sorted(n for n in os.listdir(team) if n.endswith(".md")) == ["org-gotcha.md", "org-java.md", "org-pii.md"]
    assert os.path.exists(os.path.join(team, ".synced"))
    assert not os.listdir(os.path.join(p, ".agent-spec", "memory", "facts")), "local facts untouched"


def test_merge_team_replaces_previous_set_and_reads_facts_subdir():
    p, src = project(), team_source()
    mem(p, "merge-team", src)
    fresh = tempfile.mkdtemp()
    fact(os.path.join(fresh, "facts"), "only-one", "reference", "wiki", "Runbooks live in the team wiki.")
    res = mem(p, "merge-team", fresh)
    assert "1 team fact(s)" in res.stdout, res.stdout
    team = os.path.join(p, ".agent-spec", "team-facts")
    assert [n for n in os.listdir(team) if n.endswith(".md")] == ["only-one.md"], "stale team facts must go"


def test_digest_shows_org_constraints_and_local_wins():
    p, src = project(), team_source()
    mem(p, "merge-team", src)
    out = mem(p, "digest").stdout
    assert "- [org] pii logging: Never log customer PII" in out, out
    assert "java version" not in out, "only org *constraints* are surfaced in the digest"
    fact(os.path.join(p, ".agent-spec", "memory", "facts"), "local-pii", "constraint", "pii logging",
         "Local override: log hashed ids only.")
    out = mem(p, "digest").stdout
    assert "[org] pii logging" not in out and "Local override" in out, "local fact must win on (type, subject)"


def test_digest_org_section_is_capped_and_local_facts_still_fit():
    p = project()
    src = tempfile.mkdtemp()
    for i in range(12):
        fact(src, "c%d" % i, "constraint", "org rule %d" % i, "Org constraint number %d: " % i + "word " * 25)
    mem(p, "merge-team", src)
    fact(os.path.join(p, ".agent-spec", "memory", "facts"), "loc", "gotcha", "local one", "Local gotcha stays visible.")
    out = mem(p, "digest").stdout
    org = [l for l in out.splitlines() if l.startswith("- [org]")]
    assert sum(len(l) for l in org) < 700 and any("more org constraints" in l for l in org), org
    assert "Local gotcha stays visible" in out


def test_lint_reports_team_vs_local_conflict():
    p, src = project(), team_source()
    mem(p, "merge-team", src)
    fact(os.path.join(p, ".agent-spec", "memory", "facts"), "loc", "constraint", "request logging",
         "Always log customer PII and request bodies.")
    res = mem(p, "lint")
    assert res.returncode == 1 and "CONFLICT" in res.stdout, res.stdout


def test_submodule_checkout_is_not_overwritten():
    p, src = project(), team_source()
    team = os.path.join(p, ".agent-spec", "team-facts")
    os.makedirs(team)
    open(os.path.join(team, ".git"), "w").write("gitdir: elsewhere")
    fact(team, "sub-fact", "constraint", "from submodule", "Submodule facts are used as-is.")
    res = mem(p, "merge-team", src)
    assert "submodule" in res.stdout and os.listdir(team).count("sub-fact.md") == 1
    assert "[org] from submodule" in mem(p, "digest").stdout


class Sandbox:
    def __init__(self):
        self.root = tempfile.mkdtemp()
        self.home = os.path.join(self.root, "home")
        self.proj = os.path.join(self.root, "proj")
        os.makedirs(os.path.join(self.home, ".cursor"))
        os.makedirs(self.proj)
        open(os.path.join(self.proj, "app.py"), "w").write("import os\n")

    def register(self, **env):
        e = {k: v for k, v in os.environ.items() if k not in ("TEAM_FACTS_REPO", "WIN_CURSOR_HOME")}
        e.update(HOME=self.home, **env)
        return subprocess.run(["bash", INSTALL, "--register", self.proj], cwd=self.root,
                              capture_output=True, text=True, env=e)

    def doctor(self, **env):
        script = os.path.join(self.proj, ".agent-spec", "bin", "agent-spec-doctor.py")
        e = {k: v for k, v in os.environ.items() if k != "TEAM_FACTS_REPO"}
        e.update(HOME=self.home, **env)
        res = subprocess.run([sys.executable, script, "--json"], cwd=self.proj, capture_output=True,
                             text=True, env=e)
        return [c for c in json.loads(res.stdout)["checks"] if c["id"] == "team-facts"]

    def close(self):
        shutil.rmtree(self.root, ignore_errors=True)


def test_register_syncs_from_local_path_and_doctor_checks():
    sb, src = Sandbox(), team_source()
    try:
        assert sb.register().returncode == 0
        assert sb.doctor() == [], "silent when team facts are not in use"
        res = sb.register(TEAM_FACTS_REPO=src)
        assert res.returncode == 0, res.stdout + res.stderr
        assert "team facts merged" in res.stdout, res.stdout
        assert not os.path.exists(os.path.join(REPO_DIR, ".agent-spec", "team-facts")), \
            "registering a workspace must not write team facts into the package clone"
        digest = subprocess.run([sys.executable, os.path.join(sb.proj, ".agent-spec", "bin", "agent-spec-memory.py"),
                                 "digest"], cwd=sb.proj, capture_output=True, text=True).stdout
        assert "[org] pii logging" in digest
        assert sb.doctor(TEAM_FACTS_REPO=src)[0]["status"] == "OK"
        # age the sync marker past the stale threshold
        marker = os.path.join(sb.proj, ".agent-spec", "team-facts", ".synced")
        old = os.path.getmtime(marker) - 30 * 86400
        os.utime(marker, (old, old))
        assert sb.doctor(TEAM_FACTS_REPO=src)[0]["status"] == "WARN"
    finally:
        sb.close()


def test_register_survives_unreachable_repo_and_doctor_warns():
    sb = Sandbox()
    try:
        bogus = "/nonexistent/path/team-facts.git"
        res = sb.register(TEAM_FACTS_REPO=bogus)
        assert res.returncode == 0, "a bad TEAM_FACTS_REPO must never stop registration"
        assert "team facts: could not clone" in res.stdout, res.stdout
        checks = sb.doctor(TEAM_FACTS_REPO=bogus)
        assert checks and checks[0]["status"] == "WARN" and "no team facts are merged" in checks[0]["message"]
    finally:
        sb.close()


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print("  ok", fn.__name__)
    print("%d team-facts tests passed" % len(tests))
