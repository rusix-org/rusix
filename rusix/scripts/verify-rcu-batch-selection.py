#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Bind batch policy to its original C source, compiled dispatch and linked Rust bridge."""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
import re
from pathlib import Path

spec = importlib.util.spec_from_file_location('batch_lists', Path(__file__).with_name('verify-rcu-list-selection.py'))
lists = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lists)
PROFILES = {'rcu-batch-c': False, 'rcu-batch-plain-c': False,
            'rcu-batch-rust': True, 'rcu-batch-plain-rust': True}
BRIDGES = ('rusix_rcu_do_batch', 'rusix_rcu_batch_check_time')
HOOKS = ('rusix_rcubatch_private', 'rusix_rcubatch_private_accounting', 'rusix_rcubatch_time_samples')
FIXTURE = ('rusix_rcubatch_start', 'rusix_rcubatch_wait', 'rusix_rcubatch_result', 'rusix_rcubatch_put')
ORIGINAL_TREE_SHA256 = 'e44083c2f67df3a0de8f08a7a59d42c7d854d283c66b7e481b64a9fc36f2ef73'


def check_config(profile, config):
    enabled = config.get('CONFIG_RUSIX_RCU_BATCH_TEST', 'n') == 'y'
    rust = config.get('CONFIG_RUSIX_RCU_BATCH_RUST', 'n') == 'y'
    if profile not in PROFILES:
        if enabled or rust:
            raise ValueError('Batch fixture selected outside explicit C-first profiles')
        return
    lists.check_config(profile, config)
    if rust != PROFILES[profile]:
        raise ValueError('Batch policy does not match profile')
    if not enabled:
        raise ValueError('Missing batch fixtures')
    for name in ('RCU_NOCB_CPU', 'RCU_BOOST', 'PREEMPT_RT', 'MODULES'):
        if config.get('CONFIG_' + name, 'n') != 'n':
            raise ValueError('Unsupported batch fixture configuration: ' + name)
    for name in ('RUSIX_RCU_LIST_RUST', 'RUSIX_COMPLETION_RUST', 'RUSIX_BRD_RUST'):
        if config.get('CONFIG_' + name) != 'y':
            raise ValueError('Missing existing Rust dependency: ' + name)


def original_policy(source):
    text = source.read_bytes()
    start = b'#ifdef CONFIG_RUSIX_RCU_BATCH_RUST\n'
    middle = b'#else\n/* Return true if callback-invocation time limit exceeded. */'
    end = b'#endif /* CONFIG_RUSIX_RCU_BATCH_RUST */\n\n'
    if any(text.count(marker) != 1 for marker in (start, middle, end)):
        raise ValueError('Missing/ambiguous policy selection boundaries')
    before, dispatch = text.split(start)
    _, original = dispatch.split(middle)
    body, after = original.split(end)
    reconstructed = before + middle.split(b'#else\n')[1] + body + after
    start = b'#ifdef CONFIG_RUSIX_RCU_BATCH_TEST\n#include "rcu_batch_test.h"'
    end = b'/*\n * This function is invoked from each scheduling-clock interrupt,'
    if reconstructed.count(start) != 1 or reconstructed.count(end) != 1:
        raise ValueError('Missing/ambiguous test-only boundary')
    first, rest = reconstructed.split(start)
    _, last = rest.split(end)
    if hashlib.sha256(first + end + last).hexdigest() != ORIGINAL_TREE_SHA256:
        raise ValueError('Original C policy changed outside dispatch/test additions')


def function_body(text, name):
    # Preprocessor removes comments. Ignore line markers and quoted strings for
    # structural parsing; neither is executable policy or a brace delimiter.
    text = re.sub(r'^#.*$', '', text, flags=re.M)
    text = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', '""', text)
    pattern = r'\bstatic\s+(?:void|bool|_Bool)\s+' + re.escape(name) + r'\s*\([^;{}]*\)\s*\{'
    matches = list(re.finditer(pattern, text))
    if len(matches) != 1:
        raise ValueError('Missing/duplicate compiled policy body: ' + name)
    begin = matches[0].end()
    depth = 1
    for i in range(begin, len(text)):
        if text[i] == '{': depth += 1
        elif text[i] == '}': depth -= 1
        if not depth: return re.sub(r'\s+', '', text[begin:i])
    raise ValueError('Unterminated compiled policy body')


def check_preprocessed(text, rust):
    batch = function_body(text, 'rcu_do_batch')
    time = function_body(text, 'rcu_do_batch_check_time')
    if rust:
        if batch != 'rusix_rcu_do_batch(rdp);' or time != 'returnrusix_rcu_batch_check_time(count,tlimit,jlimit_check,jlimit);':
            raise ValueError('Compiled Rust selection leaks C policy or wrong forwarding')
    else:
        if any(symbol in batch + time for symbol in BRIDGES):
            raise ValueError('C selection forwards into Rust')
        for token in ('rcu_segcblist_extract_done_cbs(', 'rcu_segcblist_insert_done_cbs(',
                      'rcu_segcblist_add_len(', 'count++;', 'f(rhp);'):
            if token not in batch: raise ValueError('Compiled original C transaction absent')
        if 'local_clock()' not in time:
            raise ValueError('Compiled original C time predicate absent')


def check_relocation(text, rust):
    # objdump -dr: only executable call/jump relocations count, not an address
    # taken into data, a symbol declaration, or absence of an inline C symbol.
    previous = ''
    bridges = set()
    for line in text.splitlines():
        relocation = re.search(r'R_X86_64_PLT32\s+(rusix_rcu_do_batch|rusix_rcu_batch_check_time)(?:-0x4)?\s*$', line)
        if relocation:
            if not re.search(r'\b(?:callq?|jmpq?)\b', previous):
                raise ValueError('Bridge relocation is not a call/jump')
            bridges.add(relocation[1])
        if re.match(r'^\s*[0-9a-f]+:', line) and 'R_X86_64_' not in line:
            previous = line
    expected = set(BRIDGES) if rust else set()
    if bridges != expected:
        raise ValueError('Missing/unexpected actual bridge call relocation')


def compare_configs(c_text, rust_text):
    c, rust = lists.config_values(c_text), lists.config_values(rust_text)
    key = 'CONFIG_RUSIX_RCU_BATCH_RUST'
    differences = {name for name in c.keys() | rust.keys() if c.get(name, 'n') != rust.get(name, 'n')}
    if c.get(key, 'n') != 'n' or rust.get(key) != 'y' or differences != {key}:
        raise ValueError('Expected only the batch policy selector to differ')
    return {'different_settings': sorted(differences)}


def symbols(path, required):
    found = Counter()
    for line in path.read_text().splitlines():
        fields = line.split()
        if len(fields) == 3 and fields[2] in required:
            if fields[1] != 'T':
                raise ValueError('Fixture symbol is not global text')
            found[fields[2]] += 1
    if found != Counter(required):
        raise ValueError('Missing/duplicate fixture definition')


def check_objects(profile, evidence, source, preprocessed):
    if profile not in PROFILES:
        raise ValueError('Object proof requires explicit batch profile')
    rust = PROFILES[profile]
    original_policy(source)
    check_preprocessed(preprocessed.read_text(), rust)
    check_relocation((evidence / 'rcu-batch-tree-disassembly.txt').read_text(), rust)
    entries = [Path(row).name for row in (evidence / 'rcu-archive.txt').read_text().splitlines()]
    if entries.count('tree.o') != 1 or entries.count('rcu_batch_test.o') != 1:
        raise ValueError('Missing/duplicate C tree or fixture object')
    batch_objects = [name for name in entries if 'batch' in name and name != 'rcu_batch_test.o']
    if batch_objects != (['rcu_batch_rust.o'] if rust else []):
        raise ValueError('Unexpected batch policy archive object')
    symbols(evidence / 'rcu-batch-tree-symbols.txt', HOOKS)
    symbols(evidence / 'rcu-batch-fixture-symbols.txt', FIXTURE)
    symbols(evidence / 'rcu-batch-kernel-symbols.txt', HOOKS + FIXTURE + (BRIDGES if rust else ()))
    tree_text = (evidence / 'rcu-batch-tree-symbols.txt').read_text()
    if any(re.search(r'\b' + bridge + r'$', tree_text, re.M) for bridge in BRIDGES):
        raise ValueError('Rust bridge defined in C tree object')
    if rust:
        symbols(evidence / 'rcu-batch-rust-symbols.txt', BRIDGES)
    elif any(re.search(r'\b' + bridge + r'$', (evidence / 'rcu-batch-kernel-symbols.txt').read_text(), re.M) for bridge in BRIDGES):
        raise ValueError('Rust bridge remains linked in C selection')
    return {'status': 'PASS', 'implementation': 'rust' if rust else 'c',
            'fixture': 'rcu_batch_test.o', 'original_tree_sha256': ORIGINAL_TREE_SHA256,
            'definitions': list(HOOKS + FIXTURE + (BRIDGES if rust else ())),
            'compiled_policy': 'Rust-only forwarding bodies and executable bridge relocations' if rust else 'Original C transaction',
            'scope': 'Source/preprocessor/object/linked selection; runtime acceptance is separate'}



def check_preprocess_record(evidence, source, preprocessed):
    spec = importlib.util.spec_from_file_location('batch_preprocess_proof', Path(__file__).with_name('preprocess-rcu-batch.py'))
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    build = preprocessed.parents[2]
    saved = build / 'kernel/rcu/.tree.o.cmd'
    record = json.loads((evidence / 'rcu-batch-preprocess.json').read_text())
    paths = [saved, build / '.config', build / 'kernel/rcu/tree.o', source]
    expected = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    if record['input_sha256'] != expected or record['preprocessed_sha256'] != hashlib.sha256(preprocessed.read_bytes()).hexdigest():
        raise ValueError('Preprocessor proof input/output hashes differ')
    if record['argv'] != tool.command(saved.read_text(), preprocessed) or record['cwd'] != str(build) or record['output'] != str(preprocessed):
        raise ValueError('Preprocessor command is not derived from actual compilation')
    if record['ignored_post_compile_argv'] != list(tool.OBJTOOL):
        raise ValueError('Unrecognized post-compile command')
    if (evidence / 'rcu-batch-preprocess.exit').read_text().strip() != '0':
        raise ValueError('Preprocessing did not finish successfully')
    if re.search(r'warning:|error:', (evidence / 'rcu-batch-preprocess.log').read_text(), re.I):
        raise ValueError('Preprocessor emitted diagnostics')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('config', 'objects', 'compare'))
    parser.add_argument('--profile')
    parser.add_argument('--config', type=Path)
    parser.add_argument('--c', type=Path)
    parser.add_argument('--rust', type=Path)
    parser.add_argument('--preprocessed', type=Path)
    parser.add_argument('--evidence', type=Path)
    parser.add_argument('--source', type=Path)
    args = parser.parse_args()
    if args.command == 'compare':
        print(json.dumps(compare_configs(args.c.read_text(), args.rust.read_text()), indent=2))
        return
    check_config(args.profile, lists.config_values(args.config.read_text()))
    if args.command == 'objects':
        check_preprocess_record(args.evidence, args.source, args.preprocessed)
        print(json.dumps(check_objects(args.profile, args.evidence, args.source, args.preprocessed), indent=2))


if __name__ == '__main__':
    main()
