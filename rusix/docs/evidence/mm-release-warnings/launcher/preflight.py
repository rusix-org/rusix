#!/usr/bin/env python3
"""Read-only identities; no build, cache copy, Docker or guest invocation."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

BASE = Path('/home/aaron/code/rusix')
SOURCE = BASE/'linux-mm-release'
EXPECTED = '42318e69e5f27a2f2363c0fea285cca59f710baf'
IMAGE = 'sha256:c02eb3929889b3f0cc035d57a02c844e0c74c71d24fbda1311249faeb8257f63'
RUN = BASE/'linux-out/mm-release-verification-002'
DRAFT = BASE/'linux-out/mm-release-retry-draft'


def git(*args):
    return subprocess.check_output(['git', '-C', str(SOURCE), *args], text=True).strip()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_record():
    if git('rev-parse', 'HEAD') != EXPECTED or git('status', '--porcelain'):
        raise ValueError('Source must be clean at exact frozen checkpoint')
    files = git('ls-files', 'rusix', 'kernel/task_construction*', 'kernel/mm_construction*', 'kernel/fork.c', 'kernel/Makefile', 'init/Kconfig', 'kernel/mm_release*', 'rust/helpers', 'rust/kernel', 'rust/bindings', 'rust/Makefile', 'tools/testing/kunit').splitlines()
    # Snapshot all project tooling/configuration/fixture inputs, not just imports.
    hashes = {name: digest(SOURCE/name) for name in files if (SOURCE/name).is_file()}
    return dict(source=EXPECTED, tree=git('rev-parse', 'HEAD^{tree}'), input_sha256=hashes,
                image=IMAGE, cache_policy='Fresh builds; no seed objects copied')


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--require-fresh', action='store_true'); args = ap.parse_args()
    if args.require_fresh and RUN.exists(): raise ValueError('Fresh output root already exists')
    print(json.dumps(source_record(), indent=2, sort_keys=True))


if __name__ == '__main__': main()
