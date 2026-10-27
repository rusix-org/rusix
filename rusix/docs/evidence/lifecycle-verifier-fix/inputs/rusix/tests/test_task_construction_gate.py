#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Host-only acceptance and initramfs tests; never execute a guest binary."""
import importlib.util
from pathlib import Path
import stat
import sys
import unittest

sys.dont_write_bytecode = True
scripts = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(scripts))
spec = importlib.util.spec_from_file_location('task_vm', scripts / 'test-task-construction-vm.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class GateTests(unittest.TestCase):
    def setUp(self):
        self.names = ('fork_private_and_wait', 'exec_fresh_image', 'vfork_exec_handoff',
                      'affinity_inherited', 'seccomp_filter_inherited')
        self.lines = [f'RUSIX_TASK_CONSTRUCTION_CASE {name} PASS' for name in self.names]
        self.lines.append('RUSIX_TASK_CONSTRUCTION_PASS')

    def rejected(self, lines, status=0):
        with self.assertRaises(ValueError):
            runner.accept_console('\n'.join(lines), status)

    def test_exact_literal_inventory(self):
        result = runner.accept_console('\n'.join(self.lines), 0)
        self.assertEqual(result, {'status': 'PASS', 'cases': list(self.names), 'qemu_exit': 0})

    def test_every_missing_and_duplicated_marker_is_rejected(self):
        for i in range(len(self.lines)):
            with self.subTest(i=i):
                self.rejected(self.lines[:i] + self.lines[i+1:])
                self.rejected(self.lines[:i] + [self.lines[i]] + self.lines[i:])

    def test_reorder_and_nonpass_statuses(self):
        self.rejected([self.lines[1], self.lines[0]] + self.lines[2:])
        for status in ('FAIL', 'SKIP', 'UNKNOWN'):
            self.rejected([self.lines[0].replace(' PASS', ' ' + status)] + self.lines[1:])

    def test_extra_fail_unknown_and_prefixed_markers(self):
        for extra in ('RUSIX_TASK_CONSTRUCTION_FAIL cleanup',
                      'RUSIX_TASK_CONSTRUCTION_CASE invented PASS',
                      'RUSIX_TASK_CONSTRUCTION_SKIP',
                      'noise RUSIX_TASK_CONSTRUCTION_PASS'):
            self.rejected(self.lines + [extra])
        self.rejected(['[1.0] ' + line for line in self.lines])

    def test_nonzero_exit_even_after_success(self):
        for status in (1, 124, 125, 137, 143, -9):
            self.rejected(self.lines, status)

    def test_late_diagnostics_rejected(self):
        for diagnostic in ('WARNING: lockdep', 'warning: compiler', 'BUG: failure', 'Oops: fault',
                           'Kernel panic', 'CPU feature dependency check failure',
                           'ACPI BIOS Error: test', 'ACPI Exception: test',
                           'ACPI: Unable to load the System Description Tables'):
            self.rejected(self.lines + [diagnostic])

    def test_nonfault_boot_noise_allowed(self):
        console = '\n'.join(['Booting Linux', 'PCI: report a bug if necessary'] + self.lines + ['Power down'])
        self.assertEqual(runner.accept_console(console, 0)['status'], 'PASS')

    def config(self, rust=False):
        names = set(runner.REQUIRED_CONFIG) | set(runner.selection.REQUIRED)
        values = {f'CONFIG_{name}': 'y' for name in names}
        values.update({f'CONFIG_{name}': 'n' for name in runner.selection.EXCLUDED})
        values[runner.selection.SELECTOR] = 'y' if rust else 'n'
        return '\n'.join(f'{k}={v}' for k, v in values.items())

    def test_config_selection_and_guest_requirements(self):
        for rust in (False, True):
            config = self.config(rust)
            profile = 'task-construction-' + ('rust' if rust else 'c')
            self.assertEqual(runner.validate_config(profile, config, ''), 'rust' if rust else 'c')
            other = 'task-construction-' + ('c' if rust else 'rust')
            with self.assertRaises(ValueError):
                runner.validate_config(other, config, '')
            for name in runner.REQUIRED_CONFIG:
                with self.subTest(name=name), self.assertRaises(ValueError):
                    runner.validate_config(profile, config.replace(f'CONFIG_{name}=y', f'CONFIG_{name}=n'), '')

    def test_config_duplicate_target_drift_and_kunit_rejected(self):
        config = self.config()
        for altered, target in ((config + '\nCONFIG_SMP=y', ''),
                                (config, 'CONFIG_EXT4_FS=y'),
                                (config.replace('CONFIG_KUNIT=n', 'CONFIG_KUNIT=y'), '')):
            with self.assertRaises(ValueError):
                runner.validate_config('task-construction-c', altered, target)

    def test_elf_dynamic_and_wrong_arch_rejected(self):
        header = 'Machine: Advanced Micro Devices X86-64\n'
        runner.static_elf(header)
        for text in ('Machine: AArch64', header + '[Requesting program interpreter: /lib/ld.so]',
                     header + '(NEEDED) Shared library: [libc.so.6]'):
            with self.assertRaises(ValueError):
                runner.static_elf(text)

    def test_initramfs_contains_only_static_fixtures_and_required_nodes(self):
        blob = runner.make_initramfs(b'init-bytes', b'probe-bytes')
        self.assertEqual(blob, runner.make_initramfs(b'init-bytes', b'probe-bytes'))
        offset, records = 0, {}
        while True:
            self.assertEqual(blob[offset:offset+6], b'070701')
            fields = [int(blob[offset+6+i*8:offset+14+i*8], 16) for i in range(13)]
            name = blob[offset+110:offset+110+fields[11]-1].decode()
            start = (offset + 110 + fields[11] + 3) & ~3
            data = blob[start:start+fields[6]]
            records[name] = (fields, data)
            offset = (start + fields[6] + 3) & ~3
            if name == 'TRAILER!!!':
                break
        self.assertEqual(set(records), {'dev', 'proc', 'dev/console', 'init', 'probe', 'TRAILER!!!'})
        self.assertEqual(records['init'][1], b'init-bytes')
        self.assertEqual(records['probe'][1], b'probe-bytes')
        for name in ('init', 'probe'):
            self.assertEqual(records[name][0][1], stat.S_IFREG | 0o755)
        self.assertEqual(records['dev/console'][0][1], stat.S_IFCHR | 0o600)
        self.assertEqual(records['dev/console'][0][9:11], [5, 1])
        self.assertEqual(len(blob) % 512, 0)


if __name__ == '__main__':
    unittest.main()
