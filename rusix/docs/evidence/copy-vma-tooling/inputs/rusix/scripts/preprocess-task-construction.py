#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Capture fork.c preprocessing from its actual pinned Clang command; never shell-evaluate it."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from saved_clang_command import command


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inputs(build, source):
    return [build/'kernel/.fork.o.cmd', build/'.config', build/'kernel/fork.o',
            source/'kernel/fork.c', source/'kernel/task_construction_impl.h',
            source/'kernel/task_construction_rust.rs',
            source/'rusix/scripts/saved_clang_command.py',
            source/'rusix/scripts/preprocess-task-construction.py',
            source/'rusix/scripts/with-local-tools.sh', source/'rusix/scripts/repo-paths.sh',
            build/'include/generated/autoconf.h',
            source/'include/linux/compiler-version.h', source/'include/linux/kconfig.h',
            source/'include/linux/compiler_types.h']


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--build', type=Path, required=True)
    ap.add_argument('--evidence', type=Path, required=True)
    args = ap.parse_args()
    build = args.build.resolve()
    if not build.is_relative_to('/out/builds'):
        raise ValueError('Expected container build directory below /out/builds')
    output = build/'kernel/fork.i'
    if output.exists():
        raise ValueError('Refusing stale preprocessing output')
    args.evidence.mkdir(parents=True, exist_ok=True)
    before = {str(p): digest(p) for p in inputs(build, Path('/src'))}
    argv = command((build/'kernel/.fork.o.cmd').read_text(), output)
    with (args.evidence/'task-preprocess.log').open('x') as log:
        result = subprocess.run(['bash', '/src/rusix/scripts/with-local-tools.sh'] + argv,
                                cwd=build, stdout=log, stderr=subprocess.STDOUT)
    (args.evidence/'task-preprocess.exit').write_text(str(result.returncode)+'\n')
    result.check_returncode()
    if before != {str(p): digest(p) for p in inputs(build, Path('/src'))}:
        raise ValueError('Inputs changed during preprocessing')
    record = dict(argv=argv, cwd=str(build), input_sha256=before,
                  output=str(output), preprocessed_sha256=digest(output))
    (args.evidence/'task-preprocess.json').write_text(json.dumps(record, indent=2, sort_keys=True)+'\n')


if __name__ == '__main__':
    main()
