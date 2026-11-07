#!/usr/bin/env python3
"""O-011: `agent-spec-run.py validate` — the tiny stdlib workflow validator.

Run: python3 tests/test_workflow_validate.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _run_helpers import Sandbox, EXAMPLE_WF, workflow_text  # noqa: E402


def wf(steps_block, name="agent-spec-wf-t"):
    return ("---\nname: \"%s\"\ndescription: >-\n  Test.\n---\n\n# t\n\n```steps\n%s\n```\n"
            % (name, steps_block))


class ValidateTest(unittest.TestCase):
    def setUp(self):
        self.sb = Sandbox()

    def tearDown(self):
        self.sb.cleanup()

    def validate(self, text):
        path = os.path.join(self.sb.root, "wf", "SKILL.md")
        self.sb.write_workflow(text)
        code, out, err = self.sb.run("validate", path)
        return code, out, err

    def assert_rejected(self, text, fragment):
        code, out, err = self.validate(text)
        self.assertEqual(code, 3, out)
        self.assertFalse(out["ok"])
        joined = "\n".join(out["errors"])
        self.assertIn(fragment, joined)
        for line in out["errors"]:
            self.assertTrue(line.startswith(os.path.join(self.sb.root, "wf", "SKILL.md") + ": "), line)
        return joined

    def test_example_workflow_accepted(self):
        code, out, err = self.sb.run("validate", EXAMPLE_WF)
        self.assertEqual(code, 0, (out, err))
        self.assertTrue(out["ok"])
        self.assertEqual([s["id"] for s in out["steps"]], ["gather", "analyze", "summarize"])
        self.assertEqual(out["steps"][1]["needs"], ["gather"])

    def test_generated_valid_workflow_accepted(self):
        code, out, _ = self.validate(workflow_text())
        self.assertEqual(code, 0, out)

    def test_full_feature_set_accepted(self):
        block = ("- id: x\n  ai: true\n  agent: agent-spec-search\n  writes: []\n  retries: 3\n  timeout_s: 60\n"
                 "- id: y\n  needs: [x]\n  gate: human\n  when: \"risk is high\"\n  writes: [a.txt, b.txt]\n"
                 "  retries: 0")
        code, out, _ = self.validate(wf(block))
        self.assertEqual(code, 0, out)
        self.assertEqual(out["steps"][1]["writes"], ["a.txt", "b.txt"])
        self.assertEqual(out["steps"][1]["gate"], "human")

    def test_cycle_rejected(self):
        self.assert_rejected(wf("- id: a\n  needs: [b]\n- id: b\n  needs: [a]"), "cycle")
        self.assert_rejected(wf("- id: a\n  needs: [a]"), "cycle")

    def test_missing_need_rejected(self):
        self.assert_rejected(wf("- id: a\n  needs: [ghost]"), "unknown step 'ghost'")

    def test_duplicate_id_rejected(self):
        self.assert_rejected(wf("- id: a\n- id: a"), "duplicate step id 'a'")

    def test_legacy_pipeline_format_rejected_with_migration_message(self):
        legacy = "---\nname: old\ndescription: x\npipeline:\n  - gather\nsub_agents:\n  - foo\n---\n"
        joined = self.assert_rejected(legacy, "legacy")
        self.assertIn("agent-spec-wf-", joined)
        self.assertIn("```steps", joined)

    def test_field_rules(self):
        self.assert_rejected(wf("- id: a\n  retries: 4"), "retries")
        self.assert_rejected(wf("- id: a\n  retries: -1"), "retries")
        self.assert_rejected(wf("- id: a\n  writes: out.txt"), "writes must be a list")
        self.assert_rejected(wf("- id: a\n  gate: robot"), "gate")
        self.assert_rejected(wf("- id: a\n  timeout_s: soon"), "timeout_s")
        self.assert_rejected(wf("- id: a\n  bogus: 1"), "unknown key 'bogus'")
        self.assert_rejected(wf("- name: a"), "missing id")

    def test_structure_rules(self):
        self.assert_rejected("---\nname: \"agent-spec-wf-t\"\n---\n\nno steps here\n", "steps")
        self.assert_rejected(wf("", name="agent-spec-wf-t"), "no steps")
        self.assert_rejected(wf("- id: a", name="other-name"), "agent-spec-wf-")
        self.assert_rejected("no frontmatter\n```steps\n- id: a\n```\n", "frontmatter")

    def test_gate_human_does_not_require_when(self):
        code, out, _ = self.validate(wf("- id: a\n  gate: human"))
        self.assertEqual(code, 0, out)

    def test_missing_file_refused_and_usage(self):
        code, out, _ = self.sb.run("validate", os.path.join(self.sb.root, "nope.md"))
        self.assertEqual(code, 3)
        self.assertEqual(self.sb.run("validate")[0], 2)


if __name__ == "__main__":
    unittest.main(verbosity=1)
