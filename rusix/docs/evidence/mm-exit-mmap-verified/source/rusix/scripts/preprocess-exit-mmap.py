#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Capture four actual compiler units under one teardown-source interval."""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
from saved_clang_command import command as saved_command
import exit_mmap_source as extension


def load(name, filename):
    spec=importlib.util.spec_from_file_location(name,Path(__file__).with_name(filename))
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod


vma=load('exit_pre_vma','preprocess-vma-lifecycle.py')
dup=load('exit_pre_dup','preprocess-dup-mmap.py')
copy=load('exit_pre_copy','preprocess-mm-copy.py')
digest=vma.digest


def command(text, output):
    return saved_command(text, output, unit='mm/vma')


def inputs(build, source):
    paths=copy.inputs(build,source)+dup.inputs(build,source)+vma.inputs(build,source)
    paths+=extension.paths(source,extension.ID)+[
        build/'mm/.vma.o.cmd',build/'mm/vma.o',source/'mm/vma.h',source/'mm/vma_internal.h',
        source/'include/asm-generic/tlb.h',source/'include/linux/mmu_notifier.h',
        source/'include/linux/mman.h',source/'include/linux/oom.h',source/'include/linux/mm_inline.h',
        source/'include/linux/mmap_lock.h',source/'include/linux/file.h',
        source/'arch/x86/include/asm/tlb.h',source/'arch/x86/include/asm/mmu_context.h',
        source/'include/trace/events/mmap.h',source/'rusix/scripts/preprocess-exit-mmap.py']
    return list(dict.fromkeys(paths))


def record(build, source):
    return dict(input_sha256={str(p):digest(p) for p in inputs(build,source)},
        argv=command((build/'mm/.vma.o.cmd').read_text(),build/'mm/vma.i'),cwd=str(build),
        output=str(build/'mm/vma.i'),preprocessed_sha256=digest(build/'mm/vma.i'),
        prerequisite_outputs={str(build/name):digest(build/name) for name in
                              ('kernel/fork.i','mm/mmap.i','mm/vma_init.i')})


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build',type=Path,required=True);parser.add_argument('--evidence',type=Path,required=True)
    args=parser.parse_args();build=args.build.resolve();source=Path('/src');evidence=args.evidence.resolve()
    if not build.is_relative_to('/out/builds'):raise ValueError('Expected container output root')
    for name in ('kernel/fork.i','mm/mmap.i','mm/vma_init.i','mm/vma.i'):
        if (build/name).exists():raise ValueError('Refusing stale preprocessor output: '+name)
    evidence.mkdir(parents=True,exist_ok=True)
    extension.validate(source,extension.ID)
    before={str(p):digest(p) for p in inputs(build,source)}
    with (evidence/'exit-mmap-preprocess.log').open('x') as log:
        for script in ('preprocess-mm-copy.py','preprocess-dup-mmap.py','preprocess-vma-lifecycle.py'):
            subprocess.run(['python3','-B',str(source/'rusix/scripts'/script),'--build',str(build),'--evidence',str(evidence)],check=True,stdout=log,stderr=subprocess.STDOUT)
        argv=command((build/'mm/.vma.o.cmd').read_text(),build/'mm/vma.i')
        result=subprocess.run(['bash','/src/rusix/scripts/with-local-tools.sh']+argv,cwd=build,stdout=log,stderr=subprocess.STDOUT)
    (evidence/'exit-mmap-preprocess.exit').write_text(str(result.returncode)+'\n');result.check_returncode()
    actual=record(build,source)
    extension.require_unchanged(inputs(build,source),before)
    (evidence/'exit-mmap-preprocess.json').write_text(json.dumps(actual,indent=2,sort_keys=True)+'\n')


if __name__=='__main__':main()
