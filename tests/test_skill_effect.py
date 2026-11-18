#!/usr/bin/env python3
"""PI-011 skill effectiveness: measured rates per skill, AI-judged quality only past the
sample-size floor, and a no-skill baseline.

Run: python3 tests/test_skill_effect.py
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "bin"))
from aspec_platform import skill_effect, traces  # noqa: E402
from test_traces import hook_rows  # noqa: E402


class SkillEffectTest(unittest.TestCase):
    def setUp(self):
        self.p = tempfile.mkdtemp()
        metrics = os.path.join(self.p, ".agent-spec", "metrics")
        os.makedirs(os.path.join(metrics, "reviews"))
        rows = []
        for i in range(12):  # 12 requests that ran /agent-spec-investigate (hook_rows' prompt)
            rows += [dict(r, id="%s-%d" % (r["id"], i)) for r in
                     hook_rows(conv="c%d" % i, gen="g%d" % i, t0=1_700_000_000_000 + i * 100_000)]
        for i in range(3):  # 3 without a skill
            rows += [dict(r, id="%s-n%d" % (r["id"], i), prompt="plain question")
                     for r in hook_rows(conv="n%d" % i, gen="n%d" % i, t0=1_800_000_000_000 + i * 100_000)]
        with open(os.path.join(metrics, "events.jsonl"), "w") as fh:
            fh.write("\n".join(json.dumps(r) for r in rows) + "\n")
        self.reviews = os.path.join(metrics, "reviews")
        self.env = os.environ.get("AGENT_SPEC_CURSOR_STORE")
        os.environ["AGENT_SPEC_CURSOR_STORE"] = "0"
        traces._CACHE.clear()

    def tearDown(self):
        if self.env is None:
            os.environ.pop("AGENT_SPEC_CURSOR_STORE", None)
        else:
            os.environ["AGENT_SPEC_CURSOR_STORE"] = self.env
        shutil.rmtree(self.p)

    def review(self, n, score):
        for i in range(n):
            with open(os.path.join(self.reviews, "c%d.json" % i), "w") as fh:
                json.dump({"conversation_id": "c%d" % i, "quality": [{"trace_id": "g%d" % i, "overall": score}]}, fh)

    def rows(self):
        traces._CACHE.clear()
        return {r["skill"]: r for r in skill_effect.overview(self.p)["skills"]}

    def test_rates_and_quality_gate(self):
        rows = self.rows()
        skill = next(k for k in rows if k != skill_effect.NO_SKILL)
        r = rows[skill]
        self.assertEqual(r["requests"], 12)
        self.assertEqual(r["failure_rate"], 1.0, "every fixture request has a failed npm test")
        self.assertIsNone(r["quality"])
        self.assertIn("not enough data", r["note"])
        self.review(9, 4)
        self.assertIsNone(self.rows()[skill]["quality"], "9 reviewed is below the floor")
        self.review(10, 4)
        self.assertEqual(self.rows()[skill]["quality"], 4.0)

    def test_baseline_needs_its_own_sample(self):
        base = self.rows().get(skill_effect.NO_SKILL)
        if base is not None:  # fewer than MIN_REQUESTS: no rate
            self.assertIsNone(base["failure_rate"])


if __name__ == "__main__":
    unittest.main(verbosity=1)
