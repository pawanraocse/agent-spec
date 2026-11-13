#!/usr/bin/env python3
"""DV-003, DV-010..DV-013, DV-041, DV-050, DV-055, DV-056: trace model, ingest, read API, live stream."""
import http.client
import json
import os
import shutil
import sys
import tempfile
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TESTS_DIR)
from _api_support import ApiCase, REPO_DIR  # noqa: E402
from aspec_platform import cursor_sessions, db, ingest, observe, traces  # noqa: E402

FIXTURES = os.path.join(TESTS_DIR, "fixtures", "hooks")


def hook_rows(conv="conv-1", gen="gen-1", t0=1_700_000_000_000):
    """One request on the documented contract, as cursor-event.py writes it (ids fixed)."""
    ts = lambda off: traces.iso(t0 + off)  # noqa: E731
    base = {"conversation_id": conv, "generation_id": gen, "model": "m", "cursor_version": "2.1.0"}
    return [
        dict(base, id="e1", ts=ts(0), event="beforeSubmitPrompt", prompt="/agent-spec-investigate why", prompt_chars=27),
        dict(base, id="e2", ts=ts(1000), event="postToolUse", tool_name="Read", target="file_path=/p/a.py",
             ranged=False, input_bytes=20, output_bytes=900, duration_ms=200, status="ok"),
        dict(base, id="e3", ts=ts(1500), event="subagentStart", subagent_id="sub-1", subagent_type="agent-spec-search",
             task="find callers", task_bytes=12),
        dict(base, id="e4", conversation_id="sub-1", ts=ts(2500), event="postToolUse", tool_name="Grep",
             target="pattern=login", duration_ms=100, status="ok"),
        dict(base, id="e5", ts=ts(4000), event="subagentStop", subagent_type="agent-spec-search", task="find callers",
             status="completed", summary="3 callers", summary_bytes=9, duration_ms=2500, tool_call_count=1),
        dict(base, id="g1", ts=ts(4200), event="guard", decision="deny", rule="whole-file-read", tool_name="Read",
             target="big.py"),
        dict(base, id="e6", ts=ts(5000), event="postToolUseFailure", tool_name="Shell", target="command=npm test",
             duration_ms=600, status="error", error_message="exit 1", failure_type="error"),
        dict(base, id="e7", ts=ts(5200), event="afterFileEdit", file_path="/p/a.py", edit_count=1),
        dict(base, id="e8", ts=ts(6000), event="afterAgentResponse", text="done", text_chars=4),
        dict(base, id="e9", ts=ts(6100), event="stop", status="completed", loop_count=0),
    ]


class BuilderTest(unittest.TestCase):
    def test_hook_trace_tree(self):
        trs, spans = traces.build_from_events(hook_rows())
        self.assertEqual(len(trs), 1)
        t = trs[0]
        self.assertEqual((t["trace_id"], t["session_id"], t["status"], t["source"]), ("gen-1", "conv-1", "completed", "hook"))
        self.assertEqual(t["skills"], ["agent-spec-investigate"])
        self.assertEqual((t["tool_count"], t["subagent_count"], t["guard_count"], t["edit_count"]), (3, 1, 1, 1))
        self.assertEqual(t["duration_ms"], 6100)
        by = {s["span_id"]: s for s in spans}
        skill = "gen-1#skill:agent-spec-investigate"
        self.assertEqual(by[skill]["parent_span_id"], "gen-1#root")
        self.assertEqual(by["e2"]["parent_span_id"], skill)
        self.assertEqual(by["e2"]["duration_ms"], 200)
        self.assertEqual(by["e3"]["kind"], "subagent")
        self.assertEqual(by["e3"]["duration_ms"], 2500, "subagentStop duration_ms wins")
        self.assertEqual(by["e3"]["attributes"]["summary"], "3 callers")
        self.assertEqual(by["e4"]["parent_span_id"], "e3", "rows from the subagent's conversation nest under it")
        self.assertEqual(by["e4"]["trace_id"], "gen-1")
        self.assertEqual((by["g1"]["kind"], by["g1"]["status"]), ("guard", "blocked"))
        self.assertEqual(by["e6"]["status"], "error")
        self.assertEqual(by["e8"]["kind"], "response")
        self.assertEqual(by["e8"]["duration_ms"], 6000 - 5200, "response = gap since the previous step")

    def test_running_until_stop(self):
        trs, spans = traces.build_from_events(hook_rows()[:4])
        self.assertEqual(trs[0]["status"], "running")
        self.assertIsNone(next(s for s in spans if s["span_id"] == "e3")["end"])

    def test_without_generation_id_each_prompt_is_a_trace(self):
        rows = [dict(r, generation_id=None) for r in hook_rows()] + \
            [dict(r, generation_id=None, id=r["id"] + "b", ts=traces.iso(traces.ms(r["ts"]) + 60000)) for r in hook_rows()]
        trs, _ = traces.build_from_events(rows)
        self.assertEqual(sorted(t["trace_id"] for t in trs), ["conv-1:1", "conv-1:2"])

    def test_store_conversations(self):
        conv = {"composer_id": "c1", "name": "n", "workspace": "/w", "model": "m", "subagent_ids": ["c2"], "bubbles": [
            {"type": 1, "created": 1000, "text": "/agent-spec-review go"},
            {"type": 2, "created": 2000, "text": "", "tool": {"name": "read_file_v2", "status": "completed",
                                                               "params": "{\"targetFile\":\"skills/xy/SKILL.md\"}",
                                                               "params_bytes": 30, "result_bytes": 500}},
            {"type": 2, "created": 5000, "text": "answer"},
            {"type": 1, "created": 9000, "text": "second"},
        ]}
        child = {"composer_id": "c2", "name": "sub", "subagent_type": "explore", "subagent_ids": [], "bubbles": [
            {"type": 1, "created": 2500, "text": "task text"},
            {"type": 2, "created": 3000, "text": "", "tool": {"name": "grep", "status": "completed", "params": "p"}},
            {"type": 2, "created": 4000, "text": "summary"}]}
        trs, spans = traces.build_from_store([conv, child])
        self.assertEqual(sorted(t["trace_id"] for t in trs), ["cs:c1:1", "cs:c1:2"])
        first = next(t for t in trs if t["trace_id"] == "cs:c1:1")
        self.assertEqual(first["skills"], ["agent-spec-review", "xy"])
        self.assertEqual(first["provenance"], "estimated")
        sub = next(s for s in spans if s["kind"] == "subagent")
        self.assertEqual((sub["name"], sub["trace_id"], sub["attributes"]["summary"]), ("explore", "cs:c1:1", "summary"))
        grep = next(s for s in spans if s["name"] == "grep")
        self.assertEqual(grep["parent_span_id"], sub["span_id"])
        read = next(s for s in spans if s["name"] == "read_file_v2")
        self.assertEqual(read["duration_ms"], 3000, "estimated as the gap to the next message")

    def test_lag_percentiles(self):
        self.assertEqual(traces._pct([10, 20, 30, 40], 0.5), 25)
        self.assertIsNone(traces._pct([], 0.5))


class ResolverTest(unittest.TestCase):
    def test_candidates_per_os(self):
        mac = cursor_sessions.user_dir_candidates({}, "darwin", "/Users/u", False)
        self.assertEqual(mac, ["/Users/u/Library/Application Support/Cursor/User"])
        win = cursor_sessions.user_dir_candidates({"APPDATA": r"C:\Users\u\AppData\Roaming"}, "win32", "/h", False)
        self.assertTrue(win[0].startswith(r"C:\Users\u\AppData\Roaming") and win[0].endswith(os.path.join("Cursor", "User")))
        linux = cursor_sessions.user_dir_candidates({}, "linux", "/home/u", False)
        self.assertEqual(linux, ["/home/u/.config/Cursor/User"])
        wsl = cursor_sessions.user_dir_candidates({"USER": "u"}, "linux", "/home/u", True)
        self.assertEqual(wsl[:2], ["/home/u/.config/Cursor/User", "/mnt/c/Users/u/AppData/Roaming/Cursor/User"])
        override = cursor_sessions.user_dir_candidates({"AGENT_SPEC_CURSOR_USER_DIR": "/x"}, "linux", "/h", False)
        self.assertEqual(override[0], "/x")

    def test_override_dir_is_used_when_store_exists(self):
        d = tempfile.mkdtemp()
        os.makedirs(os.path.join(d, "globalStorage"))
        open(os.path.join(d, "globalStorage", "state.vscdb"), "w").close()
        self.assertEqual(cursor_sessions.cursor_user_dir({"AGENT_SPEC_CURSOR_USER_DIR": d}, "linux", "/nohome", False), d)
        self.assertIsNone(cursor_sessions.cursor_user_dir({}, "linux", "/nohome", False))

    def test_folder_uris(self):
        f = cursor_sessions.folder_path
        self.assertEqual(f("vscode-remote://wsl%2Bubuntu-22.04/home/u/p"), "/home/u/p")
        self.assertEqual(f("file://wsl.localhost/Ubuntu-22.04/home/u/p"), "/home/u/p")
        self.assertEqual(f("file:///home/u/p"), "/home/u/p")
        self.assertEqual(cursor_sessions._unc_to_path(r"\\wsl.localhost\Ubuntu\home\u\p"), "/home/u/p")


class IngestTest(unittest.TestCase):
    def setUp(self):
        self.project = tempfile.mkdtemp()
        metrics = os.path.join(self.project, ".agent-spec", "metrics")
        os.makedirs(metrics)
        with open(os.path.join(metrics, "events.jsonl"), "w") as fh:
            for r in hook_rows():
                fh.write(json.dumps(r) + "\n")
        self.env = dict(os.environ)
        os.environ["AGENT_SPEC_CURSOR_STORE"] = "0"
        os.environ["AGENT_SPEC_DB"] = os.path.join(self.project, "p.db")
        self.addCleanup(self._restore)

    def _restore(self):
        os.environ.clear()
        os.environ.update(self.env)

    def test_ingest_persists_hook_traces_idempotently(self):
        for _ in range(2):
            rep = ingest.run(self.project, ["traces"])
        self.assertEqual(rep["traces"]["hook_traces"], 1)
        conn = db.connect(os.environ["AGENT_SPEC_DB"], readonly=True)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM traces").fetchone()[0], 1)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM spans WHERE kind='subagent'").fetchone()[0], 1)
        self.assertEqual(db.schema_version(conn), db.SCHEMA_VERSION)

    def test_run_joins_its_request(self):
        rd = os.path.join(self.project, ".agent-spec", "runs", "r1")
        os.makedirs(rd)
        with open(os.path.join(rd, "run.json"), "w") as fh:
            json.dump({"run_id": "r1", "workflow_id": "wf-rca", "status": "success", "generation_id": "gen-1",
                       "started": "2023-11-14T22:13:21Z", "finished": "2023-11-14T22:13:25Z"}, fh)
        with open(os.path.join(rd, "result.json"), "w") as fh:
            json.dump({"steps": {"collect": {"status": "success", "attempts": 1}}}, fh)
        ingest.run(self.project, ["runs", "traces"])
        conn = db.connect(os.environ["AGENT_SPEC_DB"], readonly=True)
        trs, spans = traces.all_traces(self.project, conn)
        self.assertEqual([t["trace_id"] for t in trs], ["gen-1"], "the run trace folds into its request")
        wf = next(s for s in spans if s["kind"] == "workflow")
        self.assertEqual((wf["trace_id"], wf["parent_span_id"]), ("gen-1", "gen-1#root"))
        self.assertTrue(any(s["kind"] == "run_step" and s["name"] == "collect" for s in spans))


class LearningTest(unittest.TestCase):
    """DV-050: fixed fixtures, exact counts."""

    def setUp(self):
        self.project = tempfile.mkdtemp()
        spec = os.path.join(self.project, ".agent-spec")
        os.makedirs(os.path.join(spec, "metrics", "reviews"))
        os.makedirs(os.path.join(spec, "memory", "facts"))
        for i, (day, cats) in enumerate([("2026-10-01", ["whole_file_read", "whole_file_read"]),
                                         ("2026-10-02", ["whole_file_read"]),
                                         ("2026-10-10", ["slow_tool"]),
                                         ("2026-10-11", [])]):
            with open(os.path.join(spec, "metrics", "reviews", "s%d.json" % i), "w") as fh:
                json.dump({"conversation_id": "s%d" % i, "session_started": day + "T10:00:00Z", "grade": "B",
                           "rubric_version": "2.0.0", "findings": [{"category": c, "severity": "high", "title": c,
                                                                    "span_id": "x", "fix_prompt": "/fix " + c}
                                                                   for c in cats]}, fh)
        with open(os.path.join(spec, "memory", "facts", "f1.md"), "w") as fh:
            fh.write("---\nid: f1\ntype: constraint\nsubject: input discipline\ncreated: 2026-10-05\n"
                     "addresses: whole_file_read\n---\nQuery the graph first.\n")
        with open(os.path.join(spec, "memory", "facts", "f2.md"), "w") as fh:
            fh.write("---\nid: f2\ntype: gotcha\nsubject: unlinked\ncreated: 2026-10-05\n---\nx\n")

    def test_recurrence_before_after(self):
        rec = observe.recurrence(self.project, window=10)
        self.assertEqual(len(rec), 1)
        r = rec[0]
        self.assertEqual((r["before_sessions"], r["before_findings"], r["after_sessions"], r["after_findings"]), (2, 3, 2, 0))
        self.assertEqual((r["before_rate"], r["after_rate"], r["verdict"]), (1.5, 0.0, "fewer"))
        self.assertEqual(observe.learning(self.project)["unlinked"], 1)

    def test_coach_issues_rank_and_fix_prompt(self):
        out = observe.coach_issues(self.project)
        self.assertEqual(out["reviewed_sessions"], 4)
        top = out["issues"][0]
        self.assertEqual((top["category"], top["count"], top["sessions"]), ("whole_file_read", 3, 2))
        self.assertEqual(top["fix_prompt"], "/fix whole_file_read")
        self.assertEqual(top["provenance"], "ai_judged")


class PanelTest(unittest.TestCase):
    def test_schema(self):
        v = observe.validate_panel
        self.assertIsNone(v({"type": "kpi", "title": "t", "value": 3, "provenance": "measured"}))
        self.assertIn("provenance", v({"type": "kpi", "title": "t", "value": 3}))
        self.assertIn("type", v({"type": "pie", "title": "t", "provenance": "measured"}))
        self.assertIn("columns", v({"type": "table", "title": "t", "provenance": "measured"}))
        self.assertIsNone(v({"type": "timeline", "title": "t", "provenance": "estimated", "events": []}))

    def test_dashboard_frontmatter(self):
        d = tempfile.mkdtemp()
        path = os.path.join(d, "SKILL.md")
        with open(path, "w") as fh:
            fh.write("---\nname: x\ndescription: y\ndashboard:\n  category: Diagnose\n  icon: search\n"
                     "  emits: [subagent, tool]\n  steps:\n    - collect\n    - judge\n---\nbody\n")
        self.assertEqual(observe._dashboard_block(path),
                         {"category": "Diagnose", "icon": "search", "emits": ["subagent", "tool"], "steps": ["collect", "judge"]})


class RequestApiTest(ApiCase):
    def setUp(self):
        os.environ["AGENT_SPEC_CURSOR_STORE"] = "0"
        super().setUp()
        self.metrics = os.path.join(self.project, ".agent-spec", "metrics")
        os.makedirs(self.metrics, exist_ok=True)
        self.events = os.path.join(self.metrics, "events.jsonl")
        with open(self.events, "w") as fh:
            for r in hook_rows():
                fh.write(json.dumps(r) + "\n")

    def test_list_filters_and_detail(self):
        body = self.get_json("/api/requests?skill=agent-spec-investigate")
        self.assertEqual((body["total"], body["requests"][0]["trace_id"]), (1, "gen-1"))
        self.assertEqual(self.get_json("/api/requests?status=running")["total"], 0)
        detail = self.get_json("/api/requests/gen-1")
        self.assertEqual(len(detail["spans"]), 9)  # root, skill, 2 tools, subagent + its tool, guard, edit, response
        self.assertEqual(detail["responses"][0]["text"], "done")
        self.assertIsNone(detail["review"])
        self.assertEqual(self.request("/api/requests/nope")[0], 404)

    def test_live_requests_follow_the_file_without_ingest(self):
        with open(self.events, "a") as fh:
            for r in hook_rows(gen="gen-2", t0=1_700_000_100_000):
                fh.write(json.dumps(r) + "\n")
        self.assertEqual(self.get_json("/api/requests")["total"], 2)

    def test_coach_lag(self):
        lag = self.get_json("/api/coach/lag")
        tool = next(r for r in lag["by_kind"] if r["key"] == "tool")
        self.assertEqual((tool["count"], tool["provenance"]), (3, "measured"))
        self.assertEqual((lag["guard_blocks"], lag["whole_file_reads"], lag["subagent_bytes_in"]), (1, 1, 12))

    def test_live_requires_token(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("GET", "/api/live", headers={"Host": "127.0.0.1:%d" % self.port})
        self.assertEqual(conn.getresponse().status, 401)

    def test_live_stream_resumes_from_offset(self):
        size = os.path.getsize(self.events)
        with open(self.events, "a") as fh:
            fh.write(json.dumps(dict(hook_rows()[0], id="late")) + "\n")
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("GET", "/api/live?max_s=1", headers={"Host": "127.0.0.1:%d" % self.port,
                                                           "X-Agent-Spec-Token": self.token,
                                                           "Last-Event-ID": str(size)})
        resp = conn.getresponse()
        self.assertEqual(resp.status, 200)
        self.assertEqual(resp.getheader("Content-Type"), "text/event-stream")
        body = resp.read().decode()
        self.assertIn('"id":"late"', body)
        self.assertNotIn('"id":"e1"', body, "rows before the offset are not replayed")
        self.assertIn("id: %d" % os.path.getsize(self.events), body)


if __name__ == "__main__":
    unittest.main()
