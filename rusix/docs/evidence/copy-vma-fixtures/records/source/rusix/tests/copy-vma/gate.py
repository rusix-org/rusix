#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Strict native mremap_dontunmap TAP acceptance; never executes a guest."""
import argparse
import json
from pathlib import Path
import re

CASES = ('mremap_dontunmap_simple', 'mremap_dontunmap_simple_shmem',
         'mremap_dontunmap_simple_fixed', 'mremap_dontunmap_partial_mapping',
         'mremap_dontunmap_partial_mapping_overwrite')
BEGIN = 'RUSIX_COPY_VMA_BEGIN'
END = 'RUSIX_COPY_VMA_END'
PASS = 'RUSIX_COPY_VMA_PASS'
TOTAL = '# Totals: pass:5 fail:0 xfail:0 xpass:0 skip:0 error:0'


def validate(console):
    # Permit serial CRLF, but no arbitrary whitespace/prefix stripping from TAP.
    lines = console.replace('\r\n', '\n').splitlines()
    if re.search(r'(?i:\bwarning\b)|\bBUG\b|Oops:|Kernel panic|CPU feature dependency check failure|ACPI (?:BIOS )?(?:Error|Exception|Warning)|ACPI: Unable to load|Call Trace:|KASAN:|UBSAN:|RUSIX_COPY_VMA_FAIL', console):
        raise ValueError('Kernel/guest diagnostics')
    markers = [line for line in lines if 'RUSIX_COPY_VMA_' in line]
    if markers != [BEGIN, END, PASS]:
        raise ValueError('Missing, duplicate, failed or unknown wrapper markers')
    start, end, passed = (lines.index(marker) for marker in (BEGIN, END, PASS))
    expected = ['TAP version 13', '1..5',
                *[f'ok {i} {name}' for i, name in enumerate(CASES, 1)], TOTAL]
    if lines[start + 1:end] != expected or passed != end + 1:
        raise ValueError('Native five-case TAP inventory/plan/totals differs')
    # A second TAP stream outside the bounded child output cannot certify success.
    outside = lines[:start] + lines[passed + 1:]
    if any(re.match(r'(?:TAP version |\d+\.\.|(?:not )?ok \d|# Totals:)', line) for line in outside):
        raise ValueError('Unexpected TAP outside native output')
    return {'status': 'PASS', 'cases': list(CASES), 'count': 5,
            'scope': 'Native upstream MREMAP_DONTUNMAP success cases only'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('console', type=Path)
    args = parser.parse_args()
    print(json.dumps(validate(args.console.read_text()), indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
