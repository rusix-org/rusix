#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
import importlib.util
from pathlib import Path
import sys
import subprocess
import unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'rusix/scripts'))
spec=importlib.util.spec_from_file_location('release',ROOT/'rusix/scripts/verify-mm-release.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
spec=importlib.util.spec_from_file_location('constructor_cases',ROOT/'rusix/tests/test_mm_construction_selection.py')
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)

class Selection(unittest.TestCase):
    def test_full_pinned_reconstruction(self):
        text=subprocess.check_output(['git','show','261575d0a60d42025318ef384b88a8e5ccd37cb1:kernel/fork.c'],cwd=ROOT,text=True);m.original_policy(text)
        with self.assertRaises(ValueError):m.original_policy((ROOT/'kernel/fork.c').read_text())
        for bad in (text+'\n',text.replace('exit_mmap(mm);','exit_mmap(NULL);'),text.replace('EXPORT_SYMBOL_GPL(mmput);',''),text.replace('#include "mm_release_impl.h"','#include "other.h"')):
            with self.assertRaises(ValueError):m.original_policy(bad)
        with self.assertRaises(ValueError):m.mm.original_policy(text)

    def test_profiles_and_axis(self):
        configs=[m.config_values((ROOT/f'rusix/configs/x86_64-mm-release-{mode}.config').read_text()) for mode in ('c','rust')]
        self.assertEqual(m.compare(*configs),[m.SELECTOR])
        target=m.config_values((ROOT/'rusix/configs/x86_64-server.config').read_text())
        for name,values in zip(m.PROFILES,configs):
            values.update(CONFIG_X86_64='y',CONFIG_THREAD_INFO_IN_TASK='y',CONFIG_MMU='y')
            m.check_config(name,values,target)
            for missing in (m.SELECTOR,m.mm.SELECTOR,m.task.SELECTOR):
                bad=values.copy();bad.pop(missing)
                with self.assertRaises(ValueError):m.check_config(name,bad,target)
        with self.assertRaises(ValueError):m.compare(configs[0],configs[1]|{'CONFIG_DEBUG_LIST':'n'})

    def test_preprocess_preserves_constructor(self):
        base=c.TASK+c.DUP+c.RUST
        m.check_preprocessed(base,True)
        for name in (*m.PUBLIC,'mmput_async_fn','__mmput'):
            with self.assertRaises(ValueError):m.check_preprocessed(base+'void '+name+'(void){}',True)
        with self.assertRaises(ValueError):m.check_preprocessed(c.TASK+c.DUP+c.CINIT+c.CALLOC,True)
        cbody='void mmput(void){atomic_dec_and_test(x);__mmput(mm);}void mmput_async(void){mmput_async_fn;schedule_work(w);}void __mmdrop(void){mm_free_pgd(mm);destroy_context(mm);kmem_cache_free(mm_cachep,(mm));}void __mmput(void){exit_mmap(mm);futex_hash_free(mm);mmdrop(mm);}void mmput_async_fn(void){}'
        m.check_preprocessed(base+cbody,False)
        with self.assertRaises(ValueError):m.check_preprocessed(base+cbody.replace('futex_hash_free(mm);',''),False)

    def test_public_ownership(self):
        good=''.join('0000 T '+n+'\n' for n in m.PUBLIC);m.definitions(good,m.PUBLIC)
        for bad in ('',good+good,good.replace(' T ',' D '),good.replace(' T ',' t ')):
            with self.assertRaises(ValueError):m.definitions(bad,m.PUBLIC)
        with self.assertRaises(ValueError):m.definitions(good,())

    def test_callback_identity_and_prefixes(self):
        name='_RNvC123mmput_async_fn';good='0000 t '+name+'\n'
        self.assertEqual(m.callback(good,True),name)
        self.assertEqual(m.callback(good+'0000 t __pfx_'+name+'\n0000 t __cfi_'+name+'\n',True),name)
        for bad in ('',good+good,good.replace(' t ',' D '),good+'0000 t __pfx_wrong_mmput_async_fn\n',good+'0000 t mmput_async_fn\n',good.replace(name,'anything_mmput_async_fn')):
            with self.assertRaises(ValueError):m.callback(bad,True)
        self.assertEqual(m.callback('0000 t mmput_async_fn\n',False),'mmput_async_fn')

    def test_code_registration_not_debug_or_direct_call(self):
        name='_RNvC123mmput_async_fn'
        address='0000 <mmput_async>:\n 10: leaq 0(%rip), %rsi\n 13: R_X86_64_PC32 '+name+'-0x4\n'
        call=' 20: callq 0\n 21: R_X86_64_PLT32 rusix_mm_release_work_init-0x4\n'
        m.registration(address+call,name,True)
        for bad in (address,call,address.replace('leaq','callq')+call,address.replace('PC32','PLT32')+call,address+call.replace('callq','movq'),address.replace('-0x4','+0x4')+call,address.replace('<mmput_async>','<unrelated>')+call):
            with self.assertRaises(ValueError):m.registration(bad,name,True)
        m.registration(address.replace(name,'mmput_async_fn'),'mmput_async_fn',False)

    def test_section_relative_callback_exact_elf_identity(self):
        import copy
        name='mmput_async_fn'
        metadata=[{'FileSummary':{'Format':'elf64-x86-64','Arch':'x86_64'},
          'Sections':[{'Section':{'Index':2,'Name':{'Name':'.text'},'Type':{'Value':1},'Flags':{'Value':6},'Size':0x2000}}],
          'Symbols':[{'Symbol':{'Name':{'Name':name},'Type':{'Value':2},'Size':12,'Value':0x1550,'Section':{'Value':2}}},
                     {'Symbol':{'Name':{'Name':'.text'},'Type':{'Value':3},'Size':0,'Value':0,'Section':{'Value':2}}}]}]
        absolute='000014a0 <mmput_async>:\n 150b: movq $0, 0x840(%r14)\n 1512: R_X86_64_32S .text+0x1550\n'
        m.registration(absolute,name,False,metadata)
        m.registration(absolute.replace('32S .text+0x1550','64 .text+0x1550'),name,False,metadata)
        m.registration(absolute.replace('movq $0, 0x840(%r14)','leaq 0(%rip), %rsi').replace('32S .text+0x1550','PC32 .text+0x154c'),name,False,metadata)
        for bad in (absolute.replace('1550','1540'),absolute.replace('1550','1551'),absolute.replace('.text+','.other+'),absolute.replace('32S','PC32'),absolute.replace('32S','PLT32'),absolute.replace('movq','callq'),absolute.replace('$0','%rax'),absolute.replace('32S .text+0x1550','PC32 .text+0x154c'),absolute+absolute.split('\n',1)[1]):
            with self.assertRaises(ValueError):m.registration(bad,name,False,metadata)
        for change in ('wrong_index','duplicate_symbol','duplicate_section','nonexec','nonsized'):
            bad=copy.deepcopy(metadata)
            if change=='wrong_index':bad[0]['Symbols'][0]['Symbol']['Section']['Value']=3
            if change=='duplicate_symbol':bad[0]['Symbols'].append(copy.deepcopy(bad[0]['Symbols'][1]))
            if change=='duplicate_section':bad[0]['Sections'].append(copy.deepcopy(bad[0]['Sections'][0]))
            if change=='nonexec':bad[0]['Sections'][0]['Section']['Flags']['Value']=2
            if change=='nonsized':bad[0]['Symbols'][0]['Symbol']['Size']=0
            with self.assertRaises(ValueError):m.registration(absolute,name,False,bad)

    def test_archive_and_input_identity(self):
        base='fork.o\ntask_construction_rust.o\nmm_construction_rust.o\nmm_release_test.o\n'
        m.archive_members(base,False);m.archive_members(base+'mm_release_rust.o\n',True)
        for bad in (base,base+'mm_release_rust.o\n'*2,base+'mm_release_other.o\n',base.replace('mm_release_test.o\n','')+'mm_release_rust.o\n',base+'mm_release_test.o\nmm_release_rust.o\n'):
            with self.assertRaises(ValueError):m.archive_members(bad,True)
        for rust in (False,True):
            paths=m.input_paths(Path('/out/builds/test'),Path('/src'),rust)
            self.assertEqual(len(paths),len(set(paths)))
            for path in ('kernel/mm_release_impl.h','kernel/mm_release_rust.rs','rusix/scripts/preprocess-mm-release.py','rusix/scripts/verify-mm-construction.py','rusix/scripts/saved_clang_command.py'):
                self.assertIn(Path('/src')/path,paths)
            self.assertIn(Path('/out/builds/test/include/generated/autoconf.h'),paths)

if __name__=='__main__':unittest.main()
