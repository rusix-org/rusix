#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Modeled ownership/preprocessor negatives; no compiled candidate evidence."""
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[2]
SCRIPTS=ROOT/'rusix/scripts'
sys.path.insert(0,str(SCRIPTS))
spec=importlib.util.spec_from_file_location('modify_selection',SCRIPTS/'verify-vma-modify.py')
gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)

class Selection(unittest.TestCase):
    def test_actual_source_extension_restores_ancestors(self):
        record=gate.copy.source_policy(ROOT,source_context=gate.extension.ID)
        self.assertEqual(record['extension'],gate.extension.ID)
        with self.assertRaises(ValueError):gate.copy.source_policy(ROOT)
        with self.assertRaises(ValueError):gate.copy.source_policy(ROOT,source_context='unknown')

    def test_input_closure_and_original_four_units(self):
        paths={str(p) for p in gate.input_paths(Path('/out/builds/test'),Path('/src'),True)}
        for name in ('vma_modify.h','vma_modify_impl.h','vma_modify_rust.rs'):
            self.assertIn('/src/mm/'+name,paths)
        for name in ('vma_modify_source.py','verify-vma-modify.py','preprocess-vma-modify.py',
                     'verify-copy-vma.py','exit_mmap_source.py','saved_clang_command.py'):
            self.assertIn('/src/rusix/scripts/'+name,paths)
        for unit in ('kernel/fork','mm/mmap','mm/vma_init','mm/vma'):
            self.assertIn('/out/builds/test/'+unit+'.i',paths)
        self.assertIn('/out/builds/test/mm/vma_modify_rust.o',paths)
        self.assertNotIn('/out/builds/test/mm/vma_modify_rust.o',
                         {str(p) for p in gate.input_paths(Path('/out/builds/test'),Path('/src'),False)})

    def test_symbol_owner_exact(self):
        expected=set(gate.RUST)
        good='\n'.join('00000000 T '+name for name in expected)
        gate.definitions(good,expected)
        for bad in (good.replace(' T ',' t ',1),good+'\n00000000 T '+gate.RUST[0],
                    good+'\n00000000 T '+gate.extension.PRIMITIVES[0],good.replace(gate.RUST[0],'missing')):
            with self.assertRaises(ValueError):gate.definitions(bad,expected)

    def test_archive_exact(self):
        gate.archive_members('vma.o\nvma_modify_rust.o\n',True)
        gate.archive_members('vma.o\n',False)
        for text,rust in [('vma.o\n',True),('vma.o\nvma_modify_rust.o\n',False),
                          ('vma.o\nvma.o\nvma_modify_rust.o\n',True),
                          ('vma.o\nvma_modify_rust.o\nvma_modify_other.o\n',True)]:
            with self.assertRaises(ValueError):gate.archive_members(text,rust)

    @staticmethod
    def dis(names):
        return '00000000 <rusix_vma_prepare>:\n'+''.join(
            f' {i*5:x}: e8 00 00 00 00 callq 0\n {i*5+1:x}: R_X86_64_PLT32 {name}-0x4\n'
            for i,name in enumerate(names))

    def test_actual_prepare_call_relationship(self):
        names=['rusix_link_mapping_lock','rusix_vma_link_file_locked']
        gate.prepare_calls(self.dis(names))
        for bad in (names[::-1],names[:1],names+names[:1]):
            with self.assertRaises(ValueError):gate.prepare_calls(self.dis(bad))

    def test_prepare_missing_executable_instruction(self):
        bad=self.dis(['rusix_link_mapping_lock','rusix_vma_link_file_locked']).replace('callq','nop')
        with self.assertRaises(ValueError):gate.prepare_calls(bad)

    def test_inherited_gate_never_accepts_unknown_context(self):
        with self.assertRaises(ValueError):gate.copy.check_preprocessed('',True,source_context='unknown')
        with self.assertRaises(ValueError):gate.copy.check_preprocessed('',True,modify_rust=True)

    def test_native_forwarder_specialization_is_exact(self):
        # Exercise actual inherited gate; a missing later copy/link definition is
        # okay here only to identify which earlier prepare assertion fired.
        text='static void vma_prepare(struct vma_prepare *vp) { rusix_vma_prepare(vp); }'
        with self.assertRaisesRegex(ValueError,'already-locked'):
            gate.copy.check_preprocessed(text,True)
        with self.assertRaisesRegex(ValueError,'native copy/link'):
            gate.copy.check_preprocessed(text,True,source_context=gate.extension.ID,modify_rust=True)
        with self.assertRaisesRegex(ValueError,'forwarder'):
            gate.copy.check_preprocessed(text.replace('(vp);','(NULL);'),True,source_context=gate.extension.ID,modify_rust=True)

    def test_selected_wrappers_original_leak_and_abi(self):
        header=(ROOT/'mm/vma_modify.h').read_text()
        good={name:[value] for name,value in gate.SHIMS.items()}
        good.update({n:['stub;'] for n in gate.extension.PRIMITIVES})
        good.update({'rusix_modify_set_start':['vma->vm_start=value;'],
                     'rusix_modify_set_end':['vma->vm_end=value;'],
                     'rusix_modify_set_pgoff':['vma->vm_pgoff=value;'],
                     'rusix_modify_set_vm_flags':['((structvma_merge_struct*)opaque)->vm_flags=value;'],
                     'rusix_modify_may_split':['returnops->may_split;'],
                     'rusix_modify_split':['return__split_vma(iter,vma,addr,new_below);'],
                     'rusix_modify_merge':['returnvma_merge_existing_range(opaque);'],
                     'commit_merge':['init_multi_vma_prep();vma_prepare();vma_complete();'],
                     'vma_shrink':['init_vma_prep();vma_prepare();vma_complete();']})
        # Focus modeled branches while other actual parsers have independent tests.
        def check(mapping,text=header):
            with patch.object(gate.copy,'check_preprocessed'),patch.object(gate,'bodies',side_effect=lambda t,n:mapping.get(n,[])):
                gate.check_preprocessed(text,True,header)
        check(good)
        for name,body in [('vma_modify',['native;']),('split_vma',['native;']),
                          ('vma_prepare',['wrong();']),('rusix_modify_set_start',['vma->vm_end=value;']),
                          ('commit_merge',['vma_prepare();']), (gate.extension.PRIMITIVES[0],[])]:
            with self.assertRaises(ValueError):check(good|{name:body})
        with self.assertRaises(ValueError):check(good,header.replace('unsigned long addr','unsigned int addr'))

    def test_routing_only_build_and_config_order(self):
        text=(SCRIPTS/'build-kernel.sh').read_text()
        configure=text.index('KCONFIG_ALLCONFIG="$config" allnoconfig')
        before=text.index('> "$evidence/vma-modify-config-before.json"')
        build=text.index('-j2 bzImage')
        after=text.index('> "$evidence/vma-modify-config-after.json"')
        preprocess=text.index('scripts/preprocess-vma-modify.py')
        proof=text.index('> "$evidence/vma-modify-selection.json"')
        self.assertLess(configure,before);self.assertLess(before,build)
        self.assertLess(build,after);self.assertLess(after,preprocess);self.assertLess(preprocess,proof)
        self.assertIn('test-vma-lifecycle-vm.py\" --vma-modify', (ROOT/'rusix/ci/run.sh').read_text())

if __name__=='__main__':unittest.main()
