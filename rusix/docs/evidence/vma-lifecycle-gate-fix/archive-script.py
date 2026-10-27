#!/usr/bin/env python3
"""Archive retained-kernel selection reinspection; no compiler or VM invocation."""
from pathlib import Path
import gzip
import hashlib
import json
import shutil
import subprocess

BASE=Path('/home/aaron/code/rusix')
SOURCE=BASE/'linux-vma-lifecycle'
RAW=BASE/'linux-out/vma-lifecycle-gate-fix-001'
HOST=BASE/'linux-out/vma-lifecycle-gate-fix-host-001'
REVIEW=BASE/'linux-out/vma-lifecycle-cache-name-review-001'
BUILD_OUTPUT=BASE/'linux-out/vma-lifecycle-verification-001/rust'
OUT=BASE/'linux-out/vma-lifecycle-gate-fix-evidence'
TRACKED=SOURCE/'rusix/docs/evidence/vma-lifecycle-gate-fix'
COMPILED='74258332885b9c41b373e1456a2922933b6e2a5a'

def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def need(value,message):
    if not value:raise ValueError(message)

def resolve(name):
    p=Path(name)
    need(p.is_absolute() and '..' not in p.parts,'Noncanonical selected input')
    if p.is_relative_to('/src'):return SOURCE/p.relative_to('/src')
    if p.is_relative_to('/out'):return BUILD_OUTPUT/p.relative_to('/out')
    raise ValueError('Unexpected selected mount: '+name)

need(not OUT.exists() and not TRACKED.exists(),'Archive already exists')
need((RAW/'actual-selection.exit').read_text().strip()=='0' and not (RAW/'actual-selection.stderr').read_bytes(),'Verifier failed/diagnostics')
selected=json.loads((RAW/'actual-selection.json').read_text())
need(selected['status']=='PASS' and selected['implementation']=='rust' and len(selected['input_sha256'])==85,'Wrong actual result inventory')
inputs={}
def collect(record):
    for key,value in record.items():
        if key=='input_sha256':
            for name,sha256 in value.items():
                need(name not in inputs or inputs[name]==sha256,'Conflicting nested inputs');inputs[name]=sha256
        elif isinstance(value,dict):collect(value)
collect(selected)
need(len(inputs)==85,'Outer input inventory does not cover nested proofs')
for name,value in inputs.items():need(sha(resolve(name))==value,'Actual selection input changed: '+name)
fix=json.loads((RAW/'fix-source.json').read_text())
for name,value in fix.items():need(sha(SOURCE/name)==value,'Fix source drift')
review=json.loads((REVIEW/'fix-review.json').read_text());need(review['inputs']==fix,'Reviewed different fix')
need((HOST/'tests.exit').read_text().strip()=='0' and 'Ran 11 tests' in (HOST/'tests.log').read_text() and '\nOK\n' in (HOST/'tests.log').read_text(),'Host regression failure')
need(subprocess.check_output(['git','-C',str(SOURCE),'rev-parse','HEAD'],text=True).strip()==COMPILED,'Unexpected source ancestor')
prior=BASE/'linux-out/vma-lifecycle-initial-evidence/manifest.json'
need(sha(prior)=='24c45050ab6fb499be36fd181053b5f1046cd6ad70920b7a1780fb816707ffd6','Prior failure reference changed')
OUT.mkdir();files={};raw_hashes={};compressed={}
def copy(p,relative):
    value=sha(p);raw_hashes[str(p)]=value
    data=p.read_bytes();data.decode('utf-8');need(b'\0' not in data,'Nontext archive input')
    if len(data)>4*1024*1024:
        relative=Path(str(relative)+'.gz');compressed[str(relative)]={'raw_sha256':value,'raw_bytes':len(data),'path':str(p)};data=gzip.compress(data,mtime=0)
    destination=OUT/relative;destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(data);files[str(relative)]=sha(destination)
for p in sorted(RAW.rglob('*')):
    if p.is_file() and 'tmp' not in p.relative_to(RAW).parts:copy(p,Path('records')/p.relative_to(RAW))
for p in sorted(REVIEW.iterdir()):
    if p.is_file():copy(p,Path('review')/p.name)
for p in sorted(HOST.iterdir()):
    if p.is_file():copy(p,Path('host')/p.name)
for name in fix:copy(SOURCE/name,Path('source')/name)
copy(Path(__file__),Path('archive-script.py'))
manifest=dict(status='PASS',compiled_kernel_source=COMPILED,verifier_state='Uncommitted two-file correction on compiled source ancestor',
    source_sha256=fix,controller_session=43808,host_command=['python3','-B','linux-vma-lifecycle/rusix/tests/test_vma_lifecycle_selection.py'],host_tests=11,
    actual_selection_input_sha256=inputs,retained_inputs={str(resolve(n)):{'sha256':v,'bytes':resolve(n).stat().st_size} for n,v in inputs.items()},
    prior_failure_reference={'path':str(prior),'source':COMPILED,'sha256':sha(prior),'status':'FAIL'},
    files=files,raw_input_sha256=raw_hashes,compressed_text=compressed,
    scope='Full pinned command selection reinspection passes against retained Rust001 kernel;11 host negatives pass. No kernel rebuild or VM. Historical pending review/status records retained unchanged; this manifest records the later actual PASS. Original paired run remains failed. Resource settings are recorded by command; this --rm run retained no container-inspect record.')
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
for n,v in files.items():need(sha(OUT/n)==v,'Archive drift')
for n,v in raw_hashes.items():need(sha(Path(n))==v,'Raw text drift')
for n,v in inputs.items():need(sha(resolve(n))==v,'Postarchive ELF/source drift')
shutil.copytree(OUT,TRACKED)
for n,v in files.items():need(sha(TRACKED/n)==v,'Tracked copy drift')
need(sha(TRACKED/'manifest.json')==sha(OUT/'manifest.json'),'Manifest copy drift')
print(json.dumps({'status':'PASS','records':len(files),'actual_inputs':len(inputs),'manifest_sha256':sha(OUT/'manifest.json')},indent=2))
