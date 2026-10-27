#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Compose retained MM-copy proof with actual mapping-duplication selection."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess


def load(name,filename):
    spec=importlib.util.spec_from_file_location(name,Path(__file__).with_name(filename))
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod


copy=load('dup_copy','verify-mm-copy.py')
preprocessor=load('dup_preprocessor','preprocess-dup-mmap.py')
elf_reader=load('dup_elf','verify-brd-parameter-owner.py')
digest,config_values=copy.digest,copy.config_values
PROFILES={'mm-dup-mmap-c':False,'mm-dup-mmap-rust':True}
SELECTOR='CONFIG_RUSIX_DUP_MMAP_RUST'
BRIDGE='rusix_dup_mmap'
START='#ifdef CONFIG_RUSIX_DUP_MMAP_RUST\n'
END='#endif /* CONFIG_RUSIX_DUP_MMAP_RUST */\n'
SHIM='''#include "dup_mmap_impl.h"
extern int rusix_dup_mmap(struct mm_struct *mm, struct mm_struct *oldmm,
			 struct rusix_dup_mmap_context *ctx);

__latent_entropy int dup_mmap(struct mm_struct *mm, struct mm_struct *oldmm)
{
	LIST_HEAD(uf);
	VMA_ITERATOR(vmi, mm, 0);
	struct rusix_dup_mmap_context ctx = { .vmi = &vmi, .uf = &uf };

	return rusix_dup_mmap(mm, oldmm, &ctx);
}
#else
'''
PINNED_MMAP_SHA256='20daa6fcd4021b6c08fa20ba2e6d11d8acc2c2e05bdef7da8c92d8900e5fb5a3'


def original_policy(text):
    if text.count(START)!=1 or text.count(END)!=1:raise ValueError('Ambiguous mapping selection guards')
    before,rest=text.split(START)
    if not rest.startswith(SHIM):raise ValueError('Changed stack-context dispatch')
    original,after=rest[len(SHIM):].split(END)
    if after or not original.startswith('__latent_entropy int dup_mmap('):raise ValueError('Wrong mapping boundary')
    restored=before+original
    if hashlib.sha256(restored.encode()).hexdigest()!=PINNED_MMAP_SHA256:raise ValueError('Pinned mmap.c changed outside selection')
    return restored


def check_config(profile,values,target):
    if profile not in PROFILES:raise ValueError('Unknown duplication profile')
    copy.check_config('mm-copy-rust',values,target)
    if values.get(SELECTOR)!=('y' if PROFILES[profile] else 'n'):raise ValueError('Wrong explicit duplication selection')


def compare(c,rust):
    changes={k for k in c.keys()|rust.keys() if c.get(k,'n')!=rust.get(k,'n')}
    if c.get(SELECTOR)!='n' or rust.get(SELECTOR)!='y' or changes!={SELECTOR}:raise ValueError('Only duplication selector may differ')
    for values in (c,rust):
        for option in (copy.SELECTOR,copy.release.SELECTOR,copy.release.mm.SELECTOR,copy.release.task.SELECTOR):
            if values.get(option)!='y':raise ValueError('Inherited Rust policy missing')
    return sorted(changes)


# Literal canonical macro expansion; no synthetic text is passed to ancestor
# checkers. Unknown expansion changes require explicit source/build review.
CONTEXT_BODY=('structlist_headuf={&(uf),&(uf)};'
              'structvma_iteratorvmi={.mas={.tree=&(mm)->mm_mt,.index=0,.node=((void*)0),.status=ma_start,},};'
              'structrusix_dup_mmap_contextctx={.vmi=&vmi,.uf=&uf};'
              'returnrusix_dup_mmap(mm,oldmm,&ctx);')


def check_preprocessed(text,rust):
    bodies=copy.int_bodies(text,'dup_mmap')
    if len(bodies)!=1:raise ValueError('Missing/duplicate public mapping function')
    body=bodies[0]
    if rust:
        if body!=CONTEXT_BODY:raise ValueError('Selected C entry is not exact context-only dispatch')
    else:
        if BRIDGE in body:raise ValueError('C mapping mode dispatches Rust')
        for token in ('mmap_write_lock_killable(oldmm)','flush_cache_dup_mm(oldmm)',
                      'uprobe_dup_mmap(oldmm,mm)','dup_mm_exe_file(mm,oldmm)',
                      '__mt_dup(&oldmm->mm_mt,&mm->mm_mt,','mt_clear_in_rcu(vmi.mas.tree)',
                      'vma_start_write(mpnt)','vma_iter_clear_gfp(','vm_stat_account(',
                      'security_vm_enough_memory_mm(oldmm,len)','vm_area_dup(mpnt)',
                      'vma_dup_policy(mpnt,tmp)','dup_userfaultfd(tmp,&uf)','anon_vma_fork(tmp,mpnt)',
                      'vma_iter_bulk_store(&vmi,tmp)','mm->map_count++','tmp->vm_ops->open(tmp)',
                      'vma_interval_tree_insert_after(','copy_page_range(tmp,mpnt)',
                      'mpnt=vma_next(&vmi);gotoloop_out;','arch_dup_mmap(oldmm,mm)',
                      'vma_iter_free(&vmi)','mt_set_in_rcu(vmi.mas.tree)','mas_store(&vmi.mas,',
                      'dup_userfaultfd_complete(&uf)','dup_userfaultfd_fail(&uf)',
                      'mpol_put(','vm_area_free(tmp)','vm_unacct_memory(charge)'):
            if token not in body:raise ValueError('Missing original duplication operation: '+token)


def definitions(text,public,bridge):
    for name,expected in [('dup_mmap',public),(BRIDGE,bridge)]:
        rows=[r.split() for r in text.splitlines() if r.split() and r.split()[-1]==name]
        if len(rows)!=int(expected) or (rows and (len(rows[0])!=3 or rows[0][1]!='T')):raise ValueError('Wrong mapping definition: '+name)


def check_relocations(text,rust):
    found=False;previous=''
    for row in text.splitlines():
        if 'R_X86_64_' in row and BRIDGE in row:
            if not re.search(r'R_X86_64_PLT32\s+'+BRIDGE+r'(?:-0x4)?\s*$',row) or not re.search(r'\b(?:callq?|jmpq?)\b',previous):raise ValueError('Bridge is not an executable call/jump')
            found=True
        elif re.match(r'^\s*[0-9a-f]+:',row):previous=row
    if found!=rust:raise ValueError('Missing/unexpected Rust mapping call')


def archive_members(text,rust):
    names=[Path(row).name for row in text.splitlines()]
    if names.count('mmap.o')!=1 or names.count('dup_mmap_rust.o')!=int(rust):raise ValueError('Wrong mapping archive selection')
    if any('dup_mmap' in n and n!='dup_mmap_rust.o' for n in names):raise ValueError('Alternate duplication object')


# Canonical pinned x86_64 vm_flags_t constants, independently checked against
# actual object and linked storage; these are not inferred from nm letters.
CONSTANTS = {'rusix_dup_dontcopy': 1 << 17, 'rusix_dup_account': 1 << 20,
             'rusix_dup_wipeonfork': 1 << 25}


def constant_storage(elf, nm, *, linked, expected=CONSTANTS):
    if elf.relocatable == linked:
        raise ValueError('Wrong constant ELF object kind')
    result = {}
    for name, expected_value in expected.items():
        rows = [r.split() for r in nm.splitlines() if r.split() and r.split()[-1] == name]
        # Uppercase ensures global binding. Final .rodata may acquire SHF_WRITE
        # from merged input sections and consequently be reported as D by nm.
        allowed = {'R', 'D'} if linked else {'R'}
        if len(rows) != 1 or len(rows[0]) != 3 or rows[0][1] not in allowed:
            raise ValueError('Missing/ambiguous/non-global canonical constant: '+name)
        symbol = elf.symbol(name)
        index, offset = elf.location(symbol)
        section = elf.headers[index]
        if (symbol['kind'] != 1 or symbol['size'] != 8 or
                int(rows[0][0],16) != symbol['address'] or symbol['address'] % 8 or
                elf.names[index] != '.rodata' or section[1] != 1 or
                not section[2] & 2 or section[2] & 4 or
                (not linked and section[2] & 1) or
                offset < 0 or offset + 8 > section[5]):
            raise ValueError('Wrong canonical constant storage: '+name)
        value = int.from_bytes(elf.section_data(index)[offset:offset+8], 'little')
        if value != expected_value:
            raise ValueError('Wrong canonical constant value: '+name)
        result[name] = value
    return result


def check_constants(object_path, kernel_path, object_symbols, kernel_symbols, *, expected=CONSTANTS):
    obj = constant_storage(elf_reader.Elf(object_path, indexed_sections=True), object_symbols, linked=False, expected=expected)
    linked = constant_storage(elf_reader.Elf(kernel_path, indexed_sections=True), kernel_symbols, linked=True, expected=expected)
    if obj != linked:
        raise ValueError('Object/linked constant values differ')
    return linked


def input_paths(build,source,rust):
    # Ancestor objects/headers/scripts are bound even though their policy does
    # not vary in this pair. Preserve order while deduplicating shared inputs.
    paths=copy.input_paths(build,source,True)+preprocessor.inputs(build,source)+[
        build/'mm/mmap.i',build/'mm/built-in.a',source/'mm/Makefile',
        source/'rusix/scripts/verify-dup-mmap.py',
        source/'rusix/scripts/verify-brd-parameter-owner.py',
        source/'rusix/scripts/measure-kernel-languages.py',
        source/f'rusix/configs/x86_64-mm-dup-mmap-{"rust" if rust else "c"}.config']
    if rust:paths.append(build/'mm/dup_mmap_rust.o')
    return list(dict.fromkeys(paths))


def verify(args):
    source,build,evidence=args.source.resolve(),args.build.resolve(),args.evidence.resolve();rust=PROFILES[args.profile]
    check_config(args.profile,config_values((build/'.config').read_text()),config_values((source/'rusix/configs/x86_64-server.config').read_text()))
    original_policy((source/'mm/mmap.c').read_text())
    paths=input_paths(build,source,rust);before={str(p):digest(p) for p in paths}
    # The inherited copy profile describes its actual Rust selector, not this
    # new public profile name. It rechecks the real fork.i and actual objects.
    inherited=copy.verify(argparse.Namespace(source=source,build=build,evidence=evidence,profile='mm-copy-rust'))
    if inherited['status']!='PASS' or inherited['implementation']!='rust':raise ValueError('Inherited MM copy selection failed')
    (evidence/'dup-mmap-mm-copy-selection.json').write_text(json.dumps(inherited,indent=2,sort_keys=True)+'\n')
    output=build/'mm/mmap.i'
    record=dict(argv=preprocessor.command((build/'mm/.mmap.o.cmd').read_text(),output),cwd=str(build),
                input_sha256={str(p):digest(p) for p in preprocessor.inputs(build,source)},output=str(output),preprocessed_sha256=digest(output))
    if json.loads((evidence/'dup-mmap-preprocess.json').read_text())!=record:raise ValueError('Actual mmap preprocessing provenance changed')
    if (evidence/'dup-mmap-preprocess.exit').read_text().strip()!='0' or re.search('warning:|error:',(evidence/'dup-mmap-preprocess.log').read_text(),re.I):raise ValueError('Mapping preprocessing failure/diagnostic')
    check_preprocessed(output.read_text(),rust)
    def run(name,argv):
        result=subprocess.run(argv,check=True,capture_output=True,text=True)
        if result.stderr:raise ValueError('Object inspection diagnostic: '+result.stderr)
        (evidence/name).write_text(result.stdout);return result.stdout
    archive=build/'mm/built-in.a';members=run('dup-mmap-archive.txt',['llvm-ar','t',str(archive)]);archive_members(members,rust)
    hashes={};symbols={}
    for name in ['mmap']+(['dup_mmap_rust'] if rust else []):
        obj=build/f'mm/{name}.o';member=next(row for row in members.splitlines() if Path(row).name==obj.name)
        hashes[member]=copy.release.task.archive_member_hash(archive,member,obj)
        symbols[name]=run('dup-mmap-'+name+'-symbols.txt',['llvm-nm','--defined-only',str(obj)])
        definitions(symbols[name],name=='mmap',name=='dup_mmap_rust')
    linked=run('dup-mmap-kernel-symbols.txt',['llvm-nm','--defined-only',str(build/'vmlinux')]);definitions(linked,True,rust)
    check_relocations(run('dup-mmap-disassembly.txt',['llvm-objdump','-dr',str(build/'mm/mmap.o')]),rust)
    constants = {}
    if rust:
        helpers=set(re.findall(r'fn (rusix_dup_[a-z_]+)\(', (source/'mm/dup_mmap_rust.rs').read_text()))-{BRIDGE}
        for helper in sorted(helpers):
            for table in (symbols['mmap'],linked):
                rows=[r.split() for r in table.splitlines() if r.split() and r.split()[-1]==helper]
                if len(rows)!=1 or len(rows[0])!=3 or rows[0][1]!='T':raise ValueError('Missing/wrong canonical primitive: '+helper)
        constants = check_constants(build/'mm/mmap.o', build/'vmlinux', symbols['mmap'], linked)
    if before!={str(p):digest(p) for p in paths}:raise ValueError('Verification inputs changed')
    return dict(status='PASS',implementation='rust' if rust else 'c',input_sha256=before,archive_member_sha256=hashes,
                constant_values=constants,mm_copy_selection=inherited,scope='Original C, actual preprocessing and linked selection; no runtime claim')


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='action',required=True)
    p=sub.add_parser('source');p.add_argument('--source',type=Path,required=True)
    p=sub.add_parser('objects');p.add_argument('--profile',choices=PROFILES,required=True)
    for name in ('source','build','evidence'):p.add_argument('--'+name,type=Path,required=True)
    p=sub.add_parser('config');p.add_argument('--profile',choices=PROFILES,required=True);p.add_argument('--config',type=Path,required=True);p.add_argument('--source',type=Path,required=True)
    p=sub.add_parser('compare');p.add_argument('--c',type=Path,required=True);p.add_argument('--rust',type=Path,required=True)
    args=parser.parse_args()
    if args.action=='objects':result=verify(args)
    elif args.action=='source':original_policy((args.source/'mm/mmap.c').read_text());result=dict(status='PASS',scope='Original mmap.c source and shim only')
    elif args.action=='compare':result=compare(config_values(args.c.read_text()),config_values(args.rust.read_text()))
    else:
        check_config(args.profile,config_values(args.config.read_text()),config_values((args.source/'rusix/configs/x86_64-server.config').read_text()));result=dict(status='PASS',scope='Resolved configuration only')
    print(json.dumps(result,indent=2,sort_keys=True))


if __name__=='__main__':main()
