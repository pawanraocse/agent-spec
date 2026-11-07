#!/usr/bin/env python3
"""Tests for bin/aspec_platform/redact.py (S-003): the redaction corpus.

Run: python3 tests/test_redact.py
"""
import os
import sys
import unittest

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_DIR, "bin"))

from aspec_platform import redact  # noqa: E402

B64 = "dGhpcyBpcyBhIHNlY3JldCB0b2tlbiB2YWx1ZQ=="  # 40 chars
HEX64 = "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"
SHA40 = "3b18e512dba79e4c8300dd08aeb37f8e728b8dad"
URLSAFE = "xK9_mQ2vLp4Zr8TnW3yB7cDfGh1JsAeU-oPq"
PEM = ("-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEAvbXk\nabcdefghijklmnop\n"
       "-----END RSA PRIVATE KEY-----")

# (text, secret that must not survive, kind that must appear)
SECRETS = [
    ("password=hunter22", "hunter22", "secret"),
    ("export API_KEY=abcd1234efgh", "abcd1234efgh", "secret"),
    ("db_password: 'p@ss w0rd'", "p@ss w0rd", "secret"),
    ('{"client_secret": "s3cr3tvalue"}', "s3cr3tvalue", "secret"),
    ("curl -H 'Authorization: Bearer abc.def-123_xyz' http://x", "abc.def-123_xyz", None),
    ("Authorization: Basic dXNlcjpwYXNz", "dXNlcjpwYXNz", "secret"),
    ("token = ghp_ABCdef1234567890", "ghp_ABCdef1234567890", "secret"),
    ("sent Bearer eyJhbGciOiJIUzI1NiJ9 to the server", "eyJhbGciOiJIUzI1NiJ9", "bearer"),
    ("aws key AKIAIOSFODNN7EXAMPLE here", "AKIAIOSFODNN7EXAMPLE", "aws_key"),
    ("temp ASIAY34FZKBOKMUTVV7A creds", "ASIAY34FZKBOKMUTVV7A", "aws_key"),
    ("key:\n" + PEM + "\nafter", "MIIEowIBAAKCAQEAvbXk", "private_key"),
    ("-----BEGIN PRIVATE KEY-----\ntruncated base64 only", "truncated base64 only", "private_key"),
    ("blob " + B64 + " end", B64, "token"),
    ("value " + HEX64, HEX64, "hex"),
    ("id " + URLSAFE, URLSAFE, "token"),
    ("git clone https://bob:s3cretpw@github.com/x/y.git", "s3cretpw", "url_credentials"),
    ("jwt eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4ifQ.sig",
     "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9", "token"),
]

# Must pass through unchanged.
BENIGN = [
    "Please read the token budget docs and the password hashing section.",
    "tokens estimated at chars/4; no secret here",
    "/Users/pawan.yadav/development/algosec-agent-spec/bin/aspec_platform/ingest.py",
    "bin/aspec_platform/transcripts/subagents/children-and-parents/link-order",
    "see docs/IMPLEMENTATION-GUIDE.md section 4.2 for the event schema",
    "agent-spec-implementation-guide-phase-two-ingestor-design-2026",
    "uuid 7725e31c-4ebb-425e-a4bb-859dcc9fc852 is a session",
    "getUserPreferencesForCurrentSessionHandler is long but is prose",
    "commit " + SHA40 + " fixed it",
    "sha=" + SHA40,
    "git rev: " + SHA40,
    "token=$GITHUB_TOKEN",
    '  "tokens": {"input": 1493}',
    "docs/platform-design/adr/ADR-001-CURSOR-CLI-ORCHESTRATOR-DESIGN-DECISION-RECORD.md",
    "def f(password): return password",
    "Run python3 tests/test_redact.py and paste the real output.",
]


class RedactTest(unittest.TestCase):
    def test_secret_corpus_is_redacted(self):
        for text, secret, kind in SECRETS:
            out = redact.redact(text)
            self.assertNotIn(secret, out, text)
            self.assertIn("«redacted:", out, text)
            if kind:
                self.assertIn("«redacted:%s»" % kind, out, text)

    def test_benign_corpus_is_untouched(self):
        for text in BENIGN:
            self.assertEqual(redact.redact(text), text)

    def test_sha_without_context_is_redacted_rule(self):
        # documented rule: a 40-hex string is a SHA only with commit/sha/hash context before it
        self.assertEqual(redact.redact("x " + SHA40), "x «redacted:hex»")

    def test_surrounding_text_and_keys_survive(self):
        out = redact.redact("run with password=hunter22 now")
        self.assertEqual(out, "run with password=«redacted:secret» now")

    def test_idempotent(self):
        for text, _, _ in SECRETS:
            once = redact.redact(text)
            self.assertEqual(redact.redact(once), once)

    def test_non_string_inputs(self):
        self.assertEqual(redact.redact(None), "")
        self.assertEqual(redact.redact(12), "12")

    def test_redact_obj_nested(self):
        obj = {"password": "hunter22", "cmd": "echo password=abc12345", "n": 3, "ok": True,
               "list": ["AKIAIOSFODNN7EXAMPLE", {"deep": "Bearer abcdefgh12345"}], "none": None}
        out = redact.redact_obj(obj)
        flat = repr(out)
        for secret in ("hunter22", "abc12345", "AKIAIOSFODNN7EXAMPLE", "abcdefgh12345"):
            self.assertNotIn(secret, flat)
        self.assertEqual(out["n"], 3)
        self.assertIs(out["ok"], True)
        self.assertIsNone(out["none"])
        self.assertEqual(obj["password"], "hunter22")  # input not mutated

    def test_large_text_is_fast(self):
        import time
        text = ("lorem ipsum dolor sit amet token budget " * 2000) + " password=abc12345"
        start = time.time()
        out = redact.redact(text)
        self.assertLess(time.time() - start, 2.0)
        self.assertIn("«redacted:secret»", out)


if __name__ == "__main__":
    unittest.main(verbosity=1)
