#!/usr/bin/env python3
"""Archive a mixed terminal result without converting build success into parity."""
from pathlib import Path
import gzip,hashlib,json,stat,subprocess
BASE=Path('/home/aaron/code/rusix');RUN=BASE/'linux-out/vma-lifecycle-verification-001';OUT=BASE/'linux-out/vma-lifecycle-initial-evidence';SRC=BASE/'linux-vma-lifecycle'
SOURCE='74258332885b9c41b373e1456a2922933b6e2a5a'
CASES=['shared_clone_write_and_exit','shared_clone_exec_detaches_mm','private_fork_cow','dontfork_omits_only_advised_range','wipeonfork_clears_child_and_grandchild','private_file_mapping_cow_and_lifetime','shared_file_mapping_survives_parent_unmap','mprotect_middle_split_and_restore','fixed_mremap_preserves_unlinked_file_mapping']
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def git(*args):return subprocess.check_output(['git','-C',str(SRC),*args],text=True).strip()
assert not OUT.exists()
assert git('rev-parse','HEAD')==SOURCE and not git('status','--porcelain')
assert (RUN/'matrix.exit').read_text().strip()=='1'
for side in ('c','rust'):
 p,=(RUN/side/'logs').glob('ci-vma-lifecycle-'+side+'-build.*')
 assert (p/'build.exit').read_text().strip()=='0'
assert (RUN/'c-postcheck.exit').read_text().strip()=='0' and not (RUN/'c-postcheck.stderr').read_bytes()
guest=RUN/'c/logs/ci-vma-lifecycle-c-vma-lifecycle.run'
result=json.loads((guest/'result.json').read_text());assert result['status']=='PASS' and result['cases']==CASES and result['source_revision']==SOURCE
for name in ('runner.exit','qemu.exit','selection.exit'):assert (guest/name).read_text().strip()=='0'
console=(guest/'console.log').read_text()
assert [line for line in console.splitlines() if 'RUSIX_VMA_LIFECYCLE_' in line]==[f'RUSIX_VMA_LIFECYCLE_CASE {name} PASS' for name in CASES]+['RUSIX_VMA_LIFECYCLE_PASS']
assert (RUN/'c/logs/container.exit').read_text().strip()=='0' and (RUN/'rust/logs/container.exit').read_text().strip()=='1'
assert not list((RUN/'rust/logs').glob('*-vma-lifecycle.run'))
assert 'Wrong Rust cache symbol' in (RUN/'rust/logs/container.log').read_text()
source=json.loads((RUN/'source-before.json').read_text());assert source['source']==SOURCE
for name,value in source['input_sha256'].items():assert sha(SRC/name)==value
OUT.mkdir();files={};raw={};compressed={};artifacts={};special={}
def copy(p,rel):
 assert p.is_file() and not p.is_symlink()
 data=p.read_bytes();data.decode('utf-8');assert b'\0' not in data
 value=hashlib.sha256(data).hexdigest();raw[str(p)]=value
 if len(data)>4*1024*1024:
  rel=Path(str(rel)+'.gz');compressed[str(rel)]={'sha256':value,'bytes':len(data),'raw_path':str(p)};data=gzip.compress(data,compresslevel=6,mtime=0)
 dest=OUT/rel;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data);files[str(rel)]=sha(dest)
for p in sorted(RUN.rglob('*')):
 rel=p.relative_to(RUN)
 if 'builds' in rel.parts or 'tmp' in rel.parts or any(x.endswith('-tmp') for x in rel.parts):continue
 if p.is_file():copy(p,Path('records')/rel)
for line in (RUN/'launcher.sha256').read_text().splitlines():
 value,name=line.split('  ',1);p=Path(name);assert sha(p)==value;copy(p,Path('launcher')/p.name)
for name in source['input_sha256']:
 if name.startswith(('mm/vma','mm/dup_mmap','kernel/mm_copy','rusix/scripts/')) or name in ('mm/mmap.c','mm/internal.h','mm/Makefile','init/Kconfig','rusix/ci/run.sh','rusix/ci/run-container.sh') or name.startswith(('rusix/tests/vma-lifecycle/','rusix/configs/x86_64-vma-lifecycle')):
  copy(SRC/name,Path('source')/name)
copy(Path(__file__),Path('archive-script.py'))
for side in ('c','rust'):
 for p in sorted((RUN/side/'builds').rglob('*')):
  info=p.lstat()
  if stat.S_ISREG(info.st_mode):
   value=sha(p);after=p.stat();assert (info.st_size,info.st_mtime_ns)==(after.st_size,after.st_mtime_ns)
   artifacts[str(p)]={'sha256':value,'bytes':info.st_size}
  elif stat.S_ISLNK(info.st_mode):special[str(p)]={'type':'symlink','target':str(p.readlink())}
  elif not stat.S_ISDIR(info.st_mode):special[str(p)]={'type':'special','mode':info.st_mode,'scope':'metadata only; never opened'}
assert git('rev-parse','HEAD')==SOURCE and not git('status','--porcelain')
for name,value in files.items():assert sha(OUT/name)==value
for name,value in raw.items():assert sha(Path(name))==value
for name,item in artifacts.items():assert sha(Path(name))==item['sha256']
for name,item in compressed.items():assert hashlib.sha256(gzip.decompress((OUT/name).read_bytes())).hexdigest()==item['sha256']
m=dict(status='FAIL',source=SOURCE,controller_session=34483,matrix_exit=1,c_build_exit=0,rust_build_exit=0,c_guest=result,c_pinned_postcheck='PASS',rust_guest_started=False,scope='C nine ordinary guest cases and pinned postcheck passed. Rust kernel built, but cache_owner rejected the emitted private cache symbol before guest. No paired parity or failure-path coverage claimed; no LLVM rerun by archiver.',raw_output=str(RUN),files=files,raw_input_sha256=raw,compressed_text=compressed,raw_artifacts=artifacts,special_artifacts=special)
(OUT/'manifest.json').write_text(json.dumps(m,indent=2,sort_keys=True)+'\n');print(json.dumps(dict(records=len(files),artifacts=len(artifacts),compressed=len(compressed),manifest_sha256=sha(OUT/'manifest.json')),indent=2))
