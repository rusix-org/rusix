#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Capture fork.c preprocessing from its actual pinned Clang command; never shell-evaluate it."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from saved_clang_command import command
import importlib.util
spec = importlib.util.spec_from_file_location('mm_task_preprocess', Path(__file__).with_name('preprocess-mm-release.py'))
task = importlib.util.module_from_spec(spec)
spec.loader.exec_module(task)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inputs(build, source):
    return task.inputs(build, source) + [source/'kernel/mm_copy_impl.h',
        source/'kernel/mm_copy_rust.rs', source/'include/linux/sched/task.h', source/'include/uapi/linux/sched.h',
        source/'rusix/scripts/preprocess-mm-copy.py']


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
    with (args.evidence/'mm-copy-preprocess.log').open('x') as log:
        result = subprocess.run(['bash', '/src/rusix/scripts/with-local-tools.sh'] + argv,
                                cwd=build, stdout=log, stderr=subprocess.STDOUT)
    (args.evidence/'mm-copy-preprocess.exit').write_text(str(result.returncode)+'\n')
    result.check_returncode()
    if before != {str(p): digest(p) for p in inputs(build, Path('/src'))}:
        raise ValueError('Inputs changed during preprocessing')
    record = dict(argv=argv, cwd=str(build), input_sha256=before,
                  output=str(output), preprocessed_sha256=digest(output))
    (args.evidence/'mm-copy-preprocess.json').write_text(json.dumps(record, indent=2, sort_keys=True)+'\n')


if __name__ == '__main__':
    main()
