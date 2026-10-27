#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Synthetic discovery/transport regressions, never guest execution."""
import importlib.util
from pathlib import Path
import sys
import unittest
S=Path(__file__).resolve().parents[1]/'scripts'
sys.path.insert(0,str(S))
spec=importlib.util.spec_from_file_location('fault_vm',S/'test-task-faults-vm.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
SYMBOLS='00001000 00000100 t copy_process\n00002000 00000100 T kmem_cache_alloc_node_noprof\n00003000 00000100 T __alloc_pages_noprof\n'
DISASM='1000: nop\n1010: callq 0x2000 <kmem_cache_alloc_node_noprof>\n1015: nop\n1020: callq 0x3000 <__alloc_pages_noprof>\n1025: nop\n'
def console():
 return '\n'.join([f'RUSIX_TASK_FAULT_ARTIFACT {name} 78' for name in m.ARTIFACTS]+['RUSIX_TASK_FAULT_CAPTURE_COMPLETE','RUSIX_TASK_FAULT_INIT_COMPLETE'])
class Pipeline(unittest.TestCase):
 def test_discover_actual_return_sites(self):
  c=m.generator.discover(SYMBOLS,DISASM,'c')
  self.assertEqual(c['slab_frame'],'copy_process+0x15/0x100')
  self.assertEqual(c['stack_frame'],'copy_process+0x25/0x100')
 def test_discovery_ignores_unrelated_local_duplicates_only(self):
  symbols=SYMBOLS+'00004000 00000000 t .Ltmp0\n00005000 00000000 t .Ltmp0\n'
  self.assertEqual(m.generator.discover(symbols,DISASM,'c')['stack_frame'],'copy_process+0x25/0x100')
  for extra in ['00004000 00000100 t copy_process\n','00004000 00000100 T __alloc_pages_noprof\n']:
   with self.assertRaises(ValueError):m.generator.discover(symbols+extra,DISASM,'c')
 def test_discovery_rejects_missing_ambiguous_unrelated(self):
  for text in [DISASM.replace('callq','jmpq'),DISASM+'1030: callq 0x3000 <__alloc_pages_noprof>\n1035: nop\n']:
   with self.assertRaises(ValueError):m.generator.discover(SYMBOLS,text,'c')
  with self.assertRaises(ValueError):m.generator.discover(SYMBOLS,DISASM,'rust')
 def test_discovery_streams_listing_and_excludes_other_owners(self):
  class Listing(str):
   def splitlines(self, *args, **kwargs):
    raise AssertionError('Whole disassembly split is forbidden')
  symbols=SYMBOLS+'00005000 00000100 t unrelated\n'
  text=Listing(DISASM+'5010: callq 0x2000 <kmem_cache_alloc_node_noprof>\n5015: nop\n5020: callq 0x3000 <__alloc_pages_noprof>\n5025: nop\n')
  self.assertEqual(m.generator.discover(symbols,text,'c')['slab_frame'],'copy_process+0x15/0x100')
 def test_adjacency_is_not_reconstructed_from_owner_filtered_rows(self):
  # A foreign instruction between call and proposed return must invalidate
  # attribution, even though it lies outside the retained owner extent.
  text=DISASM.replace('1015: nop','5000: nop\n1015: nop')
  with self.assertRaises(ValueError):m.generator.discover(SYMBOLS,text,'c')
 def test_exact_capture(self):
  self.assertEqual(set(m.decode_console(console(),0)),set(m.ARTIFACTS))
 def test_all_artifact_omissions_duplicates_and_order(self):
  rows=console().splitlines()
  for i in range(len(m.ARTIFACTS)):
   for bad in [rows[:i]+rows[i+1:],rows[:i]+[rows[i]]+rows[i:]]:
    with self.assertRaises(ValueError):m.decode_console('\n'.join(bad),0)
  rows[0],rows[1]=rows[1],rows[0]
  with self.assertRaises(ValueError):m.decode_console('\n'.join(rows),0)
 def test_no_cleanup_failure_status_or_warning(self):
  for bad in [console().replace('RUSIX_TASK_FAULT_CAPTURE_COMPLETE','RUSIX_TASK_FAULT_CAPTURE_FAIL x'),console().replace('RUSIX_TASK_FAULT_INIT_COMPLETE',''),console()+'\nWARNING: bad']:
   with self.assertRaises(ValueError):m.decode_console(bad,0)
  with self.assertRaises(ValueError):m.decode_console(console(),124)
 def test_strict_hex_and_names(self):
  for bad in [console().replace(' 78',' xyz',1),console().replace(' 78',' 7',1),console().replace('calibration.tsv','../outside',1)]:
   with self.assertRaises(ValueError):m.decode_console(bad,0)
 def test_comm_guard_fits_kernel_limit(self):
  fixture=S.parent/'tests/task-construction-faults'
  name='rusix-faultinit';self.assertLessEqual(len(name),15)
  for filename in ['init.rs','controller.rs','worker.c']:
   self.assertIn(name,(fixture/filename).read_text())
 def test_pair_identity_requires_matching_source_image_and_fixture(self):
  spec=importlib.util.spec_from_file_location('fault_pair',S/'compare-task-fault-runs.py')
  pair=importlib.util.module_from_spec(spec);spec.loader.exec_module(pair)
  source=dict(source_revision='a'*40,container_image='image-sha',sources={'fixture':'digest'})
  pair.matched_inputs(source,dict(source))
  for key in source:
   with self.assertRaises(ValueError):pair.matched_inputs(source,source|{key:'different'})
 def test_pair_remaps_only_explicit_container_roots(self):
  spec=importlib.util.spec_from_file_location('fault_pair',S/'compare-task-fault-runs.py')
  pair=importlib.util.module_from_spec(spec);spec.loader.exec_module(pair)
  remap=pair.remapper(Path('/disk/c'),Path('/disk/source'))
  self.assertEqual(remap(Path('/out/build/vmlinux')),Path('/disk/c/build/vmlinux'))
  self.assertEqual(remap(Path('/src/kernel/fork.c')),Path('/disk/source/kernel/fork.c'))
  self.assertEqual(remap(Path('/outside/file')),Path('/outside/file'))
  self.assertEqual(pair.remapper()(Path('/out/file')),Path('/out/file'))
 def test_exact_qemu_contract(self):
  command=m.qemu_command(Path('/out/image'),Path('/out/archive'))
  self.assertEqual(command[:3],['/usr/bin/timeout','--kill-after=5s','300s'])
  for key,value in [('-accel','kvm'),('-smp','2'),('-m','512M'),('-nic','none')]:
   self.assertEqual(command[command.index(key)+1],value)
  self.assertIn('nokaslr',command[-1].split())
 def test_ramfs_contains_only_guarded_programs(self):
  data=m.make_initramfs(b'INIT',b'CONTROLLER',b'WORKER',b'CALIBRATION')
  for name in [b'fault-controller',b'fault-worker',b'calibration.tsv',b'dev/console']:
   self.assertIn(name,data)
if __name__=='__main__':unittest.main()
