#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
import importlib.util
from pathlib import Path
import sys
import subprocess
import unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'rusix/scripts'))
spec=importlib.util.spec_from_file_location('mm_selection',ROOT/'rusix/scripts/verify-mm-construction.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
TASK='static struct task_struct *dup_task_struct(struct task_struct *orig,int node){return rusix_dup_task_struct(orig,node);}'
DUP='static struct mm_struct *dup_mm(struct task_struct *tsk, struct mm_struct *oldmm){if (!mm_init(mm, tsk, mm->user_ns)) goto fail_nomem;}'
RUST='static struct mm_struct *mm_init(struct mm_struct *mm,struct task_struct *p,struct user_namespace *user_ns){return rusix_mm_init(mm,p,user_ns);}'
CINIT='static struct mm_struct *mm_init(void){futex_mm_init(mm);mm_alloc_pgd(mm);mm_alloc_id(mm);init_new_context(p,mm);mm_alloc_cid(mm,p);get_user_ns(user_ns);fail_pcpu:mm_destroy_cid(mm);destroy_context(mm);mm_free_id(mm);mm_free_pgd(mm);futex_hash_free(mm);}'
CALLOC='struct mm_struct *mm_alloc(void){mm=kmem_cache_alloc_noprof(cache,flags);memset(mm,0,sizeof(*mm));return mm_init(mm,current,ns);}'
TASK_RELOC=' 10: callq 0\n 11: R_X86_64_PLT32 rusix_dup_task_struct-0x4\n'
MM_RELOC=' 20: callq 0\n 21: R_X86_64_PLT32 rusix_mm_init-0x4\n'


class Selection(unittest.TestCase):
    def test_full_fork_two_insertions(self):
        text=subprocess.check_output(['git','show','0fd31f0fde1744335d3c745185b99b7e8966a6a3:kernel/fork.c'],cwd=ROOT,text=True);m.original_policy(text)
        with self.assertRaises(ValueError):m.original_policy((ROOT/'kernel/fork.c').read_text())
        for bad in (text+'\n',text.replace('return rusix_mm_init(mm, p, user_ns);','mm++; return rusix_mm_init(mm, p, user_ns);'),
                    text.replace('mm->user_ns = get_user_ns(user_ns);','mm->user_ns = user_ns;'),
                    text.replace('return rusix_dup_task_struct(orig, node);','return NULL;'),
                    text.replace('EXPORT_SYMBOL_IF_KUNIT(mm_alloc);','')):
            with self.assertRaises(ValueError):m.original_policy(bad)
        with self.assertRaises(ValueError):m.task.original_policy(text)

    def test_pair_configs_and_limits(self):
        values=[m.config_values((ROOT/f'rusix/configs/x86_64-mm-construction-{i}.config').read_text()) for i in ('c','rust')]
        self.assertEqual(m.compare(*values),[m.SELECTOR])
        target=m.config_values((ROOT/'rusix/configs/x86_64-server.config').read_text())
        for profile,config in zip(m.PROFILES,values):
            config.update(CONFIG_X86_64='y',CONFIG_THREAD_INFO_IN_TASK='y',CONFIG_MMU='y')
            m.check_config(profile,config,target)
            for name in m.EXCLUDED:
                with self.assertRaises(ValueError):m.check_config(profile,config|{'CONFIG_'+name:'y'},target)
            for name in ('MMU','RUSIX_TASK_CONSTRUCTION_RUST','RUSIX_COMPLETION_RUST','RUSIX_BRD_RUST','SECCOMP','SMP'):
                with self.assertRaises(ValueError):m.check_config(profile,config|{'CONFIG_'+name:'n'},target)
            bad=config.copy();del bad[m.SELECTOR]
            with self.assertRaises(ValueError):m.check_config(profile,bad,target)
        with self.assertRaises(ValueError):m.compare(values[0],values[1]|{'CONFIG_DEBUG_LIST':'n'})
        with self.assertRaises(ValueError):m.check_config('task-construction-rust',values[1],target)

    def test_preprocessed_both_callers(self):
        m.check_preprocessed(TASK+DUP+RUST,True)
        m.check_preprocessed(TASK+DUP+CINIT+CALLOC,False)
        for bad in (TASK+DUP+RUST+CALLOC,TASK+DUP+RUST+RUST,TASK+RUST,
                    (TASK+DUP+RUST).replace('mm->user_ns','current_user_ns()'),
                    (TASK+DUP+RUST).replace('return rusix_mm_init','mm++;return rusix_mm_init')):
            with self.assertRaises(ValueError):m.check_preprocessed(bad,True)
        with self.assertRaises(ValueError):m.check_preprocessed(TASK+DUP+RUST,False)
        with self.assertRaises(ValueError):m.check_preprocessed((TASK+DUP+CINIT+CALLOC).replace('mm_free_pgd(mm);',''),False)

    def test_real_bridge_relocation_categories(self):
        m.check_relocations(TASK_RELOC+MM_RELOC,True)
        m.check_relocations(TASK_RELOC,False)
        for bad in (MM_RELOC,TASK_RELOC, TASK_RELOC+MM_RELOC.replace('callq','movq'),TASK_RELOC+MM_RELOC.replace('PLT32','64')):
            with self.assertRaises(ValueError):m.check_relocations(bad,True)
        with self.assertRaises(ValueError):m.check_relocations(TASK_RELOC+MM_RELOC,False)

    def test_public_symbol_ownership(self):
        both='0000 T mm_alloc\n0010 T rusix_mm_init\n'
        m.definitions(both,m.MM_SYMBOLS);m.definitions('0000 T mm_alloc\n',('mm_alloc',));m.definitions('',())
        for bad in ('',both+both,both.replace(' T ',' t '),both.replace(' T ',' D ')):
            with self.assertRaises(ValueError):m.definitions(bad,m.MM_SYMBOLS)
        with self.assertRaises(ValueError):m.definitions(both,('mm_alloc',))

    def test_archive_both_rust_transactions(self):
        c='kernel/fork.o\nkernel/task_construction_rust.o\n';r=c+'kernel/mm_construction_rust.o\n'
        m.archive_members(c,False);m.archive_members(r,True)
        for bad in (c,r+r,r.replace('task_construction_rust.o','task_construction_other.o'),r+'mm_construction_other.o\n'):
            with self.assertRaises(ValueError):m.archive_members(bad,True)
        with self.assertRaises(ValueError):m.archive_members(r,False)

    def test_provenance_includes_both_implementations_and_parser(self):
        paths=m.input_paths(Path('/out/builds/mm'),Path('/src'),True)
        self.assertEqual(len(paths),len(set(paths)))
        for name in ('kernel/mm_construction_rust.rs','kernel/mm_construction_impl.h','kernel/task_construction_rust.rs',
                     'rusix/scripts/verify-task-construction.py','rusix/scripts/saved_clang_command.py'):
            self.assertIn(Path('/src')/name,paths)
        self.assertIn(Path('/out/builds/mm/include/generated/autoconf.h'),paths)
        self.assertNotIn(Path('/out/builds/mm/kernel/mm_construction_rust.o'),m.input_paths(Path('/out/builds/mm'),Path('/src'),False))


if __name__=='__main__':unittest.main()
