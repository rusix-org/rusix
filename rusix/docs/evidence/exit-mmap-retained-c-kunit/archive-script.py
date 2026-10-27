#!/usr/bin/env python3
from pathlib import Path
import hashlib,json,subprocess,stat
BASE=Path('/home/aaron/code/rusix');RUN=BASE/'linux-out/exit-mmap-retained-c-kunit-001';DRAFT=BASE/'linux-out/exit-mmap-retained-c-kunit-draft';SRC=BASE/'linux-mm-exit-mmap';FIX=BASE/'linux-mm-exit-mmap-fix';OUT=FIX/'rusix/docs/evidence/exit-mmap-retained-c-kunit'
SOURCE='0ff7a933c198dda0c3e2c0005e4bb97db3867acc';CHECKER='13e0ddc71a57d7576e9cc6f34603bd96d5bbfa08'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for x in iter(lambda:f.read(1024*1024),b''):h.update(x)
 return h.hexdigest()
for n in ['boots.exit','container.exit','launcher.exit','host-after-check.exit','container-inspect.exit']:assert (RUN/n).read_text().strip()=='0'
assert not (RUN/'host-after-check.stderr').read_bytes()
for n in ['prerequisite-before.json','prerequisite-after.json','host-after-check.json']:
 d=json.loads((RUN/n).read_text());assert d['status']=='PASS' and d['source']==SOURCE and d['pinned_files']==5469
pins=json.loads((DRAFT/'inputs.json').read_text())
for n,h in pins['sha256'].items():assert sha(Path(n))==h,n
for root,names in pins['inventories'].items():assert len(names)==len(set(names)) and sorted(str(p.relative_to(root)) for p in Path(root).rglob('*') if p.is_file())==sorted(names)
for label,count,combined in [('retained-c-combined',79,True),('retained-c-isolated',3,False)]:
 for kind in ['qemu','parse','gate']:assert (RUN/'logs'/f'{label}-{kind}.exit').read_text().strip()=='0'
 assert (RUN/f'{label}-runner.exit').read_text().strip()=='0'
 assert (RUN/'logs'/f'{label}-gate.log').read_text().strip()==f'mapping teardown KUnit acceptance passed: {count} required cases, all PASS'
 argv=['python3','-B',str(SRC/'rusix/scripts/validate-exit-mmap-kunit.py'),str(RUN/'logs'/f'{label}-kunit.json')]+(['--combined'] if combined else [])
 subprocess.run(argv,check=True,capture_output=True,text=True)
c=json.loads((RUN/'container-inspect.json').read_text())[0];h=c['HostConfig'];assert c['Image']=='sha256:c02eb3929889b3f0cc035d57a02c844e0c74c71d24fbda1311249faeb8257f63' and c['State']['ExitCode']==0 and not c['State']['Running'] and not c['State']['OOMKilled'];assert h['NanoCpus']==2*10**9 and h['Memory']==2**31 and h['MemorySwap']==2**31 and h['NetworkMode']=='none' and h['CapDrop']==['ALL'] and h['ReadonlyRootfs'];assert [x['PathOnHost'] for x in h['Devices']]==['/dev/kvm'];assert all(not m['RW'] or m['Destination']==str(RUN) for m in c['Mounts'])
assert not OUT.exists();OUT.mkdir(parents=True);files={};raw={};special={}
def copy(p,n):
 data=p.read_bytes();data.decode('utf8');assert b'\0' not in data
 t=OUT/n;t.parent.mkdir(parents=True,exist_ok=True);t.write_bytes(data);files[str(n)]=sha(t);raw[str(p)]={'sha256':sha(p),'bytes':len(data),'mode':stat.S_IMODE(p.stat().st_mode)}
for p in sorted(RUN.rglob('*')):
 if p.is_symlink():special[str(p)]={'type':'symlink','target':str(p.readlink())}
 elif p.is_file():copy(p,Path('records')/p.relative_to(RUN))
for line in (RUN/'launcher.sha256').read_text().splitlines():
 h,n=line.split('  ',1);p=Path(n);assert sha(p)==h;copy(p,Path('launcher')/p.name)
copy(Path(__file__),Path('archive-script.py'))
prior={}
for tree,commit,name in [(BASE/'linux-mm-exit-mmap-evidence','2c5cb433fda90480d492261a38222922f3d02cc5','mm-exit-mmap-initial'),(FIX,CHECKER,'exit-mmap-fixture-gate-fix')]:
 n='rusix/docs/evidence/'+name+'/manifest.json';prior[n]={'commit':commit,'sha256':sha(tree/n)}
m={'status':'PASS','scope':'Retained original C teardown kernel: strict79 combined and3 isolated KUnit cases passed. No rebuild, no Rust teardown KUnit execution, no complete paired-matrix acceptance. Original matrix remains failed.','source':SOURCE,'checker_commit':CHECKER,'files':files,'raw_input_sha256':raw,'special_artifacts':special,'prior_evidence':prior,'immutable_input_count':len(pins['sha256']),'audit':'All5469 pins/inventories rehashed, strict original JSON gates independently rerun (host parser only), actual Docker limits checked. No VM/compiler invoked by archiver.'}
(OUT/'manifest.json').write_text(json.dumps(m,indent=2,sort_keys=True)+'\n');print('records',len(files),'manifest',sha(OUT/'manifest.json'))
