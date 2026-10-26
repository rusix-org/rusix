#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Bind dedicated RCU profiles to their exact configuration and linked policy."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re

PROFILES = {
    'rcu-batch-c': True, 'rcu-batch-plain-c': True,
    'rcu-list-c': False, 'rcu-list-rust': True,
    'rcu-list-plain-c': False, 'rcu-list-plain-rust': True,
    'rcu-list-ext4-c': False, 'rcu-list-ext4-rust': True,
    'rcu-list-server-c': False, 'rcu-list-server-rust': True,
}
PRODUCTION_PROFILES = frozenset(('rcu-list-ext4-c', 'rcu-list-ext4-rust',
                                 'rcu-list-server-c', 'rcu-list-server-rust'))
SYMBOLS = (
    'rcu_cblist_init', 'rcu_cblist_enqueue', 'rcu_cblist_flush_enqueue',
    'rcu_cblist_dequeue', 'rcu_segcblist_get_seglen',
    'rcu_segcblist_n_segment_cbs', 'rcu_segcblist_add_len',
    'rcu_segcblist_inc_len', 'rcu_segcblist_init', 'rcu_segcblist_disable',
    'rcu_segcblist_ready_cbs', 'rcu_segcblist_pend_cbs',
    'rcu_segcblist_first_cb', 'rcu_segcblist_first_pend_cb',
    'rcu_segcblist_nextgp', 'rcu_segcblist_enqueue', 'rcu_segcblist_entrain',
    'rcu_segcblist_extract_done_cbs', 'rcu_segcblist_extract_pend_cbs',
    'rcu_segcblist_insert_count', 'rcu_segcblist_insert_done_cbs',
    'rcu_segcblist_insert_pend_cbs', 'rcu_segcblist_advance',
    'rcu_segcblist_accelerate', 'rcu_segcblist_merge',
)


def config_values(text):
    result = {}
    for line in text.splitlines():
        match = re.fullmatch(r'(CONFIG_[A-Z0-9_]+)=(.*)', line)
        disabled = re.fullmatch(r'# (CONFIG_[A-Z0-9_]+) is not set', line)
        if match or disabled:
            name, value = match.groups() if match else (disabled[1], 'n')
            if name in result:
                raise ValueError(f'duplicate configuration: {name}')
            result[name] = value
    return result


def check_config(profile, config):
    rust = config.get('CONFIG_RUSIX_RCU_LIST_RUST', 'n') == 'y'
    fixture = config.get('CONFIG_RUSIX_RCU_LIST_TEST', 'n') == 'y'
    if profile not in PROFILES:
        if rust or fixture:
            raise ValueError('RCU migration selected outside explicit RCU profiles')
        return
    expected_fixture = profile not in PRODUCTION_PROFILES
    if rust != PROFILES[profile] or fixture != expected_fixture:
        raise ValueError('RCU policy/test selector does not match profile')
    if (config.get('CONFIG_KUNIT', 'n') == 'y') != expected_fixture:
        raise ValueError('KUnit selection does not match profile')
    if expected_fixture and config.get('CONFIG_TREE_SRCU') != 'y':
        raise ValueError('RCU fixtures require TREE_SRCU')
    for name in ('RUST', 'X86_64', 'SMP', 'TREE_RCU',
                 'RCU_NEED_SEGCBLIST', 'RUSIX_COMPLETION_RUST',
                 'RUSIX_BRD_RUST', 'BLK_DEV_RAM'):
        if config.get('CONFIG_' + name) != 'y':
            raise ValueError(f'missing required setting: {name}')
    for name in ('MODULES', 'RCU_NOCB_CPU', 'RUSIX_BRD_C_PARAMETER_FIX'):
        if config.get('CONFIG_' + name, 'n') != 'n':
            raise ValueError(f'excluded setting enabled: {name}')


def check_symbols(text):
    symbols = Counter()
    for line in text.splitlines():
        fields = line.split()
        if len(fields) == 3 and fields[2] in SYMBOLS:
            if fields[1] != 'T':
                raise ValueError(f'policy symbol is not global executable text: {line}')
            symbols[fields[2]] += 1
    if symbols != Counter(SYMBOLS):
        raise ValueError('expected exactly one definition of each of 25 policy symbols')


def check_objects(profile, evidence):
    if profile not in PROFILES:
        raise ValueError('object proof requires dedicated RCU profile')
    selected = 'rcu_segcblist_rust.o' if PROFILES[profile] else 'rcu_segcblist.o'
    entries = (evidence / 'rcu-archive.txt').read_text().splitlines()
    actual = [Path(entry).name for entry in entries
              if Path(entry).name in ('rcu_segcblist.o', 'rcu_segcblist_rust.o')]
    if actual != [selected]:
        raise ValueError(f'RCU archive selection mismatch: {actual}')
    expected_fixture = 0 if profile in PRODUCTION_PROFILES else 1
    if sum(Path(entry).name == 'rcu_list_test.o' for entry in entries) != expected_fixture:
        raise ValueError('RCU fixture object count does not match profile')
    for name in ('rcu-object-symbols.txt', 'rcu-kernel-symbols.txt'):
        check_symbols((evidence / name).read_text())
    return {'implementation': 'rust' if PROFILES[profile] else 'c',
            'object': selected, 'definitions': list(SYMBOLS),
            'scope': 'Archive/object/linked symbol selection, not runtime evidence'}


def compare_configs(c_text, rust_text):
    c, rust = config_values(c_text), config_values(rust_text)
    key = 'CONFIG_RUSIX_RCU_LIST_RUST'
    if c.get(key, 'n') != 'n' or rust.get(key) != 'y':
        raise ValueError('comparison requires C then Rust RCU selection')
    differences = {name for name in c.keys() | rust.keys()
                   if c.get(name, 'n') != rust.get(name, 'n')}
    if differences != {key}:
        raise ValueError(f'pair differs beyond RCU policy: {sorted(differences)}')
    return {'different_settings': sorted(differences)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ('config', 'objects'):
        child = sub.add_parser(command)
        child.add_argument('--profile', required=True)
        child.add_argument('--config', required=True, type=Path)
        if command == 'objects':
            child.add_argument('--evidence', required=True, type=Path)
    child = sub.add_parser('compare')
    child.add_argument('--c', required=True, type=Path)
    child.add_argument('--rust', required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.command == 'compare':
            result = compare_configs(args.c.read_text(), args.rust.read_text())
        else:
            check_config(args.profile, config_values(args.config.read_text()))
            result = ({'profile': args.profile, 'configuration': 'PASS'}
                      if args.command == 'config' else
                      check_objects(args.profile, args.evidence))
        print(json.dumps(result, indent=2))
    except (OSError, ValueError) as error:
        parser.exit(1, f'RCU list selection rejected: {error}\n')


if __name__ == '__main__':
    main()
