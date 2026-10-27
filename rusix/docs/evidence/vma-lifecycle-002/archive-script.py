#!/usr/bin/env python3
"""Archive terminal paired VMA lifecycle success with exact retained evidence."""
from pathlib import Path
import gzip,hashlib,json,stat,subprocess
BASE=Path('/home/aaron/code/rusix');RUN=BASE/'linux-out/vma-lifecycle-verification-002';OUT=BASE/'linux-out/vma-lifecycle-002-evidence';SRC=BASE/'linux-vma-lifecycle'
SOURCE='e0632d27293ba2e5b2eff3bc8baec405d8d4a233'
CASES=['shared_clone_write_and_exit','shared_clone_exec_detaches_mm','private_fork_cow','dontfork_omits_only_advised_range','wipeonfork_clears_child_and_grandchild','private_file_mapping_cow_and_lifetime','shared_file_mapping_survives_parent_unmap','mprotect_middle_split_and_restore','fixed_mremap_preserves_unlinked_file_mapping']
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def git(*args):return subprocess.check_output(['git','-C',str(SRC),*args],text=True).strip()
assert not OUT.exists()
assert git('rev-parse','HEAD')==SOURCE and not git('status','--porcelain')
assert (RUN/'matrix.exit').read_text().strip()=='0'
import importlib.util,sys,re
sys.path.insert(0,str(SRC/'rusix/scripts'))
spec=importlib.util.spec_from_file_location('guest',SRC/'rusix/scripts/test-vma-lifecycle-vm.py');guestmod=importlib.util.module_from_spec(spec);spec.loader.exec_module(guestmod)
pair=json.loads((RUN/'pair-result.json').read_text());assert pair['status']=='PASS' and pair['source']==SOURCE and pair['cases']==CASES and pair['different_settings']==['CONFIG_RUSIX_VMA_LIFECYCLE_RUST']
metadata={}
for label in ('c','rust','pair'):
 assert (RUN/(label+'-postcheck.exit')).read_text().strip()=='0' and not (RUN/(label+'-postcheck.stderr')).read_bytes()
for side in ('c','rust'):
 logs=RUN/side/'logs';build,=logs.glob('ci-vma-lifecycle-'+side+'-build.*')
 assert (build/'build.exit').read_text().strip()=='0'
 assert not re.search(r'warning:|error:|objtool:.*warning', (build/'build.log').read_text(),re.I)
 guest=logs/('ci-vma-lifecycle-'+side+'-vma-lifecycle.run')
 result=json.loads((guest/'result.json').read_text());assert result['status']=='PASS' and result['cases']==CASES and result['source_revision']==SOURCE
 assert guestmod.accept_console((guest/'console.log').read_text(),0)['cases']==CASES
 for name in ('runner.exit','qemu.exit','selection.exit'):assert (guest/name).read_text().strip()=='0'
 metadata[side]=json.loads((guest/'inputs.json').read_text())
 def resolve(name):
  if name.startswith('/src/'):return SRC/name[5:]
  if name.startswith('/out/'):return RUN/side/name[5:]
  return Path(name)
 def proof(obj):
  if isinstance(obj,dict):
   for key,val in obj.items():
    if key in ('input_sha256','archive_member_sha256'):
     for name,h in val.items():assert sha(resolve(name))==h,(name,h)
    else:proof(val)
  elif isinstance(obj,list):
   for x in obj:proof(x)
 proof(metadata[side]['selection'])
 for name,h in metadata[side]['artifacts'].items():assert sha(resolve(name))==h
 for name,h in metadata[side]['sources'].items():assert sha(SRC/name)==h
 assert metadata[side]['config_sha256']==sha(RUN/side/'builds'/('ci-vma-lifecycle-'+side)/'.config')
for name in ('init','probe','initramfs.cpio'):
 vals=[[v for k,v in metadata[side]['artifacts'].items() if Path(k).name==name] for side in ('c','rust')];assert len(vals[0])==1 and vals[0]==vals[1]
assert metadata['c']['sources']==metadata['rust']['sources']
assert (RUN/'source-before.json').read_bytes()==(RUN/'source-after.json').read_bytes()
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
# Archive current migration and its actual source dependency closure only.
# Earlier archives are referenced by manifest/commit, never recursively copied.
selected_sources=set()
def source_dependencies(record):
 if isinstance(record,dict):
  for key,value in record.items():
   if key in ('input_sha256','archive_member_sha256'):
    selected_sources.update(name[5:] for name in value if name.startswith('/src/'))
   else:source_dependencies(value)
 elif isinstance(record,list):
  for value in record:source_dependencies(value)
for side in ('c','rust'):source_dependencies(metadata[side]['selection'])
for name in source['input_sha256']:
 if name.startswith('rusix/docs/evidence/'):continue
 if name in selected_sources or name.startswith(('mm/vma_lifecycle','rusix/scripts/','rusix/tests/vma-lifecycle/','rusix/configs/x86_64-vma-lifecycle')) or name in ('mm/vma_init.c','mm/vma.h','mm/internal.h','mm/Makefile','init/Kconfig','rusix/ci/run.sh','rusix/ci/run-container.sh','rusix/PROGRESS.md'):
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
m=dict(status='PASS',source=SOURCE,matrix_exit=0,pair=pair,independent_audit='Raw console strict gate, diagnostics, source/config/fixture and nested selection artifact hashes verified read-only. Existing pinned postchecks retained; no compiler or VM rerun by archiver.',scope=pair['scope'],raw_output=str(RUN),files=files,raw_input_sha256=raw,compressed_text=compressed,raw_artifacts=artifacts,special_artifacts=special,prior_evidence={name:dict(commit=SOURCE,path='rusix/docs/evidence/'+name+'/manifest.json',sha256=sha(SRC/'rusix/docs/evidence'/name/'manifest.json')) for name in ('vma-lifecycle-initial','vma-lifecycle-gate-fix','vma-upstream-baseline')})
(OUT/'manifest.json').write_text(json.dumps(m,indent=2,sort_keys=True)+'\n');print(json.dumps(dict(records=len(files),artifacts=len(artifacts),compressed=len(compressed),manifest_sha256=sha(OUT/'manifest.json')),indent=2))
