#!/usr/bin/env python3
"""Archive attributed host/tool evidence; no candidate build or VM claim."""
import gzip,hashlib,json,shutil
from pathlib import Path
BASE=Path('/home/aaron/code/rusix');RAW=BASE/'linux-out';SOURCE=BASE/'linux-mm-exit-mmap'
OUT=RAW/'mm-exit-mmap-kunit-tooling-evidence';DEST=SOURCE/'rusix/docs/evidence/mm-exit-mmap-kunit-tooling'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(p.read_text())
assert not OUT.exists() and not DEST.exists()
old=read(RAW/'exit-mmap-routing-host-001/result.json');new=read(RAW/'exit-mmap-routing-host-002/result.json')
assert old['status']==new['status']=='PASS' and old['cases']==329 and new['cases']==331 and new['suites']==32
assert new['source_unchanged_during_checks'] and new['input_count']==164
for directory,record,key in [('exit-mmap-routing-host-001',old,'logs_sha256'),('exit-mmap-routing-host-002',new,'records_sha256')]:
 for name,value in record[key].items():assert sha(RAW/directory/name)==value,(directory,name)
old_inputs=read(RAW/'exit-mmap-routing-host-001/inputs.json');inputs=read(RAW/'exit-mmap-routing-host-002/inputs-before.json')
assert len(inputs)==164
for name,value in inputs.items():assert sha(SOURCE/name)==value,name
changed={name:old_inputs[name] for name in old_inputs if old_inputs[name]!=inputs.get(name)}
assert set(changed)=={'rusix/scripts/verify-exit-mmap.py','rusix/scripts/exit_kunit_elf.py','rusix/tests/test_exit_kunit_elf.py'}
helper=RAW/'exit-helper-archive-check-002';hm=read(helper/'manifest.json');hr=read(helper/'result.json')
for name,value in hm['records'].items():assert sha(helper/name)==value
for name,value in hm['source_files'].items():assert sha(BASE/name)==value
assert hr['status']=='PASS' and (helper/'launcher.exit').read_text().strip()=='0' and not (helper/'stderr.log').read_bytes()
artifact_base=RAW/'mm-release-verification-003/rust/builds/ci-mm-release-rust/rust'
artifacts={}
for name,value in hr['inputs'].items():
 p=artifact_base/Path(name).relative_to('/artifacts');assert sha(p)==value
 artifacts[str(p)]={'sha256':value,'bytes':p.stat().st_size}
files={}
for directory in ('exit-mmap-routing-host-001','exit-mmap-routing-host-002','exit-helper-archive-check-001','exit-helper-archive-check-002'):
 for p in (RAW/directory).iterdir():
  if p.is_file():files[directory+'/'+p.name]=p
for name in inputs:files['final-inputs/'+name]=SOURCE/name
files['archive.py']=Path(__file__).resolve()
for p in files.values():
 assert not p.is_symlink();data=p.read_bytes();assert b'\0' not in data;data.decode('utf-8')
OUT.mkdir();records={}
for name,p in sorted(files.items()):
 data=p.read_bytes();rawhash=hashlib.sha256(data).hexdigest();compressed=len(data)>32768
 stored=name+'.gz' if compressed else name;q=OUT/stored;q.parent.mkdir(parents=True,exist_ok=True)
 q.write_bytes(gzip.compress(data,mtime=0) if compressed else data)
 records[stored]={'sha256':sha(q),'bytes':q.stat().st_size,'original':str(p),'uncompressed_sha256':rawhash,'uncompressed_bytes':len(data),'encoding':'gzip-utf8' if compressed else 'utf8'}
manifest={'status':'PASS','source_base':'3be164215e02002db32d856a4323cb8fd522d06c',
 'scope':'Final host routing/model regressions32 suites331 cases on164 snapshotted inputs; no Kconfig resolution, candidate compilation or VM. Separate pinned LLVM19 helper extraction used historical release artifacts only.',
 'final_host':{'suites':32,'cases':331,'inputs':164,'record':'exit-mmap-routing-host-002/result.json'},
 'prior_host':{'suites':old['suites'],'cases':329,'record':'exit-mmap-routing-host-001/result.json','source_versions_available_only_as_hashes':changed,'unchanged_sources_use_final_snapshots':True},
 'historical_archive_probe':'Actual helpers.o extraction through llvm-ar pP; not proof of uncompiled new KUnit registration.',
 'retained_failure':'exit-helper-archive-check-001 Docker socket sandbox rejection; no container started. Empty result preserved.',
 'raw_artifacts':artifacts,'files':records}
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
for name,record in records.items():
 p=OUT/name;assert sha(p)==record['sha256'];data=p.read_bytes();data=gzip.decompress(data) if record['encoding']=='gzip-utf8' else data;assert hashlib.sha256(data).hexdigest()==record['uncompressed_sha256']
shutil.copytree(OUT,DEST)
for p in OUT.rglob('*'):
 if p.is_file():assert sha(p)==sha(DEST/p.relative_to(OUT))
print(json.dumps({'status':'PASS','records':len(records),'gzip_records':sum(x['encoding']=='gzip-utf8' for x in records.values()),'manifest_sha256':sha(OUT/'manifest.json')},indent=2))
