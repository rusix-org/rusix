#!/usr/bin/env python3
"""Regression tests for accepting real test coverage rather than aggregate PASS."""
import copy
import importlib.util
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location(
    "kunit_gate", Path(__file__).resolve().parent.parent / "scripts/validate-kunit-results.py"
)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def suite(name, cases):
    return {
        "name": name,
        "sub_groups": [],
        "test_cases": [{"name": name, "status": "PASS"} for name in cases],
        "misc": {"tests": len(cases), "passed": len(cases), "failed": 0,
                 "crashed": 0, "skipped": 0, "errors": 0},
    }


class AcceptanceGateTests(unittest.TestCase):
    def setUp(self):
        self.result = suite("KUnit Test Group", ())
        self.result["sub_groups"] = [
            suite("math-int_sqrt", gate.UPSTREAM_CASES),
            suite("rusix-int-sqrt-compatibility", gate.COMPATIBILITY_CASES),
        ]

    def test_complete_inventory_passes(self):
        self.assertEqual(gate.validate(self.result), 24)

    def test_baseline_requires_explicit_opt_in(self):
        self.result["sub_groups"].pop()
        with self.assertRaises(ValueError):
            gate.validate(self.result)
        self.assertEqual(gate.validate(self.result, baseline=True), 21)

    def test_skipped_required_case_is_rejected_even_with_other_passes(self):
        case = self.result["sub_groups"][0]["test_cases"][0]
        case["status"] = "SKIP"
        with self.assertRaises(ValueError):
            gate.validate(self.result)

    def test_missing_required_case_is_rejected(self):
        self.result["sub_groups"][0]["test_cases"].pop()
        with self.assertRaises(ValueError):
            gate.validate(self.result)

    def test_missing_upstream_suite_is_rejected(self):
        self.result["sub_groups"].pop(0)
        with self.assertRaises(ValueError):
            gate.validate(self.result)

    def test_duplicate_case_cannot_replace_missing_case(self):
        cases = self.result["sub_groups"][0]["test_cases"]
        cases[-1] = copy.deepcopy(cases[0])
        with self.assertRaises(ValueError):
            gate.validate(self.result)

    def test_duplicate_suite_is_rejected(self):
        self.result["sub_groups"].append(copy.deepcopy(self.result["sub_groups"][0]))
        with self.assertRaises(ValueError):
            gate.validate(self.result)

    def test_parse_errors_are_rejected(self):
        self.result["misc"]["errors"] = 1
        with self.assertRaises(ValueError):
            gate.validate(self.result)

    def test_failed_compatibility_case_cannot_be_ignored_in_baseline_mode(self):
        self.result["sub_groups"][1]["test_cases"][0]["status"] = "FAIL"
        with self.assertRaises(ValueError):
            gate.validate(self.result, baseline=True)


if __name__ == "__main__":
    unittest.main()
