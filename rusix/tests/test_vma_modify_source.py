#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Source/config negatives; modeled configs are not actual Kconfig resolution."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT/'rusix/scripts'
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location('modify_source', SCRIPTS/'vma_modify_source.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


# Historical source-only fixtures, never actual preprocessor evidence. Keep the
# original modifier gate strict while testing its original exact source context.
ORIGINAL_ROOT = ROOT
_historical = None

def setUpModule():
    global ROOT, _historical
    import vma_merge_source
    _historical = tempfile.TemporaryDirectory(prefix='historical-modify-')
    ROOT = Path(_historical.name)
    names = ('mm/vma.c', *gate.REVIEWED,
             'rusix/configs/x86_64-server.config', 'rusix/configs/x86_64-copy-vma-rust.config',
             'rusix/configs/x86_64-vma-modify-c.config', 'rusix/configs/x86_64-vma-modify-rust.config')
    for name in names:
        dest=ROOT/name; dest.parent.mkdir(parents=True,exist_ok=True)
        data=(ORIGINAL_ROOT/name).read_text()
        if name=='mm/vma.c':data=vma_merge_source.restore(data,source_context=vma_merge_source.ID)
        dest.write_text(data)

def tearDownModule():
    global ROOT
    if _historical is not None:_historical.cleanup()
    ROOT=ORIGINAL_ROOT


class Source(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = (ROOT/'mm/vma.c').read_text()

    def reject(self, text):
        with self.assertRaises(ValueError):
            gate.restore(text, source_context=gate.ID)

    def test_exact_original_and_inventory(self):
        result = gate.source_policy(ROOT, source_context=gate.ID)
        self.assertEqual(len(result['native_policies']), 11)
        self.assertEqual(len(result['primitives']), 70)
        self.assertEqual(result['restored_vma_sha256'], gate.BASE_SHA256)

    def test_context_required_and_unknown_rejected(self):
        for context in (None, '', 'copy-vma-v1', 'vma-modify-v2'):
            with self.subTest(context=context), self.assertRaises(ValueError):
                gate.restore(self.text, source_context=context)

    def test_missing_guard(self):
        self.reject(self.text.replace('#ifndef '+gate.SELECTOR+'\n', '', 1))

    def test_duplicate_guard(self):
        self.reject(self.text+'\n#ifdef '+gate.SELECTOR+'\n#else\n#endif\n')

    def test_unknown_guard(self):
        self.reject(self.text.replace('#ifdef '+gate.SELECTOR, '#if defined('+gate.SELECTOR+')', 1))

    def test_nested_guard(self):
        self.reject(self.text.replace('#else\nstatic void init_multi_vma_prep',
                                      '#ifdef '+gate.SELECTOR+'\n#endif\n#else\nstatic void init_multi_vma_prep', 1))

    def test_changed_wrapper_argument(self):
        self.reject(self.text.replace('rusix_init_multi_vma_prep(vp, vma, vmg);',
                                      'rusix_init_multi_vma_prep(vp, vma, NULL);', 1))

    def test_native_cleanup_change(self):
        self.reject(self.text.replace('vm_area_free(vp->remove);', 'remove_vma(vp->remove);', 1))

    def test_missing_include(self):
        self.reject(self.text.replace('#include "vma_modify.h"\n', '', 1))

    def test_wrong_terminator(self):
        self.reject(self.text.replace('#endif /* '+gate.SELECTOR+' */', '#endif', 1))

    def test_primitive_missing_duplicate_or_semantic_change(self):
        with tempfile.TemporaryDirectory(prefix='rusix-modify-source-') as directory:
            path = Path(directory)
            (path/'mm').mkdir()
            for name in ('mm/vma.c', *gate.REVIEWED):
                (path/name).write_bytes((ROOT/name).read_bytes())
            impl = path/'mm/vma_modify_impl.h'
            original = impl.read_text()
            for changed in (original.replace('return sysctl_max_map_count;', 'return 0;'),
                            original+'\nvoid rusix_prep_zero(void *p) {}\n',
                            original.replace('rusix_prep_zero', 'rusix_prep_missing')):
                impl.write_text(changed)
                with self.assertRaises(ValueError):
                    gate.source_policy(path, source_context=gate.ID)

    def test_abi_or_rust_change(self):
        with tempfile.TemporaryDirectory(prefix='rusix-modify-source-') as directory:
            path = Path(directory)
            (path/'mm').mkdir()
            for name in ('mm/vma.c', *gate.REVIEWED):
                (path/name).write_bytes((ROOT/name).read_bytes())
            for name in ('mm/vma_modify.h', 'mm/vma_modify_rust.rs'):
                original = (path/name).read_bytes()
                (path/name).write_bytes(original+b'\n')
                with self.assertRaises(ValueError):
                    gate.source_policy(path, source_context=gate.ID)
                (path/name).write_bytes(original)


class Config(unittest.TestCase):
    def setUp(self):
        self.copy = gate.copy_gate()
        self.target = self.copy.config_values((ROOT/'rusix/configs/x86_64-server.config').read_text())
        self.values = {}
        for side in ('c', 'rust'):
            values = self.copy.config_values((ROOT/f'rusix/configs/x86_64-vma-modify-{side}.config').read_text())
            # Explicit modeled resolution of prerequisites; not a Kconfig result.
            values.update({f'CONFIG_{name}':'y' for name in ('X86_64','THREAD_INFO_IN_TASK','MMU','PER_VMA_LOCK')})
            self.values[side] = values

    def test_fragments_derive_exact_parent(self):
        original = self.copy.config_values((ROOT/'rusix/configs/x86_64-copy-vma-rust.config').read_text())
        for side in ('c', 'rust'):
            values = self.copy.config_values((ROOT/f'rusix/configs/x86_64-vma-modify-{side}.config').read_text())
            self.assertEqual(values.pop(gate.SELECTOR), 'y' if side=='rust' else 'n')
            self.assertEqual(values, original)

    def test_exact_pair(self):
        self.assertEqual(gate.compare(self.values['c'], self.values['rust'], self.target,
                                      source_context=gate.ID), [gate.SELECTOR])

    def test_unknown_profile_context_and_wrong_selector(self):
        for profile, context, values in (('copy-vma-rust', gate.ID, self.values['rust']),
                                         ('vma-modify-rust', None, self.values['rust']),
                                         ('vma-modify-rust', gate.ID, self.values['c'])):
            with self.assertRaises(ValueError):
                gate.check_config(profile, values, self.target, source_context=context)

    def test_extra_axis(self):
        self.values['rust']['CONFIG_NEW_UNREVIEWED_OPTION']='y'
        with self.assertRaises(ValueError):
            gate.compare(self.values['c'], self.values['rust'], self.target, source_context=gate.ID)

    def test_ancestors_exclusions_and_fixtures(self):
        for name,value in (('RUSIX_COPY_VMA_RUST','n'),('RUSIX_MM_RELEASE_RUST','n'),
                           ('KUNIT','y'),('PREEMPT_RT','y'),('RUSIX_EXIT_MMAP_TEST','y'),
                           ('RUSIX_UNKNOWN_TEST','y')):
            values=self.values['rust'] | {'CONFIG_'+name:value}
            with self.subTest(name=name), self.assertRaises(ValueError):
                gate.check_config('vma-modify-rust', values, self.target, source_context=gate.ID)


if __name__ == '__main__':
    unittest.main()
