#!/usr/bin/env python3
"""Read-only identities; no build, cache copy, Docker or guest invocation."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

BASE = Path('/home/aaron/code/rusix')
SOURCE = BASE/'linux-mm-exit-mmap-fix'
# The reviewed metadata repair makes every promised archive record Git-complete.
HISTORICAL_EVIDENCE = SOURCE/'rusix/docs/evidence'
EXPECTED = '8b6ab8382784f5873e416d5bdadae62b4565bb2d'
PREVIOUS_SOURCE = '247da0572e899f8c9e721e1c605a4c5f298bc7ef'
CONFIG_SOURCE = '8ec785568045a3cd2245e87d1854a7f5ab664ef3'
CONFIG_MANIFEST_SHA = '9d4f11d40683a9f405cf7a83a44665fb167b081b3ced6660b08819d39e912d06'
REVIEWED_LAUNCH_READY = True
# Final documented source; launch still requires root review.
IMAGE = 'sha256:c02eb3929889b3f0cc035d57a02c844e0c74c71d24fbda1311249faeb8257f63'
PROFILES = {'ordinary-c':'exit-mmap-c', 'ordinary-rust':'exit-mmap-rust',
            'kunit-c':'exit-mmap-kunit-c', 'kunit-rust':'exit-mmap-kunit-rust'}
RUN = BASE/'linux-out/mm-exit-mmap-verification-002'
DRAFT = BASE/'linux-out/mm-exit-mmap-verification-retry-draft'


def git(*args):
    return subprocess.check_output(['git', '-C', str(SOURCE), *args], text=True).strip()


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def config_prerequisite(*, raw=False):
    """Reference the accepted config archive; never copy its evidence recursively."""
    archive = HISTORICAL_EVIDENCE/'mm-exit-mmap-config'
    manifest = archive/'manifest.json'
    if digest(manifest) != CONFIG_MANIFEST_SHA:
        raise ValueError('Config prerequisite manifest identity changed')
    m = json.loads(manifest.read_text())
    if m['source'] != CONFIG_SOURCE or m['status'] != 'PASS':
        raise ValueError('Config prerequisite source/status mismatch')
    for name, sha in m['files'].items():
        if digest(archive/name) != sha:
            raise ValueError(f'Config archive record drift: {name}')
    result_path = archive/'records/builds/result.json'
    result = json.loads(result_path.read_text())
    if result != m['result'] or result['status'] != 'PASS' or result['source'] != CONFIG_SOURCE:
        raise ValueError('Config result differs from manifest')
    if result['inputs_before_sha256'] != result['inputs_after_sha256']:
        raise ValueError('Config source inputs changed during resolution')
    if set(result['config_sha256']) != set(PROFILES.values()):
        raise ValueError('Incomplete config prerequisite')
    for name, sha in result['config_sha256'].items():
        if digest(archive/f'records/builds/{name}/.config') != sha:
            raise ValueError('Resolved config identity mismatch')
    for name in ('container.exit', 'launcher.exit'):
        if (archive/'records'/name).read_text().strip() != '0':
            raise ValueError('Config prerequisite did not terminate successfully')
    if (archive/'records/source.commit').read_text().strip() != CONFIG_SOURCE:
        raise ValueError('Config source record mismatch')
    subprocess.run(['git', '-C', str(SOURCE), 'merge-base', '--is-ancestor', CONFIG_SOURCE, EXPECTED], check=True)
    changed = git('diff', '--name-only', CONFIG_SOURCE, PREVIOUS_SOURCE).splitlines()
    if not changed or any(name not in ('rusix/AGENTS.md', 'rusix/PROGRESS.md') and
                          not name.startswith('rusix/docs/evidence/mm-exit-mmap-config/') for name in changed):
        raise ValueError('Config-tested source has non-documentation changes')
    if raw:
        # Host-only before/after audit. Generated markers remain hash-only here.
        for field in ('raw_input_sha256', 'retained_binary_sha256'):
            for name, sha in m[field].items():
                expected_sha = sha['sha256'] if field == 'retained_binary_sha256' else sha
                if digest(Path(name)) != expected_sha:
                    raise ValueError(f'Config retained input drift: {name}')
                if field == 'retained_binary_sha256' and Path(name).stat().st_size != sha['bytes']:
                    raise ValueError(f'Config retained artifact size drift: {name}')
        raw_root = BASE/'linux-out/mm-exit-mmap-config-001'
        for suffix in ('before', 'after'):
            if digest(raw_root/f'builds/inputs-{suffix}.json') != result[f'inputs_{suffix}_sha256']:
                raise ValueError('Config source inventory identity mismatch')
    return dict(manifest=str(manifest), manifest_sha256=CONFIG_MANIFEST_SHA,
                tested_source=CONFIG_SOURCE, candidate_source=EXPECTED,
                result_sha256=digest(result_path),
                inputs_before_sha256=result['inputs_before_sha256'],
                inputs_after_sha256=result['inputs_after_sha256'],
                config_sha256=result['config_sha256'], documentation_only_delta_to_previous=changed,
                reviewed_tooling_delta=tooling_delta(),
                archive_records=len(m['files']), raw_records=len(m['raw_input_sha256']),
                retained_artifacts=len(m['retained_binary_sha256']),
                scope='Kconfig resolution only; candidate kernel and VM verification pending')



def tooling_delta():
    review = json.loads((DRAFT/'source-continuity.json').read_text())
    if review['base'] != PREVIOUS_SOURCE or review['candidate'] != EXPECTED:
        raise ValueError('Wrong tooling continuity endpoints')
    changed = git('diff', '--name-only', PREVIOUS_SOURCE, EXPECTED).splitlines()
    if changed != sorted(review['changed_sha256']):
        raise ValueError('Tooling delta inventory changed')
    for name, sha in review['changed_sha256'].items():
        if digest(SOURCE/name) != sha:
            raise ValueError('Reviewed tooling delta changed: '+name)
    archive = HISTORICAL_EVIDENCE/'lifecycle-verifier-fix'
    manifest = json.loads((archive/'manifest.json').read_text())
    for name, sha in manifest['files'].items():
        if digest(archive/name) != sha:
            raise ValueError('Inherited fix evidence changed: '+name)
    return dict(review_sha256=digest(DRAFT/'source-continuity.json'),
                base=PREVIOUS_SOURCE, candidate=EXPECTED,
                kernel_config_fixture_changes=False,
                changed_sha256=review['changed_sha256'])


def source_record():
    if git('rev-parse', 'HEAD') != EXPECTED or git('status', '--porcelain'):
        raise ValueError('Source must be clean at exact frozen checkpoint')
    files = git('ls-files', 'rusix', 'kernel/task_construction*', 'kernel/mm_construction*', 'kernel/fork.c', 'mm', 'include/kunit/test.h', 'kernel/Makefile', 'init/Kconfig', 'kernel/mm_release*', 'rust/helpers', 'rust/kernel', 'rust/bindings', 'rust/Makefile', 'tools/testing/kunit').splitlines()
    # Snapshot all project tooling/configuration/fixture inputs, not just imports.
    hashes = {name: digest(SOURCE/name) for name in files if (SOURCE/name).is_file() and not name.startswith('rusix/docs/evidence/')}
    return dict(source=EXPECTED, tree=git('rev-parse', 'HEAD^{tree}'), input_sha256=hashes,
                config_prerequisite=config_prerequisite(), image=IMAGE, cache_policy='Four fresh kernels; no cache copies; six fresh boots (two ordinary, four KUnit)')


def lifecycle_prerequisite():
    # Separate interpreter prevents the two launchers' preflight module names colliding.
    return json.loads(subprocess.check_output(['python3', '-B', str(DRAFT/'lifecycle-prerequisite.py')], text=True))


def retained_c_prerequisite():
    return json.loads(subprocess.check_output(['python3', '-B', str(DRAFT/'retained-c-prerequisite.py')], text=True))


REVIEWED_FILES = ('README.md', 'check-results.py', 'config-prerequisite-review.json', 'disabled-check.json', 'initial-preflight-failure.json', 'lifecycle-prerequisite-review.json', 'lifecycle-prerequisite.py', 'preflight.py', 'retained-c-prerequisite-review.json', 'retained-c-prerequisite.py', 'retained-c-records.json', 'run.sh', 'source-continuity.json', 'source-review.json')

def reviewed_files():
    ready = json.loads((DRAFT/'root-ready.json').read_text())
    if ready['source'] != EXPECTED or set(ready['files_sha256']) != set(REVIEWED_FILES):
        raise ValueError('Reviewed launcher inventory/source differs')
    for name, expected_hash in ready['files_sha256'].items():
        if digest(DRAFT/name) != expected_hash:
            raise ValueError('Reviewed launcher file changed: '+name)
    return tuple(sorted(REVIEWED_FILES)) + ('root-ready.json',)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--require-fresh', action='store_true'); ap.add_argument('--prerequisite', action='store_true'); ap.add_argument('--lifecycle-prerequisite', action='store_true'); ap.add_argument('--retained-c-prerequisite', action='store_true'); ap.add_argument('--launcher-hashes', action='store_true'); args = ap.parse_args()
    reviewed = reviewed_files()
    if args.launcher_hashes:
        for name in reviewed: print(digest(DRAFT/name)+'  '+str(DRAFT/name))
        return
    if args.require_fresh:
        if not REVIEWED_LAUNCH_READY or not json.loads((DRAFT/'root-ready.json').read_text())['enabled']: raise ValueError('Root launch/source review pending')
        if RUN.exists(): raise ValueError('Fresh output required')
        lifecycle_prerequisite()
        retained_c_prerequisite()
    result = retained_c_prerequisite() if args.retained_c_prerequisite else (lifecycle_prerequisite() if args.lifecycle_prerequisite else (config_prerequisite(raw=True) if args.prerequisite else source_record()))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__': main()
