#!/usr/bin/env python3
"""Read-only retained-source/object prerequisites; no compilation or guest execution."""
import hashlib,json,subprocess
from pathlib import Path
BASE=Path('/home/aaron/code/rusix');DRAFT=Path(__file__).resolve().parent
SOURCE=BASE/'linux-mm-exit-mmap';FIX=BASE/'linux-mm-exit-mmap-fix'
RAW=BASE/'linux-out/mm-exit-mmap-verification-001/kunit-c'
INSPECT=BASE/'linux-out/exit-mmap-fixture-gate-reinspection-002'
EXPECTED='0ff7a933c198dda0c3e2c0005e4bb97db3867acc'
IMAGE='sha256:c02eb3929889b3f0cc035d57a02c844e0c74c71d24fbda1311249faeb8257f63'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for x in iter(lambda:f.read(1024*1024),b''):h.update(x)
 return h.hexdigest()
def check():
 ready=json.loads((DRAFT/'ready.json').read_text());assert ready['enabled'] is True,'Draft disabled pending root and independent review'
 for n,h in ready['draft_sha256'].items():assert sha(DRAFT/n)==h,n
 pins=json.loads((DRAFT/'inputs.json').read_text())
 for n,h in pins['sha256'].items():assert sha(Path(n))==h,n
 for root,names in pins['inventories'].items():
  assert len(names)==len(set(names)),'Duplicate inventory: '+root
  assert all(not Path(n).is_absolute() and '..' not in Path(n).parts and str(Path(n))==n for n in names),'Noncanonical inventory: '+root
  assert sorted(str(p.relative_to(root)) for p in Path(root).rglob('*') if p.is_file())==sorted(names),root
 assert subprocess.check_output(['git','-C',str(SOURCE),'rev-parse','HEAD'],text=True).strip()==EXPECTED
 assert not subprocess.check_output(['git','-C',str(SOURCE),'status','--porcelain','--untracked-files=all'])
 assert (INSPECT/'inspection.exit').read_text().strip()=='0' and not (INSPECT/'stderr.log').read_bytes()
 result=json.loads((INSPECT/'result.json').read_text());proof=json.loads((INSPECT/'actual-selection.json').read_text())
 assert result['status']=='PASS' and result['original_source']==EXPECTED
 assert proof['status']=='PASS' and proof['implementation']=='c' and proof['test_context']=='exit-mmap-kunit-v1'
 assert proof['fixture_selection']['enabled'] and proof['fixture_selection']['cases']==['empty_final_users_retains_storage','mapped_final_users_closes_before_file_put','fixed_replace_close_dummy_reset']
 def hashes(o):
  if isinstance(o,dict):
   for k,v in o.items():
    if k in ('input_sha256','archive_member_sha256'):
     for n,h in v.items():assert sha(Path(n))==h,n
    else:hashes(v)
  elif isinstance(o,list):
   for v in o:hashes(v)
 hashes(proof)
 for n,h in result['fixed_tooling_sha256'].items():assert sha(FIX/n)==h,n
 container=json.loads((INSPECT/'container-inspect.json').read_text())[0]
 assert container['Image']==IMAGE and container['State']['ExitCode']==0 and not container['State']['OOMKilled']
 resources=container['HostConfig']
 assert resources['NanoCpus']==10**9 and resources['Memory']==2**31 and resources['MemorySwap']==2**31
 assert resources['NetworkMode']=='none' and resources['CapDrop']==['ALL'] and resources['ReadonlyRootfs'] and not resources['Devices']
 assert all(not m['RW'] or m['Destination']==str(INSPECT) for m in container['Mounts'])
 assert (RAW/'logs/container.exit').read_text().strip()=='1'
 assert (RAW/'logs/ci-exit-mmap-kunit-c-build.Rvh4zoui/exit-mmap-selection.json').read_bytes()==b''
 assert 'CONFIG_RUSIX_EXIT_MMAP_RUST=y' not in (RAW/'builds/ci-exit-mmap-kunit-c/.config').read_text()
 return {'status':'PASS','source':EXPECTED,'attribution':'Original retained C teardown kernel; separately corrected object verifier; initial matrix remains failed','pinned_files':len(pins['sha256'])}
if __name__=='__main__':print(json.dumps(check(),indent=2))
