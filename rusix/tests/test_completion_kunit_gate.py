#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Completion inventory and shared strict KUnit validation regression checks."""
import copy
import importlib.util
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location(
    "completion_gate", Path(__file__).resolve().parents[1] / "scripts/validate-completion-kunit.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def suite(name, cases=()):
    return {"name": name, "sub_groups": [],
            "test_cases": [{"name": case, "status": "PASS"} for case in cases],
            "misc": {"tests": len(cases), "passed": len(cases), "failed": 0,
                     "crashed": 0, "skipped": 0, "errors": 0}}


class CompletionGateTests(unittest.TestCase):
    def setUp(self):
        self.result = suite("KUnit Test Group")
        self.result["sub_groups"] = [suite(name, cases) for name, cases in gate.SUITES.items()]

    def rejected(self, result):
        with self.assertRaises((ValueError, KeyError, TypeError)):
            gate.validate(result)

    def test_exact_inventory_passes(self):
        self.assertEqual(gate.validate(self.result), 5)

    def test_every_omitted_case_rejected(self):
        for index in range(5):
            result = copy.deepcopy(self.result)
            result["sub_groups"][0]["test_cases"].pop(index)
            self.rejected(result)

    def test_missing_suite_rejected(self):
        self.rejected(suite("KUnit Test Group"))

    def test_duplicate_suite_rejected(self):
        self.result["sub_groups"] *= 2
        self.rejected(self.result)

    def test_duplicate_case_cannot_replace_missing(self):
        cases = self.result["sub_groups"][0]["test_cases"]
        cases[-1] = copy.deepcopy(cases[0])
        self.rejected(self.result)

    def test_unknown_extra_case_rejected(self):
        self.result["sub_groups"][0]["test_cases"].append({"name": "extra", "status": "PASS"})
        self.rejected(self.result)

    def test_nonpass_required_or_unrelated_case_rejected(self):
        for status in ("SKIP", "FAIL", "ERROR", "CRASHED"):
            for extra in (False, True):
                result = copy.deepcopy(self.result)
                if extra:
                    result["sub_groups"].append(suite("other", ("case",)))
                result["sub_groups"][-1]["test_cases"][0]["status"] = status
                self.rejected(result)

    def test_error_counters_and_bad_totals_rejected(self):
        for field in ("failed", "crashed", "skipped", "errors", "tests", "passed"):
            result = copy.deepcopy(self.result)
            result["sub_groups"][0]["misc"][field] += 1
            self.rejected(result)

    def test_malformed_result_rejected(self):
        for result in ({}, [], {"name": "root", "sub_groups": None, "test_cases": []}):
            self.rejected(result)

    def test_brd_default_inventory_stays_independent(self):
        self.rejected({**self.result, "sub_groups": [
            suite(name, cases) for name, cases in gate.common.SUITES.items()]})
        with self.assertRaises(ValueError):
            gate.common.validate(self.result)


if __name__ == "__main__":
    unittest.main()
