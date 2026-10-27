#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Actual merge source/compiler/archive/object/linked ownership; no runtime proof."""
import argparse
import json
from pathlib import Path
import re
import shlex
import subprocess
import vma_merge_source as extension
import importlib.util

def load(name, filename):
    spec=importlib.util.spec_from_file_location(name,Path(__file__).with_name(filename))
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod

modify=load('merge_modify','verify-vma-modify.py')
preprocessor=load('merge_pre','preprocess-vma-merge.py')
copy=modify.copy
config_values,digest=modify.config_values,modify.digest
PROFILES,SELECTOR=extension.PROFILES,extension.SELECTOR
WRAPPERS={'vma_merge_existing_range':'rusix_merge_existing',
          'vma_merge_new_range':'rusix_merge_new',
          'vma_merge_copied_range':'rusix_merge_copied',
          'vma_expand':'rusix_merge_expand',
          'vma_shrink':'rusix_merge_shrink',
          'vma_merge_extend':'rusix_merge_extend'}
GLOBAL_NATIVE=('vma_merge_new_range','vma_expand','vma_shrink','vma_merge_extend')
PRIVATE_NATIVE=set(extension.NATIVE)-set(WRAPPERS)
OBLIGATIONS=['vma-merge-rust-direct-prepare-protocol']
# Observed pinned toolchain command shape; only unit identity and output root
# differ from retained teardown ordinary-Rust command SHA256 b6e5b07c7cc5d57a2aea370f8258a2da5dca02f9bca73e6a8941a1fc60c4b199.
RUST_ARGV = ('OBJTREE={build}',
 'RUST_MODFILE=mm/vma_merge_rust',
 'rustc',
 '--edition=2021',
 '-Zbinary_dep_depinfo=y',
 '-Astable_features',
 '-Aunused_features',
 '-Dnon_ascii_idents',
 '-Dunsafe_op_in_unsafe_fn',
 '-Wmissing_docs',
 '-Wrust_2018_idioms',
 '-Wunreachable_pub',
 '-Wclippy::all',
 '-Wclippy::as_ptr_cast_mut',
 '-Wclippy::as_underscore',
 '-Wclippy::cast_lossless',
 '-Aclippy::collapsible_if',
 '-Aclippy::collapsible_match',
 '-Wclippy::ignored_unit_patterns',
 '-Wclippy::mut_mut',
 '-Wclippy::needless_bitwise_bool',
 '-Aclippy::needless_lifetimes',
 '-Wclippy::no_mangle_with_rust_abi',
 '-Wclippy::ptr_as_ptr',
 '-Wclippy::ptr_cast_constness',
 '-Wclippy::ref_as_ptr',
 '-Wclippy::undocumented_unsafe_blocks',
 '-Aclippy::uninlined_format_args',
 '-Wclippy::unnecessary_safety_comment',
 '-Wclippy::unnecessary_safety_doc',
 '-Aclippy::unwrap_or_default',
 '-Wrustdoc::missing_crate_level_docs',
 '-Wrustdoc::unescaped_backticks',
 '-Cpanic=abort',
 '-Cembed-bitcode=n',
 '-Clto=n',
 '-Cforce-unwind-tables=n',
 '-Ccodegen-units=1',
 '-Csymbol-mangling-version=v0',
 '-Crelocation-model=static',
 '-Zfunction-sections=n',
 '-Wclippy::float_arithmetic',
 '--target=./scripts/target.json',
 '-Ctarget-feature=-sse,-sse2,-sse3,-ssse3,-sse4.1,-sse4.2,-avx,-avx2',
 '-Ctarget-cpu=x86-64',
 '-Ztune-cpu=generic',
 '-Cno-redzone=y',
 '-Ccode-model=kernel',
 '-Zfunction-return=thunk-extern',
 '-Zpatchable-function-entry=16,16',
 '-Copt-level=2',
 '-Cdebug-assertions=n',
 '-Coverflow-checks=n',
 '@./include/generated/rustc_cfg',
 '-Zallow-features=asm_const,asm_goto,arbitrary_self_types,lint_reasons,offset_of_nested,raw_ref_op,used_with_arg',
 '-Zcrate-attr=no_std',
 '-Zcrate-attr=feature(asm_const,asm_goto,arbitrary_self_types,lint_reasons,offset_of_nested,raw_ref_op,used_with_arg)',
 '-Zunstable-options',
 '--extern',
 'pin_init',
 '--extern',
 'kernel',
 '--crate-type',
 'rlib',
 '-L',
 './rust/',
 '--crate-name',
 'vma_merge_rust',
 '--sysroot=/dev/null',
 '--out-dir',
 'mm/',
 '--emit=dep-info=mm/.vma_merge_rust.o.d',
 '--emit=obj=mm/vma_merge_rust.o',
 '/src/mm/vma_merge_rust.rs',
 ';',
 './tools/objtool/objtool',
 '--hacks=jump_label',
 '--hacks=noinstr',
 '--hacks=skylake',
 '--orc',
 '--retpoline',
 '--rethunk',
 '--static-call',
 '--uaccess',
 '--prefix=16',
 'mm/vma_merge_rust.o')
RUST_DEPS=('libcore.rmeta','libcompiler_builtins.rmeta','libkernel.rmeta','libffi.rmeta',
           'libpin_init.rmeta','libmacros.so','libpin_init_internal.so','libbuild_error.rmeta',
           'libbindings.rmeta','libuapi.rmeta')
PREP_RUST=('rusix_init_multi_vma_prep','rusix_init_vma_prep','rusix_vma_prepare','rusix_vma_complete')
EXTEND=('structvma_merge_structvmg={.mm=vma->vm_mm,.vmi=vmi,.prev=vma,.middle=vma,'
        '.next=((void*)0),.start=vma->vm_end,.end=vma->vm_end+delta,.vm_flags=vma->vm_flags,'
        '.pgoff=vma_pgoff_offset(vma,vma->vm_end),.file=vma->vm_file,.anon_vma=vma->anon_vma,'
        '.policy=((void*)0),.uffd_ctx=vma->vm_userfaultfd_ctx,.anon_name=anon_vma_name(vma),'
        '.state=VMA_MERGE_START,};')

def bodies(text,name):
    # Declaration-anchored, including private bool policies; never a call site.
    text=re.sub(r'^#.*$', '', text,flags=re.M)
    text=re.sub(r'/\*.*?\*/|//[^\n]*','',text,flags=re.S)
    pattern=(r'^\s*(?:static\s+)?(?:inline\s+)?(?:__must_check\s+)?'
             r'(?:struct\s+\w+\s*\*|unsigned\s+long|vm_flags_t|pgoff_t|bool|void|int)\s*'
             +re.escape(name)+r'\s*\([^;{}]*\)\s*\{')
    result=[]
    for match in re.finditer(pattern,text,re.M):
        start=pos=match.end();depth=1
        while pos<len(text) and depth:
            depth+=(text[pos]=='{')-(text[pos]=='}');pos+=1
        if depth:raise ValueError('Unterminated definition: '+name)
        result.append(re.sub(r'\s+','',text[start:pos-1]))
    return result

def check_config(profile,values,target):
    extension.check_config(profile,values,target,source_context=extension.ID)

def compare(c,rust,target):
    return extension.compare(c,rust,target,source_context=extension.ID)

def check_preprocessed(text,rust,header):
    if rust:
        for name,callee in WRAPPERS.items():
            args='vmg,&prep'
            prefix=''
            if name=='vma_merge_extend':prefix=EXTEND;args='&vmg,&prep'
            if name=='vma_shrink':args='vmi,vma,start,end,pgoff,&prep'
            expected=prefix+'structvma_prepareprep;return'+callee+'('+args+');'
            if bodies(text,name)!=[expected]:raise ValueError('Changed native merge stack wrapper: '+name)
        for name in PRIVATE_NATIVE|set(extension.PREP):
            if bodies(text,name):raise ValueError('Native merge/prepare policy still selected: '+name)
        for name in extension.PRIMITIVES:
            if len(bodies(text,name))!=1:raise ValueError('Missing/duplicate actual merge primitive: '+name)
        actual=modify.compact(text)
        for declaration in modify.compact(header).split(';'):
            if declaration and declaration+';' not in actual:raise ValueError('Changed canonical merge ABI')
        enum='enumvma_merge_state{VMA_MERGE_START,VMA_MERGE_ERROR_NOMEM,VMA_MERGE_NOMERGE,VMA_MERGE_SUCCESS,};'
        if enum not in actual:raise ValueError('Changed merge state enum')
    else:
        for name in (*extension.NATIVE,*extension.PREP):
            if len(bodies(text,name))!=1:raise ValueError('Missing original merge/prepare policy: '+name)
        if any(bodies(text,name) for name in extension.PRIMITIVES):raise ValueError('Merge primitive in C comparison')
        for name in extension.CONSTANTS:
            if re.search(r'\b'+name+r'\s*=',text):raise ValueError('Merge constant in C comparison')

def definitions(table,owned):
    for name in (*GLOBAL_NATIVE,*extension.ENTRIES,*extension.PRIMITIVES):
        rows=[r.split() for r in table.splitlines() if r.split() and r.split()[-1]==name]
        if len(rows)!=int(name in owned) or (rows and (len(rows[0])!=3 or rows[0][1]!='T')):
            raise ValueError('Wrong global executable merge owner: '+name)

def archive_members(text,rust):
    names=[Path(n).name for n in text.splitlines()]
    if names.count('vma.o')!=1 or names.count('vma_merge_rust.o')!=int(rust):raise ValueError('Wrong merge archive members')
    if any('vma_merge' in n and n!='vma_merge_rust.o' for n in names):raise ValueError('Alternate merge object')

def require_obligations(proof,rust):
    if (proof.get('status')!='PASS' or proof.get('implementation')!='rust' or
        proof.get('source_context')!=extension.ID or proof.get('outer_obligations')!=(OBLIGATIONS if rust else []) or
        proof.get('consumed_outer_obligations')!=['vma-modify-rust-prepare-lock-before-file-link']):
        raise ValueError('Missing/unknown/incorrect parent proof obligations')

def rust_command(text):
    # Retain the actual saved command, never execute it. Exact source/output and
    # crate identity tie private inlined policies to the reviewed Rust unit.
    key='savedcmd_mm/vma_merge_rust.o := '
    lines=[line[len(key):] for line in text.splitlines() if line.startswith(key)]
    sources=[line for line in text.splitlines() if line.startswith('source_mm/vma_merge_rust.o := ')]
    if len(lines)!=1 or sources!=['source_mm/vma_merge_rust.o := /src/mm/vma_merge_rust.rs']:
        raise ValueError('Wrong actual Rust source command record')
    argv=shlex.split(lines[0])
    if argv.count('/src/mm/vma_merge_rust.rs')!=1 or argv.count('rustc')!=1:
        raise ValueError('Missing/duplicate Rust compiler/source')
    for flag,value in [('--crate-name','vma_merge_rust'),('--out-dir','mm/')]:
        if argv.count(flag)!=1 or argv[argv.index(flag)+1:argv.index(flag)+2]!=[value]:raise ValueError('Wrong Rust unit/output')
    emits=[token for token in argv if token.startswith('--emit=')]
    if emits != ['--emit=dep-info=mm/.vma_merge_rust.o.d','--emit=obj=mm/vma_merge_rust.o']:
        raise ValueError('Wrong actual Rust emissions')
    if argv.count(';')!=1 or argv[argv.index(';')+1:] != ['./tools/objtool/objtool','--hacks=jump_label','--hacks=noinstr','--hacks=skylake','--orc','--retpoline','--rethunk','--static-call','--uaccess','--prefix=16','mm/vma_merge_rust.o']:
        raise ValueError('Wrong saved Rust postpass')
    roots=[token[len('OBJTREE='):] for token in argv if token.startswith('OBJTREE=')]
    if len(roots)!=1 or not roots[0].startswith('/out/builds/') or 'RUST_MODFILE=mm/vma_merge_rust' not in argv:
        raise ValueError('Wrong Rust output/module context')
    if argv != [token.replace('{build}',roots[0]) for token in RUST_ARGV]:
        raise ValueError('Changed reviewed Rust compiler flags/inputs/postpass')
    deps=re.findall(r'^deps_mm/vma_merge_rust.o := (.*?)(?=\n\n)',text,re.M|re.S)
    if len(deps)!=1 or deps[0].replace('\\','').split()!=[roots[0]+'/rust/'+name for name in RUST_DEPS]:
        raise ValueError('Wrong actual Rust binary dependency closure')
    return argv

def constant_storage(elf,table,values,*,linked):
    if elf.relocatable==linked:raise ValueError('Wrong constant ELF kind')
    sticky=0x800 | (0x08000000 if values.get('CONFIG_MEM_SOFT_DIRTY')=='y' else 0)
    expected=dict(zip(extension.CONSTANTS,(sticky,0x10044400,sticky,2,3,1)))
    result={}
    for index,(name,value) in enumerate(expected.items()):
        size=8 if index<3 else 4
        rows=[r.split() for r in table.splitlines() if r.split() and r.split()[-1]==name]
        if len(rows)!=1 or len(rows[0])!=3 or rows[0][1] not in ({'R','D'} if linked else {'R'}):raise ValueError('Wrong merge constant binding')
        sym=elf.symbol(name);section,offset=elf.location(sym);sec=elf.headers[section]
        if (sym['kind']!=1 or sym['size']!=size or sym['address']%size or int(rows[0][0],16)!=sym['address'] or
            elf.names[section]!='.rodata' or sec[1]!=1 or not sec[2]&2 or sec[2]&4 or (not linked and sec[2]&1) or
            offset<0 or offset+size>sec[5]):raise ValueError('Wrong canonical constant storage')
        actual=int.from_bytes(elf.section_data(section)[offset:offset+size],'little')
        if actual!=value:raise ValueError('Wrong canonical merge constant value')
        result[name]=actual
    return result

def input_paths(build,source,rust):
    paths=modify.input_paths(build,source,True,source_context=extension.ID)+preprocessor.inputs(build,source)
    paths+=[source/f'rusix/configs/x86_64-vma-merge-{"rust" if rust else "c"}.config']
    if rust:
        paths += [build/'mm/vma_merge_rust.o',build/'mm/.vma_merge_rust.o.cmd',build/'scripts/target.json',build/'include/generated/rustc_cfg']
        paths += [build/'rust'/name for name in RUST_DEPS]
    return list(dict.fromkeys(paths))

def verify(args):
    source,build,evidence=args.source.resolve(),args.build.resolve(),args.evidence.resolve()
    rust=PROFILES[args.profile];values=config_values((build/'.config').read_text())
    check_config(args.profile,values,config_values((source/'rusix/configs/x86_64-server.config').read_text()))
    source_proof=extension.source_policy(source,source_context=extension.ID)
    paths=input_paths(build,source,rust);before={str(p):digest(p) for p in paths}
    inherited=modify.verify(argparse.Namespace(source=source,build=build,evidence=evidence,profile='vma-modify-rust'),source_context=extension.ID)
    require_obligations(inherited,rust)
    (evidence/'vma-merge-modify-selection.json').write_text(json.dumps(inherited,indent=2,sort_keys=True)+'\n')
    check_preprocessed((build/'mm/vma.i').read_text(),rust,(source/'mm/vma_merge.h').read_text())
    command=rust_command((build/'mm/.vma_merge_rust.o.cmd').read_text()) if rust else None
    def run(name,argv):
        result=subprocess.run(argv,check=True,capture_output=True,text=True)
        if result.stderr:raise ValueError('Object inspection diagnostics: '+result.stderr)
        (evidence/name).write_text(result.stdout);return result.stdout
    archive=build/'mm/built-in.a';members=run('vma-merge-archive.txt',['llvm-ar','t',str(archive)])
    archive_members(members,rust)
    expected={'vma':set(GLOBAL_NATIVE)|(set(extension.PRIMITIVES) if rust else set()),
              'linked':set(GLOBAL_NATIVE)|(set(extension.PRIMITIVES)|set(extension.ENTRIES) if rust else set())}
    if rust:expected['vma_merge_rust']=set(extension.ENTRIES)
    payloads={};dis={};tables={};constants={}
    for label,owned in expected.items():
        obj=build/'vmlinux' if label=='linked' else build/f'mm/{label}.o'
        if label!='linked':
            member=next(n for n in members.splitlines() if Path(n).name==obj.name)
            payloads[member]=copy.exit.vma.dup.copy.release.task.archive_member_hash(archive,member,obj)
            dis[label]=run('vma-merge-'+label+'-disassembly.txt',['llvm-objdump','-dr',str(obj)])
        table=run('vma-merge-'+label+'-symbols.txt',['llvm-nm','--defined-only',str(obj)]);tables[label]=table
        definitions(table,owned)
        metadata=json.loads(run('vma-merge-'+label+'-elf.json',['llvm-readobj','--elf-output-style=JSON','--sections','--symbols',str(obj)]))
        for symbol in owned:copy.exit.vma.function_location(metadata,symbol,False)
        if not rust and any(re.search(r'\b'+n+r'$',table,re.M) for n in extension.CONSTANTS):raise ValueError('Merge constant selected in C ELF')
    if rust:
        # Two private native wrappers may inline; their exact .i stack bodies
        # and executable calls in the defining C unit remain required.
        for name in extension.ENTRIES:copy.exit.executable_calls(dis['vma'],name)
        for native in GLOBAL_NATIVE:copy.exit.vma.call_from(dis['vma'],native,WRAPPERS[native])
        for name in (*extension.PRIMITIVES,*extension.REUSED):copy.exit.executable_calls(dis['vma_merge_rust'],name)
        for name in PREP_RUST:copy.exit.executable_calls(dis['vma_merge_rust'],name)
        elf=copy.exit.vma.dup.elf_reader.Elf
        constants=constant_storage(elf(build/'mm/vma.o',indexed_sections=True),tables['vma'],values,linked=False)
        if constant_storage(elf(build/'vmlinux',indexed_sections=True),tables['linked'],values,linked=True)!=constants:raise ValueError('Linked constants differ')
    copy.exit_mmap_source.require_unchanged(paths,before)
    return dict(status='PASS',implementation='rust' if rust else 'c',source_context=extension.ID,
                source=source_proof,input_sha256=before,archive_member_sha256=payloads,constant_values=constants,
                actual_rust_command=command,policy_inventory=list(extension.NATIVE),
                consumed_outer_obligations=OBLIGATIONS if rust else [],modify_selection=inherited,
                private_policy_provenance='Exact reviewed Rust source and saved source/object command; private policies may inline into six selected exports',
                scope='Actual preprocessing/archive/object/linked ownership only; no runtime or complete compatibility proof')

def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='action',required=True)
    for action in ('source','config','objects','compare'):
        item=sub.add_parser(action);item.add_argument('--source',type=Path,required=True)
        if action in ('config','objects'):item.add_argument('--profile',choices=PROFILES,required=True)
        if action=='config':item.add_argument('--config',type=Path,required=True)
        if action=='objects':
            for name in ('build','evidence'):item.add_argument('--'+name,type=Path,required=True)
        if action=='compare':item.add_argument('--c',type=Path,required=True);item.add_argument('--rust',type=Path,required=True)
    args=parser.parse_args();target=lambda:config_values((args.source/'rusix/configs/x86_64-server.config').read_text())
    if args.action=='source':result=extension.source_policy(args.source,source_context=extension.ID)
    elif args.action=='config':check_config(args.profile,config_values(args.config.read_text()),target());result={'status':'PASS','scope':'configuration only'}
    elif args.action=='compare':result=compare(config_values(args.c.read_text()),config_values(args.rust.read_text()),target())
    else:result=verify(args)
    print(json.dumps(result,indent=2,sort_keys=True))
if __name__=='__main__':main()
