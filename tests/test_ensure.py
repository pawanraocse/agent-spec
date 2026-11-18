#!/usr/bin/env python3
"""Tests for bin/agent-spec-ensure.py (HA-005): register, index and report onboarding for the
project in the current directory, from any project, in one command.

Run: python3 tests/test_ensure.py
"""
import json
import re
import shutil
import os
import subprocess
import sys
import tempfile

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENSURE = os.path.join(REPO_DIR, "bin", "agent-spec-ensure.py")


def workspace():
    home = os.path.realpath(tempfile.mkdtemp())
    proj = os.path.realpath(tempfile.mkdtemp())
    subprocess.run(["git", "init", "-q", proj], check=True)
    with open(os.path.join(proj, "a.py"), "w") as fh:
        fh.write("import os\n")
    with open(os.path.join(proj, "b.py"), "w") as fh:
        fh.write("from a import *\n")
    return home, proj


def run(home, cwd, *args, env=None):
    res = subprocess.run([sys.executable, ENSURE, *args], cwd=cwd, capture_output=True, text=True,
                         env=dict(os.environ, HOME=home, **(env or {})), timeout=240)
    return res.returncode, json.loads(res.stdout)


def automation_rows(proj):
    path = os.path.join(proj, ".agent-spec", "metrics", "automation.jsonl")
    if not os.path.isfile(path):
        return []
    return [json.loads(line) for line in open(path) if line.strip()]


def test_check_reports_without_changing_anything():
    home, proj = workspace()
    code, out = run(home, proj, "--check")
    assert code == 0 and out["registered"] == "needed" and out["graph"] == "needed", out
    assert "no .agent-spec/bin" in out["gaps"]
    assert not os.path.exists(os.path.join(proj, ".agent-spec"))


def test_opt_out_env_is_check_only():
    home, proj = workspace()
    code, out = run(home, proj, env={"AGENT_SPEC_AUTO_REGISTER": "0"})
    assert out["registered"] == "needed" and not os.path.exists(os.path.join(proj, ".agent-spec"))


def test_unregistered_project_is_installed_indexed_and_flags_onboarding():
    home, proj = workspace()
    sub = os.path.join(proj, "pkg")
    os.makedirs(sub)
    code, out = run(home, sub)  # from a subdirectory: the git root is the project
    assert code == 0 and out["root"] == proj and out["registered"] == "installed", out
    assert out["graph"] == "ok" and os.path.isfile(os.path.join(proj, ".agent-spec", "graph", "knowledge-graph.json"))
    assert out["onboard"] == "needed" and out["next"] == "/agent-spec-onboard"
    assert "agent-spec-session-start" in open(os.path.join(proj, ".cursor", "hooks.json")).read()
    rows = [r for r in automation_rows(proj) if r["name"] == "register"]
    assert len(rows) == 1 and rows[0]["status"] == "installed", rows
    code, again = run(home, proj)
    assert again["registered"] == "ok" and "gaps" not in again, "second run is a no-op"
    assert again["skills"] == "ok" and "skill_gaps" not in again, again
    assert len(automation_rows(proj)) == len(rows) + 1  # the first run's skills-sync row, nothing new


def test_missing_or_edited_skill_is_reinstalled():
    home, proj = workspace()
    run(home, proj)
    dest = os.path.join(home, ".cursor", "skills")
    shutil.rmtree(os.path.join(dest, "agent-spec-ask"))
    with open(os.path.join(dest, "agent-spec-debt", "SKILL.md"), "a") as fh:
        fh.write("\nstale edit\n")
    code, out = run(home, proj, "--check")
    assert out["skills"] == "needed" and {"agent-spec-ask", "agent-spec-debt"} <= set(out["skill_gaps"]), out
    assert not os.path.isdir(os.path.join(dest, "agent-spec-ask")), "--check changes nothing"
    code, out = run(home, proj)
    assert code == 0 and out["skills"] == "installed", out
    assert os.path.isfile(os.path.join(dest, "agent-spec-ask", "SKILL.md"))
    assert "stale edit" not in open(os.path.join(dest, "agent-spec-debt", "SKILL.md")).read()
    assert automation_rows(proj)[-1]["name"] == "skills-sync"


def test_skill_sync_keeps_the_install_mode():
    """Review fix: a full install missing every SDLC design skill must not be re-installed lean."""
    home, proj = workspace()
    run(home, proj)
    dest = os.path.join(home, ".cursor", "skills")
    assert os.path.isfile(os.path.join(dest, "agent-spec-prd", "SKILL.md")), "the first sync is a full install"
    for name in ("agent-spec-prd", "agent-spec-hld", "agent-spec-lld", "agent-spec-intent",
                 "agent-spec-requirements", "agent-spec-tech-spec", "agent-spec-ask"):
        shutil.rmtree(os.path.join(dest, name), ignore_errors=True)
    code, out = run(home, proj)
    assert code == 0 and out["skills"] == "installed", out
    assert os.path.isfile(os.path.join(dest, "agent-spec-prd", "SKILL.md")), "no lean marker: a full install stays full"
    for name in ("agent-spec-prd", "agent-spec-hld", "agent-spec-lld", "agent-spec-intent",
                 "agent-spec-requirements", "agent-spec-tech-spec"):
        shutil.rmtree(os.path.join(dest, name))
    open(os.path.join(dest, ".algosec-agent-spec-lean"), "w").close()
    shutil.rmtree(os.path.join(dest, "agent-spec-ask"))
    code, out = run(home, proj)
    assert out["skills"] == "installed" and os.path.isfile(os.path.join(dest, ".algosec-agent-spec-lean")), out
    assert not os.path.isdir(os.path.join(dest, "agent-spec-prd")), "a lean install stays lean"


def test_dashboard_switch_turns_skills_sync_into_a_report():
    home, proj = workspace()
    run(home, proj)
    with open(os.path.join(proj, ".agent-spec", "automation.json"), "w") as fh:
        json.dump({"disabled": ["skills-sync"]}, fh)
    shutil.rmtree(os.path.join(home, ".cursor", "skills", "agent-spec-ask"))
    code, out = run(home, proj)
    assert out["skills"] == "needed" and not os.path.isdir(os.path.join(home, ".cursor", "skills", "agent-spec-ask"))


def test_stale_harness_is_re_registered():
    home, proj = workspace()
    run(home, proj)
    mdc = os.path.join(proj, ".cursor", "rules", "agent-spec.mdc")
    text = open(mdc).read()
    open(mdc, "w").write(re.sub(r"(?m)^version:.*$", "version: 0.0.1", text))
    code, out = run(home, proj)
    assert code == 0 and out["registered"] == "installed", out
    assert any("harness 0.0.1" in g for g in out["gaps"])


def test_missing_graph_is_rebuilt():
    home, proj = workspace()
    run(home, proj)
    os.remove(os.path.join(proj, ".agent-spec", "graph", "knowledge-graph.json"))
    code, out = run(home, proj)
    assert code == 0 and out["registered"] == "ok" and out["graph"] == "built", out
    assert automation_rows(proj)[-1]["name"] == "graph-refresh"


def test_dashboard_switch_turns_registration_into_a_report():
    home, proj = workspace()
    run(home, proj)
    with open(os.path.join(proj, ".agent-spec", "automation.json"), "w") as fh:
        json.dump({"disabled": ["register"]}, fh)
    os.remove(os.path.join(proj, ".cursor", "hooks.json"))
    code, out = run(home, proj)
    assert out["registered"] == "needed" and not os.path.exists(os.path.join(proj, ".cursor", "hooks.json")), out


def test_onboarded_project_has_no_next_step():
    home, proj = workspace()
    run(home, proj)
    os.remove(os.path.join(proj, ".agent-spec", ".onboarding-needed"))
    code, out = run(home, proj)
    assert out["onboard"] == "done" and out["next"] is None, out


def test_refuses_the_home_directory():
    home, _ = workspace()
    code, out = run(home, home, "--root", home)
    assert code == 1 and out["registered"] == "refused", out
    assert not os.path.exists(os.path.join(home, ".agent-spec"))




def test_unmarked_lean_install_stays_lean():
    """H-006: a lean install from before the markers keeps lean on the next skill sync."""
    home, proj = workspace()
    run(home, proj)
    dest = os.path.join(home, ".cursor", "skills")
    for marker in (".algosec-agent-spec-lean", ".algosec-agent-spec-full"):
        if os.path.exists(os.path.join(dest, marker)):
            os.remove(os.path.join(dest, marker))
    for name in ("agent-spec-prd", "agent-spec-hld", "agent-spec-lld", "agent-spec-intent",
                 "agent-spec-requirements", "agent-spec-tech-spec", "agent-spec-ask"):
        shutil.rmtree(os.path.join(dest, name), ignore_errors=True)
    code, out = run(home, proj)
    assert code == 0 and out["skills"] == "installed", out
    assert os.path.isfile(os.path.join(dest, "agent-spec-ask", "SKILL.md")), "drift still repaired"
    assert not os.path.isdir(os.path.join(dest, "agent-spec-prd")), "an unmarked lean install stays lean"
    assert os.path.isfile(os.path.join(dest, ".algosec-agent-spec-lean")), "the sync marks it from now on"


def test_full_install_writes_its_marker():
    home, proj = workspace()
    run(home, proj)
    dest = os.path.join(home, ".cursor", "skills")
    assert os.path.isfile(os.path.join(dest, ".algosec-agent-spec-full"))
    assert not os.path.exists(os.path.join(dest, ".algosec-agent-spec-lean"))


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print("ok", fn.__name__)
