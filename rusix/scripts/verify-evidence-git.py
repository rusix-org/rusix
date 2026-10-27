#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Check top-level evidence manifests against immutable Git blobs, never raw outputs.

Recognized stored promises: files/sha256 path mappings and records mappings or
lists; structured records use stored (or path), sha256, and optional bytes/size.
Raw/binary/source attribution fields are deliberately outside this storage audit.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess

PREFIX = 'rusix/docs/evidence/'
MANIFEST = re.compile(re.escape(PREFIX) + r'[^/]+/manifest\.json$')
MAX_MANIFEST = 64 * 1024 * 1024


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key: ' + key)
        result[key] = value
    return result


def promises(manifest, *, _stored_aliases=False):
    """Return normalized stored paths; reject unsupported/ambiguous promises."""
    if not isinstance(manifest, dict):
        raise ValueError('Manifest must be an object')
    fields = [key for key in ('files', 'records', 'sha256') if key in manifest]
    if not fields:
        raise ValueError('Missing recognized stored-file inventory')
    # A files map can coexist with logical records describing decompressed
    # content. Every secondary stored path must still belong to that map.
    field = fields[0]
    inventory = manifest[field]
    if isinstance(inventory, dict):
        rows = inventory.items()
    elif field == 'records' and isinstance(inventory, list):
        rows = ((None, value) for value in inventory)
    else:
        raise ValueError('Unknown stored-file inventory schema: ' + field)
    result = {}
    for logical, value in rows:
        size = None
        if isinstance(value, str):
            path, digest = logical, value
        elif isinstance(value, dict):
            path = value.get('stored', value.get('path', logical))
            digest = value.get('stored_sha256', value.get('sha256'))
            size = value['stored_bytes'] if 'stored_bytes' in value else (None if 'stored_sha256' in value else value.get('bytes', value.get('size')))
            if 'bytes' in value and 'size' in value and value['bytes'] != value['size']:
                raise ValueError('Conflicting stored sizes')
        else:
            raise ValueError('Unknown stored record: ' + str(logical))
        if not isinstance(path, str) or not path or '\x00' in path:
            raise ValueError('Missing/invalid stored path')
        relative = PurePosixPath(path)
        if relative.is_absolute() or '..' in relative.parts or str(relative) == '.':
            raise ValueError('Unsafe stored path: ' + path)
        path = str(relative)
        if not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest):
            raise ValueError('Invalid stored SHA256: ' + path)
        if size is not None and (type(size) is not int or size < 0):
            raise ValueError('Invalid stored size: ' + path)
        if path in result and (not _stored_aliases or result[path] != (digest, size)):
            raise ValueError('Duplicate/conflicting normalized stored path: ' + path)
        result[path] = (digest, size)
    for secondary in fields[1:]:
        secondary_inventory = manifest[secondary]
        # Parse the complete secondary shape, including paths, hashes and sizes.
        # For gzip logical records the raw digest is valid metadata, but cannot
        # be compared to stored compressed bytes without an explicit stored hash.
        parsed = promises({secondary: secondary_inventory}, _stored_aliases=True)
        if not set(parsed).issubset(result):
            raise ValueError('Secondary inventory declares unlisted stored paths')
        rows = secondary_inventory.items() if isinstance(secondary_inventory, dict) else ((None, v) for v in secondary_inventory)
        for logical, value in rows:
            path = str(PurePosixPath(value.get('stored', value.get('path', logical)))) if isinstance(value, dict) else str(PurePosixPath(logical))
            digest, size = parsed[path]
            encoding = value.get('encoding') if isinstance(value, dict) else None
            if encoding not in (None, 'identity', 'utf-8', 'gzip'):
                raise ValueError('Unknown secondary encoding: ' + str(encoding))
            stored_hash = not isinstance(value, dict) or 'stored_sha256' in value or encoding != 'gzip'
            stored_size = not isinstance(value, dict) or 'stored_bytes' in value or encoding != 'gzip'
            primary_hash, primary_size = result[path]
            if stored_hash and digest != primary_hash:
                raise ValueError('Conflicting secondary stored SHA256: ' + path)
            if stored_size and size is not None:
                if primary_size is not None and size != primary_size:
                    raise ValueError('Conflicting secondary stored size: ' + path)
                result[path] = (primary_hash, size)
    return result


class Git:
    def __init__(self, repo):
        self.repo = repo
        self.cache = {}
        self.process = subprocess.Popen(
            ['git', '-C', str(repo), 'cat-file', '--batch'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE)

    def command(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args])

    def close(self):
        self.process.stdin.close()
        self.process.stdout.close()
        if self.process.wait() != 0:
            raise ValueError('Git blob reader failed')

    def blob(self, oid, *, contents=False):
        if not contents and oid in self.cache:
            return self.cache[oid]
        self.process.stdin.write((oid + '\n').encode())
        self.process.stdin.flush()
        header = self.process.stdout.readline().decode().split()
        if len(header) != 3 or header[1] != 'blob':
            raise ValueError('Expected Git blob: ' + oid)
        size = int(header[2])
        # Drain even an oversized manifest so the batch stream stays aligned.
        keep = contents and size <= MAX_MANIFEST
        remaining, digest, pieces = size, hashlib.sha256(), []
        while remaining:
            chunk = self.process.stdout.read(min(remaining, 1024 * 1024))
            if not chunk:
                raise ValueError('Truncated Git blob: ' + oid)
            remaining -= len(chunk)
            digest.update(chunk)
            if keep:
                pieces.append(chunk)
        if self.process.stdout.read(1) != b'\n':
            raise ValueError('Malformed Git batch framing')
        self.cache[oid] = (digest.hexdigest(), size)
        if contents:
            if not keep:
                raise ValueError('Manifest exceeds 64 MiB bound')
            return b''.join(pieces)
        return self.cache[oid]

    def tree(self, ref):
        entries = {}
        # Only evidence subtree metadata is retained; large blob data is streamed.
        for record in self.command('ls-tree', '-rz', ref, '--', PREFIX).split(b'\0'):
            if record:
                meta, path = record.split(b'\t', 1)
                mode, kind, oid = meta.decode().split()
                entries[path.decode()] = (mode, kind, oid)
        return entries


def audit(repo, refs):
    git = Git(repo)
    reports = []
    try:
        for requested in refs:
            ref = git.command('rev-parse', '--verify', '--end-of-options', requested + '^{commit}').decode().strip()
            tree = git.tree(ref)
            report = dict(requested_ref=requested, commit=ref, manifests=0,
                          recognized_manifests=0, promised_files=0, verified_files=0,
                          issues=[], unknown_schemas=[])
            for path, (mode, kind, oid) in sorted(tree.items()):
                if not MANIFEST.fullmatch(path):
                    continue
                report['manifests'] += 1
                try:
                    if mode not in ('100644', '100755') or kind != 'blob':
                        raise ValueError('Manifest is not a regular Git blob')
                    document = json.loads(git.blob(oid, contents=True), object_pairs_hook=unique_object)
                    records = promises(document)
                except (ValueError, TypeError, UnicodeError) as error:
                    report['unknown_schemas'].append(dict(manifest=path, error=str(error)))
                    continue
                report['recognized_manifests'] += 1
                for relative, (expected, size) in records.items():
                    full = str(PurePosixPath(path).parent / relative)
                    report['promised_files'] += 1
                    entry = tree.get(full)
                    issue = dict(manifest=path, path=full, expected_sha256=expected,
                                 expected_bytes=size)
                    if entry is None:
                        issue['error'] = 'Missing Git path'
                    elif entry[0] not in ('100644', '100755') or entry[1] != 'blob':
                        issue['error'] = 'Stored record is not a regular Git blob'
                    else:
                        actual, length = git.blob(entry[2])
                        if actual != expected or (size is not None and size != length):
                            issue.update(error='Stored hash/size mismatch', actual_sha256=actual,
                                         actual_bytes=length, git_blob=entry[2])
                        else:
                            report['verified_files'] += 1
                            continue
                    report['issues'].append(issue)
            report['status'] = 'PASS' if report['manifests'] and not report['issues'] and not report['unknown_schemas'] else 'FAIL'
            if not report['manifests']:
                report['unknown_schemas'].append(dict(error='No top-level evidence manifests'))
            reports.append(report)
        return dict(status='PASS' if all(r['status'] == 'PASS' for r in reports) else 'FAIL',
                    scope='Top-level stored Git evidence only; no raw-output or runtime validation',
                    unique_blobs_hashed=len(git.cache), refs=reports)
    finally:
        git.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ref', action='append', help='Local commit/ref; repeat to audit several (default HEAD)')
    parser.add_argument('--repo', type=Path, default=Path.cwd(), help='Git checkout (default current directory)')
    args = parser.parse_args()
    try:
        result = audit(args.repo, args.ref or ['HEAD'])
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        result = dict(status='FAIL', error=str(error))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
