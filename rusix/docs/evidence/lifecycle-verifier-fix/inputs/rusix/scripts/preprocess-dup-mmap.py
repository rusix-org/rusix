#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Capture actual mmap.c preprocessing through the reviewed saved-Clang parser."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from saved_clang_command import command as saved_command


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(text, output):
    return saved_command(text, output, unit='mm/mmap')


def inputs(build, source):
    return [build/'mm/.mmap.o.cmd',build/'.config',build/'mm/mmap.o',
            build/'include/generated/autoconf.h',source/'mm/mmap.c',
            source/'mm/dup_mmap_impl.h',source/'mm/dup_mmap_rust.rs',
            source/'mm/internal.h',source/'include/linux/mm.h',source/'include/linux/mm_types.h',
            source/'include/linux/maple_tree.h',source/'include/linux/list.h',
            source/'include/linux/mempolicy.h',source/'include/linux/userfaultfd_k.h',
            source/'include/linux/compiler-version.h',source/'include/linux/kconfig.h',source/'include/linux/compiler_types.h',
            source/'rusix/scripts/preprocess-dup-mmap.py',source/'rusix/scripts/saved_clang_command.py',
            source/'rusix/scripts/with-local-tools.sh',source/'rusix/scripts/repo-paths.sh']


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build',type=Path,required=True);parser.add_argument('--evidence',type=Path,required=True)
    args=parser.parse_args();build=args.build.resolve();source=Path('/src')
    if not build.is_relative_to('/out/builds'):raise ValueError('Expected /out/builds container path')
    output=build/'mm/mmap.i'
    if output.exists():raise ValueError('Refusing stale mmap.i')
    args.evidence.mkdir(parents=True,exist_ok=True)
    before={str(p):digest(p) for p in inputs(build,source)}
    argv=command((build/'mm/.mmap.o.cmd').read_text(),output)
    with (args.evidence/'dup-mmap-preprocess.log').open('x') as log:
        result=subprocess.run(['bash','/src/rusix/scripts/with-local-tools.sh']+argv,cwd=build,stdout=log,stderr=subprocess.STDOUT)
    (args.evidence/'dup-mmap-preprocess.exit').write_text(str(result.returncode)+'\n');result.check_returncode()
    if before!={str(p):digest(p) for p in inputs(build,source)}:raise ValueError('Preprocessor inputs changed')
    record=dict(argv=argv,cwd=str(build),input_sha256=before,output=str(output),preprocessed_sha256=digest(output))
    (args.evidence/'dup-mmap-preprocess.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')


if __name__=='__main__':main()
