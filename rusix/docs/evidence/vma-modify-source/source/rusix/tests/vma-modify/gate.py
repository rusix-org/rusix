#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Accept exactly five unchanged native mprotect topology cases; no execution."""
import argparse
import json
from pathlib import Path
import re

CASES = tuple('merge.' + name for name in (
    'mprotect_unfaulted_left', 'mprotect_unfaulted_right',
    'mprotect_unfaulted_both', 'mprotect_faulted_left_unfaulted_right',
    'mprotect_unfaulted_left_faulted_right'))
BEGIN, END, PASS = ('RUSIX_VMA_MODIFY_' + suffix for suffix in ('BEGIN', 'END', 'PASS'))
TOTAL = '# Totals: pass:5 fail:0 xfail:0 xpass:0 skip:0 error:0'


def expected_output():
    lines = ['TAP version 13', '1..5', '# Starting 5 tests from 1 test cases.']
    for index, name in enumerate(CASES, 1):
        lines.extend(('#  RUN           ' + name + ' ...',
                      '# ' + '         ' + f'{"OK":>4}' + '  ' + name,
                      f'ok {index} {name}'))
    return [*lines, '# PASSED: 5 / 5 tests passed.', TOTAL]


def validate(console):
    lines = console.replace('\r\n', '\n').splitlines()
    if re.search(r'(?i:\bwarning\b)|\bBUG\b|Oops:|Kernel panic|Call Trace:|KASAN:|UBSAN:|ACPI (?:BIOS )?(?:Error|Exception|Warning)|CPU feature dependency check failure|ACPI: Unable to load|RUSIX_VMA_MODIFY_FAIL', console):
        raise ValueError('Kernel or guest diagnostics')
    if [line for line in lines if 'RUSIX_VMA_MODIFY_' in line] != [BEGIN, END, PASS]:
        raise ValueError('Missing, duplicate, failed or unknown wrapper markers')
    begin, end, passed = (lines.index(marker) for marker in (BEGIN, END, PASS))
    if lines[begin + 1:end] != expected_output() or passed != end + 1:
        raise ValueError('Native five-case harness inventory, status or totals differs')
    outside = lines[:begin] + lines[passed + 1:]
    if any(re.match(r'(?:TAP version |\d+\.\.|(?:not )?ok \d|# Totals:|# (?:Starting|PASSED|FAILED):?)', line) for line in outside):
        raise ValueError('Additional native harness output outside wrapper')
    return {'status': 'PASS', 'cases': list(CASES), 'count': 5,
            'scope': 'Native upstream mprotect split/merge topology success cases only'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('console', type=Path)
    args = parser.parse_args()
    print(json.dumps(validate(args.console.read_text()), indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
