#!/usr/bin/env python3
"""Tests for bin/agent-spec-ensure.py (HA-005): register, index and report onboarding for the
project in the current directory, from any project, in one command.

Run: python3 tests/test_ensure.py
"""
import json
import re
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
    rows = automation_rows(proj)
    assert len(rows) == 1 and rows[0]["name"] == "register" and rows[0]["status"] == "installed", rows
    code, again = run(home, proj)
    assert again["registered"] == "ok" and "gaps" not in again, "second run is a no-op"
    assert len(automation_rows(proj)) == 1


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


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print("ok", fn.__name__)
