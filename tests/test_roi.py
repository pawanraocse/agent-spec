#!/usr/bin/env python3
"""Tests for bin/agent-spec-roi.py (T-055): list, rollup math, CSV export, loopback viewer.

Run: python3 tests/test_roi.py
"""
import csv
import datetime
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import urllib.request
from http.server import HTTPServer

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROI = os.path.join(REPO_DIR, "bin", "agent-spec-roi.py")
spec = importlib.util.spec_from_file_location("roi", ROI)
roi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(roi)


def fixture():
    proj = tempfile.mkdtemp()
    d = os.path.join(proj, ".agent-spec", "metrics", "receipts")
    os.makedirs(d)
    now = datetime.datetime.now().replace(microsecond=0)

    def write(sid, days_ago, total_out, reads, graph, est):
        r = {"session_id": sid, "ts": (now - datetime.timedelta(days=days_ago)).isoformat(), "turns": 10,
             "tokens": {"input": 100, "output": total_out, "cache_read": 1000, "cache_write": 50, "estimated": est},
             "tool_calls_total": 7, "graph_queries": graph, "whole_file_reads": {"count": reads, "files": []},
             "facts_injected": 4, "gates": {"gate": 2}}
        json.dump(r, open(os.path.join(d, sid + ".json"), "w"))
    write("recent-a", 1, 200, 2, 4, True)
    write("recent-b", 3, 300, 0, 2, False)
    write("old-c", 20, 999, 9, 0, False)
    open(os.path.join(d, "broken.json"), "w").write("{not json")
    return proj


def run(proj, *args):
    return subprocess.run([sys.executable, ROI, "--project", proj, *args], capture_output=True, text=True)


def test_list_skips_broken_and_orders_newest_first():
    out = run(fixture(), "list")
    lines = out.stdout.strip().splitlines()
    assert out.returncode == 0 and len(lines) == 3, out.stdout
    assert "recent-a"[:8] in lines[0] and "old-c"[:8] in lines[2]


def test_rollup_math_over_window():
    proj = fixture()
    roll = roi.rollup(roi.within(roi.load_receipts(proj), 7))
    assert roll["sessions"] == 2, "20-day-old session is outside the window"
    assert roll["tokens_total"] == (100 + 200 + 1000 + 50) + (100 + 300 + 1000 + 50)
    assert roll["graph_queries"] == 6 and roll["whole_file_reads"] == 2
    assert roll["graph_queries_per_whole_file_read"] == 3.0
    assert roll["estimated_sessions"] == 1 and roll["avg_tokens_per_session"] == 1400
    empty = roi.rollup([])
    assert empty["sessions"] == 0 and empty["avg_tokens_per_session"] == 0


def test_csv_export():
    out = run(fixture(), "export", "--csv")
    rows = list(csv.DictReader(io.StringIO(out.stdout)))
    assert len(rows) == 3 and list(rows[0].keys()) == roi.COLUMNS
    assert rows[0]["session_id"] == "recent-a" and rows[0]["whole_file_reads"] == "2"


def test_viewer_serves_html_and_csv_on_loopback_only():
    proj = fixture()
    server = HTTPServer(("127.0.0.1", 0), roi.make_handler(proj, 7))
    assert server.server_address[0] == "127.0.0.1"
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = "http://127.0.0.1:%d" % server.server_address[1]
    try:
        page = urllib.request.urlopen(base + "/").read().decode()
        assert "agent-spec receipts" in page and "recent-a" in page and "Last 7 days" in page
        assert urllib.request.urlopen(base + "/export.csv").read().decode().startswith("ts,session_id")
        try:
            urllib.request.urlopen(base + "/etc/passwd")
            assert False, "unknown path must 404"
        except urllib.error.HTTPError as e:
            assert e.code == 404
    finally:
        server.shutdown()


def test_no_receipts_message():
    out = run(tempfile.mkdtemp(), "list")
    assert out.returncode == 0 and "no receipts yet" in out.stdout


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print("  ok", fn.__name__)
    print("%d roi tests passed" % len(tests))
