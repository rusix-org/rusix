#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Actual VMA modification source/compiler/object ownership, not runtime proof."""
import argparse
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import vma_modify_source as extension

def load(name, file):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(file))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

copy = load('modify_copy', 'verify-copy-vma.py')
preprocessor = load('modify_pre', 'preprocess-vma-modify.py')
digest, config_values = copy.digest, copy.config_values
PROFILES, SELECTOR = extension.PROFILES, extension.SELECTOR
# Ten externally callable Rust definitions own eleven native policies: the
# shared private modify policy may inline into its four Rust public consumers.
RUST = ('rusix_init_multi_vma_prep', 'rusix_init_vma_prep', 'rusix_vma_prepare',
        'rusix_vma_complete', 'rusix_split_vma_inner', 'split_vma',
        'rusix_vma_modify_flags', 'rusix_vma_modify_name', 'rusix_vma_modify_policy',
        'rusix_vma_modify_flags_uffd')
WRAPPERS = ('vma_modify_flags', 'vma_modify_name', 'vma_modify_policy', 'vma_modify_flags_uffd')
PUBLIC = RUST + WRAPPERS
MERGE = ('structvma_merge_structvmg={.mm=vma->vm_mm,.vmi=vmi,.prev=prev,.middle=vma,'
         '.next=((void*)0),.start=start,.end=end,.vm_flags=vma->vm_flags,'
         '.pgoff=vma_pgoff_offset(vma,start),.file=vma->vm_file,.anon_vma=vma->anon_vma,'
         '.policy=((void*)0),.uffd_ctx=vma->vm_userfaultfd_ctx,.anon_name=anon_vma_name(vma),'
         '.state=VMA_MERGE_START,};')
SHIMS = {
    'init_multi_vma_prep': 'rusix_init_multi_vma_prep(vp,vma,vmg);',
    'init_vma_prep': 'rusix_init_vma_prep(vp,vma);',
    'vma_prepare': 'rusix_vma_prepare(vp);',
    'vma_complete': 'rusix_vma_complete(vp,vmi,mm);',
    '__split_vma': 'structvma_preparevp;returnrusix_split_vma_inner(vmi,vma,addr,new_below,&vp);',
    'vma_modify_flags': MERGE+'returnrusix_vma_modify_flags(&vmg,vm_flags_ptr);',
    'vma_modify_name': MERGE+'returnrusix_vma_modify_name(&vmg,new_name);',
    'vma_modify_policy': MERGE+'returnrusix_vma_modify_policy(&vmg,new_pol);',
    'vma_modify_flags_uffd': MERGE+'returnrusix_vma_modify_flags_uffd(&vmg,vm_flags,&new_ctx,give_up_on_oom);',
}

def bodies(text, name):
    return copy.exit.vma.bodies(text, name)

def check_config(profile, values, target):
    extension.check_config(profile, values, target, source_context=extension.ID)

def compare(c, rust, target):
    return extension.compare(c, rust, target, source_context=extension.ID)

def compact(text):
    text = re.sub(r'^#.*$', '', text, flags=re.M)
    text = re.sub(r'/\*.*?\*/|//[^\n]*', '', text, flags=re.S)
    return re.sub(r'\s+', '', text)

def check_preprocessed(text, rust, header):
    # Check actual compiler output. Never replace it with a fabricated native
    # prepare body to make the inherited gate accept the new implementation.
    copy.check_preprocessed(text, True, source_context=extension.ID, modify_rust=rust)
    if rust:
        for name, expected in SHIMS.items():
            if bodies(text, name) != [expected]:
                raise ValueError('Changed actual native context/dispatch: '+name)
        for name in ('split_vma', 'vma_modify'):
            if bodies(text, name):
                raise ValueError('Original C policy remains selected: '+name)
        # Source review binds each exact helper body; preprocessing proves all
        # typed definitions/prototypes actually participate in this compiler unit.
        for name in extension.PRIMITIVES:
            if len(bodies(text, name)) != 1:
                raise ValueError('Missing/duplicate actual primitive: '+name)
        actual = compact(text)
        for declaration in compact(header).split(';'):
            if declaration and declaration+';' not in actual:
                raise ValueError('Private canonical ABI declaration differs')
        critical = {'rusix_modify_set_start':'vma->vm_start=value;',
                    'rusix_modify_set_end':'vma->vm_end=value;',
                    'rusix_modify_set_pgoff':'vma->vm_pgoff=value;',
                    'rusix_modify_set_vm_flags':'((structvma_merge_struct*)opaque)->vm_flags=value;',
                    'rusix_modify_may_split':'returnops->may_split;',
                    'rusix_modify_split':'return__split_vma(iter,vma,addr,new_below);',
                    'rusix_modify_merge':'returnvma_merge_existing_range(opaque);'}
        for name, expected in critical.items():
            if bodies(text, name) != [expected]:
                raise ValueError('Canonical primitive differs: '+name)
    else:
        for name in extension.NATIVE:
            if len(bodies(text, name)) != 1:
                raise ValueError('Missing original C policy: '+name)
        if any(bodies(text, name) for name in extension.PRIMITIVES):
            raise ValueError('Modify primitive selected in C comparison')
    for name, required in {'commit_merge': ('init_multi_vma_prep(', 'vma_prepare(', 'vma_complete('),
                           'vma_shrink': ('init_vma_prep(', 'vma_prepare(', 'vma_complete(')}.items():
        found = bodies(text, name)
        if len(found) != 1 or any(token not in found[0] for token in required):
            raise ValueError('Native merge/shrink dispatch changed: '+name)

def definitions(table, expected):
    for name in (*PUBLIC, *extension.PRIMITIVES):
        rows = [line.split() for line in table.splitlines() if line.split() and line.split()[-1] == name]
        if len(rows) != int(name in expected) or (rows and (len(rows[0]) != 3 or rows[0][1] != 'T')):
            raise ValueError('Wrong global executable owner: '+name)

def archive_members(text, rust):
    names = [Path(n).name for n in text.splitlines()]
    if names.count('vma.o') != 1 or names.count('vma_modify_rust.o') != int(rust):
        raise ValueError('Wrong modification archive ownership')
    if any('vma_modify' in n and n != 'vma_modify_rust.o' for n in names):
        raise ValueError('Alternate modification object')

def prepare_calls(text):
    body = copy.exit.vma.dis_body(text, 'rusix_vma_prepare')
    calls = []
    for name in ('rusix_link_mapping_lock', 'rusix_vma_link_file_locked'):
        copy.exit.executable_calls(body, name)
        found = list(re.finditer(r'R_X86_64_PLT32\s+'+name+r'(?:-0x4)?\s*$', body, re.M))
        if len(found) != 1:
            raise ValueError('Ambiguous prepare lock/file-link call')
        calls.append(found[0].start())
    if calls != sorted(calls):
        raise ValueError('Prepare file-link precedes mapping lock')
    # Static call ordering plus exact reviewed Rust control flow establishes this
    # selected path; this is not a claim about dynamic lock/race correctness.

def callback_transfers(text):
    body = copy.exit.vma.dis_body(text, 'rusix_split_vma_inner')
    raw = re.findall(r'\b(?:callq?|jmpq?)\s+\*%[a-z0-9]+\b', body)
    thunks = set(re.findall(r'R_X86_64_PLT32\s+(__x86_indirect_thunk_[a-z0-9]+)(?:-0x4)?\s*$', body, re.M))
    if len(raw) + sum(copy.exit.executable_calls(body, target) for target in thunks) != 2:
        raise ValueError('Expected exact may_split/open callback transfers')
    for getter in ('rusix_modify_may_split', 'rusix_copy_open'):
        copy.exit.executable_calls(body, getter)

def input_paths(build, source, rust):
    paths = copy.input_paths(build, source, True, source_context=extension.ID) + preprocessor.inputs(build, source)
    paths += [source/f'rusix/configs/x86_64-vma-modify-{"rust" if rust else "c"}.config',
              source/'init/Kconfig', source/'mm/Makefile', source/'rusix/scripts/build-kernel.sh']
    if rust:
        paths += [build/'mm/vma_modify_rust.o', build/'mm/.vma_modify_rust.o.cmd']
    return list(dict.fromkeys(paths))

def verify(args):
    source, build, evidence = args.source.resolve(), args.build.resolve(), args.evidence.resolve()
    rust = PROFILES[args.profile]
    check_config(args.profile, config_values((build/'.config').read_text()),
                 config_values((source/'rusix/configs/x86_64-server.config').read_text()))
    source_proof = extension.source_policy(source, source_context=extension.ID)
    paths = input_paths(build, source, rust)
    before = {str(p):digest(p) for p in paths}
    inherited = copy.verify(argparse.Namespace(source=source, build=build, evidence=evidence,
                                               profile='copy-vma-rust'), source_context=extension.ID)
    if inherited['status'] != 'PASS' or inherited['implementation'] != 'rust' or inherited['source_extension']['extension'] != extension.ID:
        raise ValueError('Inherited copy context differs')
    obligation = ['vma-modify-rust-prepare-lock-before-file-link'] if rust else []
    if inherited.get('source_context') != extension.ID or inherited.get('outer_obligations') != obligation:
        raise ValueError('Inherited proof did not declare exact outer obligation')
    (evidence/'vma-modify-copy-selection.json').write_text(json.dumps(inherited, indent=2, sort_keys=True)+'\n')
    check_preprocessed((build/'mm/vma.i').read_text(), rust, (source/'mm/vma_modify.h').read_text())
    def run(name, argv):
        result = subprocess.run(argv, check=True, capture_output=True, text=True)
        if result.stderr:
            raise ValueError('Object inspection diagnostics: '+result.stderr)
        (evidence/name).write_text(result.stdout)
        return result.stdout
    archive = build/'mm/built-in.a'
    members = run('vma-modify-archive.txt', ['llvm-ar','t',str(archive)])
    archive_members(members, rust)
    expected = {'vma':set(WRAPPERS) | (set(extension.PRIMITIVES) if rust else {'split_vma'}),
                'linked':set(PUBLIC) | set(extension.PRIMITIVES) if rust else set(WRAPPERS) | {'split_vma'}}
    if rust:
        expected['vma_modify_rust'] = set(RUST)
    payloads, dis = {}, {}
    for label, owned in expected.items():
        obj = build/'vmlinux' if label == 'linked' else build/f'mm/{label}.o'
        if label != 'linked':
            member = next(n for n in members.splitlines() if Path(n).name == obj.name)
            payloads[member] = copy.exit.vma.dup.copy.release.task.archive_member_hash(archive, member, obj)
            dis[label] = run('vma-modify-'+label+'-disassembly.txt', ['llvm-objdump','-dr',str(obj)])
        table = run('vma-modify-'+label+'-symbols.txt', ['llvm-nm','--defined-only',str(obj)])
        definitions(table, owned)
        metadata = json.loads(run('vma-modify-'+label+'-elf.json', ['llvm-readobj','--elf-output-style=JSON','--sections','--symbols',str(obj)]))
        for symbol in owned:
            copy.exit.vma.function_location(metadata, symbol, False)
    if rust:
        for name in WRAPPERS:
            copy.exit.vma.call_from(dis['vma'], name, 'rusix_'+name)
        for name in ('rusix_init_multi_vma_prep','rusix_init_vma_prep','rusix_vma_prepare','rusix_vma_complete','rusix_split_vma_inner'):
            copy.exit.executable_calls(dis['vma'], name)
        prepare_calls(dis['vma_modify_rust'])
        callback_transfers(dis['vma_modify_rust'])
        for primitive in extension.PRIMITIVES:
            copy.exit.executable_calls(dis['vma_modify_rust'], primitive)
    copy.exit_mmap_source.require_unchanged(paths, before)
    return dict(status='PASS', implementation='rust' if rust else 'c', source_context=extension.ID,
                source=source_proof, input_sha256=before, archive_member_sha256=payloads,
                policy_inventory=list(extension.NATIVE), primitive_inventory=list(extension.PRIMITIVES),
                consumed_outer_obligations=obligation, copy_vma_selection=inherited,
                scope='Actual source/preprocessing/archive/object/linked ownership; no runtime proof')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='action',required=True)
    for action in ('source','config','objects','compare'):
        item=sub.add_parser(action)
        item.add_argument('--source',type=Path,required=True)
        if action in ('config','objects'):item.add_argument('--profile',choices=PROFILES,required=True)
        if action=='config':item.add_argument('--config',type=Path,required=True)
        if action=='objects':
            for name in ('build','evidence'):item.add_argument('--'+name,type=Path,required=True)
        if action=='compare':
            item.add_argument('--c',type=Path,required=True);item.add_argument('--rust',type=Path,required=True)
    args=parser.parse_args()
    target=lambda:config_values((args.source/'rusix/configs/x86_64-server.config').read_text())
    if args.action=='source':result=extension.source_policy(args.source,source_context=extension.ID)
    elif args.action=='config':
        check_config(args.profile,config_values(args.config.read_text()),target());result={'status':'PASS','scope':'configuration only'}
    elif args.action=='compare':result=compare(config_values(args.c.read_text()),config_values(args.rust.read_text()),target())
    else:result=verify(args)
    print(json.dumps(result,indent=2,sort_keys=True))

if __name__=='__main__':main()
