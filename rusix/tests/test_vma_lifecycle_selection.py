#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Host-only negative selection tests; synthetic ELF is not runtime evidence."""
import copy
import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest
ROOT = Path(__file__).resolve().parents[2]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT/'rusix/scripts'))
spec = importlib.util.spec_from_file_location('vma_gate', ROOT/'rusix/scripts/verify-vma-lifecycle.py')
gate = importlib.util.module_from_spec(spec); spec.loader.exec_module(gate)


def metadata(name='vm_area_cachep', size=8, typ=1, section='.bss', section_type=8, flags=3, binding=0):
    return [{'FileSummary': {'Format': 'elf64-x86-64', 'Arch': 'x86_64'},
             'Sections': [{'Section': {'Index': 1, 'Name': {'Name': section}, 'Type': {'Value': section_type},
                                      'Flags': {'Value': flags}, 'Address': 0, 'Size': 64, 'AddressAlignment': 8}}],
             'Symbols': [{'Symbol': {'Name': {'Name': name}, 'Size': size, 'Type': {'Value': typ},
                                    'Binding': {'Value': binding}, 'Value': 0, 'Section': {'Value': 1}}},
                         {'Symbol': {'Name': {'Name': section}, 'Size': 0, 'Type': {'Value': 3},
                                     'Binding': {'Value': 0}, 'Value': 0, 'Section': {'Value': 1}}}]}]


class Selection(unittest.TestCase):
    def test_original_source(self):
        text = (ROOT/'mm/vma_init.c').read_text()
        original = subprocess.check_output(['git', 'show', '9cf27ef36d1d58cb65bd866d9f046ed2e56b045a:mm/vma_init.c'], cwd=ROOT, text=True)
        self.assertEqual(gate.original_policy(text), original)
        for bad in (text+'\n', text.replace('rusix_vma_state_init();', 'return;'),
                    text.replace('sheaf_capacity = 32', 'sheaf_capacity = 16'), text+gate.END):
            with self.assertRaises(ValueError): gate.original_policy(bad)

    def test_exact_preprocessed_cache_metadata(self):
        text = ('void vma_state_init(void){rusix_vma_state_init();}'
                'struct kmem_cache *rusix_vma_cache_create(void){'+gate.CACHE_ARGS+'return'+gate.CACHE_CALL+'}')
        gate.check_preprocessed(text, True)
        for old, new in (('32', '16'), ('vm_freeptr', 'vm_mm'), ('true', 'false'),
                         ('_SLAB_PANIC', '_SLAB_DEBUG'), ('"vm_area_struct"', '"wrong"')):
            with self.assertRaises(ValueError): gate.check_preprocessed(text.replace(old, new), True)
        for extra in ('void vm_area_free(void){return;}', 'static struct kmem_cache *vm_area_cachep;', text):
            with self.assertRaises(ValueError): gate.check_preprocessed(text+extra, True)
        with self.assertRaises(ValueError): gate.check_preprocessed(text, False)

    def test_cache_storage_type_size_alignment_lifetime(self):
        self.assertEqual(gate.cache_owner(metadata(), False), 'vm_area_cachep')
        rust = '_RNvtestVM_AREA_CACHE'
        self.assertEqual(gate.cache_owner(metadata(name=rust), True), rust)
        for kwargs in ({'size': 4}, {'typ': 2}, {'section': '.init.bss'}, {'section_type': 1},
                       {'flags': 2}, {'flags': 7}, {'binding': 1}):
            with self.assertRaises(ValueError): gate.cache_owner(metadata(**kwargs), False)
        for key, value in (('Value', 1), ('Size', 100)):
            bad = metadata(); bad[0]['Symbols'][0]['Symbol'][key] = value
            with self.assertRaises(ValueError): gate.cache_owner(bad, False)
        bad = metadata(); bad[0]['Symbols'].append(copy.deepcopy(bad[0]['Symbols'][0]))
        with self.assertRaises(ValueError): gate.cache_owner(bad, False)
        with self.assertRaises(ValueError): gate.cache_owner(metadata(), True)
        with self.assertRaises(ValueError): gate.cache_owner(metadata(), False, False)

    def test_cache_observed_suffix_only(self):
        name = '_RNvCs9a2lGAoVDsO_18vma_lifecycle_rust13VM_AREA_CACHE'
        for accepted in (name, name+'.0'):
            self.assertEqual(gate.cache_owner(metadata(name=accepted), True), accepted)
        for suffix in ('.1', '.00', '.llvm.1', '.0.extra', '.cold', '.0\n'):
            with self.subTest(suffix=suffix), self.assertRaises(ValueError):
                gate.cache_owner(metadata(name=name+suffix), True)
        duplicate = metadata(name=name+'.0')
        duplicate[0]['Symbols'].append(metadata(name=name)[0]['Symbols'][0])
        with self.assertRaises(ValueError):
            gate.cache_owner(duplicate, True)

    def test_refcount_constant_storage_and_value(self):
        class Elf:
            relocatable = True
            names = ['.rodata']
            headers = [[0, 1, 2, 0, 0, 4]]
            data = (0x7fffffff).to_bytes(4, 'little')
            sym = dict(kind=1, size=4, address=0)
            offset = 0
            def symbol(self, name): return self.sym
            def location(self, sym): return 0, self.offset
            def section_data(self, index): return self.data
        nm = '00000000 R rusix_vma_refcount_max'
        self.assertEqual(gate.refcount_constant(Elf(), nm, linked=False), 0x7fffffff)
        linked = Elf(); linked.relocatable = False; linked.headers = [[0, 1, 0x33, 0, 0, 4]]
        self.assertEqual(gate.refcount_constant(linked, nm.replace(' R ', ' D '), linked=True), 0x7fffffff)
        for key, value in (('kind', 2), ('size', 8), ('address', 1)):
            bad = Elf(); bad.sym = dict(Elf.sym, **{key: value})
            with self.subTest(key=key), self.assertRaises(ValueError):
                gate.refcount_constant(bad, nm, linked=False)
        for change in ({'names':['.data']}, {'headers':[[0,1,6,0,0,4]]},
                       {'headers':[[0,1,3,0,0,4]]}, {'headers':[[0,1,2,0,0,3]]},
                       {'data':b'\xff'*4}, {'offset':-1}, {'relocatable':False}):
            bad = Elf()
            for key,value in change.items(): setattr(bad,key,value)
            with self.subTest(change=change), self.assertRaises(ValueError):
                gate.refcount_constant(bad, nm, linked=False)
        for bad_nm in (nm.replace(' R ', ' D '), nm.replace(' R ', ' r '), nm+'\n'+nm):
            with self.assertRaises(ValueError): gate.refcount_constant(Elf(), bad_nm, linked=False)

    def test_init_and_live_function_sections(self):
        live = metadata(name='vm_area_alloc', size=16, typ=2, section='.text.vm_area_alloc', section_type=1, flags=6, binding=1)
        gate.function_location(live, 'vm_area_alloc', False)
        with self.assertRaises(ValueError): gate.function_location(live, 'vm_area_alloc', True)
        init = metadata(name='vma_state_init', size=16, typ=2, section='.init.text', section_type=1, flags=6, binding=1)
        gate.function_location(init, 'vma_state_init', True)
        with self.assertRaises(ValueError): gate.function_location(init, 'vma_state_init', False)
        bad = copy.deepcopy(init); bad[0]['Symbols'][0]['Symbol']['Section']['Value'] = 9
        with self.assertRaises(ValueError): gate.function_location(bad, 'vma_state_init', True)

    def test_real_dispatch_instruction_and_function_scope(self):
        text = '0000 <vma_state_init>:\n 0: callq 0\n 1: R_X86_64_PLT32 rusix_vma_state_init-0x4\n'
        gate.call_from(text, 'vma_state_init', gate.BRIDGE)
        for bad in (text.replace('callq', 'movq'), text.replace('PLT32', '64'), text.replace('-0x4', '+0x4'),
                    text.replace('<vma_state_init>', '<unrelated>'), text+text):
            with self.assertRaises(ValueError): gate.call_from(bad, 'vma_state_init', gate.BRIDGE)

    def test_cache_relocations_named_and_section_bound(self):
        for target in ('vm_area_cachep', '.bss'):
            text = f'0000 <vm_area_alloc>:\n 0: movq (%rip), %rdi\n 1: R_X86_64_PC32 {target}-0x4\n'
            gate.cache_accesses(text, metadata(), 'vm_area_cachep', ('vm_area_alloc',))
            for bad in (text.replace('-0x4', '+0x4'), text.replace('movq', 'callq'), text.replace(target, '.init.data')):
                with self.assertRaises(ValueError): gate.cache_accesses(bad, metadata(), 'vm_area_cachep', ('vm_area_alloc',))
        with self.assertRaises(ValueError): gate.cache_accesses(text, metadata(), 'vm_area_cachep', ('vm_area_free',))

    def test_archive_and_definition_ownership(self):
        gate.archive_members('vma_init.o\nvma_lifecycle_rust.o\n', True)
        gate.archive_members('vma_init.o\n', False)
        for text in ('vma_init.o\n', 'vma_init.o\nvma_init.o\nvma_lifecycle_rust.o\n',
                     'vma_init.o\nvma_lifecycle_rust.o\nvma_lifecycle_other.o\n'):
            with self.assertRaises(ValueError): gate.archive_members(text, True)
        gate.definitions('0 T vma_state_init\n', {'vma_state_init'})
        for text in ('', '0 D vma_state_init\n', '0 T vma_state_init\n1 T vm_area_free\n'):
            with self.assertRaises(ValueError): gate.definitions(text, {'vma_state_init'})

    def test_pair_and_inherited_config(self):
        values = gate.config_values((ROOT/'rusix/configs/x86_64-mm-dup-mmap-rust.config').read_text())
        values.update(CONFIG_X86_64='y', CONFIG_THREAD_INFO_IN_TASK='y', CONFIG_MMU='y', CONFIG_PER_VMA_LOCK='y')
        target = gate.config_values((ROOT/'rusix/configs/x86_64-server.config').read_text())
        c = values | {gate.SELECTOR: 'n'}; rust = values | {gate.SELECTOR: 'y'}
        self.assertEqual(gate.compare(c, rust), [gate.SELECTOR])
        for profile, config in (('vma-lifecycle-c', c), ('vma-lifecycle-rust', rust)):
            gate.check_config(profile, config, target)
            for key in (gate.SELECTOR, gate.dup.SELECTOR, 'CONFIG_PER_VMA_LOCK'):
                bad = config.copy(); bad.pop(key)
                with self.assertRaises(ValueError): gate.check_config(profile, bad, target)
            with self.assertRaises(ValueError): gate.check_config(profile, config | {'CONFIG_NUMA': 'y'}, target)
        with self.assertRaises(ValueError): gate.compare(c, rust | {'CONFIG_SWAP': 'y'})

    def test_full_dependency_chain(self):
        b, s = Path('/out/builds/x'), Path('/src')
        paths = gate.input_paths(b, s, True)
        self.assertEqual(len(paths), len(set(paths)))
        for p in gate.dup.input_paths(b, s, True): self.assertIn(p, paths)
        for name in ('mm/vma_init.c', 'mm/vma_lifecycle_impl.h', 'mm/vma_lifecycle_rust.rs',
                     'include/linux/slab.h', 'include/linux/mmap_lock.h', 'rusix/scripts/saved_clang_command.py'):
            self.assertIn(s/name, paths)
        self.assertIn(b/'mm/vma_lifecycle_rust.o', paths)
        self.assertNotIn(b/'mm/vma_lifecycle_rust.o', gate.input_paths(b, s, False))


if __name__ == '__main__': unittest.main()
