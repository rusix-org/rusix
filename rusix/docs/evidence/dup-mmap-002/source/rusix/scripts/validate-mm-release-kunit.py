#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Strict isolated or combined MM release lifecycle acceptance gate."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location(
    'mm_release_completion', Path(__file__).with_name('validate-completion-kunit.py'))
completion = importlib.util.module_from_spec(spec)
spec.loader.exec_module(completion)
common = completion.common

# Independent literal inventory: removing source cases cannot weaken this gate.
SUITES = {'rusix_mm_release': (
    'nonfinal_users_preserve_stack_vma',
    'final_users_preserve_retained_storage',
    'atomic_async_final_release_drains_work',
    'fresh_exec_style_storage_drop_accepts_live_users',
)}


def validate(result, combined=False):
    suites = dict(SUITES)
    if combined:
        suites.update(completion.SUITES)
        suites.update(common.SUITES)
    inventory = list(common.groups(result))
    if any(g['name'].startswith('rusix_') and g['name'] not in suites for g in inventory):
        raise ValueError('Unexpected MM release gate suite')
    present = [g['name'] for g in inventory if g['test_cases']]
    if set(present) != set(suites) or len(present) != len(suites):
        raise ValueError('Missing, duplicate or unexpected MM release gate suite')
    return common.validate(result, suites=suites)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--combined', action='store_true')
    parser.add_argument('results', type=Path)
    args = parser.parse_args()
    try:
        count = validate(json.loads(args.results.read_text()), args.combined)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f'MM release KUnit acceptance failed: {error}\n')
    print(f'MM release KUnit acceptance passed: {count} required cases, all PASS')


if __name__ == '__main__':
    main()
