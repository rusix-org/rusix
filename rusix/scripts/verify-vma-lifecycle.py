#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Actual VMA lifecycle/cache ownership proof, composed with the MM stack."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


dup = load('vma_dup_gate', 'verify-dup-mmap.py')
preprocessor = load('vma_preprocessor', 'preprocess-vma-lifecycle.py')
digest, config_values = dup.digest, dup.config_values
PROFILES = {'vma-lifecycle-c': False, 'vma-lifecycle-rust': True}
SELECTOR = 'CONFIG_RUSIX_VMA_LIFECYCLE_RUST'
PUBLIC = ('vm_area_alloc', 'vm_area_dup', 'vm_area_free')
BRIDGE = 'rusix_vma_state_init'
START = '#ifdef CONFIG_RUSIX_VMA_LIFECYCLE_RUST\n'
END = '#endif /* CONFIG_RUSIX_VMA_LIFECYCLE_RUST */\n'
SHIM = '''#include "vma_lifecycle_impl.h"
extern void rusix_vma_state_init(void);

/* Keep canonical init attributes and the existing boot call site. */
void __init vma_state_init(void)
{
	rusix_vma_state_init();
}
#else
'''
BASE_HASH = '9c6d4934701675a88d159de3b5e40790fa8605fabfdcec1d869327ecf480254c'


def original_policy(text):
    if text.count(START) != 1 or text.count(END) != 1:
        raise ValueError('Ambiguous VMA selection guards')
    before, rest = text.split(START)
    if not rest.startswith(SHIM) or not rest.endswith(END):
        raise ValueError('Changed VMA init dispatch/boundary')
    restored = before + rest[len(SHIM):-len(END)]
    if hashlib.sha256(restored.encode()).hexdigest() != BASE_HASH:
        raise ValueError('Original VMA lifecycle changed')
    return restored


def check_config(profile, values, target, *, test_context=None):
    if profile not in PROFILES:
        raise ValueError('Unknown VMA lifecycle profile')
    dup.check_config('mm-dup-mmap-rust', values, target, test_context=test_context)
    if values.get(SELECTOR) != ('y' if PROFILES[profile] else 'n'):
        raise ValueError('Wrong explicit VMA selection')
    if values.get('CONFIG_PER_VMA_LOCK') != 'y':
        raise ValueError('Required per-VMA locks missing')
    for name in ('CONFIG_NUMA', 'CONFIG_NUMA_BALANCING'):
        if values.get(name, 'n') != 'n':
            raise ValueError('Unreviewed NUMA lifecycle')


def compare(c, rust):
    changes = {k for k in c.keys() | rust.keys() if c.get(k, 'n') != rust.get(k, 'n')}
    if c.get(SELECTOR) != 'n' or rust.get(SELECTOR) != 'y' or changes != {SELECTOR}:
        raise ValueError('Only VMA selector may differ')
    for values in (c, rust):
        for option in (dup.SELECTOR, dup.copy.SELECTOR, dup.copy.release.SELECTOR,
                       dup.copy.release.mm.SELECTOR, dup.copy.release.task.SELECTOR, 'CONFIG_PER_VMA_LOCK'):
            if values.get(option) != 'y':
                raise ValueError('Required inherited selection missing')
    return sorted(changes)


def bodies(text, name):
    text = re.sub(r'^#.*$', '', text, flags=re.M)
    text = re.sub(r'/\*.*?\*/|//[^\n]*', '', text, flags=re.S)
    result = []
    for match in re.finditer(r'\b' + re.escape(name) + r'\s*\([^;{}]*\)\s*\{', text):
        start, depth, pos = match.end(), 1, match.end()
        while pos < len(text) and depth:
            depth += (text[pos] == '{') - (text[pos] == '}')
            pos += 1
        if depth:
            raise ValueError('Unterminated function')
        result.append(re.sub(r'\s+', '', text[start:pos-1]))
    return result


CACHE_ARGS = ('structkmem_cache_argsargs={.use_freeptr_offset=true,'
              '.freeptr_offset=__builtin_offsetof(structvm_area_struct,vm_freeptr),.sheaf_capacity=32,};')
CACHE_CALL = ('_Generic((&args),structkmem_cache_args*:__kmem_cache_create_args,'
              'void*:__kmem_cache_default_args,default:__kmem_cache_create)'
              '("vm_area_struct",sizeof(structvm_area_struct),&args,'
              '((slab_flags_t)(1U<<(_SLAB_HWCACHE_ALIGN)))|'
              '((slab_flags_t)(1U<<(_SLAB_PANIC)))|'
              '((slab_flags_t)(1U<<(_SLAB_TYPESAFE_BY_RCU)))|((slab_flags_t)(0U)));')


def check_preprocessed(text, rust):
    # MEMCG is excluded: SLAB_ACCOUNT expands to canonical unused zero flag.
    init = bodies(text, 'vma_state_init')
    if init != (['rusix_vma_state_init();'] if rust else [CACHE_ARGS+'vm_area_cachep='+CACHE_CALL]):
        raise ValueError('VMA init/cache metadata expansion differs')
    create = bodies(text, 'rusix_vma_cache_create')
    if create != ([CACHE_ARGS+'return'+CACHE_CALL] if rust else []):
        raise ValueError('Canonical cache constructor metadata differs')
    cache_decl = re.findall(r'\bstatic\s+struct\s+kmem_cache\s*\*\s*vm_area_cachep\s*;', text)
    if len(cache_decl) != int(not rust):
        raise ValueError('Wrong C cache storage selection')
    tokens = {
        'vm_area_alloc': ('vm_area_cachep', 'if(!vma)', 'vma_init(vma,mm)', 'returnvma;'),
        'vm_area_dup': ('vm_area_cachep', 'vm_area_init_from(orig,new)', 'vma_pfnmap_track_ctx_dup(orig,new)',
                        'vma_lock_init(new,true)', 'dup_anon_vma_name(orig,new)', 'returnnew;'),
        'vm_area_free': ('vma_assert_detached(vma)', 'vma_numab_state_free(vma)',
                         'free_anon_vma_name(vma)', 'vma_pfnmap_track_ctx_release(vma)', 'kmem_cache_free(vm_area_cachep,vma)')}
    for name, required in tokens.items():
        found = bodies(text, name)
        if len(found) != int(not rust) or (found and any(token not in found[0] for token in required)):
            raise ValueError('Wrong original lifecycle body selection: '+name)


def elf_tables(metadata):
    if len(metadata) != 1 or metadata[0]['FileSummary']['Format'] != 'elf64-x86-64' or metadata[0]['FileSummary']['Arch'] != 'x86_64':
        raise ValueError('Expected single x86_64 ELF')
    return ([x['Symbol'] for x in metadata[0]['Symbols']], [x['Section'] for x in metadata[0]['Sections']])


def symbol_section(metadata, name):
    symbols, sections = elf_tables(metadata)
    matches = [x for x in symbols if x['Name']['Name'] == name]
    if len(matches) != 1:
        raise ValueError('Missing/duplicate ELF symbol: '+name)
    sym = matches[0]
    found = [x for x in sections if x['Index'] == sym['Section']['Value']]
    if len(found) != 1:
        raise ValueError('Unbound ELF section: '+name)
    sec = found[0]
    offset = sym['Value']-sec['Address']
    if sym['Size'] <= 0 or not 0 <= offset < offset+sym['Size'] <= sec['Size']:
        raise ValueError('Symbol exceeds ELF section: '+name)
    return sym, sec


def function_location(metadata, name, init):
    sym, sec = symbol_section(metadata, name)
    section = sec['Name']['Name']
    if sym['Type']['Value'] != 2 or sym['Binding']['Value'] != 1 or sec['Type']['Value'] != 1 or sec['Flags']['Value'] & 6 != 6:
        raise ValueError('Expected global allocated executable function: '+name)
    if (section != '.init.text') if init else (section != '.text' and not section.startswith('.text.')):
        raise ValueError('Wrong function lifetime section: '+name)


def cache_owner(metadata, rust, present=True):
    symbols, _ = elf_tables(metadata)
    caches = [x for x in symbols if x['Name']['Name'] == 'vm_area_cachep' or 'VM_AREA_CACHE' in x['Name']['Name']]
    if len(caches) != int(present):
        raise ValueError('Missing/duplicate/alternate cache storage')
    if not present:
        return None
    name = caches[0]['Name']['Name']
    if rust:
        if not re.fullmatch(r'_R[A-Za-z0-9_]*VM_AREA_CACHE(?:\.0)?', name) or 'VM_AREA_CACHE' not in name:
            raise ValueError('Wrong Rust cache symbol')
    elif name != 'vm_area_cachep':
        raise ValueError('Wrong C cache symbol')
    sym, sec = symbol_section(metadata, name)
    if sym['Type']['Value'] != 1 or sym['Binding']['Value'] != 0 or sym['Size'] != 8 or sym['Value'] % 8:
        raise ValueError('Cache must be a local aligned pointer-sized object')
    if sec['Type']['Value'] != 8 or sec['Flags']['Value'] & 7 != 3 or sec['AddressAlignment'] < 8 or not sec['Name']['Name'].startswith('.bss'):
        raise ValueError('Cache is not permanent zeroed writable BSS')
    return name


def refcount_constant(elf, nm, *, linked):
    """Prove the canonical four-byte constant, including linked .rodata flags."""
    name = 'rusix_vma_refcount_max'
    if elf.relocatable == linked:
        raise ValueError('Wrong refcount constant ELF kind')
    rows = [r.split() for r in nm.splitlines() if r.split() and r.split()[-1] == name]
    if len(rows) != 1 or len(rows[0]) != 3 or rows[0][1] not in ({'R', 'D'} if linked else {'R'}):
        raise ValueError('Wrong refcount constant binding')
    sym = elf.symbol(name)
    index, offset = elf.location(sym)
    sec = elf.headers[index]
    if (sym['kind'] != 1 or sym['size'] != 4 or sym['address'] % 4 or
        int(rows[0][0], 16) != sym['address'] or elf.names[index] != '.rodata' or
        sec[1] != 1 or not sec[2] & 2 or sec[2] & 4 or
        (not linked and sec[2] & 1) or offset < 0 or offset + 4 > sec[5]):
        raise ValueError('Wrong refcount constant storage')
    value = int.from_bytes(elf.section_data(index)[offset:offset+4], 'little')
    if value != 0x7fffffff:
        raise ValueError('Wrong canonical refcount maximum')
    return value

def definitions(text, expected):
    for name in (*PUBLIC, 'vma_state_init', BRIDGE):
        found = [x.split() for x in text.splitlines() if x.split() and x.split()[-1] == name]
        if len(found) != int(name in expected) or (found and (len(found[0]) != 3 or found[0][1] != 'T')):
            raise ValueError('Wrong VMA definition: '+name)


def dis_body(text, name):
    blocks = re.split(r'^\s*[0-9a-f]+ <([^>]+)>:\s*$', text, flags=re.M)
    found = [blocks[i+1] for i in range(1, len(blocks), 2) if blocks[i] == name]
    if len(found) != 1:
        raise ValueError('Missing/duplicate disassembly function: '+name)
    return found[0]


def call_from(text, caller, callee):
    previous = ''; count = 0
    for row in dis_body(text, caller).splitlines():
        if 'R_X86_64_' in row and re.search(r'\b'+re.escape(callee)+r'(?:[-+]|\s|$)', row):
            if not re.search(r'R_X86_64_PLT32\s+'+re.escape(callee)+r'(?:-0x4)?\s*$', row) or not re.search(r'\b(?:callq?|jmpq?)\b', previous):
                raise ValueError('Not an executable exact dispatch')
            count += 1
        elif re.match(r'^\s*[0-9a-f]+:', row):
            previous = row
    if count != 1:
        raise ValueError('Missing/duplicate exact dispatch')



def cache_accesses(disassembly, metadata, cache, functions):
    sym, sec = symbol_section(metadata, cache)
    symbols, _ = elf_tables(metadata)
    aliases = {x['Name']['Name']: x['Value'] for x in symbols
               if x['Type']['Value'] == 3 and x['Section']['Value'] == sec['Index']}
    for caller in functions:
        found = False; previous = ''
        for row in dis_body(disassembly, caller).splitlines():
            match = re.search(r'R_X86_64_(PC32|32S|64)\s+(\S+?)((?:[+-]0x[0-9a-f]+)?)\s*$', row)
            if match and (match[2] == cache or match[2] in aliases):
                base = sym['Value'] if match[2] == cache else aliases[match[2]]
                addend = int(match[3], 16) if match[3] else 0
                address = base + addend + (4 if match[1] == 'PC32' else 0)
                if address != sym['Value']:
                    if match[2] == cache:
                        raise ValueError('Named cache reference targets an interior/other address')
                    continue  # Another object, e.g. lockdep key, shares the BSS section.
                if not re.search(r'\bmov[a-z]*\b', previous):
                    raise ValueError('Wrong cache data reference')
                found = True
            elif re.match(r'^\s*[0-9a-f]+:', row):
                previous = row
        if not found:
            raise ValueError('No actual cache reference in '+caller)


def archive_members(text, rust):
    names = [Path(n).name for n in text.splitlines()]
    if names.count('vma_init.o') != 1 or names.count('vma_lifecycle_rust.o') != int(rust):
        raise ValueError('Wrong VMA archive selection')
    if any('vma_lifecycle' in n and n != 'vma_lifecycle_rust.o' for n in names):
        raise ValueError('Alternate VMA object')


def input_paths(build, source, rust, *, source_extension=None):
    paths = dup.input_paths(build, source, True, source_extension=source_extension) + preprocessor.inputs(build, source) + [
        build/'mm/vma_init.i', source/'rusix/scripts/verify-vma-lifecycle.py',
        source/f'rusix/configs/x86_64-vma-lifecycle-{"rust" if rust else "c"}.config']
    if rust:
        paths.append(build/'mm/vma_lifecycle_rust.o')
    if source_extension is not None:
        extension = load('exit_source_inputs', 'exit_mmap_source.py')
        paths += extension.paths(source, source_extension)
    return list(dict.fromkeys(paths))


def verify(args, *, source_extension=None, test_context=None):
    source, build, evidence = args.source.resolve(), args.build.resolve(), args.evidence.resolve()
    rust = PROFILES[args.profile]
    check_config(args.profile, config_values((build/'.config').read_text()), config_values((source/'rusix/configs/x86_64-server.config').read_text()), test_context=test_context)
    original_policy((source/'mm/vma_init.c').read_text())
    paths = input_paths(build, source, rust, source_extension=source_extension); before = {str(p): digest(p) for p in paths}
    inherited = dup.verify(argparse.Namespace(source=source, build=build, evidence=evidence, profile='mm-dup-mmap-rust'), source_extension=source_extension, test_context=test_context)
    if inherited['test_context'] != test_context or inherited['status'] != 'PASS' or inherited['implementation'] != 'rust':
        raise ValueError('Inherited Rust mapping selection failed')
    (evidence/'vma-lifecycle-dup-selection.json').write_text(json.dumps(inherited, indent=2, sort_keys=True)+'\n')
    output = build/'mm/vma_init.i'
    record = dict(argv=preprocessor.command((build/'mm/.vma_init.o.cmd').read_text(), output), cwd=str(build),
                  input_sha256={str(p): digest(p) for p in preprocessor.inputs(build, source)},
                  output=str(output), preprocessed_sha256=digest(output))
    if json.loads((evidence/'vma-lifecycle-preprocess.json').read_text()) != record:
        raise ValueError('Actual VMA preprocessing provenance differs')
    if (evidence/'vma-lifecycle-preprocess.exit').read_text().strip() != '0' or re.search('warning:|error:', (evidence/'vma-lifecycle-preprocess.log').read_text(), re.I):
        raise ValueError('Preprocessing failed or emitted diagnostics')
    check_preprocessed(output.read_text(), rust)
    def run(name, argv):
        result = subprocess.run(argv, capture_output=True, text=True, check=True)
        if result.stderr:
            raise ValueError('ELF inspection diagnostics: '+result.stderr)
        (evidence/name).write_text(result.stdout)
        return result.stdout
    archive = build/'mm/built-in.a'
    members = run('vma-lifecycle-archive.txt', ['llvm-ar', 't', str(archive)]); archive_members(members, rust)
    tables, metadata, hashes = {}, {}, {}
    for name in ['vma_init'] + (['vma_lifecycle_rust'] if rust else []):
        obj = build/f'mm/{name}.o'; member = next(n for n in members.splitlines() if Path(n).name == obj.name)
        hashes[member] = dup.copy.release.task.archive_member_hash(archive, member, obj)
        tables[name] = run(f'vma-lifecycle-{name}-symbols.txt', ['llvm-nm', '--defined-only', str(obj)])
        metadata[name] = json.loads(run(f'vma-lifecycle-{name}-elf.json', ['llvm-readobj', '--elf-output-style=JSON', '--sections', '--symbols', str(obj)]))
    tables['linked'] = run('vma-lifecycle-linked-symbols.txt', ['llvm-nm', '--defined-only', str(build/'vmlinux')])
    metadata['linked'] = json.loads(run('vma-lifecycle-linked-elf.json', ['llvm-readobj', '--elf-output-style=JSON', '--sections', '--symbols', str(build/'vmlinux')]))
    definitions(tables['vma_init'], {'vma_state_init'} if rust else {*PUBLIC, 'vma_state_init'})
    if rust:
        definitions(tables['vma_lifecycle_rust'], {*PUBLIC, BRIDGE})
    definitions(tables['linked'], {*PUBLIC, 'vma_state_init'} | ({BRIDGE} if rust else set()))
    owner = 'vma_lifecycle_rust' if rust else 'vma_init'
    cache = cache_owner(metadata[owner], rust)
    if cache_owner(metadata['linked'], rust) != cache:
        raise ValueError('Linked cache owner differs')
    if rust:
        cache_owner(metadata['vma_init'], True, False)
    for target in (owner, 'linked'):
        for name in PUBLIC:
            function_location(metadata[target], name, False)
    for target in ('vma_init', 'linked'):
        function_location(metadata[target], 'vma_state_init', True)
    owner_dis = run('vma-lifecycle-owner-disassembly.txt', ['llvm-objdump', '-dr', str(build/f'mm/{owner}.o')])
    cache_accesses(owner_dis, metadata[owner], cache, (*PUBLIC, BRIDGE if rust else 'vma_state_init'))
    if rust:
        for target in (owner, 'linked'):
            function_location(metadata[target], BRIDGE, True)
        for target in ('vma_init', 'linked'):
            function_location(metadata[target], 'rusix_vma_cache_create', True)
        c_dis = run('vma-lifecycle-c-disassembly.txt', ['llvm-objdump', '-dr', str(build/'mm/vma_init.o')])
        r_dis = run('vma-lifecycle-rust-disassembly.txt', ['llvm-objdump', '-dr', str(build/'mm/vma_lifecycle_rust.o')])
        call_from(c_dis, 'vma_state_init', BRIDGE)
        call_from(r_dis, BRIDGE, 'rusix_vma_cache_create')
        helpers = set(re.findall(r'fn (rusix_vma_\w+)\(', (source/'mm/vma_lifecycle_rust.rs').read_text())) - {BRIDGE}
        for helper in helpers:
            for table in (tables['vma_init'], tables['linked']):
                rows = [r.split() for r in table.splitlines() if r.split() and r.split()[-1] == helper]
                kind = 'T'
                if len(rows) != 1 or len(rows[0]) != 3 or rows[0][1] != kind:
                    raise ValueError('Wrong canonical primitive binding: '+helper)
    if rust:
        elf = dup.elf_reader.Elf
        object_max = refcount_constant(elf(build/'mm/vma_init.o', indexed_sections=True), tables['vma_init'], linked=False)
        linked_max = refcount_constant(elf(build/'vmlinux', indexed_sections=True), tables['linked'], linked=True)
        if object_max != linked_max:
            raise ValueError('Linked refcount maximum differs')
    if before != {str(p): digest(p) for p in paths}:
        raise ValueError('Inputs changed during verification')
    return dict(test_context=test_context,status='PASS', implementation='rust' if rust else 'c', input_sha256=before,
                archive_member_sha256=hashes, cache_symbol=cache, dup_mmap_selection=inherited,
                scope='Original source, actual preprocessing, linked entry/cache ownership and lifetime; no runtime claim')


def main():
    parser = argparse.ArgumentParser(description=__doc__); sub = parser.add_subparsers(dest='action', required=True)
    p = sub.add_parser('source'); p.add_argument('--source', type=Path, required=True)
    p = sub.add_parser('objects'); p.add_argument('--profile', choices=PROFILES, required=True)
    for name in ('source', 'build', 'evidence'):
        p.add_argument('--'+name, type=Path, required=True)
    p = sub.add_parser('config'); p.add_argument('--profile', choices=PROFILES, required=True); p.add_argument('--config', type=Path, required=True); p.add_argument('--source', type=Path, required=True)
    p = sub.add_parser('compare'); p.add_argument('--c', type=Path, required=True); p.add_argument('--rust', type=Path, required=True)
    args = parser.parse_args()
    if args.action == 'objects': result = verify(args)
    elif args.action == 'source': original_policy((args.source/'mm/vma_init.c').read_text()); result = dict(status='PASS', scope='Source preservation only')
    elif args.action == 'compare': result = compare(config_values(args.c.read_text()), config_values(args.rust.read_text()))
    else:
        check_config(args.profile, config_values(args.config.read_text()), config_values((args.source/'rusix/configs/x86_64-server.config').read_text())); result = dict(status='PASS', scope='Resolved config only')
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__': main()
