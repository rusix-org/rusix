#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Source/config negatives only; modeled configuration is not Kconfig execution."""
import pathlib
import sys
import tempfile
import unittest
sys.dont_write_bytecode=True
ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'rusix/scripts'))
import vma_merge_source as gate

class Source(unittest.TestCase):
    def test_reviewed_source_inventory(self):
        proof=gate.source_policy(ROOT,source_context=gate.ID)
        self.assertEqual(len(proof['native_policies']),17)
        self.assertEqual(len(proof['primitives']),42)
        self.assertEqual(len(proof['reused']),31)
        self.assertEqual(len(proof['constants']),6)
        self.assertEqual(len(proof['reused_constants']),2)
        self.assertEqual(proof['restored_vma_sha256'],gate.BASE_SHA256)

    def test_explicit_context(self):
        for context in (None,'','vma-modify-v1','vma-merge-v2'):
            with self.subTest(context=context),self.assertRaises(ValueError):
                gate.restore((ROOT/'mm/vma.c').read_text(),source_context=context)

    def test_historical_gate_rejects_merge_source(self):
        with self.assertRaises(ValueError):
            gate.modify.source_policy(ROOT,source_context=gate.modify.ID)
        with self.assertRaises(ValueError):
            gate.modify.copy_gate().source_policy(ROOT)

    def reject_change(self, before, after):
        text=(ROOT/'mm/vma.c').read_text()
        self.assertTrue(before in text, before)
        with self.assertRaises(ValueError):
            gate.restore(text.replace(before,after,1),source_context=gate.ID)

    def test_missing_guard(self):
        self.reject_change('#ifndef '+gate.SELECTOR+'\n','')

    def test_changed_guard(self):
        self.reject_change('#ifdef '+gate.SELECTOR,'#if defined('+gate.SELECTOR+')')

    def test_missing_include(self):
        self.reject_change('#include "vma_merge_impl.h"','')

    def test_changed_native_body(self):
        self.reject_change('is_mergeable_anon_vma','changed_native_policy')

    def test_changed_wrapper(self):
        self.reject_change('return rusix_merge_existing(vmg, &prep);','return rusix_merge_existing(vmg, NULL);')

    def test_duplicate_guard(self):
        text=(ROOT/'mm/vma.c').read_text()+'\n#ifndef '+gate.SELECTOR+'\n#endif\n'
        with self.assertRaises(ValueError):gate.restore(text,source_context=gate.ID)

    def test_exact_abi_rust_primitives_parent(self):
        with tempfile.TemporaryDirectory(prefix='merge-source-') as temp:
            dest=pathlib.Path(temp);(dest/'mm').mkdir()
            paths=set(gate.REVIEWED)|set(gate.modify.REVIEWED)
            for name in paths:(dest/name).write_bytes((ROOT/name).read_bytes())
            for name in paths:
                original=(dest/name).read_bytes();(dest/name).write_bytes(original+b'\n')
                with self.subTest(name=name),self.assertRaises(ValueError):
                    gate.source_policy(dest,source_context=gate.ID)
                (dest/name).write_bytes(original)

class Config(unittest.TestCase):
    def setUp(self):
        self.parent=gate.modify.copy_gate()
        self.target=self.parent.config_values((ROOT/'rusix/configs/x86_64-server.config').read_text())
        self.values={}
        for side in ('c','rust'):
            v=self.parent.config_values((ROOT/f'rusix/configs/x86_64-vma-merge-{side}.config').read_text())
            v.update({'CONFIG_'+k:'y' for k in ('X86_64','THREAD_INFO_IN_TASK','MMU','PER_VMA_LOCK')})
            self.values[side]=v

    def test_exact_fragments(self):
        parent=self.parent.config_values((ROOT/'rusix/configs/x86_64-vma-modify-rust.config').read_text())
        for side in ('c','rust'):
            value=self.parent.config_values((ROOT/f'rusix/configs/x86_64-vma-merge-{side}.config').read_text())
            self.assertEqual(value.pop(gate.SELECTOR),'y' if side=='rust' else 'n')
            self.assertEqual(value,parent)

    def test_pair(self):
        self.assertEqual(gate.compare(self.values['c'],self.values['rust'],self.target,source_context=gate.ID),[gate.SELECTOR])

    def test_extra_axis(self):
        self.values['rust']['CONFIG_UNREVIEWED']='y'
        with self.assertRaises(ValueError):gate.compare(self.values['c'],self.values['rust'],self.target,source_context=gate.ID)

    def test_unknown_profile_context_wrong_axis(self):
        for profile,context,values in [('vma-modify-rust',gate.ID,self.values['rust']),('vma-merge-rust',None,self.values['rust']),('vma-merge-rust',gate.ID,self.values['c'])]:
            with self.assertRaises(ValueError):gate.check_config(profile,values,self.target,source_context=context)

    def test_missing_ancestor_and_native_fixtures(self):
        for name,value in [('RUSIX_VMA_MODIFY_RUST','n'),('RUSIX_COPY_VMA_RUST','n'),('RUSIX_EXIT_MMAP_RUST','n'),('RUSIX_MM_RELEASE_RUST','n'),('KUNIT','y'),('PREEMPT_RT','y'),('RUSIX_VMA_MERGE_TEST','y')]:
            with self.subTest(name=name),self.assertRaises(ValueError):
                gate.check_config('vma-merge-rust',self.values['rust']|{'CONFIG_'+name:value},self.target,source_context=gate.ID)

if __name__=='__main__':unittest.main()
