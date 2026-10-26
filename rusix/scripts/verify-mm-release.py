#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Verify MM release selection without weakening historical construction gates."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import importlib.util


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


mm = load('release_constructor', 'verify-mm-construction.py')
task = mm.task
preprocessor = load('release_preprocessor', 'preprocess-mm-release.py')
digest, config_values = task.digest, task.config_values
SELECTOR = 'CONFIG_RUSIX_MM_RELEASE_RUST'
PROFILES = {'mm-release-c': False, 'mm-release-rust': True}
PUBLIC = ('mmput', 'mmput_async', '__mmdrop')
CONSTRUCTION_FORK = '0fd31f0fde1744335d3c745185b99b7e8966a6a3'


def check_config(profile, values, target):
    if profile not in PROFILES: raise ValueError('Unknown MM release profile')
    # Release fixtures deliberately add KUnit to the constructor server derivation.
    # Validate every original constraint with only that explicit axis normalized.
    for name in ('KUNIT','RUSIX_MM_RELEASE_TEST','KUNIT_DEFAULT_ENABLED','KUNIT_AUTORUN_ENABLED'):
        if values.get('CONFIG_'+name) != 'y':raise ValueError('Missing release fixture dependency: '+name)
    mm.check_config('mm-construction-rust', values | {'CONFIG_KUNIT':'n'}, target)
    if values.get(SELECTOR) != ('y' if PROFILES[profile] else 'n'):
        raise ValueError('Missing/wrong explicit release selection')


def compare(c, rust):
    changes = {k for k in c.keys() | rust.keys() if c.get(k,'n') != rust.get(k,'n')}
    if c.get(SELECTOR) != 'n' or rust.get(SELECTOR) != 'y' or changes != {SELECTOR}:
        raise ValueError('Only release selector may differ')
    if any(v.get(mm.SELECTOR) != 'y' or v.get(task.SELECTOR) != 'y' for v in (c,rust)):
        raise ValueError('Both constructors must remain Rust')
    return sorted(changes)


def original_policy(text):
    start = '#ifdef CONFIG_RUSIX_MM_RELEASE_RUST\n#include "mm_release_impl.h"\n#else\n'
    guard = '#ifndef CONFIG_RUSIX_MM_RELEASE_RUST\n'
    end = '#endif /* CONFIG_RUSIX_MM_RELEASE_RUST */\n'
    if text.count(start)!=1 or text.count(guard)!=2 or text.count(end)!=3:
        raise ValueError('Ambiguous release guards')
    restored = text.replace(start,'').replace(guard,'').replace(end,'')
    # The exact constructor snapshot is independently hashed below, then its
    # existing gate reconstructs the pinned original Linux fork.c as before.
    if hashlib.sha256(restored.encode()).hexdigest() != CONSTRUCTION_FORK_SHA256:
        raise ValueError('Release changes extend outside exact selection guards')
    mm.original_policy(restored)
    for name in ('mmput','mmput_async'):
        if restored.count('EXPORT_SYMBOL_GPL('+name+');') != 1:
            raise ValueError('Release export placement changed')
    return restored


def bodies(text, name):
    text=re.sub(r'^#.*$', '', text, flags=re.M)
    text=re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', '""', text)
    result=[]
    for match in re.finditer(r'\bvoid\s+'+re.escape(name)+r'\s*\([^;{}]*\)\s*\{',text):
        start=match.end();depth=1
        for i in range(start,len(text)):
            if text[i]=='{':depth+=1
            elif text[i]=='}':depth-=1
            if depth==0:result.append(re.sub(r'\s+','',text[start:i]));break
        else:raise ValueError('Unterminated function')
    return result


def check_preprocessed(text,rust):
    mm.check_preprocessed(text,True)
    for name in (*PUBLIC,'mmput_async_fn','__mmput'):
        found=bodies(text,name)
        if len(found)!=int(not rust):raise ValueError('Wrong C release body selection: '+name)
    if not rust:
        for name, tokens in {'mmput':('atomic_dec_and_test(', '__mmput(mm)'),
                             'mmput_async':('mmput_async_fn','schedule_work('),
                             '__mmdrop':('mm_free_pgd(mm)','destroy_context(mm)','kmem_cache_free(mm_cachep,(mm))'),
                             '__mmput':('exit_mmap(mm)','futex_hash_free(mm)','mmdrop(mm)')}.items():
            for token in tokens:
                if token not in bodies(text,name)[0]:raise ValueError('Missing C release policy: '+token)


def definitions(text,expected):
    for name in PUBLIC:
        rows=[r.split() for r in text.splitlines() if r.split() and r.split()[-1]==name]
        if len(rows)!=int(name in expected) or (rows and (len(rows[0])!=3 or rows[0][1]!='T')):
            raise ValueError('Wrong global release definition: '+name)


def callback(text,rust):
    rows=[r.split() for r in text.splitlines() if 'mmput_async_fn' in r]
    real=[];prefix=[]
    for row in rows:
        if len(row)!=3:raise ValueError('Malformed callback symbol')
        name=row[2]
        if name.startswith(('__pfx_','__cfi_')):prefix.append(row);continue
        if row[1] not in ('t','T'):raise ValueError('Callback is not code')
        if rust:
            if not re.fullmatch(r'_R[A-Za-z0-9_]+',name):raise ValueError('Unexpected Rust callback symbol')
        elif name!='mmput_async_fn':raise ValueError('Unexpected C callback symbol')
        real.append(row)
    if len(real)!=1:raise ValueError('Missing/duplicate callback definition')
    for row in prefix:
        stem=row[2].removeprefix('__pfx_').removeprefix('__cfi_')
        if stem!=real[0][2] or row[1] not in ('t','T'):raise ValueError('Unbound callback prefix')
    if len({r[2] for r in prefix})!=len(prefix):raise ValueError('Duplicate callback prefix')
    return real[0][2]


def registration(disassembly,callback_name,rust):
    # Require a code relocation that materializes the callback address, not a
    # name in debug data or a direct call of the callback. Rust then transfers
    # the work callback through the canonical work-init adapter.
    blocks=re.split(r'^\s*[0-9a-f]+ <([^>]+)>:\s*$',disassembly,flags=re.M)
    bodies=[blocks[i+1] for i in range(1,len(blocks),2) if blocks[i]=='mmput_async']
    if len(bodies)!=1:raise ValueError('Missing/duplicate mmput_async disassembly')
    disassembly=bodies[0]
    previous='';found=False;init=False
    for row in disassembly.splitlines():
        if 'R_X86_64_' in row:
            if re.search(r'\s'+re.escape(callback_name)+r'(?:-0x4|\+0x[0-9a-f]+)?\s*$',row):
                valid_pc=re.search(r'R_X86_64_PC32\s+'+re.escape(callback_name)+r'-0x4\s*$',row)
                valid_abs=re.search(r'R_X86_64_(?:32S|64)\s+'+re.escape(callback_name)+r'(?:\+0x0)?\s*$',row)
                if not (valid_pc or valid_abs) or not re.search(r'\b(?:lea[q]?|mov[a-z]*)\b',previous):
                    raise ValueError('Callback address lacks executable materialization')
                found=True
            if 'rusix_mm_release_work_init' in row:
                if not re.search(r'R_X86_64_PLT32\s+rusix_mm_release_work_init(?:-0x4)?\s*$',row) or not re.search(r'\b(?:callq?|jmpq?)\b',previous):
                    raise ValueError('Work-init adapter is not an executable call')
                init=True
        elif re.match(r'^\s*[0-9a-f]+:',row):previous=row
    if not found or init!=rust:raise ValueError('Missing callback registration proof')


def archive_members(text,rust):
    mm.archive_members(text,True)
    names=[Path(row).name for row in text.splitlines()]
    if names.count('mm_release_rust.o')!=int(rust):raise ValueError('Wrong release object count')
    if names.count('mm_release_test.o')!=1:raise ValueError('Missing/duplicate release fixture object')
    if any('mm_release' in n and n not in ('mm_release_rust.o','mm_release_test.o') for n in names):raise ValueError('Alternate release object')


def input_paths(build,source,rust):
    paths=preprocessor.inputs(build,source)+[build/'kernel/fork.i',build/'vmlinux',build/'kernel/built-in.a',
        build/'kernel/task_construction_rust.o',build/'kernel/mm_construction_rust.o',build/'kernel/mm_release_test.o',
        source/'kernel/mm_release_test.c',source/'rust/helpers/mm_release_test.c',
        source/'rust/helpers/helpers.c',source/'rust/kernel/mm.rs',source/'rust/kernel/mm/release_tests.rs',
        source/'rusix/scripts/boot-kunit.sh',source/'rusix/scripts/validate-mm-release-kunit.py',
        source/'rusix/scripts/validate-completion-kunit.py',source/'rusix/scripts/validate-brd-kunit.py',
        source/'rusix/configs/x86_64-server.config',source/f'rusix/configs/x86_64-mm-release-{"rust" if rust else "c"}.config',
        source/'rusix/scripts/verify-task-construction.py',source/'rusix/scripts/verify-mm-construction.py',
        source/'rusix/scripts/verify-mm-release.py',source/'kernel/Makefile',source/'init/Kconfig',
        source/'rusix/scripts/build-kernel.sh',source/'rusix/ci/run.sh',source/'rusix/ci/run-container.sh']
    if rust:paths.append(build/'kernel/mm_release_rust.o')
    return paths


def verify(args):
    source,build,evidence=args.source.resolve(),args.build.resolve(),args.evidence.resolve();rust=PROFILES[args.profile]
    check_config(args.profile,config_values((build/'.config').read_text()),config_values((source/'rusix/configs/x86_64-server.config').read_text()))
    original_policy((source/'kernel/fork.c').read_text())
    output=build/'kernel/fork.i';before_pre={str(p):digest(p) for p in preprocessor.inputs(build,source)}
    record=dict(argv=preprocessor.command((build/'kernel/.fork.o.cmd').read_text(),output),cwd=str(build),input_sha256=before_pre,output=str(output),preprocessed_sha256=digest(output))
    if json.loads((evidence/'mm-release-preprocess.json').read_text())!=record:raise ValueError('Preprocessing provenance changed')
    if (evidence/'mm-release-preprocess.exit').read_text().strip()!='0' or re.search('warning:|error:',(evidence/'mm-release-preprocess.log').read_text(),re.I):raise ValueError('Preprocessor diagnostics/failure')
    check_preprocessed(output.read_text(),rust)
    paths=input_paths(build,source,rust);before={str(p):digest(p) for p in paths}
    def run(name,argv):
        result=subprocess.run(argv,check=True,capture_output=True,text=True)
        if result.stderr:raise ValueError('ELF tool diagnostic: '+result.stderr)
        (evidence/name).write_text(result.stdout);return result.stdout
    archive=build/'kernel/built-in.a';members=run('mm-release-archive.txt',['llvm-ar','t',str(archive)]);archive_members(members,rust)
    objects=['fork','task_construction_rust','mm_construction_rust','mm_release_test']+(['mm_release_rust'] if rust else [])
    member_hashes={};symbols={}
    for obj in objects:
        path=build/f'kernel/{obj}.o';member=next(row for row in members.splitlines() if Path(row).name==path.name)
        member_hashes[member]=task.archive_member_hash(archive,member,path)
        symbols[obj]=run(f'mm-release-{obj}-symbols.txt',['llvm-nm','--defined-only',str(path)])
        definitions(symbols[obj],PUBLIC if obj==('mm_release_rust' if rust else 'fork') else ())
        mm.definitions(symbols[obj],mm.MM_SYMBOLS if obj=='mm_construction_rust' else ())
        task.bridge_definition(symbols[obj],obj=='task_construction_rust')
    linked=run('mm-release-kernel-symbols.txt',['llvm-nm','--defined-only',str(build/'vmlinux')])
    definitions(linked,PUBLIC);mm.definitions(linked,mm.MM_SYMBOLS);task.bridge_definition(linked,True)
    owner='mm_release_rust' if rust else 'fork';cb=callback(symbols[owner],rust)
    if callback(linked,rust)!=cb:raise ValueError('Linked callback differs')
    for obj in objects:
        if obj!=owner and 'mmput_async_fn' in symbols[obj]:raise ValueError('Callback in alternate object')
    forkdis=run('mm-release-fork-disassembly.txt',['llvm-objdump','-dr',str(build/'kernel/fork.o')]);mm.check_relocations(forkdis,True)
    dis=run('mm-release-policy-disassembly.txt',['llvm-objdump','-dr',str(build/f'kernel/{owner}.o')])
    registration(dis,cb,rust)
    if rust:
        # Every declared typed primitive is defined once by fork.c and survives
        # into the image; no similarly named object may satisfy a missing ABI.
        helpers=re.findall(r'fn (rusix_mm_[a-z_]+)\(', (source/'kernel/mm_release_rust.rs').read_text())
        for helper in helpers:
            for table in (symbols['fork'],linked):
                rows=[r.split() for r in table.splitlines() if r.split() and r.split()[-1]==helper]
                if len(rows)!=1 or rows[0][1]!='T':raise ValueError('Missing typed primitive: '+helper)
    if before!={str(p):digest(p) for p in paths}:raise ValueError('Inputs changed')
    return dict(status='PASS',implementation='rust' if rust else 'c',input_sha256=before,archive_member_sha256=member_hashes,
                task_implementation='rust',mm_construction_implementation='rust',callback=cb,
                scope='Source, preprocessing and linked selection only; no runtime claim')


def main():
    ap=argparse.ArgumentParser(description=__doc__);sub=ap.add_subparsers(dest='action',required=True)
    p=sub.add_parser('objects');p.add_argument('--profile',choices=PROFILES,required=True)
    for name in ('source','build','evidence'):p.add_argument('--'+name,type=Path,required=True)
    p=sub.add_parser('config');p.add_argument('--profile',choices=PROFILES,required=True);p.add_argument('--config',type=Path,required=True);p.add_argument('--source',type=Path,required=True)
    p=sub.add_parser('compare');p.add_argument('--c',type=Path,required=True);p.add_argument('--rust',type=Path,required=True)
    args=ap.parse_args()
    if args.action=='objects':result=verify(args)
    elif args.action=='compare':result=compare(config_values(args.c.read_text()),config_values(args.rust.read_text()))
    else:
        check_config(args.profile,config_values(args.config.read_text()),config_values((args.source/'rusix/configs/x86_64-server.config').read_text()));result=dict(status='PASS',profile=args.profile)
    print(json.dumps(result,indent=2,sort_keys=True))


CONSTRUCTION_FORK_SHA256 = '0467323b2eb1c750329f2a59eef2763fef392dc1613c4b7d4e588132bd648f28'
if __name__=='__main__':main()
