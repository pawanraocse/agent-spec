#!/usr/bin/env python3
"""agent-spec-ensure.py — make the project in the current directory ready, then say what is left (HA-005).

A skill that runs from a project that was never registered, or was registered by an older
package, used to depend on the model reading a sentence and running the installer itself.
This does the deterministic part in one command and leaves only the AI step to the model:

  1. registration — `.agent-spec/bin`, the hooks in `.cursor/hooks.json` and the rules file
     present, and the rules file stamped with the package's VERSION. If not, run
     `install.sh --project-only --register <root>` from the package clone.
  2. graph — `.agent-spec/graph/knowledge-graph.json` present. If not, build it.
  3. onboarding — `.agent-spec/.onboarding-needed` (the installer's flag). Reported, never
     run: onboarding is a skill, so `next` names it for the model.

Run it with the clone's path, since an unregistered project has no copy of its own:

  python3 "$(cat ~/.cursor/skills/.algosec-agent-spec-root)/bin/agent-spec-ensure.py"
  ... --check   report only, change nothing (also AGENT_SPEC_AUTO_REGISTER=0)

Prints ONE JSON object. Exit 0 when the project is ready or was made ready, 1 when a step
failed or was refused. Never installs into the home directory or the filesystem root.
Allowed-code reason: plumbing (DEC-15). Stdlib only.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
INSTALL_TIMEOUT_S = 180
BUILD_TIMEOUT_S = 120
SESSION_HOOK = "agent-spec-session-start"


def project_root(cwd):
    try:
        out = subprocess.run(["git", "-C", cwd, "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, timeout=5)
        if out.returncode == 0 and out.stdout.strip():
            return os.path.realpath(out.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        pass
    return os.path.realpath(cwd)


def package_dir():
    """This script's clone when it has VERSION and install.sh, else the installer's marker."""
    parent = os.path.dirname(HERE)
    if os.path.isfile(os.path.join(parent, "VERSION")) and os.path.isfile(os.path.join(parent, "install.sh")):
        return parent
    marker = os.path.join(os.path.expanduser("~"), ".cursor", "skills", ".algosec-agent-spec-root")
    try:
        root = open(marker, encoding="utf-8").read().strip()
    except OSError:
        return None
    return root if os.path.isfile(os.path.join(root, "install.sh")) else None


def read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def registration_gaps(root, package):
    """Why this project needs (re-)registering; empty when it does not."""
    gaps = []
    if not os.path.isfile(os.path.join(root, ".agent-spec", "bin", "agent-spec-digest.py")):
        gaps.append("no .agent-spec/bin")
    if SESSION_HOOK not in read(os.path.join(root, ".cursor", "hooks.json")):
        gaps.append("hooks not merged")
    mdc = read(os.path.join(root, ".cursor", "rules", "agent-spec.mdc"))
    if not mdc:
        gaps.append("no rules file")
    elif package:
        have = re.search(r"(?m)^version:\s*(\S+)", mdc)
        want = read(os.path.join(package, "VERSION")).strip()
        if want and (not have or have.group(1) != want):
            gaps.append("harness %s, package %s" % (have.group(1) if have else "unstamped", want))
    return gaps


def enabled(root, name):
    """Off when the dashboard's Automations panel lists it in .agent-spec/automation.json."""
    try:
        with open(os.path.join(root, ".agent-spec", "automation.json"), encoding="utf-8") as fh:
            return name not in (json.load(fh).get("disabled") or [])
    except (OSError, ValueError, AttributeError):
        return True


def log_event(root, row):
    """One row in metrics/automation.jsonl (HA-006), so the dashboard shows what ran and why.
    Not events.jsonl: the trace builder would turn these rows into conversations."""
    if not os.path.isdir(os.path.join(root, ".agent-spec")):
        return
    metrics = os.path.join(root, ".agent-spec", "metrics")
    try:
        os.makedirs(metrics, exist_ok=True)
        row = dict({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "source": "ensure"}, **row)
        with open(os.path.join(metrics, "automation.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, separators=(",", ":")) + "\n")
    except OSError:
        pass


def tail(text, lines=6):
    return "\n".join((text or "").strip().splitlines()[-lines:])


def ensure(root, check_only):
    out = {"root": root, "registered": "ok", "graph": "ok", "onboard": "done", "next": None}
    home = os.path.realpath(os.path.expanduser("~"))
    if root in (home, os.path.realpath(os.sep)):
        out.update(registered="refused", error="%s is the home directory or filesystem root; "
                   "open a project folder" % root)
        return out, 1
    package = package_dir()
    gaps = registration_gaps(root, package)
    if gaps:
        out["gaps"] = gaps
        if check_only or not enabled(root, "register"):
            out["registered"] = "needed"
        elif not package:
            out.update(registered="failed", error="package clone not found: run ./install.sh from it once")
            return out, 1
        else:
            started = time.time()
            try:
                res = subprocess.run(["bash", os.path.join(package, "install.sh"), "--project-only",
                                      "--register", root], cwd=package, capture_output=True,
                                     text=True, timeout=INSTALL_TIMEOUT_S, stdin=subprocess.DEVNULL)
                ok = res.returncode == 0 and not registration_gaps(root, package)
                detail = tail(res.stdout + res.stderr)
            except (OSError, subprocess.SubprocessError) as exc:
                ok, detail = False, str(exc)
            out["registered"] = "installed" if ok else "failed"
            if not ok:
                out["error"] = detail
            log_event(root, {"name": "register", "status": out["registered"], "reason": "; ".join(gaps),
                             "duration_ms": int((time.time() - started) * 1000)})
            if not ok:
                return out, 1

    graph = os.path.join(root, ".agent-spec", "graph", "knowledge-graph.json")
    builder = os.path.join(root, ".agent-spec", "bin", "graphify-build.py")
    if not os.path.isfile(graph):
        if check_only or not os.path.isfile(builder) or not enabled(root, "graph-refresh"):
            out["graph"] = "needed"
        else:
            started = time.time()
            try:
                res = subprocess.run([sys.executable, builder, "--quiet"], cwd=root, capture_output=True,
                                     text=True, timeout=BUILD_TIMEOUT_S, stdin=subprocess.DEVNULL)
                out["graph"] = "built" if res.returncode == 0 and os.path.isfile(graph) else "failed"
            except (OSError, subprocess.SubprocessError):
                out["graph"] = "failed"
            log_event(root, {"name": "graph-refresh", "status": out["graph"], "reason": "no graph",
                             "duration_ms": int((time.time() - started) * 1000)})

    if os.path.exists(os.path.join(root, ".agent-spec", ".onboarding-needed")):
        out["onboard"] = "needed"
        out["next"] = "/agent-spec-onboard"
    failed = "failed" in (out["registered"], out["graph"])
    return out, 1 if failed else 0


def main(argv=None):
    p = argparse.ArgumentParser(description="Register, index and report onboarding for this project.")
    p.add_argument("--check", action="store_true", help="report only; change nothing")
    p.add_argument("--root", help="project directory (default: git root of the current directory)")
    args = p.parse_args(argv)
    check_only = args.check or os.environ.get("AGENT_SPEC_AUTO_REGISTER", "1") == "0"
    root = os.path.realpath(args.root) if args.root else project_root(os.getcwd())
    out, code = ensure(root, check_only)
    print(json.dumps(out))
    return code


if __name__ == "__main__":
    sys.exit(main())
