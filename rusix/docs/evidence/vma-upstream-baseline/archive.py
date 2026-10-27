#!/usr/bin/env python3
"""Archive audited pristine C evidence; never copy executable payloads."""
import hashlib, importlib.util, json, shutil
from pathlib import Path
ROOT=Path('/home/aaron/code/rusix/linux-out')
RAW=ROOT/'vma-upstream-baseline-001'
DRAFT=ROOT/'vma-upstream-baseline-draft'
OUT=ROOT/'vma-upstream-baseline-evidence'
DEST=ROOT.parent/'linux-vma-lifecycle/rusix/docs/evidence/vma-upstream-baseline'
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def dump(p,v):p.write_text(json.dumps(v,indent=2,sort_keys=True)+'\n')
assert not OUT.exists() and not DEST.exists()
spec=importlib.util.spec_from_file_location('audit',DRAFT/'check.py'); mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
acceptance=mod.results(RAW/'execution',RAW/'inputs')
assert acceptance['status']=='PASS'
for name in ('launcher.exit','container.exit','build.exit','test.exit'):
    assert (RAW/'execution'/name).read_text().strip()=='0'
for row in (RAW/'execution/launcher.sha256').read_text().splitlines():
    digest,name=row.split(maxsplit=1);assert sha(Path(name))==digest
assert (RAW/'execution/inputs-before.json').read_bytes()==(RAW/'execution/inputs-after.json').read_bytes()
inputs=json.loads((RAW/'inputs/manifest.json').read_text())
result=json.loads((RAW/'execution/result.json').read_text())
assert len(inputs['files'])==7748
build=(RAW/'execution/build.log').read_text()
commands=[s for s in build.splitlines() if s.startswith('gcc ')]
assert commands and all('-fsanitize=address' in s and '-fsanitize=undefined' in s for s in commands)
files={}
for p in (RAW/'execution').iterdir():
    if p.is_file():files['execution/'+p.name]=p
files['inputs/manifest.json']=RAW/'inputs/manifest.json'
files['preparation-failure.json']=RAW/'preparation-failure.json'
for p in DRAFT.iterdir():
    if p.is_file():files['launcher/'+p.name]=p
for p in (ROOT/'vma-tooling-001').iterdir():
    if p.is_file():files['tooling/'+p.name]=p
for name in ('tools/testing/vma/Makefile','tools/testing/vma/vma.c','tools/testing/shared/shared.mk','mm/vma_init.c'):
    p=RAW/'inputs/tree'/name
    if p.exists():files['source/'+name]=p
files['archive.py']=Path(__file__).resolve()
# Validate every payload before creating output; binaries remain only hash records.
for p in files.values():
    assert not p.is_symlink(),p
    b=p.read_bytes();assert b'\0' not in b,p;b.decode('utf-8')
OUT.mkdir()
records={}
for name,p in sorted(files.items()):
    q=OUT/name;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(p.read_bytes())
    records[name]={'sha256':sha(q),'bytes':q.stat().st_size,'original':str(p)}
raw_artifacts={'inputs/upstream.tar':{'sha256':sha(RAW/'inputs/upstream.tar'),'bytes':(RAW/'inputs/upstream.tar').stat().st_size}}
for p in sorted((RAW/'execution/tree').rglob('*')):
    if p.is_file() and not p.is_symlink() and str(p.relative_to(RAW/'execution/tree')) not in inputs['files']:
        raw_artifacts[str(p.relative_to(RAW))]={'sha256':sha(p),'bytes':p.stat().st_size}
manifest={'status':'PASS','source':inputs['source'],'image':inputs['image'],'scope':acceptance['scope'],'tests':16,'cases':result['cases'] if 'cases' in result else result.get('tests'),'original_source_inputs':7748,'all_compile_and_link_commands_use_asan_ubsan':True,'default_sanitizer_environment':True,'source_inputs_unchanged_before_after':True,'generated_artifacts_revalidated':True,'files':records,'raw_artifacts':raw_artifacts,'preparation_failure_retained':True}
dump(OUT/'manifest.json',manifest)
for name,record in records.items():assert sha(OUT/name)==record['sha256']
shutil.copytree(OUT,DEST)
for p in OUT.rglob('*'):
    if p.is_file():assert sha(p)==sha(DEST/p.relative_to(OUT))
print(json.dumps({'status':'PASS','files':len(records),'raw_artifacts':len(raw_artifacts),'manifest_sha256':sha(OUT/'manifest.json'),'destination':str(DEST)},indent=2))
