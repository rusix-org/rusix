#!/usr/bin/env python3
"""Preserve successful pinned postchecks; rehash artifacts without rerunning LLVM."""
from pathlib import Path
import gzip, hashlib, json, re, stat, subprocess
BASE=Path('/home/aaron/code/rusix');RUN=BASE/'linux-out/mm-copy-verification-001';OUT=BASE/'linux-out/mm-copy-001-evidence';SRC=BASE/'linux-mm-copy'
SOURCE='32e7c3e7b0ae825b84416b260098c2d98cd45865'
CASES=['shared_clone_write_and_exit','shared_clone_exec_detaches_mm','private_fork_cow']
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def git(*args):return subprocess.check_output(['git','-C',str(SRC),*args],text=True).strip()
assert not OUT.exists()
assert git('rev-parse','HEAD')==SOURCE and not git('status','--porcelain')
assert (RUN/'matrix.exit').read_text().strip()=='0'
result=json.loads((RUN/'pair-result.json').read_text());assert result['status']=='PASS' and result['source']==SOURCE and result['cases']==CASES and result['different_settings']==['CONFIG_RUSIX_MM_COPY_RUST']
assert (RUN/'source-before.json').read_bytes()==(RUN/'source-after.json').read_bytes()
source=json.loads((RUN/'source-before.json').read_text());assert source['source']==SOURCE
for name,value in source['input_sha256'].items():assert sha(SRC/name)==value
files={};raw={};compressed={};artifacts={};special={};sourcepaths=set()
OUT.mkdir()
def copy(p,rel):
 assert p.is_file() and not p.is_symlink(),str(p)
 data=p.read_bytes();data.decode('utf-8');assert b'\0' not in data,'Binary copy rejected '+str(p)
 value=hashlib.sha256(data).hexdigest();raw[str(p)]=value
 if len(data)>4*1024*1024:
  rel=Path(str(rel)+'.gz');compressed[str(rel)]={'sha256':value,'bytes':len(data),'raw_path':str(p)};data=gzip.compress(data,compresslevel=6,mtime=0)
 dest=OUT/rel;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data);files[str(rel)]=sha(dest)
for side in ('c','rust'):
 logs=RUN/side/'logs';build=RUN/side/'builds'/('ci-mm-copy-'+side)
 for n in ('container.exit','ci.exit','launcher.exit'):assert (logs/n).read_text().strip()=='0'
 proof,=logs.glob('ci-mm-copy-'+side+'-build.*')
 assert (proof/'build.exit').read_text().strip()=='0'
 guest=logs/('ci-mm-copy-'+side+'-mm-copy.run')
 for n in ('runner.exit','qemu.exit','selection.exit','init-compile.exit','probe-compile.exit'):assert (guest/n).read_text().strip()=='0'
 accepted=json.loads((guest/'result.json').read_text());assert accepted['status']=='PASS' and accepted['cases']==CASES and accepted['implementation']==side and accepted['source_revision']==SOURCE
 for label in (side,'pair'):
  assert (RUN/(label+'-postcheck.exit')).read_text().strip()=='0' and not (RUN/(label+'-postcheck.stderr')).read_bytes()
 selection=json.loads((proof/'mm-copy-selection.json').read_text());assert selection['status']=='PASS' and selection['implementation']==side
 assert selection==json.loads((guest/'selection.json').read_text())
 metadata=json.loads((guest/'inputs.json').read_text());assert metadata['selection']==selection
 def verify_map(mapping):
  for name,value in mapping.items():
   p=Path(name)
   if p.is_relative_to('/src'):
    host=SRC/p.relative_to('/src');sourcepaths.add(host)
   elif p.is_relative_to('/out'):host=RUN/side/p.relative_to('/out')
   else:raise ValueError('Unexpected input path '+name)
   assert sha(host)==value,name
 verify_map(selection['input_sha256']);verify_map(metadata['artifacts'])
 for name,value in metadata['sources'].items():assert sha(SRC/name)==value;sourcepaths.add(SRC/name)
 for line in (proof/'build.sha256').read_text().splitlines():
  value,name=line.split('  ',1);verify_map({name:value})
 # Full retained build/guest artifact inventory, not only linked proof inputs.
 for p in sorted((RUN/side/'builds').rglob('*')):
  info=p.lstat()
  if stat.S_ISREG(info.st_mode):
   value=sha(p);after=p.stat();assert (info.st_size,info.st_mtime_ns)==(after.st_size,after.st_mtime_ns)
   artifacts[str(p)]={'sha256':value,'bytes':info.st_size}
  elif stat.S_ISLNK(info.st_mode):special[str(p)]={'type':'symlink','target':str(p.readlink())}
  elif not stat.S_ISDIR(info.st_mode):special[str(p)]={'type':'special','mode':info.st_mode,'scope':'metadata only; never opened'}
for p in sorted(RUN.rglob('*')):
 rel=p.relative_to(RUN)
 if 'builds' in rel.parts or 'tmp' in rel.parts or any(x.endswith('-tmp') for x in rel.parts):continue
 if p.is_file():copy(p,Path('records')/rel)
for line in (RUN/'launcher.sha256').read_text().splitlines():
 value,name=line.split('  ',1);p=Path(name);assert sha(p)==value;copy(p,Path('launcher')/p.name)
for p in sorted(sourcepaths):copy(p,Path('source')/p.relative_to(SRC))
copy(Path(__file__),Path('archive-script.py'))
assert git('rev-parse','HEAD')==SOURCE and not git('status','--porcelain')
for name,value in files.items():assert sha(OUT/name)==value
for name,value in raw.items():assert sha(Path(name))==value
for name,item in compressed.items():assert hashlib.sha256(gzip.decompress((OUT/name).read_bytes())).hexdigest()==item['sha256']
for name,item in artifacts.items():assert sha(Path(name))==item['sha256']
manifest=dict(status='PASS',source=SOURCE,controller_session=86741,matrix_exit=0,scope='Three matched ordinary shared-MM/exec/COW guest cases. Existing pinned postchecks preserved and all retained artifacts rehashed; archive does not rerun LLVM or establish allocation-failure coverage.',raw_output=str(RUN),result=result,files=files,raw_input_sha256=raw,compressed_text=compressed,raw_artifacts=artifacts,special_artifacts=special)
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
print(json.dumps(dict(records=len(files),artifact_hashes=len(artifacts),compressed=len(compressed),manifest_sha256=sha(OUT/'manifest.json')),indent=2))
