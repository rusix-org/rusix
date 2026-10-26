#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Reproduce a textual completion-counter review inventory, not a race proof."""
import argparse
import hashlib
import json
from pathlib import Path
import posixpath
import re
import subprocess

DEPENDENCY_RE = r'/src/([^\s\\]+\.[ch])\b'
ACCESS_RE = r'(?:->|\.)\s*done\b'
RUNS = [
    ('lts-broadcast-rust-001', 'ci-completion-rust', 'ci-completion-rust-build.P5UqYEyn'),
    ('lts-server-003', 'ci-server', 'ci-server-build.la3juIMY'),
]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--output-root', type=Path, required=True)
    parser.add_argument('--source-commit', default='a910df12a5b7365f2806f8ebdc97d5c85744baa8')
    parser.add_argument('--write-dir', type=Path, required=True)
    args = parser.parse_args()
    commit = subprocess.check_output(['git', '-C', str(args.repo), 'rev-parse', args.source_commit + '^{commit}'], text=True).strip()
    args.write_dir.mkdir(parents=True, exist_ok=True)
    batch = subprocess.Popen(['git', '-C', str(args.repo), 'cat-file', '--batch'], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    cache = {}

    def source(path):
        if path not in cache:
            canonical = posixpath.normpath(path)
            if canonical.startswith('../') or canonical.startswith('/'):
                raise RuntimeError(f'Dependency escapes source tree: {path}')
            batch.stdin.write(f'{commit}:{canonical}\n'.encode())
            batch.stdin.flush()
            header = batch.stdout.readline().decode().strip()
            if header.endswith(' missing'):
                cache[path] = None
            else:
                oid, kind, length = header.split()
                if kind != 'blob':
                    raise RuntimeError(f'Expected source blob: {header}')
                data = batch.stdout.read(int(length))
                if batch.stdout.read(1) != b'\n':
                    raise RuntimeError('Malformed cat-file response')
                cache[path] = (oid, data)
        return cache[path]

    metadata = {
        'schema': 1,
        'status': 'textual inventory for manual review; not automatic acceptance',
        'source_commit_scanned': commit,
        'source_note': 'Historical build dependency sets scanned against the explicitly identified later source commit. This is not a claim that these source bytes were built in those runs.',
        'script_sha256': sha(Path(__file__).read_bytes()),
        'method': {
            'dependency_pattern': DEPENDENCY_RE,
            'access_pattern': ACCESS_RE,
            'command_files': 'all recursively found .*.cmd under each recorded build directory',
            'command_size_cap_bytes': 2000000,
            'dependency_paths': 'literal /src/ C/header paths, sorted and deduplicated',
            'source_reader': 'git cat-file --batch at source_commit_scanned, POSIX-normalized dependency paths, never mutable worktree content',
            'line_format': 'repository path:1-based line number:stripped source line',
        },
        'limitations': [
            'Textual scan does not resolve types, macros, pointer aliases, casts or indirect bytewise accesses.',
            'done members include unrelated counters, callbacks and whole completion objects; manual classification is required.',
            'All dependency records, including potentially stale cache records and host-tool records, form a conservative union rather than exact linked code selection.',
            'This inventory covers C/header files; Rust quiescent test accesses require separate review.',
            'Initialization/reinitialization safety still relies on caller lifetime and quiescence contracts.',
            'Known external-driver findings and configuration exclusions need separate reviewed documentation; absence of a textual match is not a whole-tree race proof.',
        ],
        'runs': [],
    }
    for run, profile, evidence_name in RUNS:
        root = args.output_root / run
        build = root / 'builds' / profile
        evidence = root / 'logs' / evidence_name
        deps = set()
        commands = []
        skipped = []
        for path in sorted(build.rglob('.*.cmd')):
            if path.stat().st_size > 2000000:
                skipped.append(str(path.relative_to(build)))
                continue
            data = path.read_bytes()
            commands.append({'path': str(path.relative_to(build)), 'sha256': sha(data)})
            deps.update(re.findall(DEPENDENCY_RE, data.decode(errors='replace')))
        if not commands:
            raise RuntimeError(f'No build command records under {build}')
        matches = []
        source_hashes = []
        missing = []
        for path in sorted(deps):
            blob = source(path)
            if blob is None:
                missing.append(path)
                continue
            oid, data = blob
            source_hashes.append(f'{sha(data)}  {path}')
            for number, line in enumerate(data.decode(errors='replace').splitlines(), 1):
                if re.search(ACCESS_RE, line):
                    matches.append(f'{path}:{number}:{line.strip()}')
        outputs = {}
        for suffix, lines in [('done-audit.txt', matches), ('dependencies.txt', sorted(deps)), ('dependencies.sha256', source_hashes)]:
            name = f'{run}-{suffix}'
            data = ('\n'.join(lines) + '\n').encode()
            (args.write_dir / name).write_bytes(data)
            outputs[name] = sha(data)
        config = (evidence / 'config').read_bytes()
        local_config = (build / '.config').read_bytes()
        if config != local_config:
            raise RuntimeError(f'Config changed since evidence: {run}')
        metadata['runs'].append({
            'run': run, 'profile': profile, 'build_directory': str(build),
            'evidence_directory': str(evidence),
            'built_source_commit': (evidence / 'source-after.commit').read_text().strip(),
            'build_exit': (evidence / 'build.exit').read_text().strip(),
            'config_sha256': sha(config),
            'environment_sha256': sha((evidence / 'environment.log').read_bytes()),
            'build_artifacts_sha256': (evidence / 'build.sha256').read_text().splitlines(),
            'dependency_count': len(deps), 'matched_line_count': len(matches),
            'missing_source_paths': missing, 'skipped_oversize_command_files': skipped,
            'command_file_inputs': commands, 'outputs_sha256': outputs,
        })
        print(f'{run}: {len(deps)} dependencies; {len(matches)} matching lines; {len(missing)} missing source paths')
    batch.stdin.close()
    if batch.wait() != 0:
        raise RuntimeError('cat-file failed')
    (args.write_dir / 'completion-counter-audit-inputs.json').write_text(json.dumps(metadata, indent=2) + '\n')


if __name__ == '__main__':
    main()
