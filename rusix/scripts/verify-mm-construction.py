#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Bind shared MM construction to preserved C, actual preprocessing and linked objects."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


task = load('mm_task_selection', 'verify-task-construction.py')
preprocessor = load('mm_preprocess', 'preprocess-mm-construction.py')
digest, config_values = task.digest, task.config_values
PROFILES = {'mm-construction-c': False, 'mm-construction-rust': True}
SELECTOR = 'CONFIG_RUSIX_MM_CONSTRUCTION_RUST'
MM_SYMBOLS = ('mm_alloc', 'rusix_mm_init')
EXCLUDED = ('MEMCG', 'MM_ID', 'SCHED_MM_CID', 'LRU_GEN', 'TRANSPARENT_HUGEPAGE',
            'HUGETLB_PAGE', 'MODIFY_LDT_SYSCALL', 'X86_INTEL_MEMORY_PROTECTION_KEYS', 'PARAVIRT')


def check_config(profile, values, target):
    if profile not in PROFILES: raise ValueError('Unknown MM constructor profile')
    task.check_config('task-construction-rust', values, target)
    if values.get(SELECTOR) != ('y' if PROFILES[profile] else 'n'):
        raise ValueError('Missing/wrong explicit MM selection')
    if values.get('CONFIG_MMU') != 'y': raise ValueError('MMU required')
    for name in EXCLUDED:
        if values.get('CONFIG_'+name, 'n') != 'n': raise ValueError('Unsupported MM lifecycle: '+name)


def compare(c, rust):
    changes = {k for k in c.keys() | rust.keys() if c.get(k,'n') != rust.get(k,'n')}
    if c.get(SELECTOR) != 'n' or rust.get(SELECTOR) != 'y' or changes != {SELECTOR}:
        raise ValueError('Expected only MM constructor selection to differ')
    if c.get(task.SELECTOR) != 'y' or rust.get(task.SELECTOR) != 'y':
        raise ValueError('Both MM profiles must retain Rust task construction')
    return sorted(changes)


def original_policy(text):
    start = '#ifdef CONFIG_RUSIX_MM_CONSTRUCTION_RUST\n#include "mm_construction_impl.h"\n'
    middle = '#else\nstatic struct mm_struct *mm_init('
    end = '#endif /* CONFIG_RUSIX_MM_CONSTRUCTION_RUST */\n'
    if text.count(start) != 1 or text.count(middle) != 1 or text.count(end) != 2:
        raise ValueError('Ambiguous MM initializer selection')
    before, rest = text.split(start)
    shim, rest = rest.split(middle)
    original, rest = rest.split(end, 1)
    expected = ('extern struct mm_struct *rusix_mm_init(struct mm_struct *mm, struct task_struct *p,\n'
                '\t\t\t\t     struct user_namespace *user_ns);\n\n'
                'static struct mm_struct *mm_init(struct mm_struct *mm, struct task_struct *p,\n'
                '\t\t\t\tstruct user_namespace *user_ns)\n'
                '{\n\treturn rusix_mm_init(mm, p, user_ns);\n}\n')
    if shim != expected: raise ValueError('Unexpected MM C dispatch body')
    text = before+'static struct mm_struct *mm_init('+original+rest
    start = '#ifndef CONFIG_RUSIX_MM_CONSTRUCTION_RUST\n'
    if text.count(start) != 1 or text.count(end) != 1: raise ValueError('Ambiguous public MM allocation selection')
    text = text.replace(start,'').replace(end,'')
    # This still contains the task insertion. Its checker removes only that
    # exact insertion, then hashes the entire pinned baseline fork.c.
    task.original_policy(text)
    if text.count('EXPORT_SYMBOL_IF_KUNIT(mm_alloc);') != 1: raise ValueError('MM export changed')


def function_bodies(text, name):
    text = re.sub(r'^#.*$', '', text, flags=re.M)
    text = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', '""', text)
    pattern = r'\b(?:static\s+)?struct\s+mm_struct\s*\*\s*'+re.escape(name)+r'\s*\([^;{}]*\)\s*\{'
    values = []
    for match in re.finditer(pattern,text):
        start, depth = match.end(), 1
        for i in range(start,len(text)):
            if text[i] == '{': depth += 1
            elif text[i] == '}': depth -= 1
            if not depth:
                values.append(re.sub(r'\s+','',text[start:i])); break
        else: raise ValueError('Unterminated '+name)
    return values


def check_preprocessed(text, rust):
    task.check_preprocessed(text, True)
    init, alloc, dup = [function_bodies(text,name) for name in ('mm_init','mm_alloc','dup_mm')]
    if len(init) != 1 or len(dup) != 1: raise ValueError('Missing/duplicate shared MM initializer or copied caller')
    if 'if(!mm_init(mm,tsk,mm->user_ns))' not in dup[0]:
        raise ValueError('dup_mm no longer invokes shared initializer with copied namespace')
    if rust:
        if init != ['returnrusix_mm_init(mm,p,user_ns);'] or alloc:
            raise ValueError('Rust selection retains C allocation policy or wrong initializer bridge')
    else:
        if len(alloc) != 1 or 'rusix_mm_init' in init[0]+alloc[0]: raise ValueError('Wrong C MM selection')
        for token in ('futex_mm_init(mm)', 'mm_alloc_pgd(mm)', 'mm_alloc_id(mm)',
                      'init_new_context(p,mm)', 'mm_alloc_cid(mm,p)', 'fail_pcpu:',
                      'mm_destroy_cid(mm)', 'destroy_context(mm)', 'mm_free_id(mm)',
                      'mm_free_pgd(mm)', 'futex_hash_free(mm)', 'get_user_ns(user_ns)'):
            if token not in init[0]: raise ValueError('Original MM C transaction missing: '+token)
        for token in ('kmem_cache_alloc_noprof(', 'sizeof(*mm)', 'returnmm_init(mm,'):
            if token not in alloc[0]: raise ValueError('Original C mm_alloc missing: '+token)


def check_relocations(text, rust):
    task.check_relocations(text, True)
    previous, found = '', False
    for line in text.splitlines():
        if 'R_X86_64_' in line and 'rusix_mm_init' in line:
            if not re.search(r'R_X86_64_PLT32\s+rusix_mm_init(?:-0x4)?\s*$', line) or not re.search(r'\b(?:callq?|jmpq?)\b', previous):
                raise ValueError('MM initializer bridge is not an executable call/jump')
            found = True
        if re.match(r'^\s*[0-9a-f]+:',line) and 'R_X86_64_' not in line: previous = line
    if found != rust: raise ValueError('Missing/unexpected MM initializer relocation')


def definitions(text, expected):
    for name in MM_SYMBOLS:
        rows = [r.split() for r in text.splitlines() if r.split() and r.split()[-1] == name]
        if len(rows) != int(name in expected) or (rows and (len(rows[0]) != 3 or rows[0][1] != 'T')):
            raise ValueError('Missing/duplicate/wrong global MM definition: '+name)


def archive_members(text, rust):
    task.archive_members(text, True)
    names = [Path(row).name for row in text.splitlines()]
    if names.count('mm_construction_rust.o') != int(rust): raise ValueError('Wrong MM archive selection')
    if any('mm_construction' in n and n != 'mm_construction_rust.o' for n in names):
        raise ValueError('Alternate MM construction object')


def input_paths(build, source, rust):
    paths = preprocessor.inputs(build,source) + [build/'kernel/fork.i', build/'vmlinux',
        build/'kernel/built-in.a', build/'kernel/task_construction_rust.o',
        source/'rusix/configs/x86_64-server.config',
        source/'rusix/configs'/('x86_64-mm-construction-'+('rust' if rust else 'c')+'.config'),
        source/'rusix/scripts/verify-task-construction.py', source/'rusix/scripts/verify-mm-construction.py',
        source/'kernel/Makefile', source/'init/Kconfig', source/'rusix/scripts/build-kernel.sh',
        source/'rusix/ci/run.sh', source/'rusix/ci/run-container.sh']
    if rust: paths.append(build/'kernel/mm_construction_rust.o')
    return paths


def verify(args):
    source, build, evidence = args.source.resolve(), args.build.resolve(), args.evidence.resolve()
    rust = PROFILES[args.profile]
    check_config(args.profile, config_values((build/'.config').read_text()), config_values((source/'rusix/configs/x86_64-server.config').read_text()))
    original_policy((source/'kernel/fork.c').read_text())
    output = build/'kernel/fork.i'
    before_pre = {str(p):digest(p) for p in preprocessor.inputs(build,source)}
    record = dict(argv=preprocessor.command((build/'kernel/.fork.o.cmd').read_text(),output),
                  cwd=str(build),input_sha256=before_pre,output=str(output),preprocessed_sha256=digest(output))
    if json.loads((evidence/'mm-preprocess.json').read_text()) != record:
        raise ValueError('Preprocessing inputs/actual command changed')
    if (evidence/'mm-preprocess.exit').read_text().strip() != '0' or re.search(r'warning:|error:',(evidence/'mm-preprocess.log').read_text(),re.I):
        raise ValueError('Preprocessing failed or emitted diagnostics')
    check_preprocessed(output.read_text(),rust)
    paths = input_paths(build,source,rust)
    before = {str(p):digest(p) for p in paths}
    def run(name, argv):
        result = subprocess.run(argv,check=True,capture_output=True,text=True)
        if result.stderr: raise ValueError('ELF tool diagnostic: '+result.stderr)
        (evidence/name).write_text(result.stdout); return result.stdout
    archive = build/'kernel/built-in.a'
    members = run('mm-archive.txt',['llvm-ar','t',str(archive)])
    archive_members(members,rust)
    member_hashes = {}
    objects = [build/'kernel/fork.o',build/'kernel/task_construction_rust.o']
    if rust: objects.append(build/'kernel/mm_construction_rust.o')
    for obj in objects:
        member = next(row for row in members.splitlines() if Path(row).name == obj.name)
        data = subprocess.run(['llvm-ar','p',str(archive),member],check=True,capture_output=True)
        if data.stderr or task.digest(obj) != hashlib.sha256(data.stdout).hexdigest():
            raise ValueError('Archive member differs from standalone object')
        member_hashes[member] = digest(obj)
    fork_symbols = run('mm-fork-symbols.txt',['llvm-nm','--defined-only',str(build/'kernel/fork.o')])
    task_symbols = run('mm-task-symbols.txt',['llvm-nm','--defined-only',str(build/'kernel/task_construction_rust.o')])
    linked = run('mm-kernel-symbols.txt',['llvm-nm','--defined-only',str(build/'vmlinux')])
    task.bridge_definition(fork_symbols,False); task.bridge_definition(task_symbols,True); task.bridge_definition(linked,True)
    definitions(fork_symbols,() if rust else ('mm_alloc',))
    definitions(task_symbols,())
    definitions(linked,MM_SYMBOLS if rust else ('mm_alloc',))
    if rust:
        definitions(run('mm-rust-symbols.txt',['llvm-nm','--defined-only',str(build/'kernel/mm_construction_rust.o')]),MM_SYMBOLS)
    check_relocations(run('mm-fork-disassembly.txt',['llvm-objdump','-dr',str(build/'kernel/fork.o')]),rust)
    if before != {str(p):digest(p) for p in paths}: raise ValueError('Selection inputs changed')
    return dict(status='PASS',implementation='rust' if rust else 'c',input_sha256=before,
                archive_member_sha256=member_hashes,task_implementation='rust',
                scope='Source/preprocessing/object/linked selection; no runtime or allocator-failure claim')


def main():
    ap=argparse.ArgumentParser(description=__doc__); sub=ap.add_subparsers(dest='action',required=True)
    p=sub.add_parser('objects');p.add_argument('--profile',choices=PROFILES,required=True)
    for name in ('source','build','evidence'):p.add_argument('--'+name,type=Path,required=True)
    p=sub.add_parser('config');p.add_argument('--profile',choices=PROFILES,required=True)
    p.add_argument('--config',type=Path,required=True);p.add_argument('--source',type=Path,required=True)
    p=sub.add_parser('compare');p.add_argument('--c',type=Path,required=True);p.add_argument('--rust',type=Path,required=True)
    args=ap.parse_args()
    if args.action=='objects': result=verify(args)
    elif args.action=='compare':result=compare(config_values(args.c.read_text()),config_values(args.rust.read_text()))
    else:
        check_config(args.profile,config_values(args.config.read_text()),config_values((args.source/'rusix/configs/x86_64-server.config').read_text()))
        result=dict(status='PASS',profile=args.profile,scope='Resolved configuration only')
    print(json.dumps(result,indent=2,sort_keys=True))
if __name__=='__main__':main()
