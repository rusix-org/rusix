#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Exercise real archiver name resolution and payload binding without compiling."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'rusix/scripts'))
spec = importlib.util.spec_from_file_location('archive_gate', ROOT/'rusix/scripts/verify-task-construction.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

class Archive(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='rusix-ar-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.obj = self.root/'fork.o'; self.obj.write_bytes(b'actual selected object\n')
        self.archive = self.root/'built-in.a'

    def create(self, thin):
        subprocess.run(['llvm-ar', 'rcST' if thin else 'rcS', self.archive.name, self.obj.name], cwd=self.root, check=True, capture_output=True)
        return subprocess.check_output(['llvm-ar','t',str(self.archive)], text=True).strip()

    def test_relative_thin_expanded_listing(self):
        member = self.create(True)
        self.assertEqual(Path(member), self.obj)
        self.assertEqual(m.archive_member_hash(self.archive, member, self.obj),m.digest(self.obj))

    def test_regular_embedded_payload(self):
        member = self.create(False)
        self.assertEqual(m.archive_member_hash(self.archive, member, self.obj),m.digest(self.obj))
        self.obj.write_bytes(b'different bytes')
        with self.assertRaises(ValueError):m.archive_member_hash(self.archive, member, self.obj)

    def test_wrong_path_same_basename(self):
        member = self.create(True)
        other = self.root/'other'; other.mkdir(); alternate = other/'fork.o'; alternate.write_bytes(self.obj.read_bytes())
        with self.assertRaises(ValueError):m.archive_member_hash(self.archive, member, alternate)

    def test_missing_thin_target(self):
        member = self.create(True); self.obj.unlink()
        with self.assertRaises(ValueError):m.archive_member_hash(self.archive, member, self.obj)

    def test_duplicate_basename_rejected(self):
        with self.assertRaises(ValueError):m.archive_members('/a/fork.o\n/b/fork.o\n',False)

    def test_unknown_format(self):
        self.archive.write_bytes(b'not an archive')
        with self.assertRaises(ValueError):m.archive_member_hash(self.archive, self.obj.name, self.obj)

if __name__ == '__main__':unittest.main()
