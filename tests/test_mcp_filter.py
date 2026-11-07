#!/usr/bin/env python3
"""Tests for bin/agent-spec-mcp-filter.py (B-006.1): deterministic MCP response filtering."""
import json
import os
import subprocess
import sys
import unittest

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILTER_CLI = os.path.join(REPO_DIR, "bin", "agent-spec-mcp-filter.py")


class McpFilterTest(unittest.TestCase):
    def test_oversized_jira_payload_is_pruned_to_essential_keys(self):
        # 80 KB raw Jira issue with schemas, transitions, avatars, user links
        oversized_payload = {
            "expand": "renderedFields,names,schema,operations,editmeta,changelog,versionedRepresentations",
            "id": "100234",
            "self": "https://jira.example.com/rest/api/2/issue/100234",
            "key": "AVC-123",
            "fields": {
                "summary": "Gateway timeout in proxy router during traffic spike",
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [
                                {"type": "text", "text": "Router fails with 504 gateway timeout under load."}
                            ]
                        }
                    ]
                },
                "components": [{"id": "1", "name": "ProxyRouter"}, {"id": "2", "name": "IngressGateway"}],
                "status": {"name": "Open", "id": "1"},
                "issuetype": {"name": "Bug", "id": "1"},
                "attachment": [
                    {"filename": "router-error.log", "size": 124000},
                    {"filename": "screenshot.png", "size": 450000}
                ],
                "labels": ["production", "router"],
                "reporter": {"name": "alice", "avatarUrls": {"48x48": "https://..." * 50}},
                "assignee": {"name": "bob", "avatarUrls": {"48x48": "https://..." * 50}},
                "schema": {"field_" + str(i): {"type": "string", "name": "Custom " + str(i)} for i in range(500)},
                "editmeta": {"fields": {"field_" + str(i): {"allowedValues": ["opt" + str(j) for j in range(20)]} for i in range(200)}}
            }
        }
        raw_json = json.dumps(oversized_payload)
        self.assertGreater(len(raw_json), 50000, "Payload fixture should be >50 KB")

        proc = subprocess.run([sys.executable, FILTER_CLI], input=raw_json,
                              capture_output=True, text=True, check=True)
        out = json.loads(proc.stdout)

        # Output must be < 2 KB (a >95% reduction from 80 KB)
        self.assertLess(len(proc.stdout), 2000, "Filtered output must be < 2 KB")
        self.assertEqual(out["key"], "AVC-123")
        self.assertEqual(out["summary"], "Gateway timeout in proxy router during traffic spike")
        self.assertIn("Router fails with 504", out["symptom"])
        self.assertEqual(out["components"], ["ProxyRouter", "IngressGateway"])
        self.assertEqual(out["status"], "Open")
        self.assertEqual(out["issuetype"], "Bug")
        self.assertEqual(len(out["attachments"]), 2)
        self.assertEqual(out["attachments"][0]["kind"], "log")
        self.assertIn("ProxyRouter", out["candidate_terms"])
        self.assertNotIn("schema", out)
        self.assertNotIn("editmeta", out)

    def test_generic_keys_whitelist(self):
        payload = {"a": 1, "b": 2, "c": 3, "bloat": "x" * 1000}
        proc = subprocess.run([sys.executable, FILTER_CLI, "--keys", "a,c"], input=json.dumps(payload),
                              capture_output=True, text=True, check=True)
        out = json.loads(proc.stdout)
        self.assertEqual(out, {"a": 1, "c": 3})


if __name__ == "__main__":
    unittest.main()
