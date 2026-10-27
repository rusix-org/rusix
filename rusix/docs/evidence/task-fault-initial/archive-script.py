#!/usr/bin/env python3
"""Preserve calibration failure: text records, compressed large text, binary hashes."""
from pathlib import Path
import gzip, hashlib, json, subprocess
BASE=Path('/home/aaron/code/rusix'); RUN=BASE/'linux-out/task-fault-verification-001'; OUT=BASE/'linux-out/task-fault-initial-evidence'; SRC=BASE/'linux-task-faults'
EXPECTED='8acd1a79a9cde4064f8b7ad3f967b48c52b60770'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def git(*a):return subprocess.check_output(['git','-C',str(SRC),*a],text=True).strip()
assert not OUT.exists()
assert git('rev-parse','HEAD')==EXPECTED and not git('status','--porcelain')
assert (RUN/'matrix.exit').read_text().strip()=='1' and not (RUN/'rust').exists()
proofs=list((RUN/'c/logs').glob('ci-task-construction-fault-c-build.*'));assert len(proofs)==1
assert (proofs[0]/'build.exit').read_text().strip()=='0'
assert 'Expected one attributable callsite pair, found 0' in (RUN/'c/logs/container.log').read_text()
assert not list(RUN.rglob('qemu-command.sh')) and not list(RUN.rglob('serial.log'))
OUT.mkdir();files={};raw={};compressed={};artifacts={}
def copy(p,rel):
 assert p.is_file() and not p.is_symlink()
 data=p.read_bytes(); original=hashlib.sha256(data).hexdigest();raw[str(p)]=original
 if b'\0' in data:
  artifacts[str(p)]={'sha256':original,'bytes':len(data),'scope':'Retained binary; not copied into text evidence'};return
 data.decode('utf-8')
 if len(data)>4*1024*1024:
  rel=Path(str(rel)+'.gz');data=gzip.compress(data,compresslevel=6,mtime=0)
  compressed[str(rel)]={'sha256':original,'bytes':p.stat().st_size,'raw_path':str(p)}
 dest=OUT/rel;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data);files[str(rel)]=hashlib.sha256(data).hexdigest()
for p in sorted(RUN.rglob('*')):
 if p.is_file() and not {'builds','tmp'} & set(p.relative_to(RUN).parts):copy(p,Path('records')/p.relative_to(RUN))
for line in (RUN/'launcher.sha256').read_text().splitlines():
 value,name=line.split('  ',1);p=Path(name);assert sha(p)==value;copy(p,Path('launcher')/p.name)
source=json.loads((RUN/'source-before.json').read_text())
assert source['source']==EXPECTED
for name,value in source['input_sha256'].items():
 p=SRC/name;assert sha(p)==value
 # Keep all production constructor and fault orchestration sources, not unrelated archives.
 if name.startswith(('kernel/task_construction','rusix/tests/task-construction','rusix/scripts/')) or name in ('kernel/fork.c','kernel/Makefile','init/Kconfig','rusix/ci/run.sh','rusix/ci/run-container.sh') or 'task-construction-fault' in name:
  copy(p,Path('source')/name)
copy(Path(__file__),Path('archive-script.py'))
build=RUN/'c/builds/ci-task-construction-fault-c'
for p in sorted(build.rglob('*')):
 if p.is_file() and not p.is_symlink() and (p.suffix in ('.o','.a') or p.name in ('vmlinux','vmlinux.map','bzImage','.config','System.map')):
  before=p.stat();value=sha(p);after=p.stat();assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns)
  artifacts[str(p)]={'sha256':value,'bytes':after.st_size,'scope':'C diagnostic build artifact; calibration rejected before VM'}
assert git('rev-parse','HEAD')==EXPECTED and not git('status','--porcelain')
for name,value in files.items():assert sha(OUT/name)==value
for name,value in raw.items():assert sha(Path(name))==value
for name,item in compressed.items():assert hashlib.sha256(gzip.decompress((OUT/name).read_bytes())).hexdigest()==item['sha256']
manifest=dict(status='FAIL',source=EXPECTED,matrix_exit=1,c_build_exit=0,vm_started=False,rust_started=False,scope='C diagnostic kernel built; actual-ELF calibration rejected zero attributable callsite pairs before VM. No fault captures or Rust execution.',raw_output=str(RUN),files=files,raw_input_sha256=raw,compressed_text=compressed,retained_artifacts=artifacts)
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
print(json.dumps(dict(text_records=len(files),binary_hashes=len(artifacts),compressed_records=len(compressed),manifest_sha256=sha(OUT/'manifest.json')),indent=2))
