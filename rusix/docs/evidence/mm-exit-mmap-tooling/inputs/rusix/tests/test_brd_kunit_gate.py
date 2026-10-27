#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Malformed-result regression coverage for the BRD ownership KUnit gate."""
import copy
import importlib.util
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location(
    "brd_kunit_gate", Path(__file__).resolve().parents[1] / "scripts/validate-brd-kunit.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def suite(name, cases=()):
    return {"name": name, "sub_groups": [],
            "test_cases": [{"name": case, "status": "PASS"} for case in cases],
            "misc": {"tests": len(cases), "passed": len(cases), "failed": 0,
                     "crashed": 0, "skipped": 0, "errors": 0}}


class AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.result = suite("KUnit Test Group")
        self.result["sub_groups"] = [suite(name, cases) for name, cases in gate.SUITES.items()]

    def rejected(self, result=None):
        with self.assertRaises((ValueError, KeyError, TypeError)):
            gate.validate(self.result if result is None else result)

    def test_exact_inventory_passes(self):
        self.assertEqual(gate.validate(self.result), 9)

    def test_unrelated_passing_suite_is_allowed(self):
        self.result["sub_groups"].append(suite("unrelated", ("passing",)))
        self.assertEqual(gate.validate(self.result), 9)

    def test_each_missing_suite_rejected(self):
        for index in range(len(gate.SUITES)):
            result = copy.deepcopy(self.result)
            result["sub_groups"].pop(index)
            self.rejected(result)

    def test_each_missing_case_rejected(self):
        for index, group in enumerate(self.result["sub_groups"]):
            for case_index in range(len(group["test_cases"])):
                result = copy.deepcopy(self.result)
                result["sub_groups"][index]["test_cases"].pop(case_index)
                self.rejected(result)

    def test_duplicate_suite_rejected(self):
        self.result["sub_groups"].append(copy.deepcopy(self.result["sub_groups"][0]))
        self.rejected()

    def test_duplicate_case_cannot_replace_missing_case(self):
        cases = self.result["sub_groups"][0]["test_cases"]
        cases[-1] = copy.deepcopy(cases[0])
        self.rejected()

    def test_unknown_required_suite_case_rejected(self):
        self.result["sub_groups"][0]["test_cases"][0]["name"] = "other"
        self.rejected()

    def test_extra_required_suite_case_rejected(self):
        self.result["sub_groups"][0]["test_cases"].append({"name": "extra", "status": "PASS"})
        self.rejected()

    def test_any_nonpass_even_unrelated_rejected(self):
        for status in ("FAIL", "SKIP", "ERROR", "CRASHED", ""):
            result = copy.deepcopy(self.result)
            extra = suite("unrelated", ("case",))
            extra["test_cases"][0]["status"] = status
            result["sub_groups"].append(extra)
            self.rejected(result)

    def test_failure_counters_rejected_at_any_level(self):
        for field in ("failed", "crashed", "skipped", "errors"):
            for root in (True, False):
                result = copy.deepcopy(self.result)
                target = result if root else result["sub_groups"][0]
                target["misc"][field] = 1
                self.rejected(result)

    def test_inconsistent_totals_rejected(self):
        for field in ("tests", "passed"):
            result = copy.deepcopy(self.result)
            result["sub_groups"][0]["misc"][field] += 1
            self.rejected(result)

    def test_malformed_shapes_and_counts_rejected(self):
        for malformed in ({}, [], {"name": "root", "sub_groups": None, "test_cases": []}):
            self.rejected(malformed)
        for value in (-1, True, "0", None):
            result = copy.deepcopy(self.result)
            result["misc"]["errors"] = value
            self.rejected(result)


if __name__ == "__main__":
    unittest.main()
