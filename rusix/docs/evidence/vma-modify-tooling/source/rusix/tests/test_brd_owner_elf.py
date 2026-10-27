#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Indexed BRD ELF reads preserve repeated section identities, not ambiguous metadata."""
import importlib.util
from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
scripts = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(scripts))
spec = importlib.util.spec_from_file_location('brd_owner_elf_gate', scripts / 'verify-brd-parameter-owner.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def object_bytes(duplicate_metadata=False):
    """Literal ELF64 relocatable: repeated prefix sections and indexed pointer."""
    strings = b'\0first\0second\0'
    symbols = b'\0' * 24
    symbols += struct.pack('<IBBHQQ', 1, 0x11, 0, 1, 0, 8)
    symbols += struct.pack('<IBBHQQ', 7, 0x11, 0, 2, 0, 8)
    # name, type, flags, payload, link, info, alignment, entry size
    sections = [
        ('__patchable_function_entries', 1, 3, b'FIRST123', 0, 0, 8, 0),
        ('__patchable_function_entries', 1, 3, b'SECOND12', 0, 0, 8, 0),
        ('__param', 1, 2, b'\0' * 8, 0, 0, 8, 0),
        ('.strtab', 3, 0, strings, 0, 0, 1, 0),
        ('.symtab', 2, 0, symbols, 4, 1, 8, 24),
        ('.rela__param', 4, 0, struct.pack('<QQq', 0, (2 << 32) | 1, 2), 5, 3, 8, 24),
    ]
    if duplicate_metadata:
        sections.append(('__param', 1, 2, b'\0' * 8, 0, 0, 8, 0))
    names = b'\0'
    offsets = {}
    for name in [row[0] for row in sections] + ['.shstrtab']:
        if name not in offsets:
            offsets[name] = len(names)
            names += name.encode() + b'\0'
    sections.append(('.shstrtab', 3, 0, names, 0, 0, 1, 0))
    payload = bytearray(b'\0' * 64)
    headers = [b'\0' * 64]
    for name, kind, flags, data, link, info, align, stride in sections:
        payload.extend(b'\0' * (-len(payload) % align))
        offset = len(payload)
        payload.extend(data)
        headers.append(struct.pack('<IIQQQQIIQQ', offsets[name], kind, flags, 0,
                                   offset, len(data), link, info, align, stride))
    payload.extend(b'\0' * (-len(payload) % 8))
    table_offset = len(payload)
    payload.extend(b''.join(headers))
    payload[:64] = struct.pack('<16sHHIQQQIHHHHHH', b'\x7fELF\x02\x01' + b'\0' * 10,
                              1, 62, 1, 0, 0, table_offset, 0, 64, 0, 0, 64,
                              len(headers), len(headers) - 1)
    return bytes(payload)


class BrdIndexedElfTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory(prefix='rusix-brd-elf-')
        self.addCleanup(scratch.cleanup)
        self.path = Path(scratch.name) / 'fixture.o'

    def test_unrelated_duplicate_sections_keep_symbol_and_relocation_identity(self):
        self.path.write_bytes(object_bytes())
        with self.assertRaisesRegex(ValueError, 'Duplicate ELF section name'):
            gate.Elf(self.path)
        elf = gate.Elf(self.path, indexed_sections=True)
        self.assertEqual(elf.names[1], elf.names[2])
        self.assertNotIn('__patchable_function_entries', elf.indices)
        self.assertEqual(elf.location(elf.symbol('first')), (1, 0))
        self.assertEqual(elf.location(elf.symbol('second')), (2, 0))
        self.assertEqual(elf.section_data(1), b'FIRST123')
        self.assertEqual(elf.section_data(2), b'SECOND12')
        self.assertEqual(elf.pointer((3, 0)), (2, 2))
        self.assertEqual(elf.record_range('__param'), (3, 0, 8))

    def test_ambiguous_metadata_still_rejected(self):
        self.path.write_bytes(object_bytes(duplicate_metadata=True))
        elf = gate.Elf(self.path, indexed_sections=True)
        self.assertNotIn('__param', elf.indices)
        with self.assertRaisesRegex(ValueError, 'Missing or ambiguous metadata'):
            elf.record_range('__param')

    def test_indexed_reader_still_rejects_truncation(self):
        self.path.write_bytes(object_bytes()[:-1])
        with self.assertRaises(ValueError):
            gate.Elf(self.path, indexed_sections=True)


if __name__ == '__main__':
    unittest.main()
