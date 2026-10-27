#!/usr/bin/env python3
"""Read-only identities; no build, cache copy, Docker or guest invocation."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

BASE = Path('/home/aaron/code/rusix')
SOURCE = BASE/'linux-mm-copy'
EXPECTED = '32e7c3e7b0ae825b84416b260098c2d98cd45865'
REVIEWED_LAUNCH_READY = True
IMAGE = 'sha256:c02eb3929889b3f0cc035d57a02c844e0c74c71d24fbda1311249faeb8257f63'
RUN = BASE/'linux-out/mm-copy-verification-001'
DRAFT = BASE/'linux-out/mm-copy-verification-draft'


def git(*args):
    return subprocess.check_output(['git', '-C', str(SOURCE), *args], text=True).strip()


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def source_record():
    if not __import__('re').fullmatch('[0-9a-f]{40}', EXPECTED):
        raise ValueError('Root review and committed source identity are pending')
    if git('rev-parse', 'HEAD') != EXPECTED or git('status', '--porcelain'):
        raise ValueError('Source must be clean at exact frozen checkpoint')
    files = git('ls-files', 'rusix', 'kernel/task_construction*', 'kernel/mm_construction*', 'kernel/mm_release*', 'kernel/mm_copy*', 'kernel/fork.c', 'kernel/Makefile', 'init/Kconfig').splitlines()
    # Snapshot all project tooling/configuration/fixture inputs, not just imports.
    hashes = {name: digest(SOURCE/name) for name in files if (SOURCE/name).is_file()}
    return dict(source=EXPECTED, tree=git('rev-parse', 'HEAD^{tree}'), input_sha256=hashes,
                image=IMAGE, cache_policy='Fresh builds; no seed objects copied')


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--require-fresh', action='store_true'); args = ap.parse_args()
    if args.require_fresh and not REVIEWED_LAUNCH_READY:
        raise ValueError('Root launch review is pending')
    if args.require_fresh and RUN.exists(): raise ValueError('Fresh output root already exists')
    print(json.dumps(source_record(), indent=2, sort_keys=True))


if __name__ == '__main__': main()
