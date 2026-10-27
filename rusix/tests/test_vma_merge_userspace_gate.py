#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Pure parser/source checks only. Never compile or execute guest binaries."""
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT/'rusix/tests/vma-merge'
spec = importlib.util.spec_from_file_location('merge_guest_gate', FIXTURE/'gate.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)
EXPECTED = [
    'RUSIX_VMA_MERGE_BEGIN',
    'RUSIX_VMA_MERGE_CASE concurrent_mprotect_procmap PASS controls=2 transitions=514 queries=258 scans=258',
    'RUSIX_VMA_MERGE_CASE fork_cow_mremap_lifetime PASS cow_children=1 grows=64 shrinks=64 zero_extensions=64',
    'RUSIX_VMA_MERGE_END', 'RUSIX_VMA_MERGE_PASS',
]
class Gate(unittest.TestCase):
    def test_literal_inventory(self):
        self.assertEqual(gate.EXPECTED, EXPECTED)
        self.assertEqual(gate.validate('\n'.join(EXPECTED))['count'], 2)
    def test_crlf_and_kernel_preamble(self):
        self.assertEqual(gate.validate('Booting kernel\r\n'+'\r\n'.join(EXPECTED)+'\r\nPower down')['count'], 2)
    def test_every_missing_marker(self):
        for i in range(len(EXPECTED)):
            with self.subTest(i=i), self.assertRaises(ValueError): gate.validate('\n'.join(EXPECTED[:i]+EXPECTED[i+1:]))
    def test_every_duplicate_marker(self):
        for marker in EXPECTED:
            with self.subTest(marker=marker), self.assertRaises(ValueError): gate.validate('\n'.join(EXPECTED+[marker]))
    def test_order(self):
        lines=EXPECTED.copy();lines[1],lines[2]=lines[2],lines[1]
        with self.assertRaises(ValueError):gate.validate('\n'.join(lines))
    def test_status_and_skip(self):
        for text in ('FAIL','SKIP','XFAIL','PASS # SKIP'):
            with self.subTest(text=text), self.assertRaises(ValueError):gate.validate('\n'.join(EXPECTED).replace(' PASS ',' '+text+' ',1))
    def test_counter_exactness(self):
        for name,value in (('controls',2),('transitions',514),('queries',258),('scans',258),('cow_children',1),('grows',64),('shrinks',64),('zero_extensions',64)):
            for replacement in ('0',str(value+1),str(value)+'0','-1'):
                with self.subTest(name=name,replacement=replacement),self.assertRaises(ValueError):gate.validate('\n'.join(EXPECTED).replace(f'{name}={value}',f'{name}={replacement}'))
    def test_unknown_foreign_extra(self):
        for extra in ('RUSIX_VMA_MERGE_CASE other PASS','RUSIX_OTHER_PASS','ok 3 extra','TAP version 13'):
            with self.subTest(extra=extra),self.assertRaises(ValueError):gate.validate('\n'.join(EXPECTED+[extra]))
    def test_no_embedded_unclassified_output(self):
        with self.assertRaises(ValueError):gate.validate('\n'.join(EXPECTED[:2]+['unexpected child output']+EXPECTED[2:]))
    def test_diagnostics(self):
        for diagnostic in ('warning: failure','WARNING: failure','BUG: failure','Kernel panic','Call Trace:','KASAN:','UBSAN:','ACPI BIOS Error: bad','CPU feature dependency check failure','RUSIX_VMA_MERGE_FAIL bad'):
            with self.subTest(diagnostic=diagnostic), self.assertRaises(ValueError):gate.validate('\n'.join(EXPECTED+[diagnostic]))
    def test_timeout_and_failure(self):
        for status in (1,124,125,137,143,-9):
            with self.subTest(status=status),self.assertRaises(ValueError):gate.validate('\n'.join(EXPECTED),status)
    def test_pinned_public_uapi_sources(self):
        record=json.loads((FIXTURE/'upstream.json').read_text())
        self.assertEqual(record['baseline'],'2926d88bb7fc4608fd942453d929c39e4e5ec006')
        self.assertEqual(record['procmap_query'],{'size':104,'request':'0xc0686611','layout':'public userspace UAPI, not an internal kernel structure'})
        for name,value in record['files'].items():
            self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),value['sha256'],name)
    def test_guard_contract_and_no_host_execution(self):
        for name in ('init.rs','probe.rs'):
            text=(FIXTURE/name).read_text();self.assertIn('rusix.vma_merge_probe=1',text);self.assertIn('rusix-mrg-init',text)
        text=(FIXTURE/'probe.rs').read_text()
        self.assertLess(text.index('    concurrent_case()?;'),text.index('    fork_remap_case()\n'))
        self.assertIn('size_of::<ProcmapQuery>() == 104',text)
        self.assertIn('Arc::try_unwrap(shared)',text)
if __name__=='__main__':unittest.main()
