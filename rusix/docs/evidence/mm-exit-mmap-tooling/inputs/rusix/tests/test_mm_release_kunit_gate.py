#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Host-only negative checks for the literal MM release result contract."""
import copy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    'mm_release_gate', Path(__file__).parents[1] / 'scripts/validate-mm-release-kunit.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def group(name, cases=(), children=()):
    count = len(cases) + sum(c['misc']['tests'] for c in children)
    return dict(name=name, test_cases=[dict(name=n, status='PASS') for n in cases],
                sub_groups=list(children), misc=dict(tests=count, passed=count,
                failed=0, crashed=0, skipped=0, errors=0))


def result(combined=False):
    suites = dict(gate.SUITES)
    if combined:
        suites.update(gate.completion.SUITES)
        suites.update(gate.common.SUITES)
    return group('kunit', children=[group(n, c) for n, c in suites.items()])


class Gate(unittest.TestCase):
    def test_exact_isolated_and_combined_counts(self):
        self.assertEqual(gate.validate(result()), 4)
        self.assertEqual(gate.validate(result(True), True), 80)

    def test_modes_cannot_substitute_for_each_other(self):
        for r, combined in ((result(), True), (result(True), False)):
            with self.assertRaises(ValueError):
                gate.validate(r, combined)

    def test_missing_duplicate_unknown_case_and_suite(self):
        base = result()
        mutations = []
        r = copy.deepcopy(base); r['sub_groups'][0]['test_cases'].pop(); mutations.append(r)
        r = copy.deepcopy(base); r['sub_groups'][0]['test_cases'].append(
            copy.deepcopy(r['sub_groups'][0]['test_cases'][0])); mutations.append(r)
        r = copy.deepcopy(base); r['sub_groups'][0]['test_cases'][0]['name'] = 'unknown'; mutations.append(r)
        r = copy.deepcopy(base); r['sub_groups'].append(copy.deepcopy(r['sub_groups'][0])); mutations.append(r)
        r = copy.deepcopy(base); r['sub_groups'].append(group('other', ['unknown'])); mutations.append(r)
        r = copy.deepcopy(base); r['sub_groups'].append(group('rusix_unknown')); mutations.append(r)
        for r in mutations:
            with self.subTest(r=r), self.assertRaises(ValueError):
                gate.validate(r)

    def test_fail_skip_crash_and_bad_totals(self):
        for field in ('failed', 'skipped', 'crashed', 'errors', 'tests', 'passed'):
            r = result(); r['sub_groups'][0]['misc'][field] += 1
            with self.subTest(field=field), self.assertRaises(ValueError):
                gate.validate(r)
        for status in ('FAIL', 'SKIP', 'ERROR', 'CRASH'):
            r = result(); r['sub_groups'][0]['test_cases'][0]['status'] = status
            with self.subTest(status=status), self.assertRaises(ValueError):
                gate.validate(r)

    def test_source_inventory_matches_independent_literals(self):
        source = (Path(__file__).parents[2] / 'rust/kernel/mm/release_tests.rs').read_text()
        import re
        actual = re.findall(r'#\[test\]\s+fn (\w+)\(', source)
        self.assertEqual(actual, list(gate.SUITES['rusix_mm_release']))


if __name__ == '__main__':
    unittest.main()
