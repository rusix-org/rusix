#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Preprocess Tree RCU using strictly parsed actual compile arguments, never a shell."""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import subprocess

# Reviewed pinned Clang/x86_64 arguments. Unknown switches fail closed instead of
# being forwarded to a compiler/plugin or silently dropped from the proof.
ALLOWED_FLAGS = frozenset(('-nostdinc', '-I/src/arch/x86/include', '-I./arch/x86/include/generated', '-I/src/include', '-I./include', '-I/src/arch/x86/include/uapi', '-I./arch/x86/include/generated/uapi', '-I/src/include/uapi', '-I./include/generated/uapi', '-D__KERNEL__', '--target=x86_64-linux-gnu', '-fintegrated-as', '-Werror=unknown-warning-option', '-Werror=ignored-optimization-argument', '-Werror=option-ignored', '-Werror=unused-command-line-argument', '-fmacro-prefix-map=/src/=', '-std=gnu11', '-fshort-wchar', '-funsigned-char', '-fno-common', '-fno-PIE', '-fno-strict-aliasing', '-mno-sse', '-mno-mmx', '-mno-sse2', '-mno-3dnow', '-mno-avx', '-mno-sse4a', '-fcf-protection=none', '-m64', '-falign-loops=1', '-mno-80387', '-mno-fp-ret-in-387', '-mstack-alignment=8', '-mskip-rax-setup', '-march=x86-64', '-mtune=generic', '-mno-red-zone', '-mcmodel=kernel', '-Wno-sign-compare', '-fno-asynchronous-unwind-tables', '-fno-delete-null-pointer-checks', '-O2', '-fno-stack-protector', '-fomit-frame-pointer', '-ftrivial-auto-var-init=zero', '-fno-stack-clash-protection', '-falign-functions=16', '-fstrict-flex-arrays=3', '-fno-strict-overflow', '-fno-stack-check', '-fno-builtin-wcslen', '-Wall', '-Wextra', '-Wundef', '-Werror=implicit-function-declaration', '-Werror=implicit-int', '-Werror=return-type', '-Werror=strict-prototypes', '-Wno-format-security', '-Wno-trigraphs', '-Wno-frame-address', '-Wno-address-of-packed-member', '-Wmissing-declarations', '-Wmissing-prototypes', '-Wframe-larger-than=2048', '-Wno-gnu', '-Wno-format-overflow-non-kprintf', '-Wno-format-truncation-non-kprintf', '-Wno-pointer-sign', '-Wcast-function-type', '-Wimplicit-fallthrough', '-Werror=date-time', '-Werror=incompatible-pointer-types', '-Wenum-conversion', '-Wunused', '-Wno-unused-but-set-variable', '-Wno-unused-const-variable', '-Wno-format-overflow', '-Wno-override-init', '-Wno-pointer-to-enum-cast', '-Wno-tautological-constant-out-of-range-compare', '-Wno-unaligned-access', '-Wno-enum-compare-conditional', '-Wno-missing-field-initializers', '-Wno-type-limits', '-Wno-shift-negative-value', '-Wno-enum-enum-conversion', '-Wno-sign-compare', '-Wno-unused-parameter', '-I/src/kernel/rcu', '-Ikernel/rcu', '-DKBUILD_MODFILE="kernel/rcu/tree"', '-DKBUILD_BASENAME="tree"', '-DKBUILD_MODNAME="tree"', '-D__KBUILD_MODNAME=kmod_tree'))
REQUIRED_INCLUDES = ('/src/include/linux/compiler-version.h', '/src/include/linux/kconfig.h', '/src/include/linux/compiler_types.h')
OBJTOOL = ('./tools/objtool/objtool', '--hacks=jump_label', '--hacks=noinstr', '--orc', '--static-call', '--uaccess', 'kernel/rcu/tree.o')


def command(text, output):
    rows = text.splitlines()
    prefix = 'savedcmd_kernel/rcu/tree.o := '
    saved = [row[len(prefix):] for row in rows if row.startswith(prefix)]
    sources = [row for row in rows if row.startswith('source_kernel/rcu/tree.o := ')]
    if len(saved) != 1 or sources != ['source_kernel/rcu/tree.o := /src/kernel/rcu/tree.c']:
        raise ValueError('Unexpected actual compiler/source record')
    lexer = shlex.shlex(saved[0], posix=True, punctuation_chars=';&|<>')
    lexer.whitespace_split = True
    argv = list(lexer)
    # The known objtool post-pass is recorded but never executed by this tool.
    if argv.count(';') != 1:
        raise ValueError('Missing/extra compiler command separator')
    split = argv.index(';')
    if tuple(argv[split + 1:]) != OBJTOOL:
        raise ValueError('Unexpected post-compile command')
    argv = argv[:split]
    if not argv or argv[0] != 'clang':
        raise ValueError('Unexpected compiler path')
    includes, retained = [], ['clang']
    source_count = compile_count = output_count = dep_count = 0
    i = 1
    while i < len(argv):
        item = argv[i]
        if item == '-include':
            if i + 1 >= len(argv): raise ValueError('Missing include operand')
            includes.append(argv[i+1]); retained.extend(argv[i:i+2]); i += 2; continue
        if item == '-o':
            if i + 1 >= len(argv) or argv[i+1] != 'kernel/rcu/tree.o':
                raise ValueError('Wrong compiled object output')
            output_count += 1; i += 2; continue
        if item == '-c': compile_count += 1
        elif item == '-Wp,-MMD,kernel/rcu/.tree.o.d': dep_count += 1
        elif item == '/src/kernel/rcu/tree.c':
            source_count += 1; retained.append(item)
        elif item in ALLOWED_FLAGS: retained.append(item)
        else: raise ValueError('Unapproved compiler switch or shell token: ' + item)
        i += 1
    if (source_count, compile_count, output_count, dep_count) != (1,1,1,1):
        raise ValueError('Ambiguous compile/source/output/dependency arguments')
    if tuple(includes) != REQUIRED_INCLUDES:
        raise ValueError('Wrong generated configuration/compiler includes')
    # No options from untrusted shell expansion are interpreted or evaluated.
    return retained + ['-E', '-o', str(output)]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    args = parser.parse_args()
    build = args.build.resolve()
    if not build.is_relative_to('/out/builds'):
        raise ValueError('Expected container build path')
    saved = build / 'kernel/rcu/.tree.o.cmd'
    output = build / 'kernel/rcu/tree.i'
    paths = [saved, build/'.config', build/'kernel/rcu/tree.o', Path('/src/kernel/rcu/tree.c')]
    before = {str(p):digest(p) for p in paths}
    argv = command(saved.read_text(), output)
    wrapper = ['bash', '/src/rusix/scripts/with-local-tools.sh']
    with (args.evidence/'rcu-batch-preprocess.log').open('w') as log:
        result = subprocess.run(wrapper + argv, cwd=build, stdout=log, stderr=subprocess.STDOUT)
    (args.evidence/'rcu-batch-preprocess.exit').write_text(str(result.returncode)+'\n')
    result.check_returncode()
    if before != {str(p):digest(p) for p in paths}:
        raise ValueError('Compile inputs/object changed during preprocessing')
    record = {'scope':'Actual saved compiler arguments with only compile/dependency output switches replaced by -E',
              'argv':argv,'cwd':str(build),'input_sha256':before,'preprocessed_sha256':digest(output),
              'output':str(output),'ignored_post_compile_argv':list(OBJTOOL)}
    (args.evidence/'rcu-batch-preprocess.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')


if __name__ == '__main__': main()
