#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Actual native teardown fixture and Rust KUnit registration ownership.

Pinned x86_64 C layout: case fields run/name at 0/8, stride72; suite inline
name[256], four callbacks, test_cases at288, total584. Exact canonical header
and actual bindgen struct signatures below reject unknown layouts first.
"""
import hashlib
import importlib.util
from pathlib import Path
import re
import subprocess

def load(name, filename):
    spec=importlib.util.spec_from_file_location(name,Path(__file__).with_name(filename))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
elfmod=load('exit_fixture_elf','verify-brd-parameter-owner.py')
task=load('exit_fixture_archive','verify-task-construction.py')
CASES=('empty_final_users_retains_storage','mapped_final_users_closes_before_file_put','fixed_replace_close_dummy_reset')
ENTRIES=tuple('rusix_exit_test_'+x for x in ('start','wait','result','put'))
BRIDGES=tuple('rust_helper_exit_test_'+x for x in ('start','wait','result','put'))
SUITE='rusix_exit_mmap'
def need(value, message):
    if not value:raise ValueError(message)
def digest(p):return task.digest(p)
def signature(text, name, rust=False):
    pattern=(r'pub struct ' if rust else r'struct ')+name+r'\s*\{.*?^\}'
    rows=re.findall(pattern,text,re.S|re.M);need(len(rows)==1,'Missing/ambiguous layout '+name)
    clean=re.sub(r'/\*.*?\*/','',rows[0],flags=re.S)
    return hashlib.sha256(re.sub(r'\s+','',clean).encode()).hexdigest()
LAYOUT = {'kunit_attributes': ('3f587fe76dd592563a26856337d50c214d387e293f52e09b53f47d194189b2ed', '5a862560d724dbbe864ef36d835b3a32f257a8ccd790b04cd67ad6f498b1a16c'), 'kunit_case': ('e50f48ec1edfbe52e95a7d5ae0a26f867c843c3e07f518480fd819a24b3fa095', '0cf687061290336a4fad39667d7946fb199f1220cccff0dfd35f4e510567c747'), 'kunit_suite': ('000634891e6272fed8dab58ffd036f1432f82100907b1224eb22f90020652aad', '8c9f79432a652ce51d495f1e02559fb66657e2f8b7bfe1bb4a3ead3b25fd8b43')}
def layout(source, build):
    header=(source/'include/kunit/test.h').read_text()
    generated=(build/'rust/bindings/bindings_generated.rs').read_text()
    for name,(c,rust) in LAYOUT.items():
        need(signature(header,name)==c and signature(generated,name,True)==rust,'Unsupported KUnit layout '+name)
    for enum in ('kunit_status','kunit_speed'):
        need(re.search(r'pub type '+enum+r' = ffi::c_uint;',generated),'Unknown enum width')

def offset(loc, n):
    need(isinstance(loc,tuple),'Pointer must resolve to defined storage')
    return loc[0],loc[1]+n

def function(elf, loc):
    need(isinstance(loc,tuple),'Case target must resolve inside ELF')
    index,position=loc
    need(0<index<len(elf.headers) and elf.headers[index][2]&4,'Case target is not executable')
    rows=[s for s in elf.symbols if s['kind']==2 and s['size']>0 and s['section']==index and elf.location(s)==loc]
    need(len(rows)==1,'Missing/ambiguous exact function entry')
    return rows[0]['name']

def registrations(elf):
    if elf.relocatable:
        need(all(elf.headers[i][5]%8==0 for i,n in enumerate(elf.names) if n=='.kunit_test_suites'),'Bad registration stride')
        return [(i,n) for i,name in enumerate(elf.names) if name=='.kunit_test_suites'
                for n in range(0,elf.headers[i][5],8)]
    bounds=[s for s in elf.symbols if s['section'] and s['name'] in ('__kunit_suites_start','__kunit_suites_end')]
    if not bounds:return []
    start=elf.symbol('__kunit_suites_start')['address'];end=elf.symbol('__kunit_suites_end')['address']
    need(end>=start and (end-start)%8==0,'Bad linked suite bounds')
    return [elf.at_address(a) for a in range(start,end,8)]

def registration(elf, enabled):
    found=[]
    for entry in registrations(elf):
        target=elf.pointer(entry)
        need(isinstance(target,tuple),'Unresolved registered suite')
        index,pos=target
        data=elf.section_data(index)
        need(0<=pos and pos+256<=len(data),'Suite name outside storage')
        name=data[pos:pos+256].split(b'\0',1)[0]
        if name==SUITE.encode():found.append(target)
    need(len(found)==int(enabled),'Missing/duplicate/unexpected teardown suite registration')
    if not enabled:return []
    suite=found[0];need(suite[1]+584<=len(elf.section_data(suite[0])),'Truncated suite')
    for n in (256,264,272,280):need(elf.pointer(offset(suite,n)) is None,'Unexpected suite callback')
    cases=elf.pointer(offset(suite,288));need(isinstance(cases,tuple),'Unresolved case array')
    need(cases[1]+4*72<=len(elf.section_data(cases[0])),'Truncated case array')
    functions=[]
    for i,expected in enumerate(CASES):
        record=offset(cases,i*72)
        need(elf.text(elf.pointer(offset(record,8)))==expected,'Wrong case name/order')
        target=function(elf,elf.pointer(record))
        need('kunit_rust_wrapper_'+expected in target and 'exit_tests' in target,'Case target is not its Rust wrapper')
        functions.append(target)
        for n in (16,32,40):need(elf.pointer(offset(record,n)) is None,'Unexpected parameter callback')
    need(len(set(functions))==3,'Duplicate case executable target')
    final=offset(cases,3*72)
    need(elf.section_data(final[0])[final[1]:final[1]+72]==bytes(72),'Missing zero case terminator')
    need(not any(offset(final,n) in elf.relocations for n in range(72)),'Relocated terminator')
    return functions

def global_definitions(text, names, enabled):
    for name in names:
        rows=[line.split() for line in text.splitlines() if line.split() and line.split()[-1]==name]
        need(len(rows)==int(enabled) and (not enabled or len(rows[0])==3 and rows[0][1]=='T'),'Wrong global owner '+name)

def bridge_calls(text):
    for bridge,target in zip(BRIDGES,ENTRIES):
        chunks=re.findall(r'^([0-9a-f]+) <'+re.escape(bridge)+r'>:\n(.*?)(?=^[0-9a-f]+ <|\Z)',text,re.M|re.S)
        need(len(chunks)==1,'Missing/duplicate helper bridge')
        # Executable relocation must follow a real branch, not data/string presence.
        lines=chunks[0][1].splitlines();good=0
        for i,line in enumerate(lines):
            if re.search(r'R_X86_64_(?:PLT32|PC32)\s+'+target+r'-0x4\s*$',line):
                need(i>0 and re.search(r'\b(?:callq?|jmpq?)\b',lines[i-1]),'Bridge relocation is not executable')
                good+=1
        need(good==1,'Wrong/missing bridge call target '+target)

def helper_payload(archive, members, object_path):
    """The sole allowed nested Rust bridge member, with actual extracted bytes."""
    archive=Path(archive).resolve();object_path=Path(object_path).resolve()
    need(object_path==archive.parent/'helpers/helpers.o','Unexpected helper object path')
    selected=[name for name in members if Path(name).name=='helpers.o']
    need(len(selected)==1,'Missing/duplicate helper archive member')
    member=selected[0]
    with archive.open('rb') as stream:magic=stream.read(8)
    if magic==b'!<thin>\n':
        listed=Path(member)
        if not listed.is_absolute():listed=archive.parent/listed
        need(listed.resolve()==object_path,'Thin helper member references another object')
        token='helpers/helpers.o'
    elif magic==b'!<arch>\n':
        token=member
    else:raise ValueError('Unsupported helper archive format')
    extracted=subprocess.run(['llvm-ar','pP',str(archive),token],capture_output=True)
    need(extracted.returncode==0 and not extracted.stderr,'Helper archive extraction failed')
    value=hashlib.sha256(extracted.stdout).hexdigest()
    need(value==digest(object_path),'Helper archive payload differs')
    return value


def input_paths(build, source, enabled):
    scripts=source/'rusix/scripts'
    paths=[scripts/'exit_kunit_elf.py',scripts/'verify-brd-parameter-owner.py',scripts/'measure-kernel-languages.py',scripts/'verify-task-construction.py',
           build/'mm/built-in.a',build/'rust/built-in.a',build/'rust/kernel.o',build/'rust/helpers/helpers.o',build/'vmlinux',build/'.config',build/'rust/.kernel.o.cmd',build/'rust/helpers/.helpers.o.cmd',
           source/'include/kunit/test.h',source/'rust/kernel/kunit.rs',source/'rust/macros/kunit.rs',
           source/'mm/exit_mmap_test.c',source/'rust/helpers/exit_mmap_test.c',source/'rust/helpers/helpers.c',source/'rust/kernel/mm/exit_tests.rs',source/'rust/kernel/mm.rs',source/'mm/Makefile',source/'init/Kconfig']
    if enabled:paths += [build/'mm/.exit_mmap_test.o.cmd',build/'mm/exit_mmap_test.o',build/'rust/bindings/bindings_generated.rs']
    return paths

def verify(build,evidence,enabled,*,source=None):
    build=Path(build);evidence=Path(evidence)
    source=Path(source).resolve() if source is not None else Path(__file__).resolve().parents[2]
    if enabled:layout(source,build)
    # Caller owns full source/config interval; artifact reads below are rehashed.
    paths=[build/'mm/built-in.a',build/'rust/built-in.a',build/'rust/kernel.o',build/'rust/helpers/helpers.o',build/'vmlinux']
    if enabled:paths.append(build/'mm/exit_mmap_test.o')
    before={str(p):digest(p) for p in paths}
    def run(name,argv):
        result=subprocess.run(argv,capture_output=True,text=True,check=True)
        need(not result.stderr,'ELF tool diagnostics')
        (evidence/name).write_text(result.stdout);return result.stdout
    members=run('exit-kunit-archive.txt',['llvm-ar','t',str(paths[0])]).splitlines()
    selected=[m for m in members if Path(m).name=='exit_mmap_test.o']
    need(len(selected)==int(enabled),'Wrong fixture archive inventory')
    rust_archive=build/'rust/built-in.a'
    rust_members=run('exit-kunit-rust-archive.txt',['llvm-ar','t',str(rust_archive)]).splitlines()
    kernel_members=[m for m in rust_members if Path(m).name=='kernel.o']
    need(len(kernel_members)==1,'Missing/duplicate Rust kernel archive member')
    helpers_payload=helper_payload(rust_archive,rust_members,build/'rust/helpers/helpers.o')
    rust_payload=task.archive_member_hash(rust_archive,kernel_members[0],build/'rust/kernel.o')
    payload=task.archive_member_hash(paths[0],selected[0],build/'mm/exit_mmap_test.o') if enabled else None
    for label,path in [('helpers',build/'rust/helpers/helpers.o'),('kernel',build/'vmlinux')]+([('fixture',build/'mm/exit_mmap_test.o')] if enabled else []):
        nm=run('exit-kunit-'+label+'-globals.txt',['llvm-nm','-g','--defined-only',str(path)])
        global_definitions(nm,ENTRIES,enabled if label!='helpers' else False)
        if label!='fixture':global_definitions(nm,BRIDGES,enabled)
    if enabled:bridge_calls(run('exit-kunit-helper-disassembly.txt',['llvm-objdump','-dr','--no-show-raw-insn',str(build/'rust/helpers/helpers.o')]))
    objects=[elfmod.Elf(build/'rust/kernel.o',indexed_sections=True),elfmod.Elf(build/'vmlinux',indexed_sections=True)]
    graphs=[registration(elf,enabled) for elf in objects]
    need(graphs[0]==graphs[1],'Object/linked registered case targets differ')
    need(before=={str(p):digest(p) for p in paths},'Fixture artifacts changed during verification')
    return dict(status='PASS',enabled=enabled,suite=SUITE if enabled else None,cases=list(CASES) if enabled else [],registered_functions=graphs[0],fixture_archive_payload_sha256=payload,rust_archive_payload_sha256=rust_payload,helpers_archive_payload_sha256=helpers_payload,input_sha256=before,scope='Actual registration pointers/executable ownership; not runtime proof')
