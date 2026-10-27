#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Source/model regressions only: no claim of compiled or runtime selection."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'rusix/scripts'))

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod

gate=load('exit_gate',ROOT/'rusix/scripts/verify-exit-mmap.py')
ext=gate.extension
commands=load('exit_command_tests',Path(__file__).with_name('test_saved_clang_command.py'))


def selected_text():
    mmap='void exit_mmap(void){'+gate.CONTEXT+'}\nvoid vma_close(void){rusix_vma_close(vma);}\nvoid rusix_exit_gather(void){tlb_gather_mmu_fullmm(ctx->tlb,mm);}'
    vma='void vma_close(void){rusix_vma_close(vma);}\ntypedef void (*rusix_vma_close_fn)(struct vm_area_struct *vma);\n'
    for name,body in {'rusix_remove_ops':'return vma->vm_ops;', 'rusix_remove_close':'return ops->close;',
                      'rusix_remove_dummy':'vma->vm_ops=&vma_dummy_vm_ops;', 'rusix_remove_file':'return vma->vm_file;',
                      'rusix_remove_fput':'fput(file);','vms_clean_up_area':'vma_close(vma);','copy_vma':'vma_close(new_vma);'}.items():
        vma+='void '+name+'(void){'+body+'}\n'
    return mmap,vma


class ExitSelection(unittest.TestCase):
    def test_actual_three_file_and_upstream_restoration(self):
        proof=gate.source_policy(ROOT)
        self.assertEqual(len(proof['raw_sha256']),3)
        self.assertEqual(proof['upstream_mmap_sha256'],gate.vma.dup.PINNED_MMAP_SHA256)
        with self.assertRaises(ValueError):gate.vma.dup.original_policy((ROOT/'mm/mmap.c').read_text())

    def test_each_file_guards_shim_and_unrelated_mutation_rejected(self):
        for name,(shim,_) in ext.REGIONS.items():
            text=(ROOT/name).read_text()
            for bad in (text+'\n',text+ext.END,text.replace(ext.START,ext.START+'/* changed */\n'),text.replace(shim,'#else\n'),text.replace(ext.END,'')):
                with self.subTest(name=name),self.assertRaises(ValueError):ext.restore(name,bad)

    def test_delegation_validates_all_files_and_identifier(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'mm').mkdir()
            for name in ext.REGIONS:(root/name).write_text((ROOT/name).read_text())
            ext.validate(root,ext.ID)
            for bad in (None,'exit-mmap-v2',lambda _:True):
                with self.assertRaises(ValueError):ext.validate(root,bad)
            (root/'mm/internal.h').write_text((root/'mm/internal.h').read_text()+'\n')
            with self.assertRaises(ValueError):ext.validate(root,ext.ID)

    def test_extension_raw_inputs_bound_at_each_level(self):
        build=Path('/out/builds/a');source=Path('/src')
        for paths in (gate.input_paths(build,source,True),gate.vma.input_paths(build,source,True,source_extension=ext.ID),gate.vma.dup.input_paths(build,source,True,source_extension=ext.ID)):
            self.assertEqual(len(paths),len(set(paths)))
            for path in ext.paths(source,ext.ID):self.assertIn(path,paths)
        for func in (gate.vma.input_paths,gate.vma.dup.input_paths):
            with self.assertRaises(ValueError):func(build,source,True,source_extension='arbitrary')
        inputs=gate.preprocessor.inputs(build,source)
        for unit in ('kernel/fork','mm/mmap','mm/vma_init','mm/vma'):
            directory,name=unit.split('/');self.assertIn(build/f'{directory}/.{name}.o.cmd',inputs)

    def test_actual_input_mutation_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'header';path.write_text('original input')
            before={str(path):gate.digest(path)}
            ext.require_unchanged([path],before)
            path.write_text('modified during delegated inspection')
            with self.assertRaises(ValueError):ext.require_unchanged([path],before)
            with self.assertRaises(ValueError):ext.require_unchanged([],before)

    def test_context_and_shared_callback_body_selection(self):
        mmap,vma=selected_text();gate.check_preprocessed(mmap,vma,True)
        for a,b in ((mmap.replace('.tlb=&tlb','.tlb=0'),vma),(mmap+'void exit_mmap(void){}',vma),
                    (mmap,vma+'void remove_vma(void){}'),(mmap,vma.replace('returnops->close;','return0;').replace('return ops->close;','return 0;')),
                    (mmap,vma.replace('vma_close(new_vma);','')), (mmap,vma.replace('(*rusix_vma_close_fn)','(*other_fn)'))):
            with self.assertRaises(ValueError):gate.check_preprocessed(a,b,True)
        with self.assertRaises(ValueError):gate.check_preprocessed(mmap,vma,False)

    def test_c_policy_landmarks_with_native_macro_expansion(self):
        restored,_=ext.validate(ROOT,ext.ID)
        header=restored['mm/internal.h']
        mmap=(restored['mm/mmap.c']+header).replace('MMF_OOM_SKIP','21')
        vma=restored['mm/vma.c']+header
        gate.check_preprocessed(mmap,vma,False)
        for bad in (mmap.replace('mm_flags_set(21, mm);',''),mmap.replace('vma_iter_set(&vmi, vma->vm_end);','',1)):
            with self.assertRaises(ValueError):gate.check_preprocessed(bad,vma,False)
        with self.assertRaises(ValueError):gate.check_preprocessed(mmap,vma.replace('vm_area_free(vma);',''),False)

    def test_exact_definition_ownership_and_prefix_labels(self):
        gate.definitions('0000 T exit_mmap\n0000 t __pfx_exit_mmap\n',{'exit_mmap'})
        for text in ('','0000 D exit_mmap\n','0000 T exit_mmap\n0000 T exit_mmap\n','0000 T exit_mmap\n0010 T rusix_exit_mmap\n'):
            with self.assertRaises(ValueError):gate.definitions(text,{'exit_mmap'})

    def test_archive_rejects_alternate_and_duplicate(self):
        gate.archive_members('mmap.o\nvma.o\nexit_mmap_rust.o\n',True)
        for text in ('mmap.o\nvma.o\n','mmap.o\nvma.o\nexit_mmap_rust.o\nexit_mmap_other.o\n','mmap.o\nvma.o\nvma.o\nexit_mmap_rust.o\n'):
            with self.assertRaises(ValueError):gate.archive_members(text,True)

    def test_callback_transfer_not_data_reference_or_unsupported_target(self):
        body='0000 <rusix_vma_close>:\n'
        for name in ('rusix_remove_ops','rusix_remove_close','rusix_remove_dummy'):
            body+=' 10: callq 0\n 11: R_X86_64_PLT32 '+name+'-0x4\n'
        for transfer in (' 20: callq *%rax\n',' 20: callq 0\n 21: R_X86_64_PLT32 __x86_indirect_thunk_rax-0x4\n'):
            gate.callback_transfer(body+transfer)
        for bad in (body,body+' 20: callq *%rax\n 30: callq *%rdi\n',body+' 20: movq 0\n 21: R_X86_64_PLT32 __x86_indirect_thunk_rax-0x4\n',body+' 20: callq 0\n 21: R_X86_64_PLT32 unknown_thunk-0x4\n'):
            with self.assertRaises(ValueError):gate.callback_transfer(bad)

    def test_vma_unit_strictness(self):
        text=commands.mmap_record().replace('mm/mmap','mm/vma').replace('mm/.mmap','mm/.vma').replace('"mmap"','"vma"').replace('kmod_mmap','kmod_vma')
        argv=gate.preprocessor.command(text,Path('/out/vma.i'));self.assertIn('/src/mm/vma.c',argv)
        for old,new in (('/src/mm/vma.c','/src/mm/vma_init.c'),('-o mm/vma.o','-o mm/mmap.o'),('mm/.vma.o.d','mm/.mmap.o.d'),('kmod_vma','kmod_mmap'),('clang ','clang -fplugin=/tmp/x '),('--uaccess mm/vma.o','--uaccess mm/mmap.o')):
            with self.subTest(old=old),self.assertRaises(ValueError):gate.preprocessor.command(text.replace(old,new),Path('/out/vma.i'))

    def test_actual_pair_and_required_ancestors(self):
        configs=[gate.config_values((ROOT/f'rusix/configs/x86_64-exit-mmap-{side}.config').read_text()) for side in ('c','rust')]
        self.assertEqual(gate.compare(*configs),[gate.SELECTOR])
        target=gate.config_values((ROOT/'rusix/configs/x86_64-server.config').read_text())
        for profile,values in zip(gate.PROFILES,configs):
            values.update(CONFIG_X86_64='y',CONFIG_THREAD_INFO_IN_TASK='y',CONFIG_MMU='y',CONFIG_PER_VMA_LOCK='y')
            gate.check_config(profile,values,target)
            for option in (gate.SELECTOR,gate.vma.SELECTOR):
                bad=values.copy();bad.pop(option)
                with self.assertRaises(ValueError):gate.check_config(profile,bad,target)
        with self.assertRaises(ValueError):gate.compare(configs[0],configs[1]|{'CONFIG_DEBUG_FS':'y'})


if __name__=='__main__':unittest.main()
