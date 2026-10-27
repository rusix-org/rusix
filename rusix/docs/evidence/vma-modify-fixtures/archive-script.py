#!/usr/bin/env python3
"""Archive both successful static-only compile attempts; never invoke guest ELFs."""
import difflib,hashlib,json,re,shlex,shutil,stat,subprocess
from pathlib import Path
BASE=Path('/home/aaron/code/rusix');NATIVE=BASE/'linux-mm-copy-vma';CANDIDATE=BASE/'linux-mm-vma-modify'
SCRATCH=BASE/'linux-out/vma-modify-fixtures-evidence';DEST=CANDIDATE/'rusix/docs/evidence/vma-modify-fixtures'
SOURCE='99fd3dd96ac0b6131c34501dff9626e95b063037';BASELINE='2926d88bb7fc4608fd942453d929c39e4e5ec006'
IMAGE='sha256:c02eb3929889b3f0cc035d57a02c844e0c74c71d24fbda1311249faeb8257f63'
def sha(path):
 with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def need(ok,message):
 if not ok:raise ValueError(message)
def load(path):return json.loads(path.read_text())
def git(*args):return subprocess.check_output(['git','-C',str(NATIVE),*args],text=True).strip()
need(not SCRATCH.exists() and not DEST.exists(),'Archive destination exists')
need(git('rev-parse','HEAD')==SOURCE and not git('status','--porcelain'),'Frozen native source changed')
results={};reviews={};raw={};binary={};launchers={};headers={}
for attempt in ('001','002'):
 run=BASE/('linux-out/vma-modify-fixtures-compile-'+attempt);e=run/'evidence'
 result=load(e/'result.json');results[attempt]=result
 need(result['status']=='PASS' and result['native_source']==SOURCE and result['baseline']==BASELINE,'Result source/status differs')
 for name in ('launcher.exit','container.exit'):need((run/name).read_text().strip()=='0','Compile attempt not terminal success')
 need((run/'source-before.json').read_bytes()==(run/'source-after.json').read_bytes(),'Host source identities changed')
 need((e/'inputs-before.json').read_bytes()==(e/'inputs-after.json').read_bytes(),'Container inputs changed')
 source=load(run/'source-before.json');review=load(run/'fixture/fixture-review.json');reviews[attempt]=review
 need(source['native_source']==SOURCE and source['image']==IMAGE and source['native_tree']==git('rev-parse',SOURCE+'^{tree}'),'Frozen source attribution differs')
 need(sha(run/'fixture/fixture-review.json')==source['fixture_review_sha256'],'Fixture review changed')
 need(source['fixture_sha256']==result['fixture_sha256']==review['fixture_sha256'],'Fixture hash inventories differ')
 upstream=load(run/'fixture/rusix/tests/vma-modify/upstream.json')
 need(upstream['baseline']==BASELINE and set(upstream['files'])==set(source['native_sha256']) and len(upstream['files'])==7,'Native input inventory differs')
 for name,record in upstream['files'].items():
  for commit in (SOURCE,BASELINE):
   data=subprocess.check_output(['git','-C',str(NATIVE),'show',commit+':'+name])
   need(hashlib.sha256(data).hexdigest()==record['sha256'] and git('rev-parse',commit+':'+name)==record['blob'],'Native baseline bytes/blob differ')
  need(sha(NATIVE/name)==record['sha256']==source['native_sha256'][name],'Native working bytes differ')
 for name,value in source['fixture_sha256'].items():need(sha(run/'fixture'/name)==value,'Frozen fixture snapshot changed')
 expected_inputs={str(Path('/source')/n):v for n,v in source['native_sha256'].items()}
 expected_inputs.update({str(Path('/fixture')/n):v for n,v in source['fixture_sha256'].items()})
 need(load(e/'inputs-before.json')==expected_inputs,'Compiled input inventory differs')
 for path in e.glob('*.exit'):need(path.read_text().strip()=='0','Compiler/tool failure: '+path.name)
 for path in e.glob('*.stderr'):need(not path.read_bytes(),'Compiler/tool diagnostic: '+path.name)
 for label in ('merge-compile','vm_util-compile','thp_settings-compile','init-compile'):need(not (e/(label+'.stdout')).read_bytes(),'Unexpected compiler output')
 for name in ('merge','vm_util','thp_settings'):
  cmd=['/usr/bin/gcc','-std=gnu11','-O2','-Wall','-Wunreachable-code','-U_FORTIFY_SOURCE','-Werror','-MD','-MF','/out/evidence/'+name+'.d','-MT','/out/artifacts/'+name+'.o','-c','/source/tools/testing/selftests/mm/'+name+'.c','-o','/out/artifacts/'+name+'.o']
  need(load(e/(name+'-compile-command.json'))==cmd,'Native compile command differs')
 need(load(e/'probe-link-command.json')==['/usr/bin/gcc','-static','/out/artifacts/merge.o','/out/artifacts/vm_util.o','/out/artifacts/thp_settings.o','-lrt','-lpthread','-lm','-Wl,-t','-o','/out/artifacts/probe'],'Static link command differs')
 need(load(e/'init-compile-command.json')==['/usr/bin/rustc','--edition','2021','--target','x86_64-unknown-linux-gnu','-C','target-feature=+crt-static','-C','panic=abort','-C','opt-level=2','/fixture/rusix/tests/vma-modify/init.rs','-o','/out/artifacts/init'],'Rust compile command differs')
 for name in ('init','probe'):
  path=run/'artifacts'/name;record=result['artifacts'][name]
  need(sha(path)==record['sha256'] and path.stat().st_size==record['bytes'] and stat.S_IMODE(path.stat().st_mode)==0o644,'Guest binary changed/mode executable')
  need(record['mode']=='0o644' and record['executed'] is False,'Guest metadata scope differs')
  need(load(e/(name+'-readelf-command.json'))==['/usr/bin/readelf','-h','-l','-d','--wide','/out/artifacts/'+name],'Unexpected ELF inspection command')
  elf=(e/(name+'-readelf.stdout')).read_text()
  need('ELF64' in elf and 'Advanced Micro Devices X86-64' in elf and 'INTERP' not in elf and '(NEEDED)' not in elf,'Not recorded static x86-64 ELF')
 for path in sorted((run/'artifacts').iterdir()):
  need(path.is_file() and not path.is_symlink(),'Unexpected artifact kind')
  binary[str(path)]={'sha256':sha(path),'bytes':path.stat().st_size,'mode':oct(stat.S_IMODE(path.stat().st_mode)),'executed':False}
 deps=load(e/'native-header-inputs.json');headers[attempt]=deps
 declared=set()
 for name in ('merge','vm_util','thp_settings'):
  target,body=(e/(name+'.d')).read_text().replace('\\\n',' ').split(':',1)
  need(target=='/out/artifacts/'+name+'.o','Dependency target differs');declared.update(shlex.split(body))
 need(declared==set(deps) and len(deps)==187,'Exact native/system dependency inventory differs')
 for name,record in deps.items():
  need(Path(name).is_absolute() and re.fullmatch('[0-9a-f]{64}',record['sha256']) and record['bytes']>0,'Malformed dependency record')
  resolved=Path(record['resolved'])
  if resolved.is_relative_to('/source'):
   host=NATIVE/resolved.relative_to('/source');need(sha(host)==record['sha256'] and host.stat().st_size==record['bytes'],'Native dependency drift')
  else:need(resolved.is_relative_to('/usr'),'Unexpected system dependency namespace')
 rustlibs=load(e/'rust-library-inputs.json');need(len(rustlibs)==27 and all(re.fullmatch('[0-9a-f]{64}',v) for v in rustlibs.values()),'Rust library hash inventory differs')
 container=load(run/'container-inspect.json')[0];host=container['HostConfig']
 need(container['Image']==IMAGE and container['State']['ExitCode']==0 and not container['State']['OOMKilled'],'Container result/image differs')
 need(host['NanoCpus']==1000000000 and host['Memory']==host['MemorySwap']==1073741824 and host['PidsLimit']==128,'Resource limits differ')
 need(host['NetworkMode']=='none' and host['CapDrop']==['ALL'] and host['Devices']==[] and host['ReadonlyRootfs'] and 'no-new-privileges' in host['SecurityOpt'],'Isolation differs')
 need(container['Config']['User']=='1000:1000' and container['Config']['Cmd']==['python3','-B','/compile.py'],'Unexpected container execution')
 mounts={m['Destination']:m for m in container['Mounts']}
 need(set(mounts)=={'/compile.py','/fixture','/source','/out/artifacts','/out/evidence','/out/tmp'},'Unexpected container mount')
 need(mounts['/source']['Source']==str(NATIVE) and mounts['/fixture']['Source']==str(run/'fixture'),'Wrong source mount')
 need(all(not mounts[n]['RW'] for n in ('/source','/fixture','/compile.py')) and all(mounts[n]['RW'] for n in ('/out/artifacts','/out/evidence','/out/tmp')),'Mount permissions differ')
 need(load(run/'image-inspect.json')[0]['Id']==IMAGE and (run/'image-id.txt').read_text().strip()==IMAGE,'Image metadata differs')
 launcher={}
 for line in (run/'launcher.sha256').read_text().splitlines():
  value,name=line.split('  ',1);need(name not in launcher and sha(Path(name))==value,'Launcher drift/duplicate');launcher[name]=value
 need({Path(n).name for n in launcher}=={'run.sh','preflight.py','compile.py','fixture-review.json','README.md'},'Launcher inventory differs');launchers[attempt]=launcher
old=(BASE/'linux-out/vma-modify-fixtures-compile-001/fixture/rusix/tests/vma-modify/init.rs').read_text();new=(BASE/'linux-out/vma-modify-fixtures-compile-002/fixture/rusix/tests/vma-modify/init.rs').read_text()
formatted,count=re.subn(r'^(\s*)\.arg\("-r"\)\.arg\("([^"]+)"\)$',lambda m:m[1]+'.arg("-r")\n'+m[1]+'.arg("'+m[2]+'")',old,flags=re.M)
need(count==5 and formatted==new,'Unexpected non-format fixture delta')
changed=[n for n,v in results['001']['fixture_sha256'].items() if results['002']['fixture_sha256'].get(n)!=v]
need(changed==['rusix/tests/vma-modify/init.rs'],'Unexpected fixture changes between attempts')
need(headers['001']==headers['002'],'Native/system dependency sets differ')
for name,value in results['002']['fixture_sha256'].items():need(sha(CANDIDATE/name)==value,'Current final fixture differs from002 compilation')
SCRATCH.mkdir();files={}
def copy(path,relative):
 data=path.read_bytes();data.decode('utf-8');need(b'\0' not in data,'Binary passed to text archive')
 target=SCRATCH/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
 files[str(relative)]=sha(target);raw[str(path)]=sha(path)
for attempt in ('001','002'):
 run=BASE/('linux-out/vma-modify-fixtures-compile-'+attempt)
 for path in sorted(run.rglob('*')):
  rel=path.relative_to(run)
  if rel.parts[0] in ('artifacts','tmp'):continue
  if path.is_file():copy(path,Path('records')/attempt/rel)
 for name in launchers[attempt]:copy(Path(name),Path('launcher')/attempt/Path(name).name)
for name in reviews['002']['native_sha256']:copy(NATIVE/name,Path('native')/name)
copy(Path(__file__),Path('archive-script.py'))
delta=dict(status='FORMAT_ONLY',changed_fixture=changed[0],changed_lines=count,before_sha256=results['001']['fixture_sha256'][changed[0]],after_sha256=results['002']['fixture_sha256'][changed[0]],exact_transformation='Split each of five paired .arg calls onto separate identically indented lines; all other bytes equal',unified_diff=''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='001/init.rs',tofile='002/init.rs')))
(SCRATCH/'format-delta.json').write_text(json.dumps(delta,indent=2)+'\n');files['format-delta.json']=sha(SCRATCH/'format-delta.json')
for name,value in raw.items():need(sha(Path(name))==value,'Raw record changed while archiving')
for name,record in binary.items():need(sha(Path(name))==record['sha256'],'Raw binary changed while archiving')
manifest=dict(status='PASS',native_source=SOURCE,baseline=BASELINE,image=IMAGE,fixture_state='Uncommitted candidate fixture snapshots:001 before formatting;002 final reviewed bytes. Mutable kernel candidate was never mounted or compiled.',final_attempt='002',results=results,files=files,raw_input_sha256=raw,retained_binary_sha256=binary,native_system_header_count=187,rust_library_count=27,system_dependency_scope='Hash inventories captured and rechecked inside immutable pinned compile containers; system paths were not rehashed against unrelated host headers.',format_delta=delta,scope='Two successful static compilation/readelf checks only; first pre-format result preserved. Neither guest binary executed. No candidate kernel, VM, actual console or Rust selection verification.')
(SCRATCH/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n');shutil.copytree(SCRATCH,DEST)
for tree in (SCRATCH,DEST):
 for name,value in files.items():need(sha(tree/name)==value,'Archive copy changed')
need(sha(SCRATCH/'manifest.json')==sha(DEST/'manifest.json'),'Manifest copy differs')
paths=['rusix/docs/evidence/vma-modify-fixtures/manifest.json']+['rusix/docs/evidence/vma-modify-fixtures/'+n for n in files]
(BASE/'linux-out/vma-modify-fixtures-stage-paths.txt').write_text('\n'.join(paths)+'\n')
print(json.dumps(dict(status='PASS',records=len(files),raw_records=len(raw),raw_binaries=len(binary),stage_paths=len(paths),manifest_sha256=sha(DEST/'manifest.json')),indent=2))
