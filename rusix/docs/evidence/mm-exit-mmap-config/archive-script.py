#!/usr/bin/env python3
"""Independent configuration evidence audit; no compilation or tool regeneration."""
from pathlib import Path
import gzip,hashlib,importlib.util,json,re,subprocess
BASE=Path('/home/aaron/code/rusix');RUN=BASE/'linux-out/mm-exit-mmap-config-001';DRAFT=BASE/'linux-out/mm-exit-mmap-config-draft';OUT=BASE/'linux-out/mm-exit-mmap-config-evidence'
SOURCE='8ec785568045a3cd2245e87d1854a7f5ab664ef3';IMAGE='sha256:c02eb3929889b3f0cc035d57a02c844e0c74c71d24fbda1311249faeb8257f63'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def load(name,p):
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
assert not OUT.exists()
for n in ('launcher.exit','container.exit'):assert (RUN/n).read_text().strip()=='0'
assert (RUN/'source.commit').read_text().strip()==SOURCE
for line in (RUN/'launcher.sha256').read_text().splitlines():
 value,name=line.split('  ',1);assert sha(Path(name))==value
inspect=json.loads((RUN/'container-inspect.json').read_text())[0];assert inspect['Image']==IMAGE and inspect['State']['ExitCode']==0 and not inspect['State']['OOMKilled']
h=inspect['HostConfig'];assert h['NanoCpus']==1000000000 and h['Memory']==h['MemorySwap']==1073741824 and h['NetworkMode']=='none' and h['CapDrop']==['ALL'] and h['Devices']==[]
assert next(m for m in inspect['Mounts'] if m['Destination']=='/src')['RW'] is False
assert json.loads((RUN/'image-inspect.json').read_text())[0]['Id']==IMAGE
archive=load('archive_input_audit',DRAFT/'archive-inputs.py');inventory=json.loads((RUN/'archive-inputs.json').read_text())
assert sha(RUN/'source.tar')==inventory['archive_sha256']
assert archive.archive_inventory(RUN/'source.tar')==inventory['members']
archive.verify(RUN/'source',inventory['members'])
builds=RUN/'builds';result=json.loads((builds/'result.json').read_text());assert result['source']==SOURCE and result['status']=='PASS'
assert (builds/'inputs-before.json').read_bytes()==(builds/'inputs-after.json').read_bytes()
for n in ('before','after'):assert sha(builds/('inputs-'+n+'.json'))==result['inputs_'+n+'_sha256']
assert sha(RUN/'archive-inputs.json')==result['archive_inventory_sha256']
def values(text):
 out={}
 for line in text.splitlines():
  if line.startswith('CONFIG_'):k,v=line.split('=',1);assert k not in out;out[k]=v
  elif line.startswith('# CONFIG_') and line.endswith(' is not set'):k=line[2:-11];assert k not in out;out[k]='n'
 return out
configs={}
for profile,wants in result['requested'].items():
 assert profile in ('exit-mmap-c','exit-mmap-rust','exit-mmap-kunit-c','exit-mmap-kunit-rust')
 assert (builds/(profile+'.exit')).read_text().strip()=='0'
 assert not re.search('warning:|error:',(builds/(profile+'.log')).read_text(),re.I)
 p=builds/profile/'.config';assert sha(p)==result['config_sha256'][profile];configs[profile]=values(p.read_text())
 assert values((RUN/f'source/rusix/configs/x86_64-{profile}.config').read_text())==wants
 assert all(configs[profile].get(k,'n')==v for k,v in wants.items())
 assert result['commands'][profile]==['make','-C','/src','O=/out/'+profile,'LLVM=1','KCONFIG_ALLCONFIG=/src/rusix/configs/x86_64-'+profile+'.config','allnoconfig']
def delta(a,b):return {k:[a.get(k,'n'),b.get(k,'n')] for k in a.keys()|b.keys() if a.get(k,'n')!=b.get(k,'n')}
assert len(configs)==4
for kind in ('','kunit-'):assert delta(configs['exit-mmap-'+kind+'c'],configs['exit-mmap-'+kind+'rust'])=={'CONFIG_RUSIX_EXIT_MMAP_RUST':['n','y']}
expected={k:['n','y'] for k in ('CONFIG_KUNIT','CONFIG_KUNIT_AUTORUN_ENABLED','CONFIG_KUNIT_DEFAULT_ENABLED','CONFIG_RUNTIME_TESTING_MENU','CONFIG_RUSIX_EXIT_MMAP_TEST')};expected['CONFIG_KUNIT_DEFAULT_TIMEOUT']=['n','300']
for side in ('c','rust'):assert delta(configs['exit-mmap-'+side],configs['exit-mmap-kunit-'+side])==expected==result['ordinary_kunit_delta'][side]
OUT.mkdir();files={};raw={};compressed={};binaries={str(RUN/'source.tar'):{'sha256':sha(RUN/'source.tar'),'bytes':(RUN/'source.tar').stat().st_size}}
def copy(p,rel):
 data=p.read_bytes();value=hashlib.sha256(data).hexdigest();raw[str(p)]=value
 try:data.decode('utf-8');assert b'\0' not in data
 except (UnicodeDecodeError,AssertionError):binaries[str(p)]={'sha256':value,'bytes':len(data)};return
 if len(data)>4*1024*1024:
  rel=Path(str(rel)+'.gz');compressed[str(rel)]={'sha256':value,'bytes':len(data)};data=gzip.compress(data,mtime=0)
 q=OUT/rel;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(data);files[str(rel)]=sha(q)
for p in sorted(RUN.rglob('*')):
 rel=p.relative_to(RUN)
 if rel.parts[0] in ('source','tmp') or p.name=='source.tar' or p.is_symlink():continue
 if p.is_file():copy(p,Path('records')/rel)
for p in DRAFT.iterdir():
 if p.is_file():copy(p,Path('launcher')/p.name)
copy(Path(__file__),Path('archive-script.py'))
for n,v in raw.items():assert sha(Path(n))==v
for n,v in files.items():assert sha(OUT/n)==v
for n,v in binaries.items():assert sha(Path(n))==v['sha256']
m={'status':'PASS','source':SOURCE,'scope':'Four actual pinned Kconfig resolutions and host config utilities only; no kernel objects, candidate ELF selection or VM execution','controller_session':88078,'result':result,'files':files,'raw_input_sha256':raw,'compressed_text':compressed,'retained_binary_sha256':binaries,'archive_source_entries':len(inventory['members'])}
(OUT/'manifest.json').write_text(json.dumps(m,indent=2,sort_keys=True)+'\n');print(json.dumps({'records':len(files),'binary_hashes':len(binaries),'manifest_sha256':sha(OUT/'manifest.json')},indent=2))
