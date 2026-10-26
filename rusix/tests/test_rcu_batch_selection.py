#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Reject missing C-first fixture selection and accidental production changes."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

PROJECT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('batch_selection', PROJECT / 'scripts/verify-rcu-batch-selection.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class BatchSelection(unittest.TestCase):
    def config(self, profile):
        values = gate.lists.config_values((PROJECT / f'configs/x86_64-{profile}.config').read_text())
        values.update(CONFIG_X86_64='y', CONFIG_RCU_NEED_SEGCBLIST='y')
        return values

    def evidence(self, root):
        (root / 'rcu-archive.txt').write_text('/out/tree.o\n/out/rcu_batch_test.o\n')
        for name, symbols in (('tree', gate.HOOKS), ('fixture', gate.FIXTURE),
                              ('kernel', gate.HOOKS + gate.FIXTURE)):
            (root / f'rcu-batch-{name}-symbols.txt').write_text(''.join('1000 T ' + s + '\n' for s in symbols))

    def test_profiles_require_fixture_and_existing_rust_dependencies(self):
        for profile in gate.PROFILES:
            original = self.config(profile)
            gate.check_config(profile, original)
            for name in ('RUSIX_RCU_BATCH_TEST', 'RUSIX_RCU_LIST_TEST', 'RUSIX_RCU_LIST_RUST',
                         'RUSIX_COMPLETION_RUST', 'RUSIX_BRD_RUST', 'KUNIT'):
                changed = dict(original); changed['CONFIG_' + name] = 'n'
                with self.assertRaises(ValueError): gate.check_config(profile, changed)
            for name in ('RCU_NOCB_CPU', 'RCU_BOOST', 'PREEMPT_RT', 'MODULES'):
                changed = dict(original); changed['CONFIG_' + name] = 'y'
                with self.assertRaises(ValueError): gate.check_config(profile, changed)
        with self.assertRaises(ValueError): gate.check_config('rcu-list-rust', self.config('rcu-batch-c'))

    def test_unchanged_original_tree_and_mutation_rejected(self):
        source = PROJECT.parent / 'kernel/rcu/tree.c'
        gate.original_policy(source)
        with tempfile.TemporaryDirectory() as directory:
            changed = Path(directory) / 'tree.c'
            changed.write_bytes(source.read_bytes().replace(b'long count = 0;', b'long count = 1;', 1))
            with self.assertRaises(ValueError): gate.original_policy(changed)

    def test_exact_object_and_symbol_inventory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.evidence(root)
            source = PROJECT.parent / 'kernel/rcu/tree.c'
            self.assertEqual(gate.check_objects('rcu-batch-c', root, source)['implementation'], 'c')
            for text in ('/out/tree.o\n', '/out/tree.o\n/out/rcu_batch_test.o\n/out/rcu_batch_test.o\n',
                         '/out/tree.o\n/out/rcu_batch_test.o\n/out/rcu_batch_rust.o\n'):
                (root / 'rcu-archive.txt').write_text(text)
                with self.assertRaises(ValueError): gate.check_objects('rcu-batch-c', root, source)
            self.evidence(root)
            path = root / 'rcu-batch-tree-symbols.txt'
            path.write_text(path.read_text() + '1000 T ' + gate.HOOKS[0] + '\n')
            with self.assertRaises(ValueError): gate.check_objects('rcu-batch-c', root, source)

    def test_debug_and_plain_keep_same_fixture_dependency_set(self):
        debug, plain = [self.config(p) for p in gate.PROFILES]
        for name in ('RUSIX_RCU_BATCH_TEST', 'RUSIX_RCU_LIST_TEST', 'RUSIX_RCU_LIST_RUST',
                     'RUSIX_COMPLETION_RUST', 'RUSIX_BRD_RUST'):
            self.assertEqual(debug['CONFIG_' + name], plain['CONFIG_' + name])
        self.assertEqual(debug['CONFIG_PROVE_LOCKING'], 'y')
        self.assertNotEqual(plain.get('CONFIG_PROVE_LOCKING'), 'y')


if __name__ == '__main__': unittest.main()
