#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Modeled selection negatives; these fixtures are never compiler output."""
from pathlib import Path
import sys
import shlex
import unittest
import importlib.util
from unittest.mock import patch
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[2];S=ROOT/'rusix/scripts';sys.path.insert(0,str(S))
spec=importlib.util.spec_from_file_location('merge_gate',S/'verify-vma-merge.py');g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)

def model(rust):
    text=''
    if rust:
        for n,c in g.WRAPPERS.items():
            prefix=g.EXTEND if n=='vma_merge_extend' else ''
            args='&vmg,&prep' if n=='vma_merge_extend' else ('vmi,vma,start,end,pgoff,&prep' if n=='vma_shrink' else 'vmg,&prep')
            text+='void '+n+'(void){'+prefix+'structvma_prepareprep;return'+c+'('+args+');}\n'
        for n in g.extension.PRIMITIVES:text+='void '+n+'(void) { stub; }\n'
        text+=(ROOT/'mm/vma_merge.h').read_text()
        text+='enum vma_merge_state { VMA_MERGE_START,VMA_MERGE_ERROR_NOMEM,VMA_MERGE_NOMERGE,VMA_MERGE_SUCCESS, };'
    else:
        for n in (*g.extension.NATIVE,*g.extension.PREP):text+='void '+n+'(void) { native; }\n'
    return text

class Selection(unittest.TestCase):
    def test_explicit_full_parent_restoration(self):
        self.assertEqual(g.copy.source_policy(ROOT,source_context=g.extension.ID)['extension'],g.extension.ID)
        for context in (None,'vma-modify-v1','unknown'):
            with self.assertRaises(ValueError):g.copy.source_policy(ROOT,source_context=context)

    def test_four_unit_closure(self):
        p={str(p) for p in g.input_paths(Path('/out/builds/test'),Path('/src'),True)}
        for n in ('kernel/fork.i','mm/mmap.i','mm/vma_init.i','mm/vma.i','mm/vma_merge_rust.o','mm/.vma_merge_rust.o.cmd'):
            self.assertIn('/out/builds/test/'+n,p)
        for n in ('vma_merge_source.py','verify-vma-merge.py','preprocess-vma-merge.py','verify-vma-modify.py','verify-copy-vma.py','exit_mmap_source.py','saved_clang_command.py'):
            self.assertIn('/src/rusix/scripts/'+n,p)
        self.assertNotIn('/out/builds/test/mm/vma_merge_rust.o',{str(p) for p in g.input_paths(Path('/out/builds/test'),Path('/src'),False)})

    def test_modeled_both_selections(self):
        for rust in (False,True):g.check_preprocessed(model(rust),rust,(ROOT/'mm/vma_merge.h').read_text())

    def test_native_leak_and_redundant_prepare(self):
        for name in (*g.PRIVATE_NATIVE,*g.extension.PREP):
            with self.subTest(name=name),self.assertRaises(ValueError):g.check_preprocessed(model(True)+'\nvoid '+name+'(void) { native; }',True,'')

    def test_missing_native_or_primitive(self):
        for rust,name in [(False,'commit_merge'),(False,'vma_complete'),(True,g.extension.PRIMITIVES[0])]:
            with self.assertRaises(ValueError):g.check_preprocessed(model(rust).replace(name,'missing'),rust,'')

    def test_wrong_stack_abi_enum(self):
        for before,after in [('vmg,&prep','vmg,NULL'),('structvma_prepareprep;',''),('VMA_MERGE_SUCCESS,','VMA_MERGE_SUCCESS=99,')]:
            with self.assertRaises(ValueError):g.check_preprocessed(model(True).replace(before,after,1),True,'')

    def test_archive_inventory(self):
        for text,rust in [('vma.o\nvma_merge_rust.o\n',True),('vma.o\n',False)]:g.archive_members(text,rust)
        for text,rust in [('vma.o\n',True),('vma.o\nvma_merge_rust.o\n',False),('vma.o\nvma.o\nvma_merge_rust.o\n',True),('vma.o\nvma_merge_other.o\nvma_merge_rust.o\n',True)]:
            with self.assertRaises(ValueError):g.archive_members(text,rust)

    def test_exact_global_executable_owner(self):
        owned=set(g.extension.ENTRIES);text='\n'.join('0 T '+n for n in owned);g.definitions(text,owned)
        for bad in (text.replace(' T ',' t ',1),text+'\n0 T '+next(iter(owned)),text+'\n0 T '+g.extension.PRIMITIVES[0],text.replace(next(iter(owned)),'missing')):
            with self.assertRaises(ValueError):g.definitions(bad,owned)

    def test_exact_obligations(self):
        good=dict(status='PASS',implementation='rust',source_context=g.extension.ID,outer_obligations=g.OBLIGATIONS,consumed_outer_obligations=['vma-modify-rust-prepare-lock-before-file-link'])
        g.require_obligations(good,True);g.require_obligations(good|{'outer_obligations':[]},False)
        for field,value in [('outer_obligations',[]),('outer_obligations',g.OBLIGATIONS*2),('outer_obligations',['unknown']),('consumed_outer_obligations',[]),('source_context','vma-modify-v1')]:
            with self.assertRaises(ValueError):g.require_obligations(good|{field:value},True)

    def test_prepare_absence_requires_exact_context(self):
        for context,modify in [(None,True),('vma-modify-v1',True),(g.extension.ID,False)]:
            with self.assertRaises(ValueError):g.copy.check_preprocessed('',True,source_context=context,modify_rust=modify,merge_rust=True)
        with self.assertRaisesRegex(ValueError,'absent C prepare'):
            g.copy.check_preprocessed('void vma_prepare(void){rusix_vma_prepare(vp);}',True,source_context=g.extension.ID,modify_rust=True,merge_rust=True)

    def test_parent_prepare_and_commit_selection(self):
        parent=g.modify
        good={name:[body] for name,body in parent.SHIMS.items() if name not in g.extension.PREP}
        good.update({name:['stub;'] for name in parent.extension.PRIMITIVES})
        good.update({'rusix_modify_set_start':['vma->vm_start=value;'],
                     'rusix_modify_set_end':['vma->vm_end=value;'],
                     'rusix_modify_set_pgoff':['vma->vm_pgoff=value;'],
                     'rusix_modify_set_vm_flags':['((structvma_merge_struct*)opaque)->vm_flags=value;'],
                     'rusix_modify_may_split':['returnops->may_split;'],
                     'rusix_modify_split':['return__split_vma(iter,vma,addr,new_below);'],
                     'rusix_modify_merge':['returnvma_merge_existing_range(opaque);'],
                     'vma_shrink':['outer_validates_stack;']})
        def check(mapping,context=g.extension.ID,merge=True):
            header=(ROOT/'mm/vma_modify.h').read_text()
            with patch.object(parent.copy,'check_preprocessed'),patch.object(parent,'bodies',side_effect=lambda t,n:mapping.get(n,[])):
                parent.check_preprocessed(header,True,header,source_context=context,merge_rust=merge)
        check(good)
        for name in (*g.extension.PREP,'commit_merge'):
            with self.assertRaises(ValueError):check(good|{name:['unexpected;']})
        with self.assertRaises(ValueError):check(good,context='vma-modify-v1')
        with self.assertRaises(ValueError):check(good,merge=False)

    def test_mixed_width_constant_storage(self):
        class Elf:
            relocatable=True
            names=['.rodata']
            headers=[(0,1,2,0,0,36)]
            values=[0x800,0x10044400,0x800,2,3,1]
            sizes=[8,8,8,4,4,4]
            def symbol(self,name):
                i=g.extension.CONSTANTS.index(name)
                return dict(kind=1,size=self.sizes[i],address=sum(self.sizes[:i]))
            def location(self,sym):return 0,sym['address']
            def section_data(self,index):return b''.join(v.to_bytes(n,'little') for v,n in zip(self.values,self.sizes))
        table='\n'.join(f'{sum(Elf.sizes[:i]):x} R {name}' for i,name in enumerate(g.extension.CONSTANTS))
        g.constant_storage(Elf(),table,{},linked=False)
        wrong=Elf();wrong.values=Elf.values.copy();wrong.values[-1]=0
        with self.assertRaises(ValueError):g.constant_storage(wrong,table,{},linked=False)
        with self.assertRaises(ValueError):g.constant_storage(Elf(),table.replace(' R ',' T ',1),{},linked=False)
        with self.assertRaises(ValueError):g.constant_storage(Elf(),table,{},linked=True)
        with self.assertRaises(ValueError):g.constant_storage(Elf(),table,{'CONFIG_MEM_SOFT_DIRTY':'y'},linked=False)

    def test_build_only_routing(self):
        text=(S/'build-kernel.sh').read_text()
        indexes=[text.index(x) for x in ('KCONFIG_ALLCONFIG="$config" allnoconfig','vma-merge-config-before.json','-j2 bzImage','vma-merge-config-after.json','scripts/preprocess-vma-merge.py','vma-merge-selection.json')]
        self.assertEqual(indexes,sorted(indexes))
        self.assertNotIn('vma-merge',(ROOT/'rusix/ci/run.sh').read_text())

    def test_saved_rust_unit_command(self):
        text='savedcmd_mm/vma_merge_rust.o := '+shlex.join([t.replace('{build}','/out/builds/test') for t in g.RUST_ARGV])+'\nsource_mm/vma_merge_rust.o := /src/mm/vma_merge_rust.rs\n'
        text+='\ndeps_mm/vma_merge_rust.o := '+ ' '.join('/out/builds/test/rust/'+n for n in g.RUST_DEPS)+'\n\n'
        g.rust_command(text)
        for before,after in [('rustc','false'),('--crate-name vma_merge_rust','--crate-name other'),('--emit=obj=mm/vma_merge_rust.o','--emit=obj=mm/other.o'),('source_mm/vma_merge_rust.o := /src/mm/vma_merge_rust.rs','source_mm/vma_merge_rust.o := /src/mm/other.rs')]:
            with self.assertRaises(ValueError):g.rust_command(text.replace(before,after))

if __name__=='__main__':unittest.main()
