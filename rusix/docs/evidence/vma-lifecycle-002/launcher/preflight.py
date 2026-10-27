#!/usr/bin/env python3
"""Read-only identities; no build, cache copy, Docker or guest invocation."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

BASE = Path('/home/aaron/code/rusix')
SOURCE = BASE/'linux-vma-lifecycle'
EXPECTED = 'e0632d27293ba2e5b2eff3bc8baec405d8d4a233'
REVIEWED_LAUNCH_READY = True
IMAGE = 'sha256:c02eb3929889b3f0cc035d57a02c844e0c74c71d24fbda1311249faeb8257f63'
RUN = BASE/'linux-out/vma-lifecycle-verification-002'
DRAFT = BASE/'linux-out/vma-lifecycle-retry-draft'


def git(*args):
    return subprocess.check_output(['git', '-C', str(SOURCE), *args], text=True).strip()


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def prerequisite_record():
    """Host-only validation; future acceptance bytes are captured, never assumed."""
    checker = BASE/'linux-out/vma-upstream-baseline-draft/check.py'
    manifest = BASE/'linux-out/vma-upstream-baseline-001/inputs/manifest.json'
    expected = {
        checker: 'b9b606422b9f13ba87ef07fe24dc6140ea332c8e08cc8523b102f84d6d6c7e7c',
        manifest: '951c7bd0d8c0faab72e8c0f3d714b41ca1131a5dbb6481bb9e8a727bfadff0a3',
    }
    for path, value in expected.items():
        if digest(path) != value:
            raise ValueError('Reviewed prerequisite input changed: '+str(path))
    m = json.loads(manifest.read_text())
    for name, value in m['tooling_provenance_sha256'].items():
        path = BASE/'linux-out/vma-tooling-001'/name
        if digest(path) != value:
            raise ValueError('Prerequisite tooling provenance changed')
        expected[path] = value
    execution = BASE/'linux-out/vma-upstream-baseline-001/execution'
    if (execution/'launcher.exit').read_text().strip() != '0':
        raise ValueError('Upstream baseline launcher did not pass')
    checked = subprocess.run(['python3','-B',str(checker),'--results'], check=True,
                             capture_output=True, text=True)
    actual = json.loads(checked.stdout)
    if checked.stderr or actual.get('status') != 'PASS' or actual != json.loads((execution/'acceptance.json').read_text()):
        raise ValueError('Saved baseline acceptance differs from actual checked result')
    # The pinned checker verifies the entire input/build trees. Capture all
    # execution control, command, result and artifact-inventory records too.
    for path in execution.iterdir():
        if path.is_symlink():
            raise ValueError('Unexpected prerequisite record symlink')
        if path.is_file():
            expected[path] = digest(path)
    for line in (execution/'launcher.sha256').read_text().splitlines():
        value, name = line.split('  ', 1)
        path = Path(name)
        if digest(path) != value:
            raise ValueError('Baseline launcher input changed')
        expected[path] = value
    for path, value in expected.items():
        if digest(path) != value:
            raise ValueError('Prerequisite changed during verification')
    return dict(status='PASS', acceptance=actual,
                input_sha256={str(p):v for p,v in sorted(expected.items())})


def source_record():
    if not __import__('re').fullmatch('[0-9a-f]{40}', EXPECTED):
        raise ValueError('Root review and committed source identity are pending')
    if git('rev-parse', 'HEAD') != EXPECTED or git('status', '--porcelain'):
        raise ValueError('Source must be clean at exact frozen checkpoint')
    files = git('ls-files', 'rusix', 'kernel/task_construction*', 'kernel/mm_construction*', 'kernel/mm_release*', 'kernel/mm_copy*', 'kernel/fork.c', 'mm/mmap.c', 'mm/vma_init.c', 'mm/vma_lifecycle*', 'mm/dup_mmap*', 'mm/Makefile', 'mm/internal.h', 'kernel/Makefile', 'init/Kconfig').splitlines()
    # Snapshot all project tooling/configuration/fixture inputs, not just imports.
    hashes = {name: digest(SOURCE/name) for name in files if (SOURCE/name).is_file()}
    return dict(source=EXPECTED, tree=git('rev-parse', 'HEAD^{tree}'), input_sha256=hashes,
                prerequisite_sha256=digest(RUN/'prerequisite-before.json') if (RUN/'prerequisite-before.json').is_file() else None,
                image=IMAGE, cache_policy='Fresh builds; no seed objects copied')


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--require-fresh', action='store_true'); ap.add_argument('--prerequisite', action='store_true'); args = ap.parse_args()
    if args.prerequisite:
        print(json.dumps(prerequisite_record(), indent=2, sort_keys=True)); return
    if args.require_fresh and not REVIEWED_LAUNCH_READY:
        raise ValueError('Root launch review is pending')
    if args.require_fresh:
        prerequisite_record()
    if args.require_fresh and RUN.exists(): raise ValueError('Fresh output root already exists')
    print(json.dumps(source_record(), indent=2, sort_keys=True))


if __name__ == '__main__': main()
