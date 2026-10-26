#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Reject incomplete or mixed RCU sync configuration/object proofs."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
PROJECT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('sync_selection', PROJECT / 'scripts/verify-rcu-sync-selection.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class SelectionTests(unittest.TestCase):
    def config(self, profile):
        return (PROJECT / f'configs/x86_64-{profile}.config').read_text()

    def values(self, profile):
        values = gate.list_selection.config_values(self.config(profile))
        values.update(CONFIG_X86_64='y', CONFIG_RCU_NEED_SEGCBLIST='y')
        return values

    def symbols(self, rust):
        callback = '_RNv18sync_rust13rcu_sync_func' if rust else 'rcu_sync_func'
        return '\n'.join([f'00000000 T {name}' for name in gate.SYMBOLS] +
                         [f'00000000 t {callback}'])

    def test_profile_pairs_only_select_sync(self):
        for prefix in ('rcu-sync-', 'rcu-sync-plain-'):
            gate.compare_configs(self.config(prefix + 'c'), self.config(prefix + 'rust'))
            for kind in ('c', 'rust'):
                gate.check_config(prefix + kind, self.values(prefix + kind))

    def test_changed_dependencies_and_wrong_profile_rejected(self):
        for name, value in (('RUSIX_RCU_LIST_RUST', 'n'), ('RUSIX_RCU_LIST_TEST', 'n'),
                            ('RUSIX_COMPLETION_RUST', 'n'), ('RUSIX_BRD_RUST', 'n'),
                            ('RUSIX_RCU_SYNC_TEST', 'n'), ('RCU_NOCB_CPU', 'y'),
                            ('MODULES', 'y')):
            config = self.values('rcu-sync-rust')
            config['CONFIG_' + name] = value
            with self.subTest(name=name), self.assertRaises(ValueError):
                gate.check_config('rcu-sync-rust', config)
        for profile in ('rcu-sync-c', 'server', 'rcu-list-rust'):
            with self.assertRaises(ValueError):
                gate.check_config(profile, self.values('rcu-sync-rust'))
        gate.check_config('rcu-list-rust', {'CONFIG_RUSIX_RCU_LIST_RUST': 'y'})

    def test_pair_rejects_other_config_change(self):
        with self.assertRaises(ValueError):
            gate.compare_configs(self.config('rcu-sync-c'),
                                 self.config('rcu-sync-rust').replace('CONFIG_NR_CPUS=2', 'CONFIG_NR_CPUS=4'))

    def test_every_public_and_private_symbol_required_once(self):
        for rust in (False, True):
            text = self.symbols(rust)
            gate.check_symbols(text, rust)
            lines = text.splitlines()
            for index in range(len(lines)):
                for bad in (lines[:index] + lines[index + 1:], lines + [lines[index]],
                            lines[:index] + [lines[index].replace(' T ', ' D ').replace(' t ', ' d ')] + lines[index + 1:]):
                    with self.assertRaises(ValueError):
                        gate.check_symbols('\n'.join(bad), rust)
            with self.assertRaises(ValueError):
                gate.check_symbols(self.symbols(not rust), rust)

    def test_real_c_prefix_rows_and_rust_analogue(self):
        public = '\n'.join(f'00000000 T {name}' for name in gate.SYMBOLS)
        # Literal rows from the passed server-C System.map, source ae62.
        actual_c = ('ffffffff812c28e0 t __pfx_rcu_sync_func\n'
                    'ffffffff812c28f0 t rcu_sync_func')
        self.assertEqual(gate.check_symbols(public + '\n' + actual_c, False),
                         'rcu_sync_func')
        rust_callback = '_RNv18sync_rust13rcu_sync_func'
        for callback, rust in (('rcu_sync_func', False), (rust_callback, True)):
            body = f'00000010 t {callback}'
            for prefix in ('__pfx_', '__cfi_'):
                metadata = f'00000000 t {prefix}{callback}'
                good = public + '\n' + metadata + '\n' + body
                gate.check_symbols(good, rust)
                for bad in (good + '\n' + body, good + '\n' + metadata,
                            public + '\n' + metadata,
                            good + '\n00000020 t ' + callback + '.cold',
                            good + '\n00000000 t __pfx_other_rcu_sync_func'):
                    with self.assertRaises(ValueError):
                        gate.check_symbols(bad, rust)

    def test_archive_proof_rejects_alternate_or_missing_fixture(self):
        with tempfile.TemporaryDirectory() as directory:
            evidence = Path(directory)
            for name in ('rcu-sync-object-symbols.txt', 'rcu-kernel-symbols.txt'):
                (evidence / name).write_text(self.symbols(True))
            good = '/out/kernel/rcu/sync_rust.o\n/out/kernel/rcu/rcu_sync_test.o\n'
            (evidence / 'rcu-archive.txt').write_text(good)
            gate.check_objects('rcu-sync-rust', evidence)
            for bad in (good + '/out/kernel/rcu/sync.o\n', good + good,
                        good.replace('sync_rust.o', 'sync.o'), good.splitlines()[0]):
                (evidence / 'rcu-archive.txt').write_text(bad)
                with self.assertRaises(ValueError):
                    gate.check_objects('rcu-sync-rust', evidence)


if __name__ == '__main__':
    unittest.main()
