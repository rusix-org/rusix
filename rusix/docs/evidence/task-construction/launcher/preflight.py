#!/usr/bin/env python3
"""Read-only identities; no build, cache copy, Docker or guest invocation."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

BASE = Path('/home/aaron/code/rusix')
SOURCE = BASE/'linux-task-construction'
EXPECTED = 'eec5ae3ecd7b9a671157694d0eceaaa89870889e'
IMAGE = 'sha256:c02eb3929889b3f0cc035d57a02c844e0c74c71d24fbda1311249faeb8257f63'
RUN = BASE/'linux-out/task-construction-verification-003'
DRAFT = BASE/'linux-out/task-construction-ffi-retry-draft'


def git(*args):
    return subprocess.check_output(['git', '-C', str(SOURCE), *args], text=True).strip()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_record():
    if git('rev-parse', 'HEAD') != EXPECTED or git('status', '--porcelain'):
        raise ValueError('Source must be clean at exact frozen checkpoint')
    files = git('ls-files', 'rusix', 'kernel/task_construction*', 'kernel/fork.c', 'kernel/Makefile', 'init/Kconfig').splitlines()
    # Snapshot all project tooling/configuration/fixture inputs, not just imports.
    hashes = {name: digest(SOURCE/name) for name in files if (SOURCE/name).is_file()}
    return dict(source=EXPECTED, tree=git('rev-parse', 'HEAD^{tree}'), input_sha256=hashes,
                image=IMAGE, cache_policy='Matching002 kernels are cache only: C complete, Rust interrupted with warnings and inherited C linked images; all proofs/results regenerated')


def verify_prepared():
    from importlib.util import spec_from_file_location, module_from_spec
    spec=spec_from_file_location('cache_prep',DRAFT/'prepare-caches.py')
    module=module_from_spec(spec);spec.loader.exec_module(module)
    module.verify_prepared()


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--require-fresh', action='store_true'); args = ap.parse_args()
    if args.require_fresh:
        verify_prepared()
    print(json.dumps(source_record(), indent=2, sort_keys=True))


if __name__ == '__main__': main()
