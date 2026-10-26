#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Keep ancestor KUnit evidence attributed to its original, unchanged kernel."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

# Exact review boundary, not a blanket permission to change rusix/ or scripts/.
MODIFIED = frozenset('''rusix/scripts/build-kernel.sh rusix/ci/run.sh
rusix/ci/run-container.sh rusix/scripts/server_target.py
rusix/scripts/verify-rcu-list-selection.py rusix/scripts/test-brd-vm.py
rusix/scripts/test-brd-ext4-vm.py rusix/scripts/test-brd-fixed-parameters-vm.py
rusix/scripts/test-brd-partitions-vm.py rusix/experiments/rcu-lists/README.md
rusix/PROGRESS.md'''.split())
ADDED = frozenset('''rusix/configs/x86_64-rcu-list-ext4-c.config
rusix/configs/x86_64-rcu-list-ext4-rust.config
rusix/scripts/verify-rcu-list-continuity.py
rusix/tests/test_rcu_list_integration.py'''.split())
KUNIT_PROFILES = ('rcu-list-c', 'rcu-list-rust', 'rcu-list-plain-c', 'rcu-list-plain-rust')


def git(source, *args):
    return subprocess.check_output(['git', '-C', str(source), *args])


def digest(data):
    return hashlib.sha256(data).hexdigest()


def verify(source, baseline, candidate):
    baseline = git(source, 'rev-parse', '--verify', baseline + '^{commit}').decode().strip()
    candidate = git(source, 'rev-parse', '--verify', candidate + '^{commit}').decode().strip()
    subprocess.run(['git', '-C', str(source), 'merge-base', '--is-ancestor', baseline, candidate], check=True)
    raw = git(source, 'diff', '--no-renames', '--name-status', baseline, candidate)
    changes = []
    for line in raw.decode().splitlines():
        status, path = line.split('\t')
        if not ((status == 'M' and path in MODIFIED) or (status == 'A' and path in ADDED)):
            raise ValueError(f'Change outside reviewed integration tooling boundary: {status} {path}')
        changes.append({'status': status, 'path': path,
                        'baseline_sha256': digest(git(source, 'show', baseline + ':' + path)) if status == 'M' else None,
                        'candidate_sha256': digest(git(source, 'show', candidate + ':' + path))})
    identities = {}
    for profile in KUNIT_PROFILES:
        path = f'rusix/configs/x86_64-{profile}.config'
        old = git(source, 'show', baseline + ':' + path)
        new = git(source, 'show', candidate + ':' + path)
        if old != new:
            raise ValueError('Existing KUnit profile changed')
        identities[path] = digest(old)
    for name in ('boot-kunit.sh', 'validate-brd-kunit.py', 'validate-completion-kunit.py', 'validate-rcu-kunit.py'):
        path = 'rusix/scripts/' + name
        old = git(source, 'show', baseline + ':' + path)
        if old != git(source, 'show', candidate + ':' + path):
            raise ValueError('Existing KUnit boot/gate changed')
        identities[path] = digest(old)
    return {'status': 'PASS', 'baseline_source': baseline, 'candidate_source': candidate,
            'scope': 'Unchanged kernel/fixtures/existing KUnit configurations; reviewed integration-tooling-only descendant',
            'changes': changes, 'unchanged_input_sha256': identities,
            'diff_sha256': digest(git(source, 'diff', '--binary', baseline, candidate)),
            'limitations': ['KUnit remains evidence for baseline_source; this does not relabel it as a candidate build.',
                            'Changed build/routing scripts require independent review and fresh candidate integration runs.',
                            'No assertion of identical linked images or matching build timestamps.']}


def check_archive(path, baseline):
    record = json.loads(path.read_text())
    if record['source'] != baseline or record['status'] != 'PASS':
        raise ValueError('KUnit archive does not identify successful baseline evidence')
    if record.get('suite') not in ('debug', 'plain'):
        raise ValueError('Expected isolated debug/plain RCU archive')
    for relative, expected in record['sha256'].items():
        part = Path(relative)
        if part.is_absolute() or '..' in part.parts:
            raise ValueError('Unsafe archived path')
        if digest((path.parent / part).read_bytes()) != expected:
            raise ValueError('Archived evidence hash changed')
    comparison = record['comparison']
    if set(comparison) != {'c', 'rust'} or any(x['cases'] != [86, 67, 10] for x in comparison.values()):
        raise ValueError('Wrong RCU KUnit inventories')
    spec = importlib.util.spec_from_file_location('continuity_rcu_gate', Path(__file__).with_name('validate-rcu-kunit.py'))
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)
    results = list(path.parent.rglob('*-kunit.json'))
    if len(results) != 6:
        raise ValueError('Expected six archived KUnit results per pair')
    observed = []
    for result in results:
        data = json.loads(result.read_text())
        if result.name.endswith('-completion-kunit.json'):
            groups = list(gate.common.groups(data))
            names = [group['name'] for group in groups if group['test_cases']]
            if len(names) != len(gate.completion.SUITES) or set(names) != set(gate.completion.SUITES):
                raise ValueError('Unexpected isolated core suites')
            if any(group['name'].startswith('rusix_') and group['name'] not in gate.completion.SUITES for group in groups):
                raise ValueError('Unknown isolated core suite')
            count = gate.completion.validate(data)
            expected = 67
        else:
            isolated = result.name.endswith('-rcu-list-kunit.json')
            count = gate.validate(data, combined=not isolated)
            expected = 10 if isolated else 86
        if count != expected:
            raise ValueError('Archived KUnit case gate failed')
        observed.append(count)
    if sorted(observed) != [10, 10, 67, 67, 86, 86]:
        raise ValueError('Archived KUnit mode inventory differs')
    exits = list(path.parent.rglob('*.exit'))
    if not exits or any(p.read_text().strip() != '0' for p in exits):
        raise ValueError('Archived nonzero terminal status')
    return {'suite': record['suite'], 'manifest': str(path.resolve()), 'manifest_sha256': digest(path.read_bytes()),
            'source': baseline, 'cases_per_kernel': [86, 67, 10]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--baseline', required=True)
    parser.add_argument('--candidate', default='HEAD')
    parser.add_argument('--evidence', type=Path, action='append', default=[])
    args = parser.parse_args()
    result = verify(args.source, args.baseline, args.candidate)
    if args.evidence:
        archives = [check_archive(path, result['baseline_source']) for path in args.evidence]
        if len(archives) != 2 or {r['suite'] for r in archives} != {'debug', 'plain'}:
            raise ValueError('Both distinct debug/plain archives are required')
        result['baseline_evidence'] = archives
    else:
        result['baseline_evidence'] = 'Not supplied: source continuity only, no test pass claim'
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
