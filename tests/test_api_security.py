#!/usr/bin/env python3
"""Tests for the dashboard server guards (S-003): Host check, launch token, read-only, loopback bind.

Run: python3 tests/test_api_security.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _api_support import ApiCase  # noqa: E402


class SecurityTest(ApiCase):
    def test_binds_loopback_only(self):
        self.assertEqual(self.httpd.server_address[0], "127.0.0.1")

    def test_bad_host_header_rejected_even_with_token(self):
        for host in ("evil.example.com", "evil.example.com:%d" % self.port, "127.0.0.1.evil.com",
                     "localhost.evil.com:80", "", "10.0.0.5:%d" % self.port):
            status, _, _ = self.request("/api/health", host=host)
            self.assertEqual(status, 403, host)

    def test_good_host_headers_accepted(self):
        for host in ("127.0.0.1:%d" % self.port, "localhost:%d" % self.port, "localhost", "127.0.0.1"):
            status, _, _ = self.request("/api/health", host=host)
            self.assertEqual(status, 200, host)

    def test_missing_or_wrong_token_is_401(self):
        self.assertEqual(self.request("/api/health", token=False)[0], 401)
        self.assertEqual(self.request("/api/health", token="wrong")[0], 401)
        self.assertEqual(self.request("/api/health", token=self.token[:-1])[0], 401)

    def test_token_in_query_string_is_not_accepted_on_api(self):
        status, _, _ = self.request("/api/health?token=%s" % self.token, token=False)
        self.assertEqual(status, 401)

    def test_token_is_random_per_launch(self):
        other_server, other = self.serve.make_server(self.project, "127.0.0.1", 0)
        other_server.server_close()
        self.assertNotEqual(other, self.token)
        self.assertGreaterEqual(len(self.token), 32)

    def test_non_loopback_bind_is_refused(self):
        for host in ("0.0.0.0", "", "192.168.1.5", "::"):
            with self.assertRaises(ValueError):
                self.serve.make_server(self.project, host, 0)

    def test_root_with_token_sets_strict_httponly_cookie_and_cookie_authorizes_api(self):
        status, headers, body = self.request("/?token=%s" % self.token, token=False)
        self.assertEqual(status, 200)
        cookie = headers.get("set-cookie", "")
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Strict", cookie)
        pair = cookie.split(";")[0]
        status, _, _ = self.request("/api/health", token=False, headers={"Cookie": pair})
        self.assertEqual(status, 200)

    def test_root_without_token_is_401(self):
        self.assertEqual(self.request("/", token=False)[0], 401)
        self.assertEqual(self.request("/?token=nope", token=False)[0], 401)

    def test_write_methods_are_405_and_never_mutate(self):
        for method in ("POST", "PUT", "DELETE", "PATCH"):
            status, _, _ = self.request("/api/runs", method=method)
            self.assertEqual(status, 405, method)

    def test_security_headers_on_every_response(self):
        for path, token in (("/api/health", True), ("/api/health", False)):
            _, headers, _ = self.request(path, token=token)
            self.assertEqual(headers.get("x-content-type-options"), "nosniff")
            self.assertEqual(headers.get("cache-control"), "no-store")
            self.assertIn("default-src 'none'", headers.get("content-security-policy", ""))

    def test_path_traversal_cannot_leave_ui(self):
        for path in ("/../serve.py", "/..%2fserve.py", "/ui/../../db.py", "/%2e%2e/db.py"):
            status, _, body = self.request(path)
            self.assertIn(status, (401, 404), path)
            self.assertNotIn(b"import", body)


if __name__ == "__main__":
    unittest.main()
