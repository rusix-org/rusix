#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Stored-evidence gates against small real Git repositories; no kernel execution."""
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/verify-evidence-git.py'
spec = importlib.util.spec_from_file_location('evidence_git', SCRIPT)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)
sha = lambda data: hashlib.sha256(data).hexdigest()


class EvidenceGit(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='rusix-evidence-git-')
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.git('init', '-q')
        self.base = self.repo / 'rusix/docs/evidence/example'
        self.base.mkdir(parents=True)

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args], stderr=subprocess.PIPE)

    def record(self, manifest, files=None):
        for path, data in (files or {}).items():
            p = self.base / path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        (self.base / 'manifest.json').write_text(json.dumps(manifest))
        self.git('add', '.')
        self.git('-c', 'user.name=Evidence fixture', '-c', 'user.email=fixture@example.invalid',
                 '-c', 'commit.gpgsign=false', 'commit', '-qm', 'fixture')
        return gate.audit(self.repo, ['HEAD'])

    def test_default_head_cli_and_relative_paths(self):
        result = self.record({'files': {'./logs/output': sha(b'ok')}}, {'logs/output': b'ok'})
        self.assertEqual(result['status'], 'PASS')
        cli = subprocess.run(['python3', '-B', str(SCRIPT), '--repo', str(self.repo)], capture_output=True, text=True)
        self.assertEqual(cli.returncode, 0, cli.stderr)

    def test_missing_ignored_config_and_compressed_records(self):
        (self.repo / '.gitignore').write_text('*.gz\n.config\n')
        result = self.record({'files': {'.config': sha(b'config'), 'proof.gz': sha(b'zip')}},
                             {'.config': b'config', 'proof.gz': b'zip'})
        self.assertEqual(len(result['refs'][0]['issues']), 2)
        self.assertEqual(result['status'], 'FAIL')

    def test_wrong_hash_and_size(self):
        result = self.record({'records': {'one': {'sha256': sha(b'wrong'), 'bytes': 2},
                                           'two': {'sha256': sha(b'ok'), 'size': 3}}},
                             {'one': b'ok', 'two': b'ok'})
        self.assertEqual(len(result['refs'][0]['issues']), 2)

    def test_logical_records_use_stored_compressed_hash(self):
        packed = gzip.compress(b'raw proof', mtime=0)
        result = self.record({'records': [{'path': 'logical-original', 'stored': 'actual.gz',
                                          'sha256': sha(packed), 'bytes': len(packed),
                                          'raw_sha256': sha(b'raw proof')}]}, {'actual.gz': packed})
        self.assertEqual(result['status'], 'PASS')

    def test_structured_files_and_raw_references_ignored(self):
        result = self.record({'files': {'logical': {'stored': 'out', 'sha256': sha(b'x'), 'size': 1}},
                              'raw_input_sha256': {'/missing/raw': sha(b'raw')},
                              'retained_binary_sha256': {'/missing/vmlinux': {'sha256': sha(b'ELF'), 'bytes': 3}}},
                             {'out': b'x'})
        self.assertEqual(result['refs'][0]['promised_files'], 1)
        self.assertEqual(result['status'], 'PASS')

    def test_files_map_owns_stored_bytes_with_raw_logical_records(self):
        packed = gzip.compress(b'raw proof', mtime=0)
        result = self.record({'files': {'proof.gz': sha(packed)},
                              'records': {'logical': {'stored': 'proof.gz', 'sha256': sha(b'raw proof'),
                                                       'bytes': 9, 'encoding': 'gzip', 'stored_sha256': sha(packed)}}},
                             {'proof.gz': packed})
        self.assertEqual(result['status'], 'PASS')
        records = gate.promises({'records': {'logical': {'stored': 'proof.gz',
                               'sha256': sha(b'raw proof'), 'bytes': 9,
                               'stored_sha256': sha(packed), 'stored_bytes': len(packed)}}})
        self.assertEqual(records['proof.gz'], (sha(packed), len(packed)))

    def test_secondary_inventory_cannot_hide_missing_or_malformed_promises(self):
        for document in (
                {'files': {}, 'records': [{'stored': 'missing.gz', 'sha256': sha(b'x')}]},
                {'files': {'out': sha(b'x')}, 'records': 'malformed'},
                {'files': {'out': sha(b'x')}, 'records': {'out': {'sha256': 'bad'}}},
                {'files': {'out': sha(b'x')}, 'sha256': {'other': sha(b'y')}},
                {'files': {'out': sha(b'x')}, 'sha256': {'out': sha(b'y')}},
                {'files': {'out': sha(b'x')}, 'records': {'out': {'sha256': sha(b'x'), 'encoding': 'future'}}}):
            with self.subTest(document=document), self.assertRaises(ValueError):
                gate.promises(document)
        result = self.record({'files': {}, 'records': [{'stored': 'missing.gz', 'sha256': sha(b'x')}]})
        self.assertEqual(result['status'], 'FAIL')
        self.assertTrue(result['refs'][0]['unknown_schemas'])

    def test_secondary_raw_gzip_hash_does_not_replace_canonical_stored_hash(self):
        packed = gzip.compress(b'raw proof', mtime=0)
        result = self.record({'files': {'proof.gz': sha(packed)},
                              'records': {'logical': {'stored': 'proof.gz', 'encoding': 'gzip',
                                                       'sha256': sha(b'raw proof'), 'bytes': 9}}},
                             {'proof.gz': packed})
        self.assertEqual(result['status'], 'PASS')

    def test_logical_aliases_may_share_identical_stored_blob(self):
        logical = {'stored': 'out', 'sha256': sha(b'x'), 'bytes': 1}
        result = gate.promises({'files': {'out': sha(b'x')},
                                'records': {'first': logical, 'second': dict(logical)}})
        self.assertEqual(result['out'], (sha(b'x'), 1))
        with self.assertRaises(ValueError):
            gate.promises({'files': {'out': sha(b'x')},
                           'records': {'first': logical, 'second': logical | {'sha256': sha(b'y')}}})

    def test_explicit_stored_size_without_stored_hash_is_enforced(self):
        packed = gzip.compress(b'raw proof', mtime=0)
        result = self.record({'files': {'proof.gz': sha(packed)},
                              'records': {'logical': {'stored': 'proof.gz', 'encoding': 'gzip',
                                                       'sha256': sha(b'raw proof'), 'stored_bytes': 999}}},
                             {'proof.gz': packed})
        self.assertEqual(result['status'], 'FAIL')
        self.assertEqual(result['refs'][0]['issues'][0]['expected_bytes'], 999)
        for size in (True, -1, '999'):
            with self.subTest(size=size), self.assertRaises(ValueError):
                gate.promises({'records': {'logical': {'stored': 'proof.gz', 'sha256': sha(b'x'),
                                                       'stored_bytes': size}}})

    def test_legacy_sha256_mapping(self):
        self.assertEqual(self.record({'sha256': {'out': sha(b'x')}}, {'out': b'x'})['status'], 'PASS')

    def test_unknown_schema_fails_closed_cli(self):
        self.record({'future_files': {'out': sha(b'x')}}, {'out': b'x'})
        cli = subprocess.run(['python3', '-B', str(SCRIPT), '--repo', str(self.repo)], capture_output=True, text=True)
        self.assertEqual(cli.returncode, 1)
        self.assertTrue(json.loads(cli.stdout)['refs'][0]['unknown_schemas'])

    def test_symlink_cannot_fulfil_regular_blob_promise(self):
        (self.base / 'out').symlink_to('target')
        result = self.record({'files': {'out': sha(b'target')}})
        self.assertEqual(result['status'], 'FAIL')

    def test_nested_historical_manifest_not_traversed(self):
        data = b'{"unknown_old_schema": true}'
        result = self.record({'files': {'nested/manifest.json': sha(data)}}, {'nested/manifest.json': data})
        self.assertEqual(result['refs'][0]['manifests'], 1)
        self.assertEqual(result['status'], 'PASS')

    def test_repeat_refs_use_immutable_blobs_not_dirty_checkout(self):
        self.record({'files': {'out': sha(b'x')}}, {'out': b'x'})
        (self.base / 'out').write_bytes(b'dirty')
        result = gate.audit(self.repo, ['HEAD', 'HEAD'])
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(result['unique_blobs_hashed'], 2)

    def test_unsafe_duplicate_unknown_record_rejected(self):
        for document in ({'files': {'../escape': sha(b'x')}}, {'files': {'/absolute': sha(b'x')}},
                         {'files': {'out': sha(b'x'), './out': sha(b'x')}},
                         {'files': {'out': {'sha256': sha(b'x'), 'bytes': True}}},
                         {'records': [{'raw_path': '/only/raw', 'sha256': sha(b'x')}]},
                         {'files': {'out': []}}):
            with self.subTest(document=document), self.assertRaises(ValueError):
                gate.promises(document)
        with self.assertRaises(ValueError):
            json.loads('{"files": {}, "files": {}}', object_pairs_hook=gate.unique_object)


if __name__ == '__main__':
    unittest.main()
