#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Capture actual vma_init.c preprocessing through the reviewed saved-Clang parser."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from saved_clang_command import command as saved_command


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(text, output):
    return saved_command(text, output, unit='mm/vma_init')


def inputs(build, source):
    return [build/'mm/.vma_init.o.cmd',build/'.config',build/'mm/vma_init.o',
            build/'include/generated/autoconf.h',source/'mm/vma_init.c',
            source/'mm/vma_lifecycle_impl.h',source/'mm/vma_lifecycle_rust.rs',
            source/'mm/vma_internal.h',source/'mm/vma.h',source/'include/linux/slab.h',source/'include/linux/mmap_lock.h',source/'include/linux/mm_inline.h',source/'include/linux/kref.h',source/'include/linux/refcount.h',source/'include/linux/stddef.h',source/'include/linux/mm.h',source/'include/linux/mm_types.h',
            source/'include/linux/maple_tree.h',source/'include/linux/list.h',
            source/'include/linux/mempolicy.h',source/'include/linux/userfaultfd_k.h',
            source/'include/linux/compiler-version.h',source/'include/linux/kconfig.h',source/'include/linux/compiler_types.h',
            source/'rusix/scripts/preprocess-vma-lifecycle.py',source/'rusix/scripts/saved_clang_command.py',
            source/'rusix/scripts/with-local-tools.sh',source/'rusix/scripts/repo-paths.sh']


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build',type=Path,required=True);parser.add_argument('--evidence',type=Path,required=True)
    args=parser.parse_args();build=args.build.resolve();source=Path('/src')
    if not build.is_relative_to('/out/builds'):raise ValueError('Expected /out/builds container path')
    output=build/'mm/vma_init.i'
    if output.exists():raise ValueError('Refusing stale vma_init.i')
    args.evidence.mkdir(parents=True,exist_ok=True)
    before={str(p):digest(p) for p in inputs(build,source)}
    argv=command((build/'mm/.vma_init.o.cmd').read_text(),output)
    with (args.evidence/'vma-lifecycle-preprocess.log').open('x') as log:
        result=subprocess.run(['bash','/src/rusix/scripts/with-local-tools.sh']+argv,cwd=build,stdout=log,stderr=subprocess.STDOUT)
    (args.evidence/'vma-lifecycle-preprocess.exit').write_text(str(result.returncode)+'\n');result.check_returncode()
    if before!={str(p):digest(p) for p in inputs(build,source)}:raise ValueError('Preprocessor inputs changed')
    record=dict(argv=argv,cwd=str(build),input_sha256=before,output=str(output),preprocessed_sha256=digest(output))
    (args.evidence/'vma-lifecycle-preprocess.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')


if __name__=='__main__':main()
