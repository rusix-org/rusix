#!/usr/bin/env python3
"""Retain audited full archive, publish concise text plus exhaustive raw hashes."""
from pathlib import Path
import hashlib,json,shutil
BASE=Path('/home/aaron/code/rusix');out=BASE/'linux-out/mm-exit-mmap-config-evidence';full=BASE/'linux-out/mm-exit-mmap-config-evidence-full';tracked=BASE/'linux-mm-exit-mmap/rusix/docs/evidence/mm-exit-mmap-config'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert not full.exists()
m=json.loads((out/'manifest.json').read_text())
assert sha(out/'manifest.json')==sha(tracked/'manifest.json')
for n,v in m['files'].items():assert sha(out/n)==sha(tracked/n)==v
out.rename(full);out.mkdir()
keep={};omitted={}
for name,value in m['files'].items():
 parts=Path(name).parts
 profile=len(parts)>3 and parts[:2]==('records','builds') and parts[2] in ('exit-mmap-c','exit-mmap-rust','exit-mmap-kunit-c','exit-mmap-kunit-rust')
 tail='/'.join(parts[3:])
 if profile and tail not in ('.config','include/generated/autoconf.h','include/config/auto.conf','include/config/auto.conf.cmd'):
  raw=(BASE/'linux-out/mm-exit-mmap-config-001')/Path(*parts[1:]);assert sha(raw)==value
  omitted[str(raw)]={'sha256':value,'bytes':raw.stat().st_size,'full_archive_record':name}
 else:
  p=out/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(full/name,p);assert sha(p)==value;keep[name]=value
m['files']=keep;m['unpublished_generated_text']=omitted;m['full_archive']={'path':str(full),'manifest_sha256':sha(full/'manifest.json'),'records':len(keep)+len(omitted)}
m['scope']+='; generated headers/dependency markers retained in full local archive and exhaustively hashed, not all copied into Git'
shutil.copyfile(Path(__file__),out/'slim-archive-script.py');m['files']['slim-archive-script.py']=sha(out/'slim-archive-script.py')
(out/'manifest.json').write_text(json.dumps(m,indent=2,sort_keys=True)+'\n')
# This exact uncommitted tree was created by this agent and verified above.
shutil.rmtree(tracked);shutil.copytree(out,tracked)
for n,v in m['files'].items():assert sha(tracked/n)==v
print(json.dumps({'published_records':len(m['files']),'omitted_generated_records':len(omitted),'retained_binary_hashes':len(m['retained_binary_sha256']),'manifest_sha256':sha(out/'manifest.json')},indent=2))
