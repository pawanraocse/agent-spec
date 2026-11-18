#!/usr/bin/env python3
"""H-053: timed dry run of the 5-minute demo, with the network off.

    python3 examples/mesh-demo/demo-dryrun.py [--runs 2] [--demo-dir DIR] [--allow-network]

Each run builds the demo with demo-setup.sh in a fresh DEMO_DIR, under a temporary HOME (the
real registry is never touched), then drives every beat of demo.md the way the presenter
does: the same shell commands, and the same dashboard calls the buttons make, against a real
server on loopback. Every beat is timed and checked; a failed check stops the run and names
the beat.

Network off: on Linux the script re-runs itself inside a new user and network namespace
(`unshare -rn`), where only loopback exists, so any beat that reaches the network fails. Where
that is not possible it says so, and the run is not counted as offline.

What it does not cover: the presenter's own timing and talk track. The demo row (H-053) still
asks for two dry runs by a person on the demo machine; this script is the check to run before each.
"""
from __future__ import annotations

import argparse
import http.client
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SETUP = os.path.join(HERE, "demo-setup.sh")
SESSION = "conv-recorded-1"


class BeatFailed(Exception):
    pass


def check(cond, msg):
    if not cond:
        raise BeatFailed(msg)


def sh(cmd, cwd, env, timeout=300):
    proc = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
    check(proc.returncode == 0, "%s exited %d: %s" % (" ".join(cmd[:3]), proc.returncode, proc.stderr[-400:]))
    return proc.stdout


class Dashboard:
    """The real dashboard server on an ephemeral loopback port, called like the UI calls it."""

    def __init__(self, hub):
        sys.path.insert(0, os.path.join(hub, ".agent-spec", "bin"))
        from aspec_platform import serve
        self.httpd, self.token = serve.make_server(hub, "127.0.0.1", 0)
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def call(self, method, path, body=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=60)
        headers = {"Host": "127.0.0.1:%d" % self.port, "X-Agent-Spec-Token": self.token}
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers.update({"Content-Type": "application/json", "Origin": "http://127.0.0.1:%d" % self.port})
        conn.request(method, path, body=data, headers=headers)
        resp = conn.getresponse()
        raw = resp.read()
        conn.close()
        check(resp.status == 200, "%s %s -> %d %s" % (method, path, resp.status, raw[:300]))
        return json.loads(raw)

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def run_once(demo, env):
    beats = []

    def beat(name, fn):
        t0 = time.monotonic()
        try:
            note = fn()
        except BeatFailed as exc:
            beats.append({"beat": name, "ok": False, "seconds": round(time.monotonic() - t0, 2), "error": str(exc)})
            raise
        beats.append({"beat": name, "ok": True, "seconds": round(time.monotonic() - t0, 2), "note": note})

    hub = os.path.join(demo, "orders-api")
    py = sys.executable
    state = {}

    def setup():
        out = sh(["bash", SETUP, demo], HERE, env, timeout=600)
        check("7/7" in out, "setup did not reach 7/7")
        return out.strip().splitlines()[-1]

    def install():
        hooks = os.listdir(os.path.join(hub, ".cursor", "hooks"))
        tools = os.listdir(os.path.join(hub, ".agent-spec", "bin"))
        check(hooks and tools, "no hooks or no harness bin in the project")
        return "%d hooks, %d harness files" % (len(hooks), len(tools))

    def digest():
        out = sh([py, ".agent-spec/bin/agent-spec-digest.py"], hub, env)
        check("stack:" in out, "digest has no stack line")
        check("ONBOARDING NEEDED" not in out, "digest on stage is an onboarding notice")
        check("routes are a public contract" in out, "digest does not carry the seeded fact")
        return "%d bytes" % len(out.encode())

    def blast():
        out = sh([py, ".agent-spec/bin/graphify-mesh.py", "query", "--file", "orders-api:orders_api/routes.py"], hub, env)
        check("shop-ui" in out, "mesh query does not name shop-ui")
        rec = json.loads(sh([py, ".agent-spec/bin/agent-spec-recall.py", "worker processes orders.created twice",
                             "--json", "--no-log"], hub, env))["matches"]
        check(rec and rec[0]["citation"] == "orders-worker:.agent-spec/experience.jsonl:1",
              "recall does not cite orders-worker")
        return rec[0]["citation"]

    def dashboard():
        state["ui"] = Dashboard(hub)
        return "port %d" % state["ui"].port

    def blocked():
        pending = state["ui"].call("GET", "/api/risk")["pending"]
        check([p["file"] for p in pending] == ["orders_api/routes.py"], "Risk does not list routes.py: %r" % pending)
        state["risk_key"] = pending[0]["key"]
        return "tier %s, %s" % (pending[0].get("tier"), pending[0]["file"])

    def approve():
        out = state["ui"].call("POST", "/api/risk", {"key": state["risk_key"], "decision": "approve"})
        check(out["ok"] and not out["risk"]["pending"], "approval did not clear the pending action")
        log = os.path.join(hub, ".agent-spec", "metrics", "risk.jsonl")
        check(os.path.isfile(log) and "dashboard" in open(log, encoding="utf-8").read(), "no audited decision row")
        return "approved, audited in metrics/risk.jsonl"

    def impact():
        reqs = state["ui"].call("GET", "/api/requests?session=%s" % SESSION)
        rows = reqs.get("requests") or reqs.get("items") or []
        check(rows, "no request for %s" % SESSION)
        detail = state["ui"].call("GET", "/api/requests/%s" % rows[0]["trace_id"])
        imp = detail.get("impact") or {}
        check("error" not in imp, "Impact tab errors: %s" % imp.get("error"))
        mem = imp.get("memory") or {}
        check(mem.get("recorded"), "Impact has no injection record for %s" % SESSION)
        subjects = [f.get("subject") for f in mem.get("facts") or []]
        check("routes are a public contract" in subjects, "Impact does not list the injected fact: %r" % subjects)
        return "%s digest bytes, facts %s" % (mem.get("digest_bytes"), subjects)

    def proposal():
        props = state["ui"].call("GET", "/api/proposals")["pending"]
        facts = [p for p in props if p["kind"] == "fact"]
        check(facts, "no pending fact proposal")
        out = state["ui"].call("POST", "/api/proposals", {"kind": "fact", "id": facts[0]["id"], "decision": "approve"})
        check(out.get("ok"), "approve failed: %r" % out)
        listed = sh([py, ".agent-spec/bin/agent-spec-memory.py", "list"], hub, env)
        check("order ids are idempotency keys" in listed, "approved fact is not in memory")
        return "approved: " + facts[0]["title"][:60]

    def audit():
        out = state["ui"].call("GET", "/api/audit-export?session=%s" % SESSION)
        check(out["verify"]["ok"], "fresh export does not verify")
        path = os.path.join(demo, "audit.jsonl")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(out["jsonl"])
        sh([py, ".agent-spec/bin/agent-spec-platform.py", "audit", "--verify", path], hub, env)
        lines = out["jsonl"].splitlines()
        row = json.loads(lines[1])
        row["edited_after_export"] = True
        lines[1] = json.dumps(row, sort_keys=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        bad = subprocess.run([py, ".agent-spec/bin/agent-spec-platform.py", "audit", "--verify", path], cwd=hub,
                             env=env, capture_output=True, text=True)
        check(bad.returncode == 1, "an edited export still verifies")
        return "%d lines; an edited line is caught" % out["lines"]

    try:
        for name, fn in (("setup (off stage)", setup), ("install", install), ("digest", digest),
                         ("cross-repo blast radius + recall", blast), ("dashboard up", dashboard),
                         ("tier-3 edit blocked", blocked), ("approved in the dashboard", approve),
                         ("impact", impact), ("learning proposal approved", proposal), ("audit export", audit)):
            beat(name, fn)
    except BeatFailed:
        pass
    finally:
        if "ui" in state:
            state["ui"].close()
    return beats


def offline_reexec(argv):
    """Re-run inside `unshare -rn` with loopback up. Returns an exit code, or None to run here."""
    if os.environ.get("AGENT_SPEC_DRYRUN_NETNS") or not sys.platform.startswith("linux") or not shutil.which("unshare"):
        return None
    inner = "ip link set lo up 2>/dev/null || true; exec %s %s" % (
        sys.executable, " ".join("'%s'" % a.replace("'", "'\\''") for a in [os.path.abspath(__file__)] + argv))
    env = dict(os.environ, AGENT_SPEC_DRYRUN_NETNS="1")
    probe = subprocess.run(["unshare", "-rn", "true"], capture_output=True)
    if probe.returncode != 0:
        return None
    return subprocess.call(["unshare", "-rn", "sh", "-c", inner], env=env)


def network_is_off():
    import socket
    try:
        socket.create_connection(("1.1.1.1", 53), timeout=2).close()
        return False
    except OSError:
        return True


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--runs", type=int, default=2)
    ap.add_argument("--demo-dir", default=None, help="default: a new temporary directory per run")
    ap.add_argument("--allow-network", action="store_true", help="skip the network namespace")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    if not args.allow_network:
        code = offline_reexec(argv)
        if code is not None:
            return code
    offline = network_is_off()
    results, failed = [], False
    for n in range(1, max(1, args.runs) + 1):
        tmp = tempfile.mkdtemp(prefix="aspec-dryrun-")
        home = os.path.join(tmp, "home")
        os.makedirs(home)
        demo = args.demo_dir or os.path.join(tmp, "demo")
        env = dict(os.environ, HOME=home, AGENT_SPEC_CURSOR_STORE="0", AGENT_SPEC_CONSOLE="0")
        env.pop("AGENT_SPEC_DB", None)
        os.environ.update(HOME=home, AGENT_SPEC_CURSOR_STORE="0")  # the in-process dashboard reads these
        t0 = time.monotonic()
        try:
            beats = run_once(demo, env)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        ok = all(b["ok"] for b in beats) and len(beats) == 10
        failed = failed or not ok
        results.append({"run": n, "ok": ok, "offline": offline, "seconds": round(time.monotonic() - t0, 1), "beats": beats})
        if not args.json:
            print("run %d: %s in %.1fs (%s)" % (n, "PASS" if ok else "FAIL", results[-1]["seconds"],
                                                 "network off" if offline else "NETWORK ON"))
            for b in beats:
                print("  %-34s %6.2fs  %s" % (b["beat"], b["seconds"], b.get("note") if b["ok"] else "FAILED: " + b["error"]))
        if not ok:
            break
    if args.json:
        print(json.dumps(results, indent=1))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
