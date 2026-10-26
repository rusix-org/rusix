#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Strict translation-unit routing; never invoke the compiler or shell."""
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'rusix/scripts'))
import saved_clang_command as parser

spec = importlib.util.spec_from_file_location('fork_cases', Path(__file__).with_name('test_task_construction_selection.py'))
fork_cases = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fork_cases)


def mmap_record():
    return (fork_cases.command_record()
            .replace('kernel/fork', 'mm/mmap').replace('kernel/.fork', 'mm/.mmap')
            .replace('-I/src/kernel', '-I/src/mm').replace('-Ikernel', '-Imm')
            .replace('"fork"', '"mmap"').replace('kmod_fork', 'kmod_mmap')
            .replace(' -c ', ' -I/src/mm -D__KBUILD_MODNAME=kmod_mmap -c '))


class TranslationUnit(unittest.TestCase):
    def test_explicit_mmap_plain_and_hardened(self):
        record = mmap_record()
        plain = ' '.join(parser.PLAIN_OBJTOOL[:-1] + ('mm/mmap.o',))
        hard = ' '.join(parser.HARDENED_OBJTOOL[:-1] + ('mm/mmap.o',))
        for text in (record, record.replace(plain, hard)):
            argv = parser.command(text, Path('/out/mmap.i'), 'mm/mmap')
            self.assertEqual(argv[-3:], ['-E', '-o', '/out/mmap.i'])
            self.assertIn('/src/mm/mmap.c', argv)
            self.assertNotIn('/src/kernel/fork.c', argv)
            self.assertFalse(any('objtool' in value for value in argv))

    def test_wrong_unit_source_output_dependency_and_metadata(self):
        text = mmap_record()
        for old, new in (('/src/mm/mmap.c', '/src/mm/memory.c'),
                         ('-o mm/mmap.o', '-o kernel/fork.o'),
                         ('-Wp,-MMD,mm/.mmap.o.d', '-Wp,-MMD,kernel/.fork.o.d'),
                         ('-I/src/mm', '-I/src/kernel'),
                         ('kmod_mmap', 'kmod_fork'),
                         ('--uaccess mm/mmap.o', '--uaccess kernel/fork.o')):
            self.assertIn(old, text)
            with self.subTest(old=old), self.assertRaises(ValueError):
                parser.command(text.replace(old, new), Path('/out/mmap.i'), 'mm/mmap')

    def test_unsupported_units_and_shell_tokens(self):
        for unit in ('mm/memory', '../mm/mmap', 'mm/mmap;id', 'kernel/exit'):
            with self.assertRaises(ValueError):
                parser.command(mmap_record(), Path('/out/mmap.i'), unit)
        for extra in ('; id', '&& id', '| cat', '-fplugin=/tmp/plugin.so'):
            with self.assertRaises(ValueError):
                parser.command(mmap_record().replace('clang ', 'clang '+extra+' ', 1),
                               Path('/out/mmap.i'), 'mm/mmap')

    def test_unit_does_not_follow_untrusted_record(self):
        with self.assertRaises(ValueError):
            parser.command(mmap_record(), Path('/out/fork.i'))
        with self.assertRaises(ValueError):
            parser.command(fork_cases.command_record(), Path('/out/mmap.i'), 'mm/mmap')


if __name__ == '__main__':
    unittest.main()
