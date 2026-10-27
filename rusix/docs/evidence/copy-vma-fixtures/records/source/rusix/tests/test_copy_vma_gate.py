#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
import importlib.util
from pathlib import Path
import unittest

PATH = Path(__file__).parent / 'copy-vma/gate.py'
spec = importlib.util.spec_from_file_location('copy_gate', PATH)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def valid():
    return '\n'.join([gate.BEGIN, 'TAP version 13', '1..5',
                      *[f'ok {i} {name}' for i, name in enumerate(gate.CASES, 1)],
                      gate.TOTAL, gate.END, gate.PASS]) + '\n'


class GateTests(unittest.TestCase):
    def reject(self, text):
        with self.assertRaises(ValueError):
            gate.validate(text)

    def test_exact_five(self):
        self.assertEqual(gate.validate(valid())['cases'], list(gate.CASES))

    def test_serial_crlf(self):
        self.assertEqual(gate.validate(valid().replace('\n', '\r\n'))['count'], 5)

    def test_old_kernel_silent_shmem_return(self):
        self.reject(valid().replace('ok 2 mremap_dontunmap_simple_shmem\n', ''))

    def test_missing_plan(self):
        self.reject(valid().replace('1..5\n', ''))

    def test_no_support_early_exit(self):
        self.reject('\n'.join([gate.BEGIN, 'TAP version 13', '# No kernel support for MREMAP_DONTUNMAP', gate.END, gate.PASS]))

    def test_skip_fail_xfail(self):
        for replacement in ('ok 2 # SKIP unavailable', 'not ok 2 failed', 'ok 2 # XFAIL expected'):
            with self.subTest(replacement=replacement):
                self.reject(valid().replace('ok 2 mremap_dontunmap_simple_shmem', replacement))

    def test_duplicate_case(self):
        self.reject(valid().replace('ok 3 mremap_dontunmap_simple_fixed', 'ok 3 mremap_dontunmap_simple_shmem'))

    def test_reorder(self):
        self.reject(valid().replace('ok 1 mremap_dontunmap_simple', 'ok 2 mremap_dontunmap_simple'))

    def test_unknown_case(self):
        self.reject(valid().replace('ok 5 mremap_dontunmap_partial_mapping_overwrite', 'ok 5 other'))

    def test_totals(self):
        self.reject(valid().replace('fail:0', 'fail:1'))

    def test_marker_failures(self):
        for text in (valid() + gate.PASS, valid().replace(gate.END, ''), valid() + 'RUSIX_COPY_VMA_FAIL init: timeout', valid() + 'RUSIX_COPY_VMA_UNKNOWN'):
            self.reject(text)

    def test_native_diagnostic_classes(self):
        for diagnostic in ('warning: low case', 'BUG at mm/mmap.c', 'CPU feature dependency check failure', 'ACPI BIOS Error: failed', 'ACPI Exception: failed', 'ACPI: Unable to load table'):
            with self.subTest(diagnostic=diagnostic):
                self.reject(valid() + diagnostic)

    def test_diagnostics_and_extra_tap(self):
        for extra in ('WARNING: broken kernel', 'TAP version 13', 'ok 1 unexpected'):
            self.reject(valid() + extra)


if __name__ == '__main__':
    unittest.main()
