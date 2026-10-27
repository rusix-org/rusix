#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Host-only runner contracts: no compiler, VM or guest invocation."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
SCRIPTS = Path(__file__).resolve().parents[1]/'scripts'
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location('copy_runner', SCRIPTS/'run-copy-vma.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
NATIVE = ('mremap_dontunmap_simple', 'mremap_dontunmap_simple_shmem',
          'mremap_dontunmap_simple_fixed', 'mremap_dontunmap_partial_mapping',
          'mremap_dontunmap_partial_mapping_overwrite')
ORDINARY = ('shared_clone_write_and_exit', 'shared_clone_exec_detaches_mm', 'private_fork_cow',
            'dontfork_omits_only_advised_range', 'wipeonfork_clears_child_and_grandchild',
            'private_file_mapping_cow_and_lifetime', 'shared_file_mapping_survives_parent_unmap',
            'mprotect_middle_split_and_restore', 'fixed_mremap_preserves_unlinked_file_mapping')


def console(kind):
    if kind == 'ordinary':
        return '\n'.join([*[f'RUSIX_VMA_LIFECYCLE_CASE {n} PASS' for n in ORDINARY], 'RUSIX_VMA_LIFECYCLE_PASS'])
    return '\n'.join(['RUSIX_COPY_VMA_BEGIN', 'TAP version 13', '1..5',
                      *[f'ok {i} {n}' for i, n in enumerate(NATIVE, 1)],
                      '# Totals: pass:5 fail:0 xfail:0 xpass:0 skip:0 error:0',
                      'RUSIX_COPY_VMA_END', 'RUSIX_COPY_VMA_PASS'])


class Tests(unittest.TestCase):
    def test_two_exact_independent_inventories(self):
        for kind, names in (('ordinary', ORDINARY), ('native', NATIVE)):
            self.assertEqual(runner.accept_console(kind, console(kind), 0)['cases'], list(names))

    def test_timeout_cannot_pass_after_markers(self):
        for kind in ('ordinary', 'native'):
            for status in (1, 124, 125, 137, 143, -9):
                with self.subTest(kind=kind, status=status), self.assertRaises(ValueError):
                    runner.accept_console(kind, console(kind), status)

    def test_cross_kind_and_unknown_rejected(self):
        for kind, text in (('native', console('ordinary')), ('ordinary', console('native')), ('other', console('native'))):
            with self.assertRaises(ValueError):
                runner.accept_console(kind, text, 0)

    def test_foreign_markers_cannot_hide_after_success(self):
        for kind, foreign in (('ordinary', 'RUSIX_COPY_VMA_FAIL'), ('native', 'RUSIX_VMA_LIFECYCLE_FAIL')):
            with self.assertRaises(ValueError):
                runner.accept_console(kind, console(kind)+'\n'+foreign, 0)

    def test_missing_native_shmem_and_duplicate_ordinary(self):
        with self.assertRaises(ValueError):
            runner.accept_console('native', console('native').replace('ok 2 mremap_dontunmap_simple_shmem\n', ''), 0)
        with self.assertRaises(ValueError):
            runner.accept_console('ordinary', console('ordinary')+'\nRUSIX_VMA_LIFECYCLE_PASS', 0)

    def test_diagnostics_both_boots(self):
        for kind in ('ordinary', 'native'):
            for text in ('warning: bad', 'BUG: broken', 'ACPI BIOS Error: bad', 'CPU feature dependency check failure'):
                with self.subTest(kind=kind, text=text), self.assertRaises(ValueError):
                    runner.accept_console(kind, console(kind)+'\n'+text, 0)

    def test_qemu_resource_bounds_and_distinct_single_guard(self):
        for kind, token in (('ordinary', 'rusix.vma_lifecycle_probe=1'), ('native', 'rusix.copy_vma_probe=1')):
            args = runner.qemu_command(Path('/kernel'), Path('/initramfs'), kind)
            self.assertEqual(args[:4], ['/usr/bin/timeout', '--kill-after=5s', '180s', '/usr/bin/qemu-system-x86_64'])
            for flag, value in (('-machine', 'q35'), ('-accel', 'kvm'), ('-m', '512M'), ('-smp', '2'), ('-nic', 'none')):
                self.assertEqual(args[args.index(flag)+1], value)
            self.assertEqual([w for w in args[-1].split() if w.startswith('rusix.')], [token])
        with self.assertRaises(ValueError):
            runner.qemu_command(Path('/k'), Path('/i'), 'unknown')

    def test_config_delegates_without_relabeling_and_requires_memfd(self):
        names = (*runner.ordinary.REQUIRED_CONFIG, 'MEMFD_CREATE')
        config = '\n'.join('CONFIG_'+n+'=y' for n in names)+'\nCONFIG_KUNIT=n\n'
        with patch.object(runner.selection, 'check_config') as check:
            self.assertEqual(runner.validate_config('copy-vma-rust', config, ''), 'rust')
            self.assertEqual(check.call_args.args[0], 'copy-vma-rust')
            for changed in (config.replace('CONFIG_MEMFD_CREATE=y', 'CONFIG_MEMFD_CREATE=n'),
                            config.replace('CONFIG_KUNIT=n', 'CONFIG_KUNIT=y')):
                with self.assertRaises(ValueError):
                    runner.validate_config('copy-vma-rust', changed, '')
            with self.assertRaises(ValueError):
                runner.validate_config('exit-mmap-rust', config, '')

    def test_prerequisite_copy_is_exact_small_inventory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); proof = root/'proof'; proof.mkdir()
            for prefix in runner.PREPROCESS:
                for suffix in ('json', 'log', 'exit'):
                    (proof/(prefix+'-preprocess.'+suffix)).write_text(prefix+suffix)
            (proof/'unrelated-large-log').write_text('must not copy')
            records = runner.copy_prerequisites(proof, root/'copy')
            self.assertEqual(len(records), 12)
            self.assertEqual(len(list((root/'copy').iterdir())), 12)
            self.assertFalse((root/'copy/unrelated-large-log').exists())
            (proof/'mm-copy-preprocess.json').unlink()
            with self.assertRaises(FileNotFoundError):
                runner.copy_prerequisites(proof, root/'missing')

    def test_postrun_changed_artifact_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); p = root/'artifact'; p.write_bytes(b'original')
            hashes = {str(p): runner.common.digest(p)}
            runner.check_inputs(root, {}, {'input_sha256': hashes}, {})
            p.write_bytes(b'changed')
            with self.assertRaises(ValueError):
                runner.check_inputs(root, {}, {'input_sha256': hashes}, {})

    def test_actual_native_baseline_and_mutation_rejected(self):
        source = SCRIPTS.parents[1]
        manifest = runner.upstream_identity(source)
        self.assertEqual(manifest['baseline'], '2926d88bb7fc4608fd942453d929c39e4e5ec006')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); p = root/'rusix/tests/copy-vma/upstream.json'; p.parent.mkdir(parents=True)
            manifest['baseline'] = 'wrong'; p.write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                runner.upstream_identity(root)

    def test_source_inventory_binds_gate_and_all_selection_sources(self):
        source = SCRIPTS.parents[1]
        extra = source/'include/linux/mm.h'
        names = runner.source_inventory(source, {'input_sha256': {str(extra): 'unused', '/out/object.o': 'unused'}})
        for name in ('include/linux/mm.h', 'rusix/tests/copy-vma/gate.py', 'rusix/tests/copy-vma/upstream.json',
                     'rusix/scripts/exit_kunit_elf.py', 'rusix/scripts/verify-copy-vma.py', *runner.NATIVE_FILES):
            self.assertIn(name, names)
        self.assertFalse(any(name.startswith('rusix/docs/evidence/') for name in names))


if __name__ == '__main__':
    unittest.main()
