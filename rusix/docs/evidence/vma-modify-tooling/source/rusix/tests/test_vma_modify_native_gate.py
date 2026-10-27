#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Acceptance regressions for missing, substituted and unsuccessful native tests."""
import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location(
    'vma_modify_native_gate', Path(__file__).parent / 'vma-modify/gate.py')
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)


class NativeGate(unittest.TestCase):
    def console(self):
        return '\n'.join([gate.BEGIN, *gate.expected_output(), gate.END, gate.PASS]) + '\n'

    def rejects(self, text):
        with self.assertRaises(ValueError):
            gate.validate(text)

    def test_exact_five_case_stream(self):
        self.assertEqual(gate.validate(self.console())['cases'], list(gate.CASES))

    def test_serial_crlf(self):
        self.assertEqual(gate.validate(self.console().replace('\n', '\r\n'))['count'], 5)

    def test_missing_case(self):
        self.rejects(self.console().replace('ok 3 ' + gate.CASES[2] + '\n', ''))

    def test_reordered_cases(self):
        self.rejects(self.console().replace(gate.CASES[0], 'TEMP').replace(
            gate.CASES[1], gate.CASES[0]).replace('TEMP', gate.CASES[1]))

    def test_duplicate_case(self):
        self.rejects(self.console().replace('ok 2 ' + gate.CASES[1], 'ok 2 ' + gate.CASES[0]))

    def test_substituted_case(self):
        self.rejects(self.console().replace(gate.CASES[4], 'merge.ksm_merge'))

    def test_skip(self):
        self.rejects(self.console().replace('ok 2 ' + gate.CASES[1],
                                           'ok 2 ' + gate.CASES[1] + ' # SKIP unsupported'))

    def test_failure(self):
        self.rejects(self.console().replace('ok 2 ', 'not ok 2 '))

    def test_wrong_plan(self):
        self.rejects(self.console().replace('1..5', '1..0 # SKIP'))

    def test_bad_totals(self):
        self.rejects(self.console().replace('skip:0', 'skip:1'))

    def test_missing_native_harness_status(self):
        self.rejects(self.console().replace('# PASSED: 5 / 5 tests passed.\n', ''))

    def test_duplicate_wrapper(self):
        self.rejects(self.console() + gate.PASS + '\n')

    def test_guest_failure(self):
        self.rejects(self.console() + 'RUSIX_VMA_MODIFY_FAIL cleanup timeout\n')

    def test_kernel_diagnostics(self):
        for text in ('WARNING: corrupted state', 'BUG: bad page', 'Oops: fault',
                     'Kernel panic - not syncing', 'KASAN: bad access'):
            with self.subTest(text=text):
                self.rejects(text + '\n' + self.console())

    def test_second_stream(self):
        self.rejects('TAP version 13\n1..0\n' + self.console())

    def test_marker_order(self):
        self.rejects(self.console().replace(gate.END + '\n' + gate.PASS,
                                           gate.PASS + '\n' + gate.END))


if __name__ == '__main__':
    unittest.main()
