#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'rusix/scripts'))
spec=importlib.util.spec_from_file_location('dup_gate',ROOT/'rusix/scripts/verify-dup-mmap.py')
gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)


class Selection(unittest.TestCase):
    def test_original_entire_source_restored(self):
        source=(ROOT/'mm/mmap.c').read_text()
        baseline=subprocess.check_output(['git','show','222684299c2648388a2483a3f370f3ad584e90a9:mm/mmap.c'],cwd=ROOT,text=True)
        self.assertEqual(gate.original_policy(source),baseline)
        for bad in (source+'\n',source.replace('mm->map_count++;','mm->map_count--;'),
                    source.replace('return rusix_dup_mmap(mm, oldmm, &ctx);','return 0;'),
                    source.replace('.vmi = &vmi','.vmi = NULL'),source+gate.END):
            with self.assertRaises(ValueError):gate.original_policy(bad)

    def test_actual_profile_pair_constraints(self):
        configs=[gate.config_values((ROOT/f'rusix/configs/x86_64-mm-dup-mmap-{s}.config').read_text()) for s in ('c','rust')]
        target=gate.config_values((ROOT/'rusix/configs/x86_64-server.config').read_text())
        self.assertEqual(gate.compare(*configs),[gate.SELECTOR])
        for profile,values in zip(gate.PROFILES,configs):
            values.update(CONFIG_X86_64='y',CONFIG_THREAD_INFO_IN_TASK='y',CONFIG_MMU='y')
            gate.check_config(profile,values,target)
            for key in (gate.SELECTOR,gate.copy.SELECTOR,gate.copy.release.SELECTOR,gate.copy.release.mm.SELECTOR,gate.copy.release.task.SELECTOR):
                bad=values.copy();bad.pop(key)
                with self.assertRaises(ValueError):gate.check_config(profile,bad,target)
            with self.assertRaises(ValueError):gate.check_config(profile,values|{'CONFIG_KUNIT':'y'},target)
        with self.assertRaises(ValueError):gate.compare(configs[0],configs[1]|{'CONFIG_DEBUG_LIST':'n'})

    def test_preprocessed_context_only_no_policy(self):
        body='int dup_mmap(void){'+gate.CONTEXT_BODY+'}'
        gate.check_preprocessed(body,True)
        for bad in (body+body,body.replace('returnrusix_dup_mmap','if(x)returnrusix_dup_mmap'),
                    body.replace('.vmi=&vmi','.vmi=0'),body.replace('.index=0','.index=1'),
                    body.replace('returnrusix_dup_mmap','mm->map_count++;returnrusix_dup_mmap')):
            with self.assertRaises(ValueError):gate.check_preprocessed(bad,True)
        with self.assertRaises(ValueError):gate.check_preprocessed(body,False)

    def test_c_policy_with_config_dependent_policy_macro(self):
        original=gate.original_policy((ROOT/'mm/mmap.c').read_text())
        body=original[original.index('__latent_entropy int dup_mmap('):]
        # Macro-only model exercises both canonical NUMA settings; this is not
        # claimed as actual compiler output, which the objects gate requires.
        for policy in ('((void *)0)','((tmp)->vm_policy)'):
            expanded=body.replace('vma_policy(tmp)',policy)
            gate.check_preprocessed(expanded,False)
            with self.assertRaises(ValueError):gate.check_preprocessed(expanded.replace('vm_unacct_memory(charge);',''),False)

    def test_c_mode_rejects_truncated_transaction(self):
        with self.assertRaises(ValueError):gate.check_preprocessed('int dup_mmap(void){return 0;}',False)
        with self.assertRaises(ValueError):gate.check_preprocessed('',False)

    def test_public_and_bridge_ownership(self):
        gate.definitions('0000 T dup_mmap\n',True,False)
        gate.definitions('0000 T rusix_dup_mmap\n',False,True)
        gate.definitions('0000 T dup_mmap\n0010 T rusix_dup_mmap\n',True,True)
        for bad in ('','0000 t dup_mmap\n','0000 D dup_mmap\n','0000 T dup_mmap\n0000 T dup_mmap\n'):
            with self.assertRaises(ValueError):gate.definitions(bad,True,False)

    def test_executable_relocation(self):
        call=' 10: callq 0\n 11: R_X86_64_PLT32 rusix_dup_mmap-0x4\n'
        gate.check_relocations(call,True);gate.check_relocations('',False)
        for bad in ('',call.replace('callq','movq'),call.replace('PLT32','64'),call.replace('-0x4','+0x1')):
            with self.assertRaises(ValueError):gate.check_relocations(bad,True)
        with self.assertRaises(ValueError):gate.check_relocations(call,False)

    def test_actual_archive_members(self):
        gate.archive_members('mmap.o\n',False)
        gate.archive_members('mmap.o\ndup_mmap_rust.o\n',True)
        for bad in ('mmap.o\n','dup_mmap_rust.o\n','mmap.o\nmmap.o\ndup_mmap_rust.o\n','mmap.o\ndup_mmap_rust.o\ndup_mmap_other.o\n'):
            with self.assertRaises(ValueError):gate.archive_members(bad,True)

    def test_full_composed_dependencies(self):
        build=Path('/out/builds/x');source=Path('/src');paths=gate.input_paths(build,source,True)
        self.assertEqual(len(paths),len(set(paths)))
        for path in gate.copy.input_paths(build,source,True):self.assertIn(path,paths)
        for name in ('mm/mmap.c','mm/dup_mmap_impl.h','mm/dup_mmap_rust.rs','mm/Makefile','include/linux/maple_tree.h','rusix/scripts/preprocess-dup-mmap.py','rusix/scripts/saved_clang_command.py'):
            self.assertIn(source/name,paths)
        for name in ('mm/.mmap.o.cmd','mm/mmap.o','mm/mmap.i','mm/built-in.a','mm/dup_mmap_rust.o','include/generated/autoconf.h'):
            self.assertIn(build/name,paths)
        self.assertNotIn(build/'mm/dup_mmap_rust.o',gate.input_paths(build,source,False))


if __name__=='__main__':unittest.main()
