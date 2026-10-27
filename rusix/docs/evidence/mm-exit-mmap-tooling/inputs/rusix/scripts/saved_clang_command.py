#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Strict saved Clang argv parser shared by constructor verification.

Derived from preprocess-rcu-batch.py SHA256 e87dfbeca470f81e2fc3d46527e94dc512affe2f761ca301a2231977cb3f3d55.
Only the translation-unit path and observed server hardening flags are generalized.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import subprocess

# Reviewed pinned Clang/x86_64 arguments. Unknown switches fail closed instead of
# being forwarded to a compiler/plugin or silently dropped from the proof.
ALLOWED_FLAGS = frozenset(('-nostdinc', '-I/src/arch/x86/include', '-I./arch/x86/include/generated', '-I/src/include', '-I./include', '-I/src/arch/x86/include/uapi', '-I./arch/x86/include/generated/uapi', '-I/src/include/uapi', '-I./include/generated/uapi', '-D__KERNEL__', '--target=x86_64-linux-gnu', '-fintegrated-as', '-Werror=unknown-warning-option', '-Werror=ignored-optimization-argument', '-Werror=option-ignored', '-Werror=unused-command-line-argument', '-fmacro-prefix-map=/src/=', '-std=gnu11', '-fshort-wchar', '-funsigned-char', '-fno-common', '-fno-PIE', '-fno-strict-aliasing', '-mno-sse', '-mno-mmx', '-mno-sse2', '-mno-3dnow', '-mno-avx', '-mno-sse4a', '-fcf-protection=none', '-m64', '-falign-loops=1', '-mno-80387', '-mno-fp-ret-in-387', '-mstack-alignment=8', '-mskip-rax-setup', '-march=x86-64', '-mtune=generic', '-mno-red-zone', '-mcmodel=kernel', '-Wno-sign-compare', '-fno-asynchronous-unwind-tables', '-fno-delete-null-pointer-checks', '-O2', '-fno-stack-protector', '-fomit-frame-pointer', '-ftrivial-auto-var-init=zero', '-fno-stack-clash-protection', '-falign-functions=16', '-fstrict-flex-arrays=3', '-fno-strict-overflow', '-fno-stack-check', '-fno-builtin-wcslen', '-Wall', '-Wextra', '-Wundef', '-Werror=implicit-function-declaration', '-Werror=implicit-int', '-Werror=return-type', '-Werror=strict-prototypes', '-Wno-format-security', '-Wno-trigraphs', '-Wno-frame-address', '-Wno-address-of-packed-member', '-Wmissing-declarations', '-Wmissing-prototypes', '-Wframe-larger-than=2048', '-Wno-gnu', '-Wno-format-overflow-non-kprintf', '-Wno-format-truncation-non-kprintf', '-Wno-pointer-sign', '-Wcast-function-type', '-Wimplicit-fallthrough', '-Werror=date-time', '-Werror=incompatible-pointer-types', '-Wenum-conversion', '-Wunused', '-Wno-unused-but-set-variable', '-Wno-unused-const-variable', '-Wno-format-overflow', '-Wno-override-init', '-Wno-pointer-to-enum-cast', '-Wno-tautological-constant-out-of-range-compare', '-Wno-unaligned-access', '-Wno-enum-compare-conditional', '-Wno-missing-field-initializers', '-Wno-type-limits', '-Wno-shift-negative-value', '-Wno-enum-enum-conversion', '-Wno-sign-compare', '-Wno-unused-parameter', '-I/src/kernel', '-Ikernel', '-DKBUILD_MODFILE="kernel/fork"', '-DKBUILD_BASENAME="fork"', '-DKBUILD_MODNAME="fork"', '-D__KBUILD_MODNAME=kmod_fork'))
ALLOWED_FLAGS = ALLOWED_FLAGS | frozenset(['-mstack-protector-guard-reg=gs', '-mstack-protector-guard-symbol=__ref_stack_chk_guard', '-mretpoline-external-thunk', '-mindirect-branch-cs-prefix', '-mfunction-return=thunk-extern', '-fpatchable-function-entry=16,16', '-fstack-protector-strong'])
REQUIRED_INCLUDES = ('/src/include/linux/compiler-version.h', '/src/include/linux/kconfig.h', '/src/include/linux/compiler_types.h')
PLAIN_OBJTOOL = ('./tools/objtool/objtool', '--hacks=jump_label', '--hacks=noinstr', '--orc', '--static-call', '--uaccess', 'kernel/fork.o')

HARDENED_OBJTOOL = ('./tools/objtool/objtool', '--hacks=jump_label', '--hacks=noinstr', '--hacks=skylake', '--orc', '--retpoline', '--rethunk', '--static-call', '--uaccess', '--prefix=16', 'kernel/fork.o')


def command(text, output, unit='kernel/fork'):
    if unit not in ('kernel/fork', 'mm/mmap', 'mm/vma_init', 'mm/vma'):
        raise ValueError('Unreviewed translation unit')
    directory, basename = unit.split('/')
    object_name = unit + '.o'
    source_name = '/src/' + unit + '.c'
    fork_flags = frozenset(('-I/src/kernel', '-Ikernel', '-DKBUILD_MODFILE="kernel/fork"',
                            '-DKBUILD_BASENAME="fork"', '-DKBUILD_MODNAME="fork"',
                            '-D__KBUILD_MODNAME=kmod_fork'))
    unit_flags = frozenset((f'-I/src/{directory}', f'-I{directory}',
                            f'-DKBUILD_MODFILE="{unit}"', f'-DKBUILD_BASENAME="{basename}"',
                            f'-DKBUILD_MODNAME="{basename}"', f'-D__KBUILD_MODNAME=kmod_{basename}'))
    allowed = (ALLOWED_FLAGS - fork_flags) | unit_flags
    rows = text.splitlines()
    prefix = f'savedcmd_{object_name} := '
    saved = [row[len(prefix):] for row in rows if row.startswith(prefix)]
    sources = [row for row in rows if row.startswith(f'source_{object_name} := ')]
    if len(saved) != 1 or sources != [f'source_{object_name} := {source_name}']:
        raise ValueError('Unexpected actual compiler/source record')
    lexer = shlex.shlex(saved[0], posix=True, punctuation_chars=';&|<>')
    lexer.whitespace_split = True
    argv = list(lexer)
    # The known objtool post-pass is recorded but never executed by this tool.
    if argv.count(';') != 1:
        raise ValueError('Missing/extra compiler command separator')
    split = argv.index(';')
    if tuple(argv[split + 1:]) not in tuple(command[:-1] + (object_name,)
                                         for command in (PLAIN_OBJTOOL, HARDENED_OBJTOOL)):
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
            if i + 1 >= len(argv) or argv[i+1] != object_name:
                raise ValueError('Wrong compiled object output')
            output_count += 1; i += 2; continue
        if item == '-c': compile_count += 1
        elif item == f'-Wp,-MMD,{directory}/.{basename}.o.d': dep_count += 1
        elif item == source_name:
            source_count += 1; retained.append(item)
        elif item in allowed: retained.append(item)
        else: raise ValueError('Unapproved compiler switch or shell token: ' + item)
        i += 1
    if (source_count, compile_count, output_count, dep_count) != (1,1,1,1):
        raise ValueError('Ambiguous compile/source/output/dependency arguments')
    if tuple(includes) != REQUIRED_INCLUDES:
        raise ValueError('Wrong generated configuration/compiler includes')
    # No options from untrusted shell expansion are interpreted or evaluated.
    return retained + ['-E', '-o', str(output)]
