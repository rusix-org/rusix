#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'rusix/scripts'))
spec = importlib.util.spec_from_file_location('copy_gate', ROOT/'rusix/scripts/verify-mm-copy.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class SourceBoundary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = subprocess.check_output(
            ['git', 'show', '261575d0a60d42025318ef384b88a8e5ccd37cb1:kernel/fork.c'],
            cwd=ROOT, text=True)
        start = cls.base.index('static struct mm_struct *dup_mm(')
        end = cls.base.index('static int copy_fs(', start)
        cls.selected = (cls.base[:start] + gate.START + gate.SHIM +
                        cls.base[start:end] + gate.END + cls.base[end:]).replace(gate.INIT_SHIM,gate.INIT_GUARDED)

    def test_exact_original_restored(self):
        self.assertEqual(gate.original_policy(self.selected), self.base)

    def test_changed_original_transaction_rejected(self):
        for old, new in [('mmget(oldmm);', 'mmgrab(oldmm);'),
                         ('if (err)\n\t\tuprobe_end_dup_mmap();', 'uprobe_end_dup_mmap();'),
                         ('mm->binfmt = NULL;', 'mm->binfmt = oldmm->binfmt;'),
                         ('return -ENOMEM;', 'return -EINVAL;')]:
            with self.subTest(old=old), self.assertRaises(ValueError):
                gate.original_policy(self.selected.replace(old, new, 1))

    def test_changed_dispatch_rejected(self):
        for changed in (self.selected.replace('return rusix_copy_mm(clone_flags, tsk);',
                                             'return 0;'),
                        self.selected + gate.END,
                        self.selected.replace(gate.START, '', 1),
                        self.selected.replace('static int copy_fs(', 'static int other(', 1)):
            with self.assertRaises(ValueError):
                gate.original_policy(changed)

    def test_initializer_wrapper_guard_is_exact(self):
        for bad in (self.selected.replace(gate.INIT_GUARDED,gate.INIT_SHIM),
                    self.selected.replace(gate.INIT_GUARDED,gate.INIT_GUARDED*2),
                    self.selected.replace('return rusix_mm_init(mm, p, user_ns);','return NULL;')):
            with self.assertRaises(ValueError):gate.original_policy(bad)

    def test_unrelated_source_change_rejected(self):
        with self.assertRaises(ValueError):
            gate.original_policy(self.selected + '\n/* unreviewed */\n')


class Configuration(unittest.TestCase):
    def setUp(self):
        self.c = {gate.SELECTOR: 'n', gate.release.SELECTOR: 'y',
                  gate.release.mm.SELECTOR: 'y', gate.release.task.SELECTOR: 'y'}
        self.rust = self.c | {gate.SELECTOR: 'y'}

    def test_only_selector(self):
        self.assertEqual(gate.compare(self.c, self.rust), [gate.SELECTOR])

    def test_missing_or_extra_axis(self):
        for rust in (self.c, self.rust | {'CONFIG_SMP': 'y'},
                     {k: v for k, v in self.rust.items() if k != gate.SELECTOR}):
            with self.assertRaises(ValueError):
                gate.compare(self.c, rust)

    def test_missing_dependency_on_both_sides(self):
        for dependency in (gate.release.SELECTOR, gate.release.mm.SELECTOR, gate.release.task.SELECTOR):
            with self.assertRaises(ValueError):
                gate.compare(self.c | {dependency: 'n'}, self.rust | {dependency: 'n'})


class CompiledBoundary(unittest.TestCase):
    TASK='static struct task_struct *dup_task_struct(void){return rusix_dup_task_struct(orig,node);}'
    INIT='static struct mm_struct *mm_init(void){return rusix_mm_init(mm,p,user_ns);}'
    COPY='static int copy_mm(void){return rusix_copy_mm(clone_flags,tsk);}'
    DUP='static struct mm_struct *dup_mm(void){mm_init(mm,tsk,mm->user_ns);uprobe_start_dup_mmap();dup_mmap(mm,oldmm);uprobe_end_dup_mmap();try_module_get(mm->binfmt->module);mm->binfmt=((void*)0);mm_init_owner(mm,((void*)0));mmput(mm);if(err)uprobe_end_dup_mmap();}'
    CCOPY='static int copy_mm(void){mmget(oldmm);dup_mm(tsk,mm);tsk->mm=mm;tsk->active_mm=mm;sched_mm_cid_fork(tsk);}'

    def test_preprocessed_new_scope(self):
        gate.check_preprocessed(self.TASK+self.COPY,True)
        gate.check_preprocessed(self.TASK+self.INIT+self.DUP+self.CCOPY,False)
        for bad in (self.TASK+self.COPY+self.DUP,self.TASK+self.INIT+self.COPY,
                    (self.TASK+self.COPY).replace('return rusix_copy_mm','tsk++;return rusix_copy_mm'),
                    self.TASK+self.COPY+'void mmput(void){}'):
            with self.assertRaises(ValueError):gate.check_preprocessed(bad,True)
        with self.assertRaises(ValueError):gate.check_preprocessed(self.TASK+self.INIT+self.DUP+self.CCOPY,True)
        with self.assertRaises(ValueError):gate.check_preprocessed((self.TASK+self.INIT+self.DUP+self.CCOPY).replace('mmput(mm);',''),False)

    def test_executable_copy_bridge_and_moved_init(self):
        task=' 10: callq 0\n 11: R_X86_64_PLT32 rusix_dup_task_struct-0x4\n'
        init=' 20: callq 0\n 21: R_X86_64_PLT32 rusix_mm_init-0x4\n'
        copy=' 30: callq 0\n 31: R_X86_64_PLT32 rusix_copy_mm-0x4\n'
        gate.check_relocations(task+init,False);gate.check_relocations(task+copy,True)
        for bad in (task,task+init,task+copy.replace('callq','movq'),task+copy.replace('PLT32','64')):
            with self.assertRaises(ValueError):gate.check_relocations(bad,True)
        with self.assertRaises(ValueError):gate.check_relocations(task+copy,False)

    def test_bridge_ownership(self):
        gate.bridge_definition('0000 T rusix_copy_mm\n',True);gate.bridge_definition('',False)
        for bad in ('','0000 t rusix_copy_mm\n','0000 D rusix_copy_mm\n','0000 T rusix_copy_mm\n0000 T rusix_copy_mm\n'):
            with self.assertRaises(ValueError):gate.bridge_definition(bad,True)

    def test_all_inherited_objects_without_fixtures(self):
        c='fork.o\ntask_construction_rust.o\nmm_construction_rust.o\nmm_release_rust.o\n'
        r=c+'mm_copy_rust.o\n';gate.archive_members(c,False);gate.archive_members(r,True)
        for bad in (c,r+r,r+'mm_release_test.o\n',r+'mm_copy_other.o\n',r.replace('mm_release_rust.o','mm_release_other.o')):
            with self.assertRaises(ValueError):gate.archive_members(bad,True)

    def test_transitive_compiler_inputs(self):
        paths=gate.input_paths(Path('/out/builds/test'),Path('/src'),True)
        self.assertEqual(len(paths),len(set(paths)))
        for name in ('kernel/mm_copy_impl.h','kernel/mm_copy_rust.rs','kernel/mm_construction_rust.rs','kernel/mm_release_rust.rs',
                     'rusix/scripts/saved_clang_command.py','rusix/scripts/preprocess-task-construction.py',
                     'rusix/scripts/preprocess-mm-construction.py','rusix/scripts/preprocess-mm-release.py','rusix/scripts/preprocess-mm-copy.py',
                     'rusix/scripts/verify-mm-copy.py'):
            self.assertIn(Path('/src')/name,paths)
        self.assertIn(Path('/out/builds/test/include/generated/autoconf.h'),paths)
        self.assertNotIn(Path('/out/builds/test/kernel/mm_copy_rust.o'),gate.input_paths(Path('/out/builds/test'),Path('/src'),False))


if __name__ == '__main__':
    unittest.main()
