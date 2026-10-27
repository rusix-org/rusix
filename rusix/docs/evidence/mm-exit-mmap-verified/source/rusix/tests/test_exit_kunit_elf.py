#!/usr/bin/env python3
"""Modeled ELF graph regressions; no compiled-kernel ownership claim."""
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import tempfile
from types import SimpleNamespace
S=Path(__file__).resolve().parents[1]/'scripts';sys.path.insert(0,str(S))
spec=importlib.util.spec_from_file_location('exitelf',S/'exit_kunit_elf.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Model:
 def __init__(self):
  self.relocatable=True;self.names=['','.kunit_test_suites','.data','.text'];self.headers=[(0,)*10,(0,1,2,0,0,8),(0,1,3,0,0,2048),(0,1,6,0,0,256)];self.data=bytearray(2048);self.data[:len(m.SUITE)]=m.SUITE.encode();self.ptr={(1,0):(2,0),(2,288):(2,600)};self.symbols=[];self.relocations={}
  self.data[816:888]=m.CASE_TERMINATOR
  for i,name in enumerate(m.CASES):
   pos=1000+i*150;self.data[pos:pos+len(name)]=name.encode();self.ptr[(2,600+i*72)]=(3,i*32);self.ptr[(2,608+i*72)]=(2,pos)
   self.symbols.append(dict(name='kernel_exit_tests_kunit_rust_wrapper_'+name,kind=2,size=24,section=3,address=i*32))
 def section_data(self,i):return bytes(self.data) if i==2 else bytes(256)
 def pointer(self,loc):return self.ptr.get(loc)
 def location(self,s):return s['section'],s['address']
 def text(self,loc):return self.section_data(loc[0])[loc[1]:].split(b'\0')[0].decode()
class Tests(unittest.TestCase):
 def test_actual_pointer_graph_required(self):
  e=Model();self.assertEqual(len(m.registration(e,True)),3)
  e.ptr[(1,0)]=(2,1000)
  with self.assertRaises(ValueError):m.registration(e,True)
 def test_missing_duplicate_or_unexpected_suite(self):
  for enabled in (True,False):
   e=Model()
   if enabled:e.names[1]='other'
   with self.assertRaises(ValueError):m.registration(e,enabled)
  e=Model();e.headers[1]=(0,1,2,0,0,16);e.ptr[(1,8)]=(2,0)
  with self.assertRaises(ValueError):m.registration(e,True)
 def test_wrong_name_order_pointer_and_target(self):
  for mutate in (lambda e:e.ptr.update({(2,608):(2,1150)}),lambda e:e.ptr.update({(2,600):(2,0)}),lambda e:e.ptr.update({(2,600):(3,1)}),lambda e:e.symbols[0].update(name='unrelated'),lambda e:e.ptr.update({(2,672):(3,0)})):
   e=Model();mutate(e)
   with self.assertRaises(ValueError):m.registration(e,True)
 def test_terminator_and_parameter_hooks(self):
  for mutate in (lambda e:e.data.__setitem__(816,1),lambda e:e.ptr.update({(2,616):(3,0)}),lambda e:e.relocations.update({(2,816):'bad'})):
   e=Model();mutate(e)
   with self.assertRaises(ValueError):m.registration(e,True)
 def test_canonical_sentinel_rejects_zero_speed_status_pointer_and_padding(self):
  for offset,value in ((24,0),(24,2),(48,1),(0,1),(8,1),(16,1),(28,1),(32,1),(40,1),(56,1),(64,1),(71,1)):
   e=Model();e.data[816+offset]=value
   with self.subTest(offset=offset,value=value),self.assertRaises(ValueError):m.registration(e,True)
  e=Model();e.data[816:888]=bytes(72)
  with self.assertRaises(ValueError):m.registration(e,True)
 def test_sentinel_relocations_and_truncation(self):
  for offset in (0,24,48,71):
   e=Model();e.relocations[(2,816+offset)]='bad'
   with self.assertRaises(ValueError):m.registration(e,True)
  e=Model();e.data=e.data[:887]
  with self.assertRaises(ValueError):m.registration(e,True)
 def test_pinned_enum_and_constructor_contract(self):
  root=S.parents[1];header=(root/'include/kunit/test.h').read_text();constructor=(root/'rust/kernel/kunit.rs').read_text()
  generated='pub type kunit_status = ffi::c_uint;\npub type kunit_speed = ffi::c_uint;\npub const kunit_status_KUNIT_SUCCESS: kunit_status = 0;\npub const kunit_speed_KUNIT_SPEED_NORMAL: kunit_speed = 3;\n'
  m.sentinel_contract(header,generated,constructor)
  for h,g,c in ((header.replace('KUNIT_SUCCESS,','KUNIT_SUCCESS = 1,'),generated,constructor),
                (header.replace('KUNIT_SPEED_NORMAL,','KUNIT_SPEED_NORMAL = 4,'),generated,constructor),
                (header,generated.replace('= 3;','= 0;'),constructor),
                (header,generated.replace('= 0;','= 1;'),constructor),
                (header,generated.replace('ffi::c_uint','ffi::c_ulong'),constructor),
                (header,generated,constructor.replace('speed: kernel::bindings::kunit_speed_KUNIT_SPEED_NORMAL','speed: 0')),
                (header,generated,constructor.replace('status: kernel::bindings::kunit_status_KUNIT_SUCCESS','status: 1')),
                (header,generated,constructor.replace('run_case: None','run_case: Some(callback)'))):
   with self.assertRaises(ValueError):m.sentinel_contract(h,g,c)
 def test_global_definitions(self):
  text='\n'.join('0000 T '+n for n in m.ENTRIES);m.global_definitions(text,m.ENTRIES,True)
  for bad in (text.replace(' T ',' D ',1),text+'\n0000 T '+m.ENTRIES[0],text.split('\n',1)[1]):
   with self.assertRaises(ValueError):m.global_definitions(bad,m.ENTRIES,True)
  with self.assertRaises(ValueError):m.global_definitions(text,m.ENTRIES,False)
 def test_executable_bridge_relocations(self):
  text=''.join(f'0000 <{b}>:\n 0: jmp 0\n 1: R_X86_64_PLT32 {t}-0x4\n' for b,t in zip(m.BRIDGES,m.ENTRIES));m.bridge_calls(text)
  for bad in (text.replace('jmp','mov',1),text.replace(m.ENTRIES[0],'wrong',1),text.replace('-0x4','+0x4',1)):
   with self.assertRaises(ValueError):m.bridge_calls(bad)
class ArchiveTests(unittest.TestCase):
 def test_nested_helper_payload_is_bound(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);archive=root/'built-in.a';archive.write_bytes(b'!<thin>\n');obj=root/'helpers/helpers.o';obj.parent.mkdir();obj.write_bytes(b'actual object')
   good=SimpleNamespace(returncode=0,stderr=b'',stdout=b'actual object')
   with patch.object(m.subprocess,'run',return_value=good) as run:
    self.assertEqual(m.helper_payload(archive,[str(obj)],obj),m.digest(obj))
    self.assertEqual(run.call_args.args[0][-1],'helpers/helpers.o')
    for members in ([],[str(obj),str(obj)],['elsewhere/helpers.o']):
     with self.assertRaises(ValueError):m.helper_payload(archive,members,obj)
   bad=SimpleNamespace(returncode=0,stderr=b'',stdout=b'wrong payload')
   with patch.object(m.subprocess,'run',return_value=bad):
    with self.assertRaises(ValueError):m.helper_payload(archive,[str(obj)],obj)
 def test_regular_payload_and_diagnostics(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);archive=root/'built-in.a';archive.write_bytes(b'!<arch>\n');obj=root/'helpers/helpers.o';obj.parent.mkdir();obj.write_bytes(b'payload')
   with patch.object(m.subprocess,'run',return_value=SimpleNamespace(returncode=0,stderr=b'',stdout=b'payload')):
    self.assertEqual(m.helper_payload(archive,['helpers.o'],obj),m.digest(obj))
   for result in (SimpleNamespace(returncode=1,stderr=b'',stdout=b'payload'),SimpleNamespace(returncode=0,stderr=b'warning',stdout=b'payload')):
    with patch.object(m.subprocess,'run',return_value=result):
     with self.assertRaises(ValueError):m.helper_payload(archive,['helpers.o'],obj)

if __name__=='__main__':unittest.main()
