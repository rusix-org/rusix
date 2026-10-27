#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Copy/link source, preprocessing and actual emitted ownership; no runtime claim."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import copy_vma_source as extension
import exit_mmap_source

# The inherited verifier retains its strict default source scope.
import importlib.util

def load(name,file):
    spec=importlib.util.spec_from_file_location(name,Path(__file__).with_name(file))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

exit=load('copy_vma_exit','verify-exit-mmap.py')
preprocessor=load('copy_vma_pre','preprocess-copy-vma.py')
digest,config_values=exit.digest,exit.config_values
PROFILES={'copy-vma-c':False,'copy-vma-rust':True}
SELECTOR='CONFIG_RUSIX_COPY_VMA_RUST'
PUBLIC=('copy_vma','vma_link','vma_link_file','rusix_copy_vma','rusix_vma_link','rusix_vma_link_file_locked')
CONSTANTS={'rusix_copy_page_shift':12,'rusix_copy_enomem':0xfffffff4}
ITER='structvma_iteratorvmi={.mas={.tree=&(mm)->mm_mt,.index=INDEX,.node=((void*)0),.status=ma_start,},};'
LINK=ITER.replace('INDEX','0')+'returnrusix_vma_link(mm,vma,&vmi);'
COPY=('structvm_area_struct*vma=*vmap;unsignedlongvma_start=vma->vm_start;structmm_struct*mm=vma->vm_mm;'+ITER.replace('INDEX','addr')+
      'structvma_merge_structvmg={.mm=vma->vm_mm,.vmi=&vmi,.prev=((void*)0),.middle=vma,.next=((void*)0),'
      '.start=addr,.end=addr+len,.vm_flags=vma->vm_flags,.pgoff=vma_pgoff_offset(vma,addr),.file=vma->vm_file,'
      '.anon_vma=vma->anon_vma,.policy=((void*)0),.uffd_ctx=vma->vm_userfaultfd_ctx,.anon_name=anon_vma_name(vma),.state=VMA_MERGE_START,};'
      'structrusix_copy_vma_contextctx={.vmi=&vmi,.vmg=&vmg,.source=vma,.mm=mm,.source_start=vma_start,};'
      'returnrusix_copy_vma(&ctx,vmap,addr,len,pgoff,need_rmap_locks,keep_source);')


def source_policy(source):
    return exit.source_policy(source,source_extension=extension.ID)


def check_config(profile,values,target):
    if profile not in PROFILES:raise ValueError('Unknown copy VMA profile')
    exit.check_config('exit-mmap-rust',values,target)
    if values.get(SELECTOR)!=('y' if PROFILES[profile] else 'n'):raise ValueError('Wrong explicit copy VMA selector')


def compare(c,rust):
    changes={k for k in c.keys()|rust.keys() if c.get(k,'n')!=rust.get(k,'n')}
    if changes!={SELECTOR} or c.get(SELECTOR)!='n' or rust.get(SELECTOR)!='y':raise ValueError('Only copy VMA selector may differ')
    for values in (c,rust):
        for key in (exit.SELECTOR,exit.vma.SELECTOR,exit.vma.dup.SELECTOR,exit.vma.dup.copy.SELECTOR,
                    exit.vma.dup.copy.release.SELECTOR,exit.vma.dup.copy.release.mm.SELECTOR,exit.vma.dup.copy.release.task.SELECTOR):
            if values.get(key)!='y':raise ValueError('Missing inherited Rust selector')
    return sorted(changes)


def bodies(text,name):
    # Anchor at a C declaration, not an if (vma_link(...)) { call site.
    text=re.sub(r'^#.*$', '', text, flags=re.M)
    text=re.sub(r'/\*.*?\*/|//[^\n]*', '', text, flags=re.S)
    pattern=r'^[ \t]*(?:static\s+)?(?:inline\s+)?(?:struct\s+vm_area_struct\s*\*|unsigned\s+long|pgoff_t|rusix_vma_open_fn|void|int)\s*'+re.escape(name)+r'\s*\([^;{}]*\)\s*\{'
    result=[]
    for match in re.finditer(pattern,text,re.M):
        start=pos=match.end();depth=1
        while pos<len(text) and depth:
            depth+=(text[pos]=='{')-(text[pos]=='}');pos+=1
        if depth:raise ValueError('Unterminated C definition')
        result.append(re.sub(r'\s+','',text[start:pos-1]))
    return result


def check_preprocessed(text,rust):
    # This caller already holds the mapping lock: selected wrapper must not add
    # another lock. Exact whole-source restoration binds the surrounding policy.
    prepare=bodies(text,'vma_prepare')
    lock='i_mmap_lock_write(vp->mapping);'
    call='__vma_link_file(vp->insert,vp->insert->vm_file->f_mapping);'
    if len(prepare)!=1 or prepare[0].count(call)!=1 or lock not in prepare[0] or prepare[0].index(lock)>prepare[0].index(call):
        raise ValueError('Missing native already-locked file-link caller')
    if rust:
        for name,body in {'copy_vma':COPY,'vma_link':LINK,'__vma_link_file':'rusix_vma_link_file_locked(vma,mapping);'}.items():
            if bodies(text,name)!=[body]:raise ValueError('Wrong native copy/link context: '+name)
        if bodies(text,'vma_link_file'):raise ValueError('Original file link remains selected')
        compact=re.sub(r'\s+','',text)
        if 'typedefvoid(*rusix_vma_open_fn)(structvm_area_struct*vma);' not in compact:raise ValueError('Changed open callback ABI')
        for name,body in {'rusix_copy_open':'returnops->open;', 'rusix_copy_start':'returnvma->vm_start;',
                          'rusix_copy_end':'returnvma->vm_end;', 'rusix_copy_pgoff':'returnvma->vm_pgoff;',
                          'rusix_link_set_count':'mm->map_count=count;'}.items():
            if bodies(text,name)!=[body]:raise ValueError('Wrong canonical field primitive '+name)
    else:
        for name in ('copy_vma','vma_link','vma_link_file','__vma_link_file'):
            if len(bodies(text,name))!=1:raise ValueError('Missing original policy '+name)
        for name in ('rusix_copy_open','rusix_copy_merge','rusix_link_prealloc'):
            if bodies(text,name):raise ValueError('Rust primitive selected in C mode')
        tokens={'copy_vma':('vma_merge_copied_range(&vmg);','*vmap=vma=new_vma;',
                            '*need_rmap_locks=(new_vma->vm_pgoff<=vma->vm_pgoff);',
                            'vma_dup_policy(vma,new_vma)','anon_vma_clone(new_vma,vma)',
                            'vma_close(new_vma);','unlink_anon_vmas(new_vma);','vm_area_free(new_vma);'),
                'vma_link':('vma_iter_prealloc(&vmi,vma)','vma_iter_store_new(&vmi,vma);','vma_link_file(vma);','mm->map_count++;'),
                'vma_link_file':('i_mmap_lock_write(mapping);','__vma_link_file(vma,mapping);','i_mmap_unlock_write(mapping);'),
                '__vma_link_file':('mapping_allow_writable(mapping);','vma_interval_tree_insert(vma,&mapping->i_mmap);')}
        for name,required in tokens.items():
            for token in required:
                if token not in bodies(text,name)[0]:raise ValueError('Original copy/link policy missing '+token)


def constant_storage32(elf,nm,*,linked):
    # A separate, exact four-byte contract: the inherited eight-byte API remains unchanged.
    if elf.relocatable == linked:raise ValueError('Wrong constant ELF kind')
    out={}
    for name,value in CONSTANTS.items():
        rows=[r.split() for r in nm.splitlines() if r.split() and r.split()[-1]==name]
        if len(rows)!=1 or len(rows[0])!=3 or rows[0][1] not in ({'R','D'} if linked else {'R'}):raise ValueError('Wrong constant binding')
        sym=elf.symbol(name);index,offset=elf.location(sym);sec=elf.headers[index]
        if (sym['kind']!=1 or sym['size']!=4 or int(rows[0][0],16)!=sym['address'] or sym['address']%4 or
            elf.names[index]!='.rodata' or sec[1]!=1 or not sec[2]&2 or sec[2]&4 or (not linked and sec[2]&1) or
            offset<0 or offset+4>sec[5]):raise ValueError('Wrong four-byte constant storage')
        actual=int.from_bytes(elf.section_data(index)[offset:offset+4],'little')
        if actual!=value:raise ValueError('Wrong canonical four-byte constant value')
        out[name]=actual
    return out


def definitions(text,expected):
    for name in PUBLIC:
        rows=[r.split() for r in text.splitlines() if r.split() and r.split()[-1]==name]
        if len(rows)!=int(name in expected) or (rows and (len(rows[0])!=3 or rows[0][1]!='T')):raise ValueError('Wrong copy/link owner '+name)


def archive_members(text,rust):
    names=[Path(n).name for n in text.splitlines()]
    if names.count('vma.o')!=1 or names.count('copy_vma_rust.o')!=int(rust):raise ValueError('Wrong copy/link archive ownership')
    if any('copy_vma' in n and n!='copy_vma_rust.o' for n in names):raise ValueError('Alternate copy VMA object')


def open_transfer(text):
    body=exit.vma.dis_body(text,'rusix_copy_vma')
    raw=re.findall(r'\b(?:callq?|jmpq?)\s+\*%[a-z0-9]+\b',body)
    thunks=set(re.findall(r'R_X86_64_PLT32\s+(__x86_indirect_thunk_[a-z0-9]+)(?:-0x4)?\s*$',body,re.M))
    if len(raw)+sum(exit.executable_calls(body,t) for t in thunks)!=1:
        raise ValueError('Missing/ambiguous recognized indirect open callback')
    exit.executable_calls(body,'rusix_remove_ops')
    exit.executable_calls(body,'rusix_copy_open')


def input_paths(build,source,rust):
    paths=exit.input_paths(build,source,True,source_extension=extension.ID)+preprocessor.inputs(build,source)
    paths += [source/f'rusix/configs/x86_64-copy-vma-{"rust" if rust else "c"}.config']
    if rust:paths += [build/'mm/copy_vma_rust.o',build/'mm/.copy_vma_rust.o.cmd']
    return list(dict.fromkeys(paths))


def verify(args):
    source,build,evidence=args.source.resolve(),args.build.resolve(),args.evidence.resolve();rust=PROFILES[args.profile]
    check_config(args.profile,config_values((build/'.config').read_text()),config_values((source/'rusix/configs/x86_64-server.config').read_text()))
    proof=source_policy(source);paths=input_paths(build,source,rust);before={str(p):digest(p) for p in paths}
    inherited=exit.verify(argparse.Namespace(source=source,build=build,evidence=evidence,profile='exit-mmap-rust'),source_extension=extension.ID)
    if inherited['status']!='PASS' or inherited['implementation']!='rust' or inherited['source_extension']!=proof:raise ValueError('Inherited proof mismatch')
    (evidence/'copy-vma-exit-selection.json').write_text(json.dumps(inherited,indent=2,sort_keys=True)+'\n')
    check_preprocessed((build/'mm/vma.i').read_text(),rust)
    def run(name,argv):
        r=subprocess.run(argv,check=True,capture_output=True,text=True)
        if r.stderr:raise ValueError('Object inspection diagnostics: '+r.stderr)
        (evidence/name).write_text(r.stdout);return r.stdout
    archive=build/'mm/built-in.a';members=run('copy-vma-archive.txt',['llvm-ar','t',str(archive)]);archive_members(members,rust)
    expected={'vma':{'copy_vma','vma_link'}| (set() if rust else {'vma_link_file'})}
    if rust:expected['copy_vma_rust']={'rusix_copy_vma','rusix_vma_link','vma_link_file','rusix_vma_link_file_locked'}
    expected['linked']=set(PUBLIC) if rust else {'copy_vma','vma_link','vma_link_file'}
    tables={};dis={};payloads={}
    for name,owned in expected.items():
        obj=build/'vmlinux' if name=='linked' else build/f'mm/{name}.o'
        if name!='linked':
            member=next(n for n in members.splitlines() if Path(n).name==obj.name)
            payloads[member]=exit.vma.dup.copy.release.task.archive_member_hash(archive,member,obj)
            dis[name]=run(f'copy-vma-{name}-disassembly.txt',['llvm-objdump','-dr',str(obj)])
        tables[name]=run(f'copy-vma-{name}-symbols.txt',['llvm-nm','--defined-only',str(obj)])
        metadata=json.loads(run(f'copy-vma-{name}-elf.json',['llvm-readobj','--elf-output-style=JSON','--sections','--symbols',str(obj)]))
        definitions(tables[name],owned)
        for symbol in owned:exit.vma.function_location(metadata,symbol,False)
    constants={}
    if rust:
        for caller,callee in (('copy_vma','rusix_copy_vma'),('vma_link','rusix_vma_link')):exit.vma.call_from(dis['vma'],caller,callee)
        exit.executable_calls(dis['vma'],'rusix_vma_link_file_locked')
        # The moved close consumer is proved in its actual new defining object.
        exit.executable_calls(exit.vma.dis_body(dis['copy_vma_rust'],'rusix_copy_vma'),'rusix_vma_close')
        open_transfer(dis['copy_vma_rust'])
        helpers=set(re.findall(r'fn (rusix_(?:copy|link)_[a-z_]+)\(', (source/'mm/copy_vma_rust.rs').read_text()))-{'rusix_copy_vma'}
        for helper in helpers:
            for table in (tables['vma'],tables['linked']):
                rows=[r.split() for r in table.splitlines() if r.split() and r.split()[-1]==helper]
                if len(rows)!=1 or len(rows[0])!=3 or rows[0][1]!='T':raise ValueError('Missing typed primitive '+helper)
            exit.executable_calls(dis['copy_vma_rust'],helper)
        elf=exit.vma.dup.elf_reader.Elf
        constants=constant_storage32(elf(build/'mm/vma.o',indexed_sections=True),tables['vma'],linked=False)
        if constant_storage32(elf(build/'vmlinux',indexed_sections=True),tables['linked'],linked=True)!=constants:raise ValueError('Linked constants changed')
    else:
        for table in tables.values():
            if any(row.split() and row.split()[-1] in CONSTANTS for row in table.splitlines()):raise ValueError('Selected constants in C mode')
    exit_mmap_source.require_unchanged(paths,before)
    return dict(status='PASS',implementation='rust' if rust else 'c',source_extension=proof,input_sha256=before,
                archive_member_sha256=payloads,constant_values=constants,exit_mmap_selection=inherited,
                scope='Actual source/preprocessing/object/linked ownership; no runtime claim')


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='action',required=True)
    s=sub.add_parser('source');s.add_argument('--source',type=Path,required=True)
    s=sub.add_parser('config');s.add_argument('--profile',choices=PROFILES,required=True);s.add_argument('--source',type=Path,required=True);s.add_argument('--config',type=Path,required=True)
    s=sub.add_parser('compare');s.add_argument('--c',type=Path,required=True);s.add_argument('--rust',type=Path,required=True)
    s=sub.add_parser('objects');s.add_argument('--profile',choices=PROFILES,required=True)
    for n in ('source','build','evidence'):s.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args()
    if a.action=='source':result=source_policy(a.source)
    elif a.action=='compare':result=compare(config_values(a.c.read_text()),config_values(a.rust.read_text()))
    elif a.action=='config':check_config(a.profile,config_values(a.config.read_text()),config_values((a.source/'rusix/configs/x86_64-server.config').read_text()));result={'status':'PASS','scope':'configuration only'}
    else:result=verify(a)
    print(json.dumps(result,indent=2,sort_keys=True))
if __name__=='__main__':main()
