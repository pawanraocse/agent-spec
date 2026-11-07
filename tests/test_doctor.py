#!/usr/bin/env python3
"""Tests for agent-spec-doctor.py and the install flows it checks (T-005, T-022, T-030,
T-031, T-054, T-004).

Run: python3 tests/test_doctor.py
Each test installs into a throwaway HOME and project, so nothing real is touched.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INSTALL = os.path.join(REPO_DIR, "install.sh")


class Sandbox:
    def __init__(self, git=False):
        self.root = tempfile.mkdtemp()
        self.home = os.path.join(self.root, "home")
        self.proj = os.path.join(self.root, "proj")
        os.makedirs(os.path.join(self.home, ".cursor"))
        os.makedirs(self.proj)
        with open(os.path.join(self.proj, "app.py"), "w") as fh:
            fh.write("import os\n")
        if git:
            subprocess.run(["git", "init", "-q"], cwd=self.proj, check=True)
        self.env = dict(os.environ, HOME=self.home)
        self.env.pop("WIN_CURSOR_HOME", None)

    def sh(self, *args, cwd=None):
        return subprocess.run(["bash", INSTALL, *args], cwd=cwd or self.root,
                              capture_output=True, text=True, env=self.env)

    def install(self, *args):
        res = self.sh("--register", self.proj, *args)
        assert res.returncode == 0, res.stdout + res.stderr
        return res

    def doctor(self, *args):
        script = os.path.join(self.proj, ".agent-spec", "bin", "agent-spec-doctor.py")
        return subprocess.run([sys.executable, script, *args], cwd=self.proj,
                              capture_output=True, text=True, env=self.env)

    def status(self):
        res = self.doctor("--json")
        return {c["id"] + ":" + c["message"][:30]: c["status"] for c in json.loads(res.stdout)["checks"]}, \
            json.loads(res.stdout)

    def statuses(self, ident):
        _, data = self.status()
        return [c for c in data["checks"] if c["id"] == ident]

    def close(self):
        shutil.rmtree(self.root, ignore_errors=True)


def test_doctor_green_after_register():
    sb = Sandbox(git=True)
    try:
        install = sb.install()
        assert "Doctor" in install.stdout, "register must run the doctor (T-054)"
        res = sb.doctor("--strict")
        assert res.returncode == 0, res.stdout + res.stderr
        assert "green" in res.stdout
        assert "always-on ~" in res.stdout and "tokens/turn" in res.stdout, "footprint line missing"
    finally:
        sb.close()


def test_doctor_fails_with_fix_when_hooks_removed():
    sb = Sandbox()
    try:
        sb.install()
        os.remove(os.path.join(sb.proj, ".cursor", "hooks.json"))
        res = sb.doctor()
        assert res.returncode == 1, res.stdout
        assert "hooks.json missing" in res.stdout
        assert "install.sh --register" in res.stdout, "must print the fix command"
    finally:
        sb.close()


def test_doctor_detects_duplicate_session_handler():
    sb = Sandbox()
    try:
        sb.install()
        path = os.path.join(sb.proj, ".cursor", "hooks.json")
        data = json.load(open(path))
        data["hooks"]["sessionStart"].append(dict(data["hooks"]["sessionStart"][0]))
        json.dump(data, open(path, "w"))
        res = sb.doctor()
        assert res.returncode == 1 and "2 agent-spec handlers" in res.stdout, res.stdout
    finally:
        sb.close()


def test_doctor_version_drift_warns():
    sb = Sandbox()
    try:
        sb.install()
        mdc = os.path.join(sb.proj, ".cursor", "rules", "agent-spec.mdc")
        import re
        text = re.sub(r"(?m)^version:.*$", "version: 0.0.1", open(mdc).read(), count=1)
        open(mdc, "w").write(text)
        res = sb.doctor()
        assert "harness 0.0.1 but package is" in res.stdout, res.stdout
        assert res.returncode == 0, "drift is WARN, not FAIL"
        assert sb.doctor("--strict").returncode == 1
    finally:
        sb.close()


def test_doctor_unregistered_workspace_warns():
    sb = Sandbox()
    try:
        sb.install()
        os.remove(os.path.join(sb.home, ".cursor", "skills", ".algosec-agent-spec-projects"))
        res = sb.doctor()
        assert "not in the registry" in res.stdout, res.stdout
    finally:
        sb.close()


def test_doctor_post_rewrite_missing_warns():
    sb = Sandbox(git=True)
    try:
        sb.install()
        hook = subprocess.run(["git", "rev-parse", "--git-path", "hooks"], cwd=sb.proj,
                              capture_output=True, text=True).stdout.strip()
        hook = hook if os.path.isabs(hook) else os.path.join(sb.proj, hook)
        os.remove(os.path.join(hook, "post-rewrite"))
        res = sb.doctor()
        assert "predates post-rewrite" in res.stdout, res.stdout
    finally:
        sb.close()


def test_doctor_graph_stale_warns_with_manual_path():
    sb = Sandbox()
    try:
        sb.install()
        status = os.path.join(sb.proj, ".agent-spec", "graph", ".status.json")
        json.dump({"state": "ok", "finished": "2020-01-01T00:00:00", "reparsed": 0, "files": 1},
                  open(status, "w"))
        res = sb.doctor()
        assert "graph last built" in res.stdout and "agent-spec-index" in res.stdout, res.stdout
    finally:
        sb.close()


def test_doctor_team_yaml_errors_warn():
    sb = Sandbox()
    try:
        sb.install()
        open(os.path.join(sb.proj, ".agent-spec", "team.yaml"), "w").write(
            "sdlc_track: warp-speed\nbogus: 1\n")
        res = sb.doctor()
        assert "team.yaml:" in res.stdout and "invalid value for sdlc_track" in res.stdout, res.stdout
    finally:
        sb.close()


def test_doctor_lean_coexistence_warns():
    sb = Sandbox()
    try:
        sb.install()
        rules = os.path.join(sb.proj, ".cursor", "rules")
        open(os.path.join(rules, "algosec-lean.mdc"), "w").write("---\nalwaysApply: true\n---\nbe terse\n")
        res = sb.doctor()
        assert "algosec-lean is Always Apply" in res.stdout, res.stdout
    finally:
        sb.close()


def test_doctor_line_mode():
    sb = Sandbox()
    try:
        sb.install()
        ok = sb.doctor("--line")
        assert ok.returncode == 0 and ok.stdout.startswith("doctor: OK"), ok.stdout
        os.remove(os.path.join(sb.proj, ".cursor", "hooks.json"))
        bad = sb.doctor("--line")
        assert bad.returncode == 0, "--line must always exit 0 (digest is fail-open)"
        assert bad.stdout.startswith("doctor: 1 issue(s)") and "fix:" in bad.stdout, bad.stdout
    finally:
        sb.close()


def test_doctor_non_project_fails():
    with tempfile.TemporaryDirectory() as t:
        res = subprocess.run([sys.executable, os.path.join(REPO_DIR, "bin", "agent-spec-doctor.py"),
                              "--project", t], capture_output=True, text=True)
        assert res.returncode == 1 and "no .agent-spec/" in res.stdout, res.stdout


def test_register_here_uses_cwd_without_git():
    sb = Sandbox()
    try:
        res = sb.sh("--register-here", cwd=sb.proj)
        assert res.returncode == 0, res.stdout + res.stderr
        assert os.path.isfile(os.path.join(sb.proj, ".cursor", "hooks.json"))
        reg = open(os.path.join(sb.home, ".cursor", "skills", ".algosec-agent-spec-projects")).read()
        assert os.path.realpath(sb.proj) in [os.path.realpath(l) for l in reg.split()], reg
    finally:
        sb.close()


def test_register_here_uses_git_root_from_subdir():
    sb = Sandbox(git=True)
    try:
        sub = os.path.join(sb.proj, "src", "deep")
        os.makedirs(sub)
        res = sb.sh("--register-here", cwd=sub)
        assert res.returncode == 0, res.stdout + res.stderr
        assert os.path.isfile(os.path.join(sb.proj, ".cursor", "hooks.json")), "must register git root"
        assert not os.path.exists(os.path.join(sub, ".cursor"))
    finally:
        sb.close()


def test_onboarding_flag_lifecycle():
    sb = Sandbox()
    try:
        sb.install()
        flag = os.path.join(sb.proj, ".agent-spec", ".onboarding-needed")
        assert os.path.exists(flag), "first register must create the flag"
        digest = os.path.join(sb.proj, ".agent-spec", "bin", "agent-spec-digest.py")
        out = subprocess.run([sys.executable, digest], cwd=sb.proj, capture_output=True, text=True).stdout
        assert "run `/agent-spec-onboard` now" in out, out
        # Onboarding finished: constitution filled in, flag removed. Re-register must not resurrect it.
        open(os.path.join(sb.proj, ".agent-spec", "CONSTITUTION.md"), "w").write("# Constitution\nJava 17.\n")
        os.remove(flag)
        sb.install()
        assert not os.path.exists(flag), "re-register must not recreate the flag after onboarding"
        # A lightly edited constitution (1 leftover example) counts as onboarded.
        open(os.path.join(sb.proj, ".agent-spec", "CONSTITUTION.md"), "w").write(
            "# Constitution\nJava 17.\nRule: e.g. [e.g., Jackson]\n")
        sb.install()
        assert not os.path.exists(flag), "1 leftover placeholder must not re-flag onboarding"
        # An untouched template means onboarding never happened.
        shutil.copy(os.path.join(REPO_DIR, "templates", "project-constitution.md"),
                    os.path.join(sb.proj, ".agent-spec", "CONSTITUTION.md"))
        sb.install()
        assert os.path.exists(flag), "untouched template must re-flag onboarding"
    finally:
        sb.close()


def test_check_install_flags_version_drift():
    sb = Sandbox()
    try:
        sb.install()
        check = os.path.join(REPO_DIR, "check-install.sh")
        good = subprocess.run(["bash", check, sb.proj], capture_output=True, text=True, env=sb.env)
        assert "OK: harness version" in good.stdout, good.stdout
        mdc = os.path.join(sb.proj, ".cursor", "rules", "agent-spec.mdc")
        text = open(mdc).read()
        import re
        open(mdc, "w").write(re.sub(r"(?m)^version:.*$", "version: 0.0.1", text, count=1))
        bad = subprocess.run(["bash", check, sb.proj], capture_output=True, text=True, env=sb.env)
        assert bad.returncode == 1 and "harness 0.0.1 but package is" in bad.stdout, bad.stdout
    finally:
        sb.close()


def test_doctor_warns_when_session_end_hook_missing():
    sb = Sandbox()
    try:
        sb.install()
        hooks = os.path.join(sb.proj, ".cursor", "hooks.json")
        cfg = json.load(open(hooks))
        assert {"sessionEnd", "stop"} <= set(cfg["hooks"]), "register must add receipt hooks (T-051)"
        for event in ("sessionEnd", "stop"):
            del cfg["hooks"][event]
        json.dump(cfg, open(hooks, "w"))
        res = sb.doctor()
        assert "session-end receipt hook not registered" in res.stdout, res.stdout
        assert res.returncode == 0, "missing receipt hook is WARN, not FAIL"
        assert sb.doctor("--strict").returncode == 1
        assert os.path.isfile(os.path.join(sb.proj, ".agent-spec", "bin", "agent-spec-receipt.py"))
    finally:
        sb.close()


def test_mcp_schema_bloat_audit_warns_when_over_budget():
    sb = Sandbox()
    try:
        sb.install()
        cursor_dir = os.path.join(sb.proj, ".cursor")
        # 20 KB of schema (~5,000 tokens, exceeds 4,000 token limit)
        giant_schema = {"mcpServers": {"bloated": {"tools": [{"name": "t%d" % i, "description": "x" * 200} for i in range(100)]}}}
        with open(os.path.join(cursor_dir, "mcp.json"), "w") as fh:
            json.dump(giant_schema, fh)
        res = sb.doctor("--json")
        data = json.loads(res.stdout)
        mcp_checks = [c for c in data["checks"] if c["id"] == "mcp"]
        assert len(mcp_checks) == 1, mcp_checks
        assert mcp_checks[0]["status"] == "WARN", mcp_checks
        assert "exceeding 4000 token limit" in mcp_checks[0]["message"], mcp_checks
        assert sb.doctor("--strict").returncode == 1
    finally:
        sb.close()


def test_mcp_schema_within_budget_ok():
    sb = Sandbox()
    try:
        sb.install()
        cursor_dir = os.path.join(sb.proj, ".cursor")
        small_schema = {"mcpServers": {"lean": {"command": "node", "args": ["server.js"]}}}
        with open(os.path.join(cursor_dir, "mcp.json"), "w") as fh:
            json.dump(small_schema, fh)
        res = sb.doctor("--json")
        data = json.loads(res.stdout)
        mcp_checks = [c for c in data["checks"] if c["id"] == "mcp"]
        assert len(mcp_checks) == 1, mcp_checks
        assert mcp_checks[0]["status"] == "OK", mcp_checks
    finally:
        sb.close()


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print("  ok", fn.__name__)
    print("%d doctor/install tests passed" % len(tests))
