#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Prove constructor source, compiled dispatch and linked implementation; no runtime claims."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
from saved_clang_command import command

SELECTOR = 'CONFIG_RUSIX_TASK_CONSTRUCTION_RUST'
BRIDGE = 'rusix_dup_task_struct'
PINNED_FORK_SHA256 = '781790e8e6af86e7ded38bbcffa8e631eac7c43f03a3337021cba06610682802'
PROFILES = {'task-construction-c': False, 'task-construction-rust': True,
            'task-construction-fault-c': False, 'task-construction-fault-rust': True}
FAULT_PROFILES = frozenset(('task-construction-fault-c', 'task-construction-fault-rust'))
FAULT_REQUIRED = ('FAULT_INJECTION', 'FAILSLAB', 'FAIL_PAGE_ALLOC',
                  'FAULT_INJECTION_DEBUG_FS', 'FAULT_INJECTION_STACKTRACE_FILTER',
                  'STACKTRACE', 'FTRACE', 'KPROBES', 'KRETPROBES', 'UNWINDER_ORC',
                  'KPROBE_EVENTS', 'TRACING',
                  'KALLSYMS', 'KALLSYMS_ALL', 'DEBUG_FS')
EXCLUDED = ('MODULES', 'PREEMPT_RT', 'VMAP_STACK', 'SHADOW_CALL_STACK', 'KASAN',
            'KMSAN', 'KCSAN', 'MEM_ALLOC_PROFILING', 'KUNIT', 'DEBUG_FS')
REQUIRED = ('RUST', 'X86_64', 'THREAD_INFO_IN_TASK', 'SMP', 'RUSIX_COMPLETION_RUST',
            'RUSIX_BRD_RUST', 'DEBUG_KERNEL', 'DEBUG_SPINLOCK', 'PROVE_LOCKING',
            'DEBUG_MUTEXES', 'DEBUG_ATOMIC_SLEEP', 'DEBUG_LIST')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def config_values(text):
    result = {}
    for line in text.splitlines():
        match = re.fullmatch(r'(CONFIG_\w+)=(.*)', line) or re.fullmatch(r'# (CONFIG_\w+) is not set', line)
        if match:
            key, value = match[1], match[2] if match.lastindex == 2 else 'n'
            if key in result:
                raise ValueError('Duplicate setting: '+key)
            result[key] = value
    return result


def check_config(profile, values, target):
    if profile not in PROFILES:
        raise ValueError('Unknown constructor profile')
    if values.get(SELECTOR) != ('y' if PROFILES[profile] else 'n'):
        raise ValueError('Missing/wrong explicit constructor selector')
    fault = profile in FAULT_PROFILES
    for name in REQUIRED + (FAULT_REQUIRED if fault else ()):
        if values.get('CONFIG_'+name) != 'y':
            raise ValueError('Missing constructor dependency: '+name)
    for name in EXCLUDED:
        if fault and name == 'DEBUG_FS':
            continue
        if values.get('CONFIG_'+name, 'n') != 'n':
            raise ValueError('Unsupported constructor setting: '+name)
    for key, value in target.items():
        # Only the explicitly diagnostic profiles override this target exclusion.
        if fault and key == 'CONFIG_DEBUG_FS':
            value = 'y'
        if values.get(key, 'n') != value:
            raise ValueError('Declared server target drift: '+key)


def compare(c, rust):
    differences = {k for k in c.keys() | rust.keys() if c.get(k, 'n') != rust.get(k, 'n')}
    if c.get(SELECTOR) != 'n' or rust.get(SELECTOR) != 'y' or differences != {SELECTOR}:
        raise ValueError('Expected only constructor selector to differ')
    return sorted(differences)


def original_policy(text):
    start = '#ifdef CONFIG_RUSIX_TASK_CONSTRUCTION_RUST\n#include "task_construction_impl.h"\n'
    middle = '#else\nstatic struct task_struct *dup_task_struct('
    end = '#endif /* CONFIG_RUSIX_TASK_CONSTRUCTION_RUST */\n'
    if any(text.count(m) != 1 for m in (start, middle, end)):
        raise ValueError('Ambiguous constructor selection boundaries')
    before, rest = text.split(start)
    dispatch, rest = rest.split(middle)
    original, after = rest.split(end)
    expected = ('extern struct task_struct *rusix_dup_task_struct(struct task_struct *orig, int node);\n\n'
                'static struct task_struct *dup_task_struct(struct task_struct *orig, int node)\n'
                '{\n\treturn rusix_dup_task_struct(orig, node);\n}\n')
    if dispatch != expected:
        raise ValueError('Dispatch contains unexpected C policy')
    reconstructed = before + 'static struct task_struct *dup_task_struct(' + original + after
    if hashlib.sha256(reconstructed.encode()).hexdigest() != PINNED_FORK_SHA256:
        raise ValueError('Pinned fork.c differs outside the exact selection insertion')


def body(text):
    text = re.sub(r'^#.*$', '', text, flags=re.M)
    text = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', '""', text)
    matches = list(re.finditer(r'\bstatic\s+struct\s+task_struct\s*\*\s*dup_task_struct\s*\([^;{}]*\)\s*\{', text))
    if len(matches) != 1:
        raise ValueError('Missing/duplicate compiled constructor')
    depth, start = 1, matches[0].end()
    for i in range(start, len(text)):
        if text[i] == '{': depth += 1
        elif text[i] == '}': depth -= 1
        if not depth: return re.sub(r'\s+', '', text[start:i])
    raise ValueError('Unterminated constructor')


def check_preprocessed(text, rust):
    value = body(text)
    if rust:
        if value != 'returnrusix_dup_task_struct(orig,node);':
            raise ValueError('Rust dispatch is not only the bridge')
    else:
        if BRIDGE in value:
            raise ValueError('C constructor invokes Rust')
        for token in ('alloc_task_struct_node(node)', 'arch_dup_task_struct(tsk,orig)',
                      'alloc_thread_stack_node(tsk,node)', 'account_kernel_stack(tsk,1)',
                      'dup_user_cpus_ptr(tsk,orig,node)', 'free_stack:', 'free_tsk:',
                      'exit_task_stack_account(tsk)', 'free_thread_stack(tsk)', 'free_task_struct(tsk)'):
            if token not in value:
                raise ValueError('Missing original C transaction: '+token)


def check_relocations(text, rust):
    previous, count = '', 0
    for line in text.splitlines():
        if 'R_X86_64_' in line and BRIDGE in line:
            if not re.search(r'R_X86_64_PLT32\s+'+BRIDGE+r'(?:-0x4)?\s*$', line):
                raise ValueError('Unexpected constructor relocation')
            if not re.search(r'\b(?:callq?|jmpq?)\b', previous):
                raise ValueError('Constructor relocation is not executable')
            count += 1
        if re.match(r'^\s*[0-9a-f]+:', line) and 'R_X86_64_' not in line:
            previous = line
    if bool(count) != rust:
        raise ValueError('Missing/unexpected Rust bridge relocation')


def bridge_definition(text, expected):
    matches = [line.split() for line in text.splitlines() if line.split() and line.split()[-1] == BRIDGE]
    if len(matches) != int(expected) or (matches and (len(matches[0]) != 3 or matches[0][1] != 'T')):
        raise ValueError('Missing/duplicate/non-global Rust definition')


def archive_members(text, rust):
    names = [Path(line).name for line in text.splitlines()]
    if names.count('fork.o') != 1 or names.count('task_construction_rust.o') != int(rust):
        raise ValueError('Missing/duplicate/unexpected constructor archive object')
    if any('task_construction' in n and n != 'task_construction_rust.o' for n in names):
        raise ValueError('Unexpected alternative constructor object')


def archive_member_hash(archive, member, object_path):
    """Bind the selected regular payload or canonical Kbuild thin reference."""
    with archive.open('rb') as stream:
        magic = stream.read(8)
    if magic == b'!<thin>\n':
        listed = Path(member)
        if not listed.is_absolute():
            listed = archive.parent / listed
        if listed.resolve() != object_path.resolve():
            raise ValueError('Thin archive references a different object: '+member)
        # llvm-ar t expands thin paths, but pP matches the stored relative name.
        # These Kbuild objects live beside built-in.a. Other storage forms fail
        # closed rather than accepting a same-basename object elsewhere.
        if object_path.parent.resolve() != archive.parent.resolve():
            raise ValueError('Selected thin object is outside its archive directory')
        token = object_path.name
    elif magic == b'!<arch>\n':
        token = member
    else:
        raise ValueError('Unrecognized archive format')
    extracted = subprocess.run(['llvm-ar', 'pP', str(archive), token], capture_output=True)
    if extracted.returncode or extracted.stderr:
        raise ValueError('Archive extraction failed: '+extracted.stderr.decode(errors='replace'))
    result = hashlib.sha256(extracted.stdout).hexdigest()
    if result != digest(object_path):
        raise ValueError('Archive member differs from selected object: '+member)
    return result


def verify(args):
    source, build, evidence = args.source.resolve(), args.build.resolve(), args.evidence.resolve()
    rust = PROFILES[args.profile]
    config = build/'.config'
    target = source/'rusix/configs/x86_64-server.config'
    check_config(args.profile, config_values(config.read_text()), config_values(target.read_text()))
    original_policy((source/'kernel/fork.c').read_text())
    spec = importlib.util.spec_from_file_location('task_preprocess', Path(__file__).with_name('preprocess-task-construction.py'))
    tool = importlib.util.module_from_spec(spec); spec.loader.exec_module(tool)
    paths = tool.inputs(build, source)
    preprocessed = build/'kernel/fork.i'
    record = json.loads((evidence/'task-preprocess.json').read_text())
    expected = {str(p): digest(p) for p in paths}
    if record != dict(argv=command((build/'kernel/.fork.o.cmd').read_text(), preprocessed),
                      cwd=str(build), input_sha256=expected, output=str(preprocessed),
                      preprocessed_sha256=digest(preprocessed)):
        raise ValueError('Preprocessor record is stale or not derived from actual compilation')
    if (evidence/'task-preprocess.exit').read_text().strip() != '0' or re.search(r'warning:|error:', (evidence/'task-preprocess.log').read_text(), re.I):
        raise ValueError('Failed/diagnostic preprocessing')
    check_preprocessed(preprocessed.read_text(), rust)
    fork, obj, image, archive = build/'kernel/fork.o', build/'kernel/task_construction_rust.o', build/'vmlinux', build/'kernel/built-in.a'
    actual = paths + [preprocessed, image, archive, target, Path(__file__)]
    if rust: actual.append(obj)
    before = {str(p): digest(p) for p in actual}
    def run(name, argv):
        result = subprocess.run(argv, check=True, capture_output=True, text=True)
        if result.stderr:
            raise ValueError('Tool diagnostics: '+result.stderr)
        (evidence/name).write_text(result.stdout)
        return result.stdout
    members = run('task-archive.txt', ['llvm-ar', 't', str(archive)])
    archive_members(members, rust)
    # Membership alone does not bind an embedded member to the separately read
    # object. Compare bytes for regular and thin archives without trusting paths.
    member_hashes = {}
    for object_path in ([fork, obj] if rust else [fork]):
        member = next(row for row in members.splitlines() if Path(row).name == object_path.name)
        member_hashes[member] = archive_member_hash(archive, member, object_path)
    check_relocations(run('task-fork-disassembly.txt', ['llvm-objdump', '-dr', str(fork)]), rust)
    bridge_definition(run('task-fork-symbols.txt', ['llvm-nm', '--defined-only', str(fork)]), False)
    bridge_definition(run('task-kernel-symbols.txt', ['llvm-nm', '--defined-only', str(image)]), rust)
    if rust:
        bridge_definition(run('task-rust-symbols.txt', ['llvm-nm', '--defined-only', str(obj)]), True)
    if before != {str(p): digest(p) for p in actual}:
        raise ValueError('Selection inputs changed')
    return dict(status='PASS', implementation='rust' if rust else 'c', input_sha256=before,
                archive_member_sha256=member_hashes,
                scope='Source/preprocessing/object/linked selection only; no fixture or runtime claim')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest='action', required=True)
    p = sub.add_parser('objects')
    p.add_argument('--profile', choices=PROFILES, required=True)
    for name in ('source', 'build', 'evidence'): p.add_argument('--'+name, type=Path, required=True)
    p = sub.add_parser('config')
    p.add_argument('--profile', choices=PROFILES, required=True)
    p.add_argument('--config', type=Path, required=True)
    p.add_argument('--source', type=Path, required=True)
    p = sub.add_parser('compare')
    p.add_argument('--c', type=Path, required=True); p.add_argument('--rust', type=Path, required=True)
    args = ap.parse_args()
    if args.action == 'objects':
        result = verify(args)
    elif args.action == 'compare':
        result = compare(config_values(args.c.read_text()), config_values(args.rust.read_text()))
    else:
        check_config(args.profile, config_values(args.config.read_text()),
                     config_values((args.source/'rusix/configs/x86_64-server.config').read_text()))
        result = {'status': 'PASS', 'profile': args.profile, 'scope': 'Resolved configuration only'}
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__': main()
