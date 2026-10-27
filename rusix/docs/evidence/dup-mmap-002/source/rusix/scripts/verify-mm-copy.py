#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Bind MM-copy source, actual compiled dispatch and linked implementation."""
import argparse
import importlib.util
import json
import re
import subprocess
from pathlib import Path


spec = importlib.util.spec_from_file_location(
    'copy_release', Path(__file__).with_name('verify-mm-release.py'))
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)
SELECTOR = 'CONFIG_RUSIX_MM_COPY_RUST'
PROFILES = {'mm-copy-c': False, 'mm-copy-rust': True}
START = '#ifdef CONFIG_RUSIX_MM_COPY_RUST\n#include "mm_copy_impl.h"\n'
SHIM = ('extern int rusix_copy_mm(u64 clone_flags, struct task_struct *tsk);\n\n'
        'static int copy_mm(u64 clone_flags, struct task_struct *tsk)\n'
        '{\n\treturn rusix_copy_mm(clone_flags, tsk);\n}\n#else\n')
END = '#endif /* CONFIG_RUSIX_MM_COPY_RUST */\n\n'

INIT_SHIM = 'static struct mm_struct *mm_init(struct mm_struct *mm, struct task_struct *p,\n\t\t\t\tstruct user_namespace *user_ns)\n{\n\treturn rusix_mm_init(mm, p, user_ns);\n}\n'
INIT_GUARDED = '#ifndef CONFIG_RUSIX_MM_COPY_RUST\nstatic struct mm_struct *mm_init(struct mm_struct *mm, struct task_struct *p,\n\t\t\t\tstruct user_namespace *user_ns)\n{\n\treturn rusix_mm_init(mm, p, user_ns);\n}\n#endif /* !CONFIG_RUSIX_MM_COPY_RUST */\n'


def original_policy(text):
    """Strip only the reviewed dispatch; ancestors prove every original C byte."""
    if text.count(START) != 1 or text.count(END) != 1:
        raise ValueError('Missing or ambiguous MM-copy selection')
    before, rest = text.split(START)
    if not rest.startswith(SHIM):
        raise ValueError('Unexpected MM-copy dispatch body')
    original, after = rest[len(SHIM):].split(END)
    if not original.startswith('static struct mm_struct *dup_mm('):
        raise ValueError('Wrong duplication boundary')
    if not after.startswith('static int copy_fs('):
        raise ValueError('Wrong MM-copy endpoint')
    restored = before + original + after
    if restored.count(INIT_GUARDED)!=1 or restored.count('#ifndef CONFIG_RUSIX_MM_COPY_RUST\n')!=1:
        raise ValueError('Missing/ambiguous guarded initializer wrapper')
    restored=restored.replace(INIT_GUARDED,INIT_SHIM)
    release.original_policy(restored)
    return restored


def check_config(profile, values, target):
    if profile not in PROFILES:
        raise ValueError('Unknown MM-copy profile')
    # Ordinary userspace profiles inherit construction constraints. The release
    # KUnit profile has a different purpose and is not normalized into this one.
    release.mm.check_config('mm-construction-rust', values, target)
    if values.get(release.SELECTOR) != 'y':
        raise ValueError('MM copy requires Rust MM release on both sides')
    if values.get('CONFIG_RUSIX_MM_RELEASE_TEST', 'n') != 'n':
        raise ValueError('Ordinary MM-copy profile must not enable release fixtures')
    if values.get(SELECTOR) != ('y' if PROFILES[profile] else 'n'):
        raise ValueError('Missing or wrong explicit MM-copy selection')


def compare(c, rust):
    changes = {key for key in c.keys() | rust.keys()
               if c.get(key, 'n') != rust.get(key, 'n')}
    if c.get(SELECTOR) != 'n' or rust.get(SELECTOR) != 'y' or changes != {SELECTOR}:
        raise ValueError('Only MM-copy selection may differ')
    for values in (c, rust):
        for dependency in (release.SELECTOR, release.mm.SELECTOR, release.task.SELECTOR):
            if values.get(dependency) != 'y':
                raise ValueError('Both sides require Rust task/MM construction and MM release')
    return sorted(changes)


def load(name, filename):
    spec=importlib.util.spec_from_file_location(name,Path(__file__).with_name(filename))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


preprocessor=load('copy_preprocessor','preprocess-mm-copy.py')
digest, config_values=release.digest,release.config_values
BRIDGE='rusix_copy_mm'


def int_bodies(text,name):
    # Reuse only lexical extraction, not historical constructor assumptions.
    # copy_mm returns int, whereas its ancestor's parser handles mm* returns.
    text=re.sub(r'^#.*$','',text,flags=re.M)
    text=re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'','""',text)
    result=[]
    for match in re.finditer(r'\bint\s+'+re.escape(name)+r'\s*\([^;{}]*\)\s*\{',text):
        start=match.end();depth=1
        for i in range(start,len(text)):
            if text[i]=='{':depth+=1
            elif text[i]=='}':depth-=1
            if not depth:result.append(re.sub(r'\s+','',text[start:i]));break
        else:raise ValueError('Unterminated copy body')
    return result


def check_preprocessed(text,rust):
    release.task.check_preprocessed(text,True)
    # Explicit new scope: C dup_mm is absent in Rust-copy mode, so calling the
    # historical MM constructor checker would incorrectly require it to exist.
    mm=release.mm
    expected_init=[] if rust else ['returnrusix_mm_init(mm,p,user_ns);']
    if mm.function_bodies(text,'mm_init')!=expected_init:
        raise ValueError('Unexpected/missing C initializer wrapper')
    if mm.function_bodies(text,'mm_alloc'):
        raise ValueError('C allocation policy remains selected')
    for name in (*release.PUBLIC,'mmput_async_fn','__mmput'):
        if release.bodies(text,name):raise ValueError('C release policy remains selected: '+name)
    copied=int_bodies(text,'copy_mm');dup=mm.function_bodies(text,'dup_mm')
    if rust:
        if copied!=['returnrusix_copy_mm(clone_flags,tsk);'] or dup:
            raise ValueError('Wrong Rust copy dispatch or retained C duplication')
    else:
        if len(copied)!=1 or len(dup)!=1 or BRIDGE in copied[0]+dup[0]:
            raise ValueError('Missing/ambiguous C copying policy')
        for token in ('mm_init(mm,tsk,mm->user_ns)','uprobe_start_dup_mmap()',
                      'dup_mmap(mm,oldmm)','uprobe_end_dup_mmap()',
                      'try_module_get(mm->binfmt->module)','mm->binfmt=NULL',
                      'mm_init_owner(mm,NULL)','mmput(mm)','if(err)uprobe_end_dup_mmap()'):
            # NULL expands to ((void *)0) in the real C preprocessor.
            token=token.replace('NULL','((void*)0)')
            if token not in dup[0]:raise ValueError('Missing C duplication operation: '+token)
        for token in ('mmget(oldmm)','dup_mm(tsk,','tsk->mm=mm','tsk->active_mm=mm','sched_mm_cid_fork(tsk)'):
            if token not in copied[0]:raise ValueError('Missing C copying operation: '+token)


def bridge_definition(text,expected):
    rows=[row.split() for row in text.splitlines() if row.split() and row.split()[-1]==BRIDGE]
    if len(rows)!=int(expected) or (rows and (len(rows[0])!=3 or rows[0][1]!='T')):
        raise ValueError('Missing/duplicate/wrong global copying bridge')


def check_relocations(text,rust):
    # Task construction remains in fork.o. The MM-init call moves from C
    # dup_mm to mm_copy_rust.o when copying itself becomes Rust.
    release.mm.check_relocations(text,not rust)
    previous='';found=False
    for row in text.splitlines():
        if 'R_X86_64_' in row and BRIDGE in row:
            if not re.search(r'R_X86_64_PLT32\s+'+BRIDGE+r'(?:-0x4)?\s*$',row) or not re.search(r'\b(?:callq?|jmpq?)\b',previous):
                raise ValueError('Copy bridge is not an executable call/jump')
            found=True
        elif re.match(r'^\s*[0-9a-f]+:',row):previous=row
    if found!=rust:raise ValueError('Missing/unexpected copying relocation')


def archive_members(text,rust):
    release.mm.archive_members(text,True)
    names=[Path(row).name for row in text.splitlines()]
    for name,count in [('mm_release_rust.o',1),('mm_release_test.o',0),('mm_copy_rust.o',int(rust))]:
        if names.count(name)!=count:raise ValueError('Wrong object count: '+name)
    if any(('mm_copy' in name and name!='mm_copy_rust.o') or
           ('mm_release' in name and name!='mm_release_rust.o') for name in names):
        raise ValueError('Alternate copying/release object')


def input_paths(build,source,rust):
    paths=preprocessor.inputs(build,source)+[build/'kernel/fork.i',build/'vmlinux',
        build/'kernel/built-in.a',build/'kernel/task_construction_rust.o',
        build/'kernel/mm_construction_rust.o',build/'kernel/mm_release_rust.o',
        source/'rusix/configs/x86_64-server.config',source/f'rusix/configs/x86_64-mm-copy-{"rust" if rust else "c"}.config',
        source/'rusix/scripts/verify-task-construction.py',source/'rusix/scripts/verify-mm-construction.py',
        source/'rusix/scripts/verify-mm-release.py',source/'rusix/scripts/verify-mm-copy.py',
        source/'kernel/Makefile',source/'init/Kconfig',source/'rusix/scripts/build-kernel.sh',
        source/'rusix/ci/run.sh',source/'rusix/ci/run-container.sh']
    if rust:paths.append(build/'kernel/mm_copy_rust.o')
    return paths


def verify(args):
    source,build,evidence=args.source.resolve(),args.build.resolve(),args.evidence.resolve();rust=PROFILES[args.profile]
    check_config(args.profile,config_values((build/'.config').read_text()),config_values((source/'rusix/configs/x86_64-server.config').read_text()))
    original_policy((source/'kernel/fork.c').read_text())
    output=build/'kernel/fork.i'
    record=dict(argv=preprocessor.command((build/'kernel/.fork.o.cmd').read_text(),output),cwd=str(build),
                input_sha256={str(p):digest(p) for p in preprocessor.inputs(build,source)},
                output=str(output),preprocessed_sha256=digest(output))
    if json.loads((evidence/'mm-copy-preprocess.json').read_text())!=record:raise ValueError('Actual preprocessor command/inputs changed')
    if (evidence/'mm-copy-preprocess.exit').read_text().strip()!='0' or re.search('warning:|error:',(evidence/'mm-copy-preprocess.log').read_text(),re.I):raise ValueError('Preprocessing failure/diagnostics')
    check_preprocessed(output.read_text(),rust)
    paths=input_paths(build,source,rust);before={str(p):digest(p) for p in paths}
    def run(name,argv):
        result=subprocess.run(argv,check=True,capture_output=True,text=True)
        if result.stderr:raise ValueError('Object inspection diagnostics: '+result.stderr)
        (evidence/name).write_text(result.stdout);return result.stdout
    archive=build/'kernel/built-in.a';members=run('mm-copy-archive.txt',['llvm-ar','t',str(archive)])
    archive_members(members,rust)
    names=['fork','task_construction_rust','mm_construction_rust','mm_release_rust']+(['mm_copy_rust'] if rust else [])
    symbols={};member_hashes={}
    for name in names:
        obj=build/f'kernel/{name}.o';member=next(row for row in members.splitlines() if Path(row).name==obj.name)
        member_hashes[member]=release.task.archive_member_hash(archive,member,obj)
        symbols[name]=run(f'mm-copy-{name}-symbols.txt',['llvm-nm','--defined-only',str(obj)])
        bridge_definition(symbols[name],name=='mm_copy_rust')
        release.task.bridge_definition(symbols[name],name=='task_construction_rust')
        release.mm.definitions(symbols[name],release.mm.MM_SYMBOLS if name=='mm_construction_rust' else ())
        release.definitions(symbols[name],release.PUBLIC if name=='mm_release_rust' else ())
    linked=run('mm-copy-kernel-symbols.txt',['llvm-nm','--defined-only',str(build/'vmlinux')])
    bridge_definition(linked,rust);release.task.bridge_definition(linked,True)
    release.mm.definitions(linked,release.mm.MM_SYMBOLS);release.definitions(linked,release.PUBLIC)
    cb=release.callback(symbols['mm_release_rust'],True)
    if release.callback(linked,True)!=cb:raise ValueError('Release callback ownership changed')
    for name in names:
        if name!='mm_release_rust' and 'mmput_async_fn' in symbols[name]:raise ValueError('Release callback in alternate object')
    release_metadata=json.loads(run('mm-copy-release-elf.json',['llvm-readobj','--elf-output-style=JSON','--sections','--symbols',str(build/'kernel/mm_release_rust.o')]))
    release.registration(run('mm-copy-release-disassembly.txt',['llvm-objdump','-dr',str(build/'kernel/mm_release_rust.o')]),cb,True,release_metadata)
    check_relocations(run('mm-copy-fork-disassembly.txt',['llvm-objdump','-dr',str(build/'kernel/fork.o')]),rust)
    if rust:
        policy=run('mm-copy-policy-disassembly.txt',['llvm-objdump','-dr',str(build/'kernel/mm_copy_rust.o')])
        previous='';found=False
        for row in policy.splitlines():
            if 'R_X86_64_' in row and 'rusix_mm_init' in row:
                if not re.search(r'R_X86_64_PLT32\s+rusix_mm_init(?:-0x4)?\s*$',row) or not re.search(r'\b(?:callq?|jmpq?)\b',previous):
                    raise ValueError('Rust copying does not call MM initialization with executable relocation')
                found=True
            elif re.match(r'^\s*[0-9a-f]+:',row):previous=row
        if not found:raise ValueError('Missing Rust copying call to MM initializer')
    # Canonical typed helpers remain fork.o definitions; inherited constructors
    # and release Rust objects must not acquire alternative copies of their ABI.
    helpers=set(re.findall(r'fn (rusix_mm_[a-z_]+)\(', (source/'kernel/mm_release_rust.rs').read_text()))
    if rust:helpers.update(re.findall(r'fn (rusix_mm_[a-z_]+)\(', (source/'kernel/mm_copy_rust.rs').read_text()))
    helpers.discard('rusix_mm_init') # Rust constructor public definition checked above.
    for helper in sorted(helpers):
        for table in (symbols['fork'],linked):
            rows=[row.split() for row in table.splitlines() if row.split() and row.split()[-1]==helper]
            if len(rows)!=1 or len(rows[0])!=3 or rows[0][1]!='T':raise ValueError('Missing typed primitive: '+helper)
    if before!={str(p):digest(p) for p in paths}:raise ValueError('Verification inputs changed')
    return dict(status='PASS',implementation='rust' if rust else 'c',input_sha256=before,
                archive_member_sha256=member_hashes,task_implementation='rust',mm_construction_implementation='rust',
                mm_release_implementation='rust',release_callback=cb,
                scope='Original source, actual preprocessing, archive/object/linked selection; no runtime claim')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    p = sub.add_parser('objects')
    p.add_argument('--profile', choices=PROFILES, required=True)
    for name in ('source','build','evidence'):
        p.add_argument('--'+name,type=Path,required=True)
    p = sub.add_parser('source')
    p.add_argument('--source', type=Path, required=True)
    p = sub.add_parser('config')
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--config', type=Path, required=True)
    p.add_argument('--profile', choices=PROFILES, required=True)
    p = sub.add_parser('compare')
    p.add_argument('--c', type=Path, required=True)
    p.add_argument('--rust', type=Path, required=True)
    args = parser.parse_args()
    if args.action == 'objects':
        result=verify(args)
    elif args.action == 'source':
        original_policy((args.source/'kernel/fork.c').read_text())
        result = {'status': 'PASS', 'scope': 'Original C and dispatch source only'}
    elif args.action == 'config':
        check_config(args.profile, release.config_values(args.config.read_text()),
                     release.config_values((args.source/'rusix/configs/x86_64-server.config').read_text()))
        result = {'status': 'PASS', 'scope': 'Resolved configuration only'}
    else:
        result = compare(release.config_values(args.c.read_text()),
                         release.config_values(args.rust.read_text()))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
