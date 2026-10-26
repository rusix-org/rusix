#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Regression tests for RCU profile and linked-policy selection rejection."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

PROJECT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'rcu_selection', PROJECT / 'scripts/verify-rcu-list-selection.py')
selection = importlib.util.module_from_spec(spec)
spec.loader.exec_module(selection)


class SelectionTests(unittest.TestCase):
    def config(self, profile):
        return (PROJECT / f'configs/x86_64-{profile}.config').read_text()

    def resolved(self, profile):
        values = selection.config_values(self.config(profile))
        values['CONFIG_RCU_NEED_SEGCBLIST'] = 'y'
        values['CONFIG_X86_64'] = 'y'
        return values

    def test_profiles_differ_only_in_rcu_policy(self):
        for prefix in ('rcu-list-', 'rcu-list-plain-'):
            selection.compare_configs(self.config(prefix + 'c'),
                                      self.config(prefix + 'rust'))
            for kind in ('c', 'rust'):
                selection.check_config(prefix + kind, self.resolved(prefix + kind))

    def test_unexpected_config_difference_rejected(self):
        with self.assertRaises(ValueError):
            selection.compare_configs(self.config('rcu-list-c'),
                                      self.config('rcu-list-rust').replace('CONFIG_NR_CPUS=2',
                                                                         'CONFIG_NR_CPUS=4'))

    def test_excluded_or_missing_dependencies_rejected(self):
        for name, value in (('RCU_NOCB_CPU', 'y'), ('MODULES', 'y'),
                            ('RUSIX_BRD_C_PARAMETER_FIX', 'y'), ('RUST', 'n'),
                            ('RUSIX_COMPLETION_RUST', 'n'), ('RUSIX_BRD_RUST', 'n'),
                            ('TREE_SRCU', 'n'), ('RUSIX_RCU_LIST_TEST', 'n')):
            with self.subTest(name=name):
                config = self.resolved('rcu-list-rust')
                config['CONFIG_' + name] = value
                with self.assertRaises(ValueError):
                    selection.check_config('rcu-list-rust', config)

    def test_wrong_policy_or_non_rcu_profile_rejected(self):
        for profile in ('rcu-list-c', 'server', 'completion-rust'):
            with self.assertRaises(ValueError):
                selection.check_config(profile, self.resolved('rcu-list-rust'))
        selection.check_config('server', {'CONFIG_RUSIX_COMPLETION_RUST': 'y'})

    def test_duplicate_configuration_rejected(self):
        with self.assertRaises(ValueError):
            selection.config_values('CONFIG_RUST=y\n# CONFIG_RUST is not set\n')

    def test_every_symbol_required_once_and_global(self):
        lines = [f'00000000 T {name}' for name in selection.SYMBOLS]
        self.assertEqual(len(lines), 25)
        selection.check_symbols('\n'.join(lines))
        for index in range(len(lines)):
            for bad in (lines[:index] + lines[index + 1:],
                        lines + [lines[index]],
                        lines[:index] + [lines[index].replace(' T ', ' t ')] + lines[index + 1:]):
                with self.assertRaises(ValueError):
                    selection.check_symbols('\n'.join(bad))

    def test_archive_selection_rejects_alternate_duplicate_and_missing_fixture(self):
        symbols = '\n'.join(f'00000000 T {name}' for name in selection.SYMBOLS)
        with tempfile.TemporaryDirectory() as directory:
            evidence = Path(directory)
            for name in ('rcu-object-symbols.txt', 'rcu-kernel-symbols.txt'):
                (evidence / name).write_text(symbols)
            good = '/build/kernel/rcu/rcu_segcblist_rust.o\n/build/kernel/rcu/rcu_list_test.o\n'
            (evidence / 'rcu-archive.txt').write_text(good)
            selection.check_objects('rcu-list-rust', evidence)
            for bad in (good + '/build/kernel/rcu/rcu_segcblist.o\n', good + good,
                        good.splitlines()[0], good.replace('_rust.o', '.o')):
                (evidence / 'rcu-archive.txt').write_text(bad)
                with self.assertRaises(ValueError):
                    selection.check_objects('rcu-list-rust', evidence)


if __name__ == '__main__':
    unittest.main()
