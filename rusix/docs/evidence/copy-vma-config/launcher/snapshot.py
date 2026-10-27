#!/usr/bin/env python3
"""Archive exact committed inputs while referencing, not recopying, prior evidence."""
import argparse
import json
from pathlib import Path
import subprocess


def git(source, *args):
    return subprocess.check_output(['git', '-C', str(source), *args], text=True).strip()


def paths(source, commit):
    result = []
    for name in git(source, 'ls-tree', '--name-only', commit).splitlines():
        if name != 'rusix':
            result.append(name)
    for name in git(source, 'ls-tree', '--name-only', commit+':rusix').splitlines():
        if name != 'docs':
            result.append('rusix/'+name)
    for name in git(source, 'ls-tree', '--name-only', commit+':rusix/docs').splitlines():
        if name != 'evidence':
            result.append('rusix/docs/'+name)
    return sorted(result)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--commit', required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    if git(a.source, 'rev-parse', 'HEAD') != a.commit or git(a.source, 'status', '--porcelain'):
        raise ValueError('Expected exact clean source checkpoint')
    entries = paths(a.source, a.commit)
    command = ['git', '-C', str(a.source), 'archive', '--format=tar', a.commit, '--', *entries]
    with (a.output/'source.tar').open('xb') as output:
        subprocess.run(command, stdout=output, check=True)
    record = {'source': a.commit, 'command': command, 'included_paths': entries,
              'omitted_evidence': {'path': 'rusix/docs/evidence', 'source': a.commit,
                                   'git_tree': git(a.source, 'rev-parse', a.commit+':rusix/docs/evidence')},
              'scope': 'Exact committed source except prior evidence tree, referenced by commit/tree identity; no recursive evidence copy'}
    (a.output/'snapshot.json').write_text(json.dumps(record, indent=2, sort_keys=True)+'\n')


if __name__ == '__main__':
    main()
