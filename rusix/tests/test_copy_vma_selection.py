#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Host source/model negatives only; emitted-kernel evidence remains pending."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'rusix/scripts'))
def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
g=load('copy_vma_gate',ROOT/'rusix/scripts/verify-copy-vma.py')
e=g.extension
import vma_modify_source
oldtests=load('old_constants',ROOT/'rusix/tests/test_dup_mmap_selection.py')

class Elf32(oldtests.ModelElf):
    def __init__(self,linked=False):
        super().__init__(linked)
        self.headers[1][5]=8;self.headers[1][8]=4
        self.data=b''.join(v.to_bytes(4,'little') for v in g.CONSTANTS.values())
        self.symbols=[dict(name=n,kind=1,size=4,section=1,address=self.base+i*4) for i,n in enumerate(g.CONSTANTS)]

def selected():
    text='static void vma_prepare(void){i_mmap_lock_write(vp->mapping);__vma_link_file(vp->insert,vp->insert->vm_file->f_mapping);}'+'\nvoid copy_vma(void){'+g.COPY+'}\nvoid vma_link(void){'+g.LINK+'}\n'
    text+='void __vma_link_file(void){rusix_vma_link_file_locked(vma,mapping);}\n'
    text+='typedef void (*rusix_vma_open_fn)(struct vm_area_struct *vma);\n'
    for name,body in {'rusix_copy_open':'returnops->open;', 'rusix_copy_start':'returnvma->vm_start;',
                      'rusix_copy_end':'returnvma->vm_end;', 'rusix_copy_pgoff':'returnvma->vm_pgoff;',
                      'rusix_link_set_count':'mm->map_count=count;'}.items():text+='void '+name+'(void){'+body+'}\n'
    return text

class Selection(unittest.TestCase):
    def setUp(self):
        # Only modeled historical source tests fold the reviewed extension.
        # Actual .i evidence is never projected or synthesized by the verifier.
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.historical=Path(tmp.name);(self.historical/'mm').mkdir()
        for name in g.exit.extension.REGIONS:
            text=(ROOT/name).read_text()
            if name=='mm/vma.c':
                import vma_merge_source
                text=vma_merge_source.restore(text,source_context=vma_merge_source.ID)
                text=vma_modify_source.restore(text,source_context=vma_modify_source.ID)
            (self.historical/name).write_text(text)

    def test_exact_source_and_ancestral_restoration(self):
        source=(self.historical/'mm/vma.c').read_text();restored=e.restore(source)
        self.assertEqual(g.exit.extension.hashlib.sha256(restored.encode()).hexdigest(),
                         '1dd5a0bbb2ae056796b0a12e506159c8af841cf38b0cb77f72a4b7d37c30950d')
        proof=g.source_policy(self.historical)
        with self.assertRaises(ValueError):g.source_policy(ROOT)
        self.assertEqual(proof['extension'],e.ID)
        self.assertEqual(proof['upstream_mmap_sha256'],g.exit.vma.dup.PINNED_MMAP_SHA256)
        with self.assertRaises(ValueError):g.exit.source_policy(ROOT)
        with self.assertRaises(ValueError):g.exit.extension.validate(ROOT,'unknown-copy-extension')

    def test_each_guard_shim_original_unrelated_mutation_rejected(self):
        text=(self.historical/'mm/vma.c').read_text()
        mutations=[text+'\n',text+e.END,text.replace(e.END,'',1)]
        for shim in e.SHIMS:mutations += [text.replace(shim,shim.replace('#else','/*change*/\n#else'),1)]
        mutations += [text.replace('mm->map_count++;','mm->map_count += 2;',1),text.replace('return NULL;', 'return (void *)1;',1)]
        for bad in mutations:
            with self.subTest(bad=bad[-30:]),self.assertRaises(ValueError):e.restore(bad)

    def test_extension_validates_all_ancestor_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'mm').mkdir()
            for name in g.exit.extension.REGIONS:(root/name).write_text((self.historical/name).read_text())
            g.source_policy(root)
            (root/'mm/internal.h').write_text((root/'mm/internal.h').read_text()+'\n')
            with self.assertRaises(ValueError):g.source_policy(root)

    def test_exact_context_dispatch_and_no_old_policy(self):
        text=selected();g.check_preprocessed(text,True)
        for bad in (text.replace('.vmi=&vmi','.vmi=0'),text.replace('.policy=((void*)0)','.policy=borrowed'),
                    text.replace('.source_start=vma_start','.source_start=0'),text.replace('keep_source);','false);'),
                    text+'void vma_link_file(void){}',text+'void copy_vma(void){}',
                    text.replace('returnops->open;','return0;'),text.replace('(*rusix_vma_open_fn)','(*wrong)'),text.replace('i_mmap_lock_write(vp->mapping);','')):
            with self.assertRaises(ValueError):g.check_preprocessed(bad,True)
        with self.assertRaises(ValueError):g.check_preprocessed(text,False)

    def test_c_oracle_policies_and_selected_primitive_rejection(self):
        text=e.restore((self.historical/'mm/vma.c').read_text());g.check_preprocessed(text,False)
        for bad in (text.replace('mm->map_count++;',''),text.replace('unlink_anon_vmas(new_vma);',''),
                    text+'void rusix_copy_merge(void){}',text.replace('*vmap = vma = new_vma;','')):
            with self.assertRaises(ValueError):g.check_preprocessed(bad,False)

    def test_legacy_close_requirement_not_silently_weakened(self):
        old=load('old_exit_selection',ROOT/'rusix/tests/test_exit_mmap_selection.py')
        mmap,text=old.selected_text();text=text.replace('vma_close(new_vma);','')
        with self.assertRaises(ValueError):g.exit.check_preprocessed(mmap,text,True)
        with self.assertRaises(ValueError):g.exit.check_preprocessed(mmap,text,True,copy_rust=True)
        g.exit.check_preprocessed(mmap,text,True,source_extension=e.ID,copy_rust=True)
        with self.assertRaises(ValueError):g.exit.check_preprocessed(mmap,text,True,source_extension='unknown',copy_rust=True)

    def test_inputs_bind_four_commands_new_headers_and_imports(self):
        b=Path('/out/builds/a');s=Path('/src');paths=g.input_paths(b,s,True)
        self.assertEqual(len(paths),len(set(paths)))
        for item in ('mm/copy_vma_impl.h','mm/copy_vma_rust.rs','rusix/scripts/copy_vma_source.py','rusix/scripts/verify-copy-vma.py','rusix/scripts/preprocess-copy-vma.py','rusix/scripts/verify-brd-parameter-owner.py','rusix/scripts/measure-kernel-languages.py'):
            self.assertIn(s/item,paths)
        for unit in ('kernel/fork','mm/mmap','mm/vma_init','mm/vma'):
            d,n=unit.split('/');self.assertIn(b/f'{d}/.{n}.o.cmd',paths)
        self.assertIn(b/'mm/.copy_vma_rust.o.cmd',paths)
        with self.assertRaises(ValueError):g.exit.input_paths(b,s,True,source_extension='unknown')

    def test_archive_and_definitions_fail_closed(self):
        g.archive_members('vma.o\ncopy_vma_rust.o\n',True)
        for text in ('vma.o\n','vma.o\nvma.o\ncopy_vma_rust.o\n','vma.o\ncopy_vma_rust.o\ncopy_vma_other.o\n'):
            with self.assertRaises(ValueError):g.archive_members(text,True)
        with self.assertRaises(ValueError):g.archive_members('vma.o\ncopy_vma_rust.o\n',False)
        g.definitions('0000 T copy_vma\n',{'copy_vma'})
        for text in ('0000 D copy_vma\n','0000 T copy_vma\n0000 T copy_vma\n','0000 T copy_vma\n0000 T rusix_copy_vma\n'):
            with self.assertRaises(ValueError):g.definitions(text,{'copy_vma'})

    def test_actual_open_call_not_pointer_data_or_unknown_thunk(self):
        body='0000 <rusix_copy_vma>:\n'
        for name in ('rusix_remove_ops','rusix_copy_open'):
            body+=' 10: callq 0\n 11: R_X86_64_PLT32 '+name+'-0x4\n'
        for transfer in (' 20: callq *%rax\n',' 20: callq 0\n 21: R_X86_64_PLT32 __x86_indirect_thunk_rax-0x4\n'):
            g.open_transfer(body+transfer)
        for bad in (body,body+' 20: callq *%rax\n 30: callq *%rdi\n',body+' 20: movq 0\n 21: R_X86_64_PLT32 __x86_indirect_thunk_rax-0x4\n',body+' 20: callq 0\n 21: R_X86_64_PLT32 unknown_thunk-0x4\n'):
            with self.assertRaises(ValueError):g.open_transfer(bad)

    def test_config_pair_axis(self):
        target=g.config_values((ROOT/'rusix/configs/x86_64-server.config').read_text())
        c=g.config_values((ROOT/'rusix/configs/x86_64-exit-mmap-rust.config').read_text());c[g.SELECTOR]='n';c.update(CONFIG_X86_64='y',CONFIG_THREAD_INFO_IN_TASK='y',CONFIG_MMU='y',CONFIG_PER_VMA_LOCK='y')
        r=dict(c);r[g.SELECTOR]='y'
        for profile,values in zip(g.PROFILES,(c,r)):g.check_config(profile,values,target)
        self.assertEqual(g.compare(c,r),[g.SELECTOR])
        with self.assertRaises(ValueError):g.compare(c,{**r,'CONFIG_NUMA':'y'})
        with self.assertRaises(ValueError):g.check_config('unknown',c,target)
        with self.assertRaises(ValueError):g.check_config('copy-vma-rust',{**r,g.exit.SELECTOR:'n'},target)

class Constants(unittest.TestCase):
    def test_four_byte_actual_values_and_old_eight_byte_rejection(self):
        for linked in (False,True):
            elf=Elf32(linked);self.assertEqual(g.constant_storage32(elf,elf.nm(),linked=linked),g.CONSTANTS)
            with self.assertRaises(ValueError):g.exit.vma.dup.constant_storage(elf,elf.nm(),linked=linked,expected=g.CONSTANTS)

    def test_storage_binding_value_and_bounds_negatives(self):
        for linked in (False,True):
            for mutation in ('size','kind','align','section','exec','bounds','value','duplicate','missing'):
                elf=Elf32(linked)
                if mutation=='size':elf.symbols[0]['size']=8
                elif mutation=='kind':elf.symbols[0]['kind']=2
                elif mutation=='align':elf.symbols[0]['address']+=1
                elif mutation=='section':elf.names[1]='.data'
                elif mutation=='exec':elf.headers[1][2]|=4
                elif mutation=='bounds':elf.headers[1][5]=7
                elif mutation=='value':elf.data=b'\x00'*8
                elif mutation=='duplicate':elf.symbols.append(dict(elf.symbols[0]))
                elif mutation=='missing':elf.symbols.pop()
                with self.subTest(linked=linked,mutation=mutation),self.assertRaises(ValueError):g.constant_storage32(elf,elf.nm(),linked=linked)
        elf=Elf32(False)
        with self.assertRaises(ValueError):g.constant_storage32(elf,elf.nm('D'),linked=False)
        with self.assertRaises(ValueError):g.constant_storage32(elf,elf.nm(),linked=True)

if __name__=='__main__':unittest.main()
