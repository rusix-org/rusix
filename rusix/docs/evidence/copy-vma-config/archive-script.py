#!/usr/bin/env python3
"""Independent configuration evidence audit; no compilation or tool regeneration."""
from pathlib import Path
import gzip,hashlib,importlib.util,json,re,subprocess
BASE=Path('/home/aaron/code/rusix');RUN=BASE/'linux-out/copy-vma-config-001';DRAFT=BASE/'linux-out/copy-vma-config-draft';OUT=BASE/'linux-out/copy-vma-config-evidence'
SOURCE='344b3b272c4e94ac5f7d337baa47dbd244bef191';IMAGE='sha256:c02eb3929889b3f0cc035d57a02c844e0c74c71d24fbda1311249faeb8257f63'
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
 assert profile in ('copy-vma-c','copy-vma-rust')
 assert (builds/(profile+'.exit')).read_text().strip()=='0'
 assert not re.search('warning:|error:',(builds/(profile+'.log')).read_text(),re.I)
 p=builds/profile/'.config';assert sha(p)==result['config_sha256'][profile];configs[profile]=values(p.read_text())
 assert values((RUN/f'source/rusix/configs/x86_64-{profile}.config').read_text())==wants
 assert all(configs[profile].get(k,'n')==v for k,v in wants.items())
 assert result['commands'][profile]==['make','-C','/src','O=/out/'+profile,'LLVM=1','KCONFIG_ALLCONFIG=/src/rusix/configs/x86_64-'+profile+'.config','allnoconfig']
def delta(a,b):return {k:[a.get(k,'n'),b.get(k,'n')] for k in a.keys()|b.keys() if a.get(k,'n')!=b.get(k,'n')}
assert len(configs)==2
assert delta(configs['copy-vma-c'],configs['copy-vma-rust'])=={'CONFIG_RUSIX_COPY_VMA_RUST':['n','y']}
for values_ in configs.values():
 assert values_.get('CONFIG_MEMFD_CREATE')=='y' and values_.get('CONFIG_KUNIT','n')=='n'
 assert not any(k.startswith('CONFIG_RUSIX_') and k.endswith('_TEST') and v!='n' for k,v in values_.items())
assert not any(n.startswith('rusix/docs/evidence/') for n in inventory['members'])
snapshot=json.loads((RUN/'snapshot.json').read_text());assert snapshot['source']==SOURCE
assert snapshot['omitted_evidence']['source']==SOURCE and snapshot['omitted_evidence']['path']=='rusix/docs/evidence'
assert (RUN/'source-after.commit').read_text().strip()==SOURCE
assert sha(builds/'environment.json')==result['environment_sha256']
OUT.mkdir();files={};raw={};compressed={};omitted={};binaries={str(RUN/'source.tar'):{'sha256':sha(RUN/'source.tar'),'bytes':(RUN/'source.tar').stat().st_size}}
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
 if p.is_file():
  if len(rel.parts)>2 and rel.parts[0]=='builds' and rel.parts[1] in configs and '/'.join(rel.parts[2:]) not in ('.config','include/generated/autoconf.h','include/config/auto.conf','include/config/auto.conf.cmd'):
   value=sha(p);raw[str(p)]=value
   with p.open('rb') as stream:head=stream.read(4)
   if head==b'\x7fELF':binaries[str(p)]={'sha256':value,'bytes':p.stat().st_size}
   else:omitted[str(p)]={'sha256':value,'bytes':p.stat().st_size}
  else:copy(p,Path('records')/rel)
for p in DRAFT.rglob('*'):
 if p.is_file():copy(p,Path('launcher')/p.relative_to(DRAFT))
copy(Path(__file__),Path('archive-script.py'))
for n,v in raw.items():assert sha(Path(n))==v
for n,v in files.items():assert sha(OUT/n)==v
for n,v in binaries.items():assert sha(Path(n))==v['sha256']
m={'status':'PASS','source':SOURCE,'scope':'Two actual pinned Kconfig resolutions and host config utilities only; no kernel objects, candidate ELF selection or VM execution; prior evidence excluded and referenced, generated dependencies hash-only/raw retained','controller_session':11634,'unpublished_generated_text':omitted,'result':result,'files':files,'raw_input_sha256':raw,'compressed_text':compressed,'retained_binary_sha256':binaries,'archive_source_entries':len(inventory['members'])}
(OUT/'manifest.json').write_text(json.dumps(m,indent=2,sort_keys=True)+'\n');print(json.dumps({'records':len(files),'binary_hashes':len(binaries),'manifest_sha256':sha(OUT/'manifest.json')},indent=2))
