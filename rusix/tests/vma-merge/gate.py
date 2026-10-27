#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Strict two-case bounded userspace stress gate; never executes guest binaries."""
import argparse
import json
from pathlib import Path
import re

CASES = (
    'concurrent_mprotect_procmap',
    'fork_cow_mremap_lifetime',
)
COUNTERS = (
    'controls=2 transitions=514 queries=258 scans=258',
    'cow_children=1 grows=64 shrinks=64 zero_extensions=64',
)
EXPECTED = [
    'RUSIX_VMA_MERGE_BEGIN',
    *(f'RUSIX_VMA_MERGE_CASE {name} PASS {counters}' for name, counters in zip(CASES, COUNTERS)),
    'RUSIX_VMA_MERGE_END',
    'RUSIX_VMA_MERGE_PASS',
]
DIAGNOSTICS = r'(?i:\bwarning\b)|\bBUG\b|Oops:|Kernel panic|Call Trace:|KASAN:|UBSAN:|ACPI (?:BIOS )?(?:Error|Exception|Warning)|CPU feature dependency check failure|ACPI: Unable to load|RUSIX_VMA_MERGE_FAIL'

def validate(console, status=0):
    if status != 0:
        raise ValueError('QEMU failure/timeout')
    if re.search(DIAGNOSTICS, console):
        raise ValueError('Kernel/guest diagnostics')
    lines = console.replace('\r\n', '\n').splitlines()
    markers = [line for line in lines if 'RUSIX_' in line]
    if markers != EXPECTED:
        raise ValueError('Missing/failed/skipped/duplicate/foreign/out-of-order cases or counters')
    begin, end = lines.index(EXPECTED[0]), lines.index(EXPECTED[-1])
    if lines[begin:end + 1] != EXPECTED:
        raise ValueError('Unexpected output inside guest result envelope')
    if any(re.match(r'(?:TAP version |\d+\.\.|(?:not )?ok \d|# Totals:)', line) for line in lines):
        raise ValueError('Unexpected additional test output')
    return {'status': 'PASS', 'cases': list(CASES), 'counters': list(COUNTERS), 'count': 2,
            'scope': 'Bounded mprotect/query read-only payload and fork/private-COW/mremap consumers only'}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('console', type=Path)
    args = parser.parse_args()
    print(json.dumps(validate(args.console.read_text()), indent=2, sort_keys=True))

if __name__ == '__main__':
    main()
