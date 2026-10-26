#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Synthetic parser regressions only; no guest or allocator faults executed."""
import importlib.util
from pathlib import Path
import unittest
S=Path(__file__).resolve().parents[1]/'scripts/validate-task-fault-trace.py'
spec=importlib.util.spec_from_file_location('fault_gate',S);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
CAL={'slab_frame':'copy_process+0x15/0x100','stack_frame':'copy_process+0x25/0x100'}
STATS=['overrun: 0\ncommit overrun: 0\ndropped events: 0\n']*2
PROBES='page_decision 10 0\nslab_decision 20 0\npages_result 10 0\n'
def row(body):return f' worker-123 [001] .... 1.000000: {body}\n'
def interval(body):return row('tracing_mark_write: ARM')+body+row('tracing_mark_write: DISARM')
def stack(frame):return row('<stack trace>')+' => '+frame+'\n'
def slab():return interval(row('slab_decision: result=-12')+stack(CAL['slab_frame'])+row('kmem_cache_alloc: ptr=0000000000000000 name=task_struct'))
def pages(frame=None):return interval(row('kmem_cache_alloc: ptr=0000000000000abc name=task_struct')+row('page_decision: order=2 injected=1')+stack(frame or CAL['stack_frame'])+row('pages_result: order=2 result=0x0')+row('kmem_cache_free: ptr=0000000000000abc name=task_struct'))
WORK='RESULT pid=123 nth=1 ret=-1 errno=12 remaining=0 child_status=0 retry_status=0'
def check(trace,worker=WORK):return m.classify(worker,trace,CAL,STATS,PROBES)
class Gate(unittest.TestCase):
 def test_two_attributed_sites(self):
  self.assertEqual(check(slab())['classification'],'task-slab-failure')
  self.assertEqual(check(pages())['classification'],'stack-page-failure')
 def test_other_failure_not_stack_coverage(self):
  self.assertEqual(check(pages('slab_refill+0x5/0x20'))['classification'],'other-page-failure')
 def test_site_and_rollback_identity(self):
  for text in [slab().replace(CAL['slab_frame'],'elsewhere+0x5/0x20'),pages().replace('kmem_cache_free: ptr=0000000000000abc','kmem_cache_free: ptr=0000000000000def'),pages().replace('result=0x0','result=0xabc'),pages().replace('order=2','order=1'),pages().replace('0000000000000abc','(ptrval)')]:
   with self.assertRaises(ValueError):check(text)
 def test_strict_loss_and_misses(self):
  for stats,probes in [(STATS[:1]+['overrun: 1\ncommit overrun: 0\ndropped events: 0\n'],PROBES),(STATS,PROBES.replace('10 0','10 1')),(['']*2,PROBES),(STATS,PROBES+'page_decision 0 0\n')]:
   with self.assertRaises(ValueError):m.classify(WORK,slab(),CAL,stats,probes)
 def test_markers_and_actor(self):
  for text in [slab().replace('tracing_mark_write: ARM','other: ARM'),slab()+row('tracing_mark_write: ARM'),slab().replace('worker-123','worker-124'),slab().replace(' => '+CAL['slab_frame']+'\n','')]:
   with self.assertRaises(ValueError):check(text)
 def test_syscall_and_retry(self):
  for w in [WORK.replace('errno=12','errno=11'),WORK.replace('retry_status=0','retry_status=-1'),WORK.replace('remaining=0','remaining=1'),WORK+' extra']:
   with self.assertRaises(ValueError):check(slab(),w)
 def test_child_publication_rejected(self):
  with self.assertRaises(ValueError):check(slab().replace(row('tracing_mark_write: DISARM'),row('sched_process_fork: child_pid=124')+row('tracing_mark_write: DISARM')))
 def test_calibration_requires_real_success_stacks(self):
  worker=WORK.replace('nth=1 ret=-1 errno=12','nth=0 ret=124 errno=0')
  trace=interval(row('slab_decision: result=0')+stack(CAL['slab_frame'])+row('page_decision: order=2 injected=0')+stack(CAL['stack_frame']))
  self.assertEqual(check(trace,worker)['classification'],'uninjected-control')
  with self.assertRaises(ValueError):check(interval(''),worker)
  for bad in [trace.replace('result=0','result=-1'),trace.replace('injected=0','injected=2')]:
   with self.assertRaises(ValueError):check(bad,worker)
 def test_slab_order(self):
  bad=interval(row('kmem_cache_alloc: ptr=0000000000000000 name=task_struct')+row('slab_decision: result=-12')+stack(CAL['slab_frame']))
  with self.assertRaises(ValueError):check(bad)
 def test_attempt_identity(self):
  seen=set();m.attempt_identity('slab-1',WORK,seen)
  with self.assertRaises(ValueError):m.attempt_identity('stack-1',WORK,seen)
  with self.assertRaises(ValueError):m.attempt_identity('stack-2',WORK,set())
  with self.assertRaises(ValueError):m.attempt_identity('calibration',WORK,set())
 def test_linked_return_pc(self):
  symbols='00001000 00000100 t copy_process\n'
  disasm='1000: nop\n1010: callq 0x2000 <kmem_cache_alloc_node_noprof>\n1015: movq %rax, %rbx\n1020: callq 0x3000 <__alloc_pages_noprof>\n1025: movq %rax, %rbx\n'
  cal=CAL|{'range_symbol':'copy_process','range_start':'0x1000','range_end':'0x1100'}
  self.assertTrue(m.callsite_proof(symbols,disasm,cal))
  for bad in [cal|{'slab_frame':'copy_process+0x14/0x100'},cal|{'range_end':'0x1200'},cal|{'stack_frame':'copy_process+0x25/0x200'}]:
   with self.assertRaises(ValueError):m.callsite_proof(symbols,disasm,bad)
  with self.assertRaises(ValueError):m.callsite_proof(symbols,disasm.replace('callq','jmpq'),cal)
 def test_rejects_unrelated_and_ambiguous_allocator_owner(self):
  symbols='00001000 00000100 t copy_process\n00002000 00000100 t unrelated\n'
  disasm='1000: nop\n1010: callq 0x3000 <kmem_cache_alloc_node_noprof>\n1015: nop\n1020: callq 0x4000 <__alloc_pages_noprof>\n1025: nop\n2010: callq 0x4000 <__alloc_pages_noprof>\n2015: nop\n'
  cal=CAL|{'range_symbol':'copy_process','range_start':'0x1000','range_end':'0x1100'}
  with self.assertRaises(ValueError):m.callsite_proof(symbols,disasm,cal|{'stack_frame':'unrelated+0x15/0x100'})
  with self.assertRaises(ValueError):m.callsite_proof(symbols,disasm+'1030: callq 0x4000 <__alloc_pages_noprof>\n1035: nop\n',cal)
 def test_pair_profiles_only_selector(self):
  root=Path(__file__).resolve().parents[1]/'configs'
  c=(root/'x86_64-task-construction-fault-c.config').read_text()
  r=(root/'x86_64-task-construction-fault-rust.config').read_text()
  self.assertEqual(c.replace('# CONFIG_RUSIX_TASK_CONSTRUCTION_RUST is not set','CONFIG_RUSIX_TASK_CONSTRUCTION_RUST=y'),r)
  self.assertIn('CONFIG_DEBUG_FS=y',c)
  self.assertIn('# CONFIG_DEBUG_FS is not set',(root/'x86_64-server.config').read_text())
class DisassemblyHeading(unittest.TestCase):
 def test_exact_recorded_to_host_remap(self):
  old='/out/build/vmlinux';new='/host/output/build/vmlinux'
  text='\n'+old+':\tfile format elf64-x86-64\n\nDisassembly of section .text:\n\n1000 <copy_process>:\n1000: nop\n'
  actual=text.replace(old,new,1)
  self.assertTrue(m.disassembly_matches(text,actual,old,new))
  self.assertTrue(m.disassembly_matches(text,text,old,old))
  for changed in (actual.replace('nop','retq'), actual.replace('elf64-x86-64','elf32-i386'), actual.replace('copy_process','other'), actual+'\n'):
   self.assertFalse(m.disassembly_matches(text,changed,old,new))
 def test_missing_wrong_duplicate_and_moved_headings(self):
  old='/out/build/vmlinux';new='/host/output/build/vmlinux'
  text='\n'+old+':\tfile format elf64-x86-64\n\n1000: nop\n'
  actual=text.replace(old,new,1)
  for bad in (actual.replace(new,'/wrong/vmlinux'), actual+new+':\tfile format elf64-x86-64\n', actual+'/wrong/vmlinux:\tfile format elf64-x86-64\n', actual.lstrip('\n'), '\n'+actual):
   with self.assertRaises(ValueError):m.disassembly_matches(text,bad,old,new)
  with self.assertRaises(ValueError):m.disassembly_matches(text.replace(old,'/wrong'),actual,old,new)
if __name__=='__main__':unittest.main()
