#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""C-first batch fixture selection; no Rust batch policy claim."""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location('batch_lists', Path(__file__).with_name('verify-rcu-list-selection.py'))
lists = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lists)
PROFILES = ('rcu-batch-c', 'rcu-batch-plain-c')
HOOKS = ('rusix_rcubatch_private', 'rusix_rcubatch_private_accounting', 'rusix_rcubatch_time_samples')
FIXTURE = ('rusix_rcubatch_start', 'rusix_rcubatch_wait', 'rusix_rcubatch_result', 'rusix_rcubatch_put')
ORIGINAL_TREE_SHA256 = 'e44083c2f67df3a0de8f08a7a59d42c7d854d283c66b7e481b64a9fc36f2ef73'


def check_config(profile, config):
    enabled = config.get('CONFIG_RUSIX_RCU_BATCH_TEST', 'n') == 'y'
    if profile not in PROFILES:
        if enabled:
            raise ValueError('Batch fixture selected outside explicit C-first profiles')
        return
    lists.check_config(profile, config)
    if not enabled:
        raise ValueError('Missing batch fixtures')
    for name in ('RCU_NOCB_CPU', 'RCU_BOOST', 'PREEMPT_RT', 'MODULES'):
        if config.get('CONFIG_' + name, 'n') != 'n':
            raise ValueError('Unsupported batch fixture configuration: ' + name)
    for name in ('RUSIX_RCU_LIST_RUST', 'RUSIX_COMPLETION_RUST', 'RUSIX_BRD_RUST'):
        if config.get('CONFIG_' + name) != 'y':
            raise ValueError('Missing existing Rust dependency: ' + name)


def original_policy(source):
    text = source.read_bytes()
    start = b'#ifdef CONFIG_RUSIX_RCU_BATCH_TEST\n'
    end = b'/*\n * This function is invoked from each scheduling-clock interrupt,'
    if text.count(start) != 1 or text.count(end) != 1:
        raise ValueError('Missing/ambiguous test-only boundary')
    first, rest = text.split(start)
    _, last = rest.split(end)
    if hashlib.sha256(first + end + last).hexdigest() != ORIGINAL_TREE_SHA256:
        raise ValueError('Original C tree policy changed outside approved test-only region')


def symbols(path, required):
    found = Counter()
    for line in path.read_text().splitlines():
        fields = line.split()
        if len(fields) == 3 and fields[2] in required:
            if fields[1] != 'T':
                raise ValueError('Fixture symbol is not global text')
            found[fields[2]] += 1
    if found != Counter(required):
        raise ValueError('Missing/duplicate fixture definition')


def check_objects(profile, evidence, source):
    if profile not in PROFILES:
        raise ValueError('Object proof requires explicit C-first batch profile')
    original_policy(source)
    entries = [Path(row).name for row in (evidence / 'rcu-archive.txt').read_text().splitlines()]
    if entries.count('tree.o') != 1 or entries.count('rcu_batch_test.o') != 1:
        raise ValueError('Missing/duplicate C batch or fixture object')
    if any('batch' in name and name != 'rcu_batch_test.o' for name in entries):
        raise ValueError('Unexpected alternative batch object')
    symbols(evidence / 'rcu-batch-tree-symbols.txt', HOOKS)
    symbols(evidence / 'rcu-batch-fixture-symbols.txt', FIXTURE)
    symbols(evidence / 'rcu-batch-kernel-symbols.txt', HOOKS + FIXTURE)
    return {'status': 'PASS', 'implementation': 'c', 'fixture': 'rcu_batch_test.o',
            'original_tree_sha256': ORIGINAL_TREE_SHA256,
            'definitions': list(HOOKS + FIXTURE),
            'scope': 'Unchanged C batch with test-only entry points; runtime acceptance is separate'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('config', 'objects'))
    parser.add_argument('--profile', required=True)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--evidence', type=Path)
    parser.add_argument('--source', type=Path)
    args = parser.parse_args()
    check_config(args.profile, lists.config_values(args.config.read_text()))
    if args.command == 'objects':
        print(json.dumps(check_objects(args.profile, args.evidence, args.source), indent=2))


if __name__ == '__main__':
    main()
