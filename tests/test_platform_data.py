#!/usr/bin/env python3
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin"))
from aspec_platform import platform_data  # noqa: E402


class PlatformDataTest(unittest.TestCase):
    def test_graph_blast_empty(self):
        out = platform_data.api_graph_blast(os.getcwd(), "no-such-file.py")
        self.assertEqual(out["direct_dependents"], [])

    def test_pricing_defaults(self):
        pricing = platform_data.api_pricing(os.getcwd())
        self.assertIn("active_preset", pricing)
        self.assertIn("presets", pricing)

    def test_gates_structure(self):
        gates = platform_data.api_gates(os.getcwd())
        self.assertIn("current_gate", gates)
        self.assertIn("gates", gates)
        self.assertEqual(len(gates["gates"]), 9)



if __name__ == "__main__":
    unittest.main()
