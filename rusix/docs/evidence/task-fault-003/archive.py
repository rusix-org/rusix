#!/usr/bin/env python3
"""Independent terminal audit and compact task-constructor fault evidence."""
import collections,gzip,hashlib,json,re,shutil,subprocess
from pathlib import Path
BASE=Path('/home/aaron/code/rusix');RUN=BASE/'linux-out/task-fault-verification-003';SOURCE=BASE/'linux-task-faults'
OUT=BASE/'linux-out/task-fault-003-evidence';DEST=SOURCE/'rusix/docs/evidence/task-fault-003'
EXPECTED='0fd8196feea002fcfa2f058e3e2caa8b4d4009b4'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(p.read_text())
def git(*a):return subprocess.check_output(['git','-C',str(SOURCE),*a],text=True).strip()
def resolve(side,name):
 p=Path(name)
 if p.is_relative_to('/src'):return SOURCE/p.relative_to('/src')
 if p.is_relative_to('/out'):return RUN/side/p.relative_to('/out')
 raise ValueError('Unknown input mount '+name)
assert not OUT.exists() and not DEST.exists()
assert git('rev-parse','HEAD')==EXPECTED and not git('status','--porcelain')
source=read(RUN/'source-before.json');assert source==read(RUN/'source-after.json') and source['source']==EXPECTED
for name,value in source['input_sha256'].items():assert sha(SOURCE/name)==value,name
for name in ('matrix.exit','c-postcheck.exit','rust-postcheck.exit','pair-postcheck.exit'):assert (RUN/name).read_text().strip()=='0',name
for name in ('c-postcheck.stderr','rust-postcheck.stderr','pair-postcheck.stderr'):assert not (RUN/name).read_bytes()
pair=read(RUN/'pair-result.json');assert pair['status']=='PASS' and pair['source']==EXPECTED and pair['attempts_per_side']==18 and pair['different_settings']==['CONFIG_RUSIX_TASK_CONSTRUCTION_RUST']
launcher={}
for row in (RUN/'launcher.sha256').read_text().splitlines():
 value,name=row.split('  ',1);assert sha(Path(name))==value;launcher[name]=value
records_to_copy={};raw_artifacts={};summaries={};metadata={};configs={};proof_hashes=0
expected_counts={'uninjected-control':1,'task-slab-failure':1,'stack-page-failure':1,'not-injected':15}
for side in ('c','rust'):
 logs=RUN/side/'logs';profile='task-construction-fault-'+side;guest=logs/f'ci-{profile}-task-faults.run';build=RUN/side/'builds'/('ci-'+profile)
 for name in ('ci.exit','container.exit','launcher.exit'):assert (logs/name).read_text().strip()=='0'
 proofs=list(logs.glob('ci-'+profile+'-build.*'));assert len(proofs)==1;proof=proofs[0]
 for name in ('build.exit','task-preprocess.exit'):assert (proof/name).read_text().strip()=='0'
 for name in ('build.log','config.log','task-preprocess.log'):assert not re.search('warning:|error:|objtool.*warning',(proof/name).read_text(),re.I)
 assert (proof/'source-after.commit').read_text().strip()==EXPECTED and not (proof/'source-after.status').read_bytes()
 for row in (proof/'build.sha256').read_text().splitlines():
  value,name=row.split('  ',1);p=resolve(side,name);assert sha(p)==value;raw_artifacts[str(p)]={'sha256':value,'bytes':p.stat().st_size};proof_hashes+=1
 m=read(guest/'inputs.json');metadata[side]=m;r=read(guest/'result.json');selected=read(proof/'task-selection.json')
 assert m['selection']==selected==read(guest/'selection.json') and selected['status']=='PASS' and selected['implementation']==side
 assert r['status']=='PASS' and r['source_revision']==m['source_revision']==EXPECTED and r['qemu_exit']==0
 assert len(r['attempts'])==18 and dict(collections.Counter(a['classification'] for a in r['attempts']))==expected_counts
 assert len({a['pid'] for a in r['attempts']})==18
 for name in ('runner.exit','qemu.exit','selection.exit','init-compile.exit','controller-compile.exit','worker-compile.exit'):assert (guest/name).read_text().strip()=='0'
 assert not (guest/'selection.stderr').read_bytes()
 for name in ('init-compile.log','controller-compile.log','worker-compile.log'):assert not re.search('warning:|error:',(guest/name).read_text(),re.I)
 for group in (m['artifacts'],selected['input_sha256']):
  for name,value in group.items():
   p=resolve(side,name);assert sha(p)==value;raw_artifacts[str(p)]={'sha256':value,'bytes':p.stat().st_size};proof_hashes+=1
   if p.is_relative_to(build):records_to_copy['actual-build-inputs/'+side+'/'+str(p.relative_to(build))]=p
 for name,value in m['sources'].items():assert sha(SOURCE/name)==value;records_to_copy['source/'+name]=SOURCE/name
 packet=read(guest/'calibration/packet.json');assert packet['build_source']==EXPECTED
 for name,item in packet['inputs'].items():
  p=resolve(side,item['path']);assert sha(p)==item['sha256'];raw_artifacts[str(p)]={'sha256':item['sha256'],'bytes':p.stat().st_size};proof_hashes+=1
 assert (guest/'records/calibration.tsv').read_bytes()==(guest/'calibration/calibration.tsv').read_bytes()
 tsv=dict(line.split('\t',1) for line in (guest/'records/calibration.tsv').read_text().splitlines())
 assert bytes.fromhex(tsv['notes_hex'])==(guest/'calibration/notes').read_bytes()
 assert tsv['implementation']==side and tsv['build_source']==EXPECTED
 # Confirm each relevant emitted symbol address against the actual runtime map.
 symbols={}
 for row in (guest/'calibration/symbols').read_text().splitlines():
  fields=row.split()
  if len(fields)==4:symbols.setdefault(fields[3],[]).append(fields)
 runtime={}
 for row in (guest/'records/runtime-kallsyms').read_text().splitlines():
  fields=row.split()
  if len(fields)>=3:runtime.setdefault(fields[2],[]).append(fields)
 for key in ('slab_frame','stack_frame'):
  name=tsv[key].split('+',1)[0];entries=[a for a in symbols[name] if int(a[1],16)>0];assert len(entries)==1 and len(runtime[name])==1
  assert entries[0][0]==runtime[name][0][0]
 console=(guest/'console.log').read_text();wire={}
 for line in console.splitlines():
  match=re.fullmatch(r'RUSIX_TASK_FAULT_ARTIFACT ([a-z0-9_.-]+) ([0-9a-f]*)',line)
  if match:
   assert match[1] not in wire;wire[match[1]]=bytes.fromhex(match[2])
 assert len(wire)==98 and set(wire)=={p.name for p in (guest/'records').iterdir()}
 for name,data in wire.items():assert data==(guest/'records'/name).read_bytes()
 assert console.count('RUSIX_TASK_FAULT_CAPTURE_COMPLETE')==1 and console.count('RUSIX_TASK_FAULT_INIT_COMPLETE')==1
 for attempt in r['attempts']:
  label=attempt['label'];worker=(guest/'records'/f'{label}.worker').read_text()
  assert 'child_status=0 retry_status=0' in worker
  for cpu in ('cpu0','cpu1'):
   text=(guest/'records'/f'{label}.{cpu}').read_text()
   for field in ('overrun','commit overrun','dropped events'):assert re.search(r'^'+field+r': 0$',text,re.M)
  for row in (guest/'records'/f'{label}.probes').read_text().splitlines():assert row.split()[-1]=='0'
 for label in ('slab-1','stack-1'):
  trace=(guest/'records'/f'{label}.trace').read_text();arm=trace.index(': ARM');end=trace.index(': DISARM');assert arm<end
  interval=trace[arm:end]
  assert 'ret=-1 errno=12 remaining=0' in (guest/'records'/f'{label}.worker').read_text()
  if label=='stack-1':
   alloc=re.search(r'kmem_cache_alloc:.*ptr=([0-9a-f]+) name=task_struct',interval);assert alloc
   assert 'order=2 injected=1' in interval and 'order=2 result=0x0' in interval
   assert re.search(r'kmem_cache_free:.*ptr='+alloc[1]+r' name=task_struct',interval)
  else:assert 'result=-12' in interval and re.search(r'ptr=0+ name=task_struct',interval)
 command=(guest/'command.sh').read_text();assert 'nokaslr' in command and 'no_hash_pointers' in command
 assert (guest/'config').read_bytes()==(build/'.config').read_bytes()==(proof/'config').read_bytes()
 configs[side]={line.split('=',1)[0]:line.split('=',1)[1] for line in (build/'.config').read_text().splitlines() if line.startswith('CONFIG_')}
 summaries[side]={'attempts':18,'classifications':expected_counts,'runtime_frames':r['runtime_frames'],'raw_captures':98,'matched_stack_task_cleanup':True,'wire_capture_bytes_match':True}
assert {k for k in configs['c'].keys()|configs['rust'].keys() if configs['c'].get(k,'n')!=configs['rust'].get(k,'n')}=={'CONFIG_RUSIX_TASK_CONSTRUCTION_RUST'}
assert metadata['c']['sources']==metadata['rust']['sources'] and metadata['c']['container_image']==metadata['rust']['container_image']
for name in ('init','controller','worker'):
 a=[v for k,v in metadata['c']['artifacts'].items() if Path(k).name==name];b=[v for k,v in metadata['rust']['artifacts'].items() if Path(k).name==name];assert len(a)==1 and a==b
for name in ('packages.lock','toolchain.log','container-image-id.txt'):assert (RUN/'c/logs'/name).read_bytes()==(RUN/'rust/logs'/name).read_bytes()
# Preserve all actual run proof/trace records, excluding build caches and scratch.
for p in sorted(RUN.rglob('*')):
 rel=p.relative_to(RUN)
 if p.is_file() and not p.is_symlink() and not any(part=='builds' or part=='tmp' or part.endswith('-tmp') for part in rel.parts):records_to_copy['run/'+str(rel)]=p
for name in source['input_sha256']:
 if not name.startswith('rusix/docs/evidence/'):records_to_copy['source/'+name]=SOURCE/name
for name in launcher:records_to_copy['launcher/'+Path(name).name]=Path(name)
records_to_copy['archive.py']=Path(__file__).resolve()
old_refs={}
for dirname in ('task-fault-initial-evidence','task-fault-capture-failure-evidence','task-fault-calibration-fix-evidence','task-fault-harness-fix-evidence'):
 p=BASE/'linux-out'/dirname/'manifest.json'
 if p.exists():old_refs[str(p)]={'sha256':sha(p),'scope':'Historical evidence retained in place, not recursively copied'}
OUT.mkdir();files={};compressed={};raw={}
for name,p in sorted(records_to_copy.items()):
 assert not p.is_symlink();data=p.read_bytes();value=hashlib.sha256(data).hexdigest();raw[str(p)]=value
 try:
  if b'\0' in data:raise UnicodeError()
  data.decode('utf-8')
 except UnicodeError:
  raw_artifacts[str(p)]={'sha256':value,'bytes':len(data),'scope':'Binary retained in raw output; no binary payload copied'};continue
 stored=name
 if len(data)>262144:
  stored=name+'.gz';compressed[stored]={'sha256':value,'bytes':len(data)};data=gzip.compress(data,compresslevel=6,mtime=0)
 dest=OUT/stored;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data);files[stored]=sha(dest)
for name,value in files.items():assert sha(OUT/name)==value
for name,item in compressed.items():assert hashlib.sha256(gzip.decompress((OUT/name).read_bytes())).hexdigest()==item['sha256']
for name,value in raw.items():assert sha(Path(name))==value
assert git('rev-parse','HEAD')==EXPECTED and not git('status','--porcelain')
manifest={'status':'PASS','source':EXPECTED,'image':metadata['c']['container_image'],'scope':'Paired diagnostic task-slab and order2 stack-allocation failure attribution, successful controls/retries and matched slab cleanup. No general failure, MM, architecture or target-completion claim.',
 'matrix_exit':0,'pair':pair,'independent_audit':{'sides':summaries,'actual_hash_checks':proof_hashes,'source_inputs':len(source['input_sha256']),'fixture_binaries_identical':['init','controller','worker'],'initramfs_note':'Calibration packets and kernels differ intentionally'},
 'files':files,'compressed_text':compressed,'raw_input_sha256':raw,'raw_artifacts':raw_artifacts,'historical_evidence':old_refs,
 'source_snapshot_scope':'All non-evidence recorded project/kernel inputs and all fixture sources; all10685 original source-input hashes retained in run/source-before.json. Historical docs/evidence payloads referenced rather than recursively copied.'}
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
shutil.copytree(OUT,DEST)
for p in OUT.rglob('*'):
 if p.is_file():assert sha(p)==sha(DEST/p.relative_to(OUT))
print(json.dumps({'status':'PASS','files':len(files),'compressed':len(compressed),'binary_hashes':len(raw_artifacts),'manifest_sha256':sha(OUT/'manifest.json')},indent=2))
