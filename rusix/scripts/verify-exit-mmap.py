#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Exact teardown source composition and actual compiled selection evidence."""
import argparse
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import exit_mmap_source as extension


def load(name, filename):
    spec=importlib.util.spec_from_file_location(name,Path(__file__).with_name(filename))
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod


vma=load('exit_vma_gate','verify-vma-lifecycle.py')
preprocessor=load('exit_preprocessor','preprocess-exit-mmap.py')
kunit_elf=load('exit_kunit_ownership','exit_kunit_elf.py')
digest,config_values=vma.digest,vma.config_values
SELECTOR='CONFIG_RUSIX_EXIT_MMAP_RUST'
PROFILES={'exit-mmap-c':False,'exit-mmap-rust':True,
          'exit-mmap-kunit-c':False,'exit-mmap-kunit-rust':True}
KUNIT_PROFILES={'exit-mmap-kunit-c','exit-mmap-kunit-rust'}
TEST_CONTEXT=vma.dup.copy.TEST_CONTEXT
PUBLIC=('exit_mmap','remove_vma','rusix_exit_mmap','rusix_vma_close')
CONTEXT=('structmmu_gathertlb;structvma_iteratorvmi={.mas={.tree=&(mm)->mm_mt,'
         '.index=0,.node=((void*)0),.status=ma_start,},};'
         'structrusix_exit_contextctx={.vmi=&vmi,.tlb=&tlb};rusix_exit_mmap(mm,&ctx);')
CLOSE='if(vma->vm_ops&&vma->vm_ops->close){vma->vm_ops->close(vma);vma->vm_ops=&vma_dummy_vm_ops;}'


def source_policy(source, *, source_extension=extension.ID):
    restored,proof=extension.validate(source,source_extension)
    upstream=vma.dup.original_policy(restored['mm/mmap.c'])
    proof['upstream_mmap_sha256']=extension.hashlib.sha256(upstream.encode()).hexdigest()
    return proof


def check_config(profile,values,target):
    if profile not in PROFILES:raise ValueError('Unknown teardown profile')
    context=TEST_CONTEXT if profile in KUNIT_PROFILES else None
    vma.check_config('vma-lifecycle-rust',values,target,test_context=context)
    if values.get(SELECTOR)!=('y' if PROFILES[profile] else 'n'):raise ValueError('Wrong explicit teardown selector')


def compare(c,rust):
    changes={k for k in c.keys()|rust.keys() if c.get(k,'n')!=rust.get(k,'n')}
    if c.get(SELECTOR)!='n' or rust.get(SELECTOR)!='y' or changes!={SELECTOR}:raise ValueError('Only teardown selector may differ')
    for values in (c,rust):
        for name in (vma.SELECTOR,vma.dup.SELECTOR,vma.dup.copy.SELECTOR,vma.dup.copy.release.SELECTOR,
                     vma.dup.copy.release.mm.SELECTOR,vma.dup.copy.release.task.SELECTOR):
            if values.get(name)!='y':raise ValueError('Inherited Rust selection missing')
    return sorted(changes)


def check_preprocessed(mmap_text,vma_text,rust, *, source_extension=extension.ID, copy_rust=False):
    if source_extension not in (extension.ID, extension.copy_extension.ID) or (copy_rust and source_extension != extension.copy_extension.ID):
        raise ValueError("Unknown close-consumer extension")
    for text in (mmap_text,vma_text):
        if vma.bodies(text,'vma_close')!=(['rusix_vma_close(vma);'] if rust else [CLOSE]):
            raise ValueError('Wrong common close policy')
    exits=vma.bodies(mmap_text,'exit_mmap');removes=vma.bodies(vma_text,'remove_vma')
    if rust:
        if exits!=[CONTEXT] or removes:raise ValueError('Selected C teardown policy remains/dispatch changed')
        expected={'rusix_remove_ops':'returnvma->vm_ops;',
                  'rusix_remove_close':'returnops->close;',
                  'rusix_remove_dummy':'vma->vm_ops=&vma_dummy_vm_ops;',
                  'rusix_remove_file':'returnvma->vm_file;',
                  'rusix_remove_fput':'fput(file);'}
        for name,body in expected.items():
            if vma.bodies(vma_text,name)!=[body]:raise ValueError('Changed canonical close primitive '+name)
        compact=re.sub(r'\s+','',vma_text)
        if 'typedefvoid(*rusix_vma_close_fn)(structvm_area_struct*vma);' not in compact:
            raise ValueError('Wrong nullable close callback ABI')
        if vma.bodies(mmap_text,'rusix_exit_gather')!=['tlb_gather_mmu_fullmm(ctx->tlb,mm);']:
            raise ValueError('Wrong gather initializer')
    else:
        if len(exits)!=1 or len(removes)!=1:raise ValueError('Missing original teardown functions')
        body=exits[0]
        for token in ('mmu_notifier_release(mm);','mmap_read_lock(mm);','arch_exit_mmap(mm);',
                      'xa_is_zero(vma)','tlb_gather_mmu_fullmm(&tlb,mm);','mmap_read_unlock(mm);',
                      'mm_flags_set(21,mm);','mt_clear_in_rcu(&mm->mm_mt);',
                      'tlb_finish_mmu(&tlb);','vma_mark_detached(vma);','remove_vma(vma);',
                      '__mt_destroy(&mm->mm_mt);','vm_unacct_memory(nr_accounted);'):
            if token not in body:raise ValueError('Missing original teardown operation '+token)
        if body.count('vma_iter_set(&vmi,vma->vm_end);')!=2:raise ValueError('Original end observations changed')
        for token in ('vma_close(vma);','if(vma->vm_file)','fput(vma->vm_file);','mpol_put(', 'vm_area_free(vma);'):
            if token not in removes[0]:raise ValueError('Missing original remove operation')
        for text in (mmap_text,vma_text):
            if any(vma.bodies(text,name) for name in ('rusix_exit_gather','rusix_remove_ops','rusix_remove_close')):
                raise ValueError('Unexpected selected primitive in C mode')
    # These independent close-only callers must still select the shared bridge.
    for name in (('vms_clean_up_area',) if copy_rust else ('vms_clean_up_area','copy_vma')):
        bodies=vma.bodies(vma_text,name)
        if len(bodies)!=1 or 'vma_close(' not in bodies[0]:raise ValueError('Missing actual close consumer '+name)


def definitions(text,expected):
    for name in PUBLIC:
        rows=[r.split() for r in text.splitlines() if r.split() and r.split()[-1]==name]
        if len(rows)!=int(name in expected) or (rows and (len(rows[0])!=3 or rows[0][1]!='T')):
            raise ValueError('Wrong teardown definition '+name)


def archive_members(text,rust, *, test_context=None):
    if test_context not in (None,TEST_CONTEXT):raise ValueError('Unknown teardown archive test context')
    names=[Path(n).name for n in text.splitlines()]
    fixture=test_context==TEST_CONTEXT
    for name,count in (('mmap.o',1),('vma.o',1),('exit_mmap_rust.o',int(rust)),
                       ('exit_mmap_test.o',int(fixture))):
        if names.count(name)!=count:raise ValueError('Wrong teardown archive ownership')
    allowed={'exit_mmap_rust.o'} | ({'exit_mmap_test.o'} if fixture else set())
    if any('exit_mmap' in n and n not in allowed for n in names):raise ValueError('Unexpected teardown object')


def executable_calls(text,target):
    count=0;previous=''
    for row in text.splitlines():
        if 'R_X86_64_' in row and re.search(r'\b'+re.escape(target)+r'(?:[-+]|\s|$)',row):
            if not re.search(r'R_X86_64_PLT32\s+'+re.escape(target)+r'(?:-0x4)?\s*$',row) or not re.search(r'\b(?:callq?|jmpq?)\b',previous):
                raise ValueError('Non-executable or inexact target '+target)
            count+=1
        elif re.match(r'^\s*[0-9a-f]+:',row):previous=row
    if not count:raise ValueError('Missing executable target '+target)
    return count


def callback_transfer(text):
    body=vma.dis_body(text,'rusix_vma_close')
    raw=re.findall(r'\b(?:callq?|jmpq?)\s+\*%[a-z0-9]+\b',body)
    thunks=set(re.findall(r'R_X86_64_PLT32\s+(__x86_indirect_thunk_[a-z0-9]+)(?:-0x4)?\s*$',body,re.M))
    for target in thunks:executable_calls(body,target)
    if len(raw)+sum(executable_calls(body,t) for t in thunks)!=1:
        raise ValueError('Missing/ambiguous recognized indirect close callback transfer')
    executable_calls(body,'rusix_remove_ops');executable_calls(body,'rusix_remove_close');executable_calls(body,'rusix_remove_dummy')


def input_paths(build,source,rust, *, kunit=False, source_extension=extension.ID):
    paths=vma.input_paths(build,source,True,source_extension=source_extension)+preprocessor.inputs(build,source,source_extension=source_extension)+[
        build/'mm/vma.i',source/'init/Kconfig',source/'mm/Makefile',
        source/'rusix/scripts/verify-exit-mmap.py',source/f'rusix/configs/x86_64-exit-mmap-{"kunit-" if kunit else ""}{"rust" if rust else "c"}.config']
    if rust:paths.append(build/'mm/exit_mmap_rust.o')
    paths += kunit_elf.input_paths(build,source,kunit)
    if kunit:
        paths += [source/'rusix/scripts/boot-kunit.sh',source/'rusix/scripts/validate-exit-mmap-kunit.py',
                  source/'rusix/scripts/validate-completion-kunit.py',source/'rusix/scripts/validate-brd-kunit.py']
    return list(dict.fromkeys(paths))


def verify(args, *, source_extension=extension.ID):
    source,build,evidence=args.source.resolve(),args.build.resolve(),args.evidence.resolve();rust=PROFILES[args.profile]
    check_config(args.profile,config_values((build/'.config').read_text()),config_values((source/'rusix/configs/x86_64-server.config').read_text()))
    proof=source_policy(source,source_extension=source_extension)
    context=TEST_CONTEXT if args.profile in KUNIT_PROFILES else None
    paths=input_paths(build,source,rust,kunit=context is not None,source_extension=source_extension);before={str(p):digest(p) for p in paths}
    actual=preprocessor.record(build,source,source_extension=source_extension)
    if json.loads((evidence/'exit-mmap-preprocess.json').read_text())!=actual:raise ValueError('Four-unit preprocessing provenance changed')
    if (evidence/'exit-mmap-preprocess.exit').read_text().strip()!='0' or re.search('warning:|error:',(evidence/'exit-mmap-preprocess.log').read_text(),re.I):raise ValueError('Teardown preprocessing failure/diagnostic')
    inherited=vma.verify(argparse.Namespace(source=source,build=build,evidence=evidence,profile='vma-lifecycle-rust'),source_extension=source_extension,test_context=context)
    if inherited['test_context']!=context or inherited['status']!='PASS' or inherited['implementation']!='rust':raise ValueError('Inherited VMA proof failed')
    if inherited['dup_mmap_selection']['source_extension']['raw_sha256']!=proof['raw_sha256']:raise ValueError('Delegated source identity mismatch')
    (evidence/'exit-mmap-vma-selection.json').write_text(json.dumps(inherited,indent=2,sort_keys=True)+'\n')
    copy_rust = source_extension == extension.copy_extension.ID and config_values((build/'.config').read_text()).get('CONFIG_RUSIX_COPY_VMA_RUST') == 'y'
    check_preprocessed((build/'mm/mmap.i').read_text(),(build/'mm/vma.i').read_text(),rust,source_extension=source_extension,copy_rust=copy_rust)
    def run(name,argv):
        result=subprocess.run(argv,check=True,capture_output=True,text=True)
        if result.stderr:raise ValueError('Object inspection diagnostics: '+result.stderr)
        (evidence/name).write_text(result.stdout);return result.stdout
    archive=build/'mm/built-in.a';members=run('exit-mmap-archive.txt',['llvm-ar','t',str(archive)]);archive_members(members,rust,test_context=context)
    tables,metadata,dis,hashes={},{},{},{}
    expected={'mmap':{'exit_mmap'},'vma':set() if rust else {'remove_vma'}}
    if rust:expected['exit_mmap_rust']={'rusix_exit_mmap','rusix_vma_close','remove_vma'}
    expected['linked']={'exit_mmap','remove_vma'}|({'rusix_exit_mmap','rusix_vma_close'} if rust else set())
    for name in expected:
        obj=build/'vmlinux' if name=='linked' else build/f'mm/{name}.o'
        if name!='linked':
            member=next(n for n in members.splitlines() if Path(n).name==obj.name)
            hashes[member]=vma.dup.copy.release.task.archive_member_hash(archive,member,obj)
        tables[name]=run(f'exit-mmap-{name}-symbols.txt',['llvm-nm','--defined-only',str(obj)])
        metadata[name]=json.loads(run(f'exit-mmap-{name}-elf.json',['llvm-readobj','--elf-output-style=JSON','--sections','--symbols',str(obj)]))
        definitions(tables[name],expected[name])
        for function in expected[name]:vma.function_location(metadata[name],function,False)
        if name!='linked':dis[name]=run(f'exit-mmap-{name}-disassembly.txt',['llvm-objdump','-dr',str(obj)])
    helpers=set(re.findall(r'fn (rusix_(?:exit|remove)_[a-z_]+)\(', (source/'mm/exit_mmap_rust.rs').read_text()))-{'rusix_exit_mmap'}
    for helper in helpers:
        owner='mmap' if helper.startswith('rusix_exit_') else 'vma'
        for table in (tables[owner],tables['linked']):
            rows=[r.split() for r in table.splitlines() if r.split() and r.split()[-1]==helper]
            kind='T'
            if len(rows)!=int(rust) or (rows and (len(rows[0])!=3 or rows[0][1]!=kind)):raise ValueError('Wrong typed primitive '+helper)
    constant_values={}
    if rust:
        constant_values=vma.dup.check_constants(build/'mm/mmap.o',build/'vmlinux',tables['mmap'],tables['linked'],expected={'rusix_exit_account':1<<20})
        vma.call_from(dis['mmap'],'exit_mmap','rusix_exit_mmap')
        # The original vma.c consumers cannot silently retain an inlined C close.
        if executable_calls(dis['vma'],'rusix_vma_close')<(1 if copy_rust else 2):raise ValueError('Missing independent close consumers')
        if not copy_rust:executable_calls(vma.dis_body(dis['vma'],'copy_vma'),'rusix_vma_close')
        callback_transfer(dis['exit_mmap_rust'])
        for helper in helpers:executable_calls(dis['exit_mmap_rust'],helper)
        executable_calls(dis['exit_mmap_rust'],'vm_area_free')
    else:
        for table in (tables['mmap'],tables['linked']):
            if any(row.split() and row.split()[-1]=='rusix_exit_account' for row in table.splitlines()):raise ValueError('Rust account primitive in C mode')
    extension.require_unchanged(paths,before)
    fixture_proof=kunit_elf.verify(build,evidence,context is not None,source=source)
    extension.require_unchanged(paths,before)
    return dict(fixture_selection=fixture_proof,test_context=context,status='PASS',implementation='rust' if rust else 'c',source_extension=proof,input_sha256=before,
                archive_member_sha256=hashes,constant_values=constant_values,vma_lifecycle_selection=inherited,
                scope='Exact source restoration, actual four-unit preprocessing and emitted selection; no runtime claim')


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='action',required=True)
    p=sub.add_parser('source');p.add_argument('--source',type=Path,required=True)
    p=sub.add_parser('objects');p.add_argument('--profile',choices=PROFILES,required=True)
    for name in ('source','build','evidence'):p.add_argument('--'+name,type=Path,required=True)
    p=sub.add_parser('config');p.add_argument('--profile',choices=PROFILES,required=True)
    for name in ('source','config'):p.add_argument('--'+name,type=Path,required=True)
    p=sub.add_parser('compare');p.add_argument('--c',type=Path,required=True);p.add_argument('--rust',type=Path,required=True)
    args=parser.parse_args()
    if args.action=='objects':result=verify(args)
    elif args.action=='source':result=dict(status='PASS',scope='Source restoration only',source_extension=source_policy(args.source))
    elif args.action=='compare':result=compare(config_values(args.c.read_text()),config_values(args.rust.read_text()))
    else:
        check_config(args.profile,config_values(args.config.read_text()),config_values((args.source/'rusix/configs/x86_64-server.config').read_text()));result=dict(status='PASS',scope='Config only',test_context=TEST_CONTEXT if args.profile in KUNIT_PROFILES else None)
    print(json.dumps(result,indent=2,sort_keys=True))


if __name__=='__main__':main()
