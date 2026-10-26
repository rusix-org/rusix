#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Require exact C/Rust RCU sync policy selection in dedicated parity profiles."""
import argparse
from collections import Counter
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location(
    'rcu_list_selection', Path(__file__).with_name('verify-rcu-list-selection.py'))
list_selection = importlib.util.module_from_spec(spec)
spec.loader.exec_module(list_selection)
PROFILES = {'rcu-sync-c': False, 'rcu-sync-rust': True,
            'rcu-sync-plain-c': False, 'rcu-sync-plain-rust': True}
SYMBOLS = ('rcu_sync_init', 'rcu_sync_enter', 'rcu_sync_exit', 'rcu_sync_dtor')


def check_config(profile, config):
    rust = config.get('CONFIG_RUSIX_RCU_SYNC_RUST', 'n') == 'y'
    tests = config.get('CONFIG_RUSIX_RCU_SYNC_TEST', 'n') == 'y'
    if profile not in PROFILES:
        if rust or tests:
            raise ValueError('RCU sync selected outside dedicated profiles')
        return
    list_selection.check_config(profile, config)
    if rust != PROFILES[profile] or not tests:
        raise ValueError('Sync policy/fixture selectors do not match profile')
    if config.get('CONFIG_RUSIX_RCU_LIST_RUST') != 'y':
        raise ValueError('Both sync profiles require Rust list policy')


def check_symbols(text, rust):
    public, callbacks, prefixes = Counter(), [], []
    for line in text.splitlines():
        fields = line.split()
        if len(fields) != 3:
            continue
        _, kind, name = fields
        if name in SYMBOLS:
            if kind != 'T':
                raise ValueError('Sync ABI must be global text: ' + line)
            public[name] += 1
        if 'rcu_sync_func' in name:
            # Objtool creates __pfx_<function> for function-prefix padding;
            # compiler CFI metadata uses __cfi_<function>. These are text labels,
            # not second callback definitions. Validate their matching function
            # below instead of ignoring every name containing the callback token.
            prefix = next((p for p in ('__pfx_', '__cfi_') if name.startswith(p)), None)
            if prefix:
                if kind not in ('T', 't'):
                    raise ValueError('Callback prefix is not text: ' + line)
                prefixes.append((name, name[len(prefix):]))
                continue
            if kind not in ('T', 't'):
                raise ValueError('Sync callback must be executable text: ' + line)
            if (name != 'rcu_sync_func') != rust:
                raise ValueError('Callback definition belongs to alternate implementation')
            callbacks.append(name)
    if public != Counter(SYMBOLS) or len(callbacks) != 1:
        raise ValueError('Expected four unique ABI definitions and one private sync callback')
    if (len({name for name, _ in prefixes}) != len(prefixes) or
            any(target != callbacks[0] for _, target in prefixes)):
        raise ValueError('Duplicate or unmatched callback prefix label')
    return callbacks[0]


def check_objects(profile, evidence):
    if profile not in PROFILES:
        raise ValueError('Object proof requires dedicated sync profile')
    rust = PROFILES[profile]
    selected = 'sync_rust.o' if rust else 'sync.o'
    archive = [Path(line).name for line in
               (evidence / 'rcu-archive.txt').read_text().splitlines()]
    if [name for name in archive if name in ('sync.o', 'sync_rust.o')] != [selected]:
        raise ValueError('Wrong, missing or duplicate sync policy archive member')
    if archive.count('rcu_sync_test.o') != 1:
        raise ValueError('Expected one sync fixture archive member')
    callback = check_symbols((evidence / 'rcu-sync-object-symbols.txt').read_text(), rust)
    linked_callback = check_symbols((evidence / 'rcu-kernel-symbols.txt').read_text(), rust)
    if callback != linked_callback:
        raise ValueError('Linked callback identity differs from selected object')
    return {'implementation': 'rust' if rust else 'c', 'object': selected,
            'definitions': list(SYMBOLS), 'callback': callback,
            'scope': 'Archive/object/linked selection only; no runtime assertion'}


def compare_configs(c_text, rust_text):
    c, rust = map(list_selection.config_values, (c_text, rust_text))
    key = 'CONFIG_RUSIX_RCU_SYNC_RUST'
    if c.get(key, 'n') != 'n' or rust.get(key) != 'y':
        raise ValueError('Expected C then Rust sync selection')
    for config in (c, rust):
        for name in ('CONFIG_RUSIX_RCU_LIST_RUST', 'CONFIG_RUSIX_COMPLETION_RUST',
                     'CONFIG_RUSIX_BRD_RUST', 'CONFIG_RUSIX_RCU_SYNC_TEST'):
            if config.get(name) != 'y':
                raise ValueError('Missing retained policy/fixture: ' + name)
    differences = {name for name in c.keys() | rust.keys()
                   if c.get(name, 'n') != rust.get(name, 'n')}
    if differences != {key}:
        raise ValueError(f'Pair differs beyond sync policy: {sorted(differences)}')
    return {'different_settings': sorted(differences)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('config', 'objects'):
        child = sub.add_parser(name)
        child.add_argument('--profile', required=True)
        child.add_argument('--config', required=True, type=Path)
        if name == 'objects':
            child.add_argument('--evidence', required=True, type=Path)
    child = sub.add_parser('compare')
    child.add_argument('--c', required=True, type=Path)
    child.add_argument('--rust', required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.command == 'compare':
            result = compare_configs(args.c.read_text(), args.rust.read_text())
        else:
            check_config(args.profile, list_selection.config_values(args.config.read_text()))
            result = ({'profile': args.profile, 'configuration': 'PASS'}
                      if args.command == 'config' else check_objects(args.profile, args.evidence))
        print(json.dumps(result, indent=2))
    except (ValueError, OSError) as error:
        parser.exit(1, f'RCU sync selection rejected: {error}\n')


if __name__ == '__main__':
    main()
