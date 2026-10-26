#!/usr/bin/env python3
"""Archive terminal MM-release003 evidence; no build/VM/LLVM invocation."""
import hashlib, importlib.util, json, re, shutil, subprocess, sys
from pathlib import Path
sys.dont_write_bytecode=True
BASE=Path('/home/aaron/code/rusix'); SOURCE=BASE/'linux-mm-release'
RUN=BASE/'linux-out/mm-release-verification-003'
DRAFT=BASE/'linux-out/mm-release-ffi-retry-draft'
OUT=BASE/'linux-out/mm-release-003-evidence'
SHA='cfc899021ac624d392d0241009374bb40acd3b49'
sys.path.insert(0,str(SOURCE/'rusix/scripts'))
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def need(v,msg):
 if not v:raise ValueError(msg)
def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def zero(p):need(p.read_text().strip()=='0','Failed '+str(p))
def hashes(p):
 rows={}
 for line in p.read_text().splitlines():
  m=re.fullmatch(r'([0-9a-f]{64})  (.+)',line);need(m and m[2] not in rows,'Malformed hashes '+str(p));rows[m[2]]=m[1]
 return rows
def main():
 need(not OUT.exists(),'Destination exists')
 need(subprocess.check_output(['git','-C',str(SOURCE),'rev-parse','HEAD'],text=True).strip()==SHA,'Source revision changed')
 need(not subprocess.check_output(['git','-C',str(SOURCE),'status','--porcelain'],text=True),'Dirty source')
 gate=load('gate',SOURCE/'rusix/scripts/validate-mm-release-kunit.py')
 sel=load('sel',SOURCE/'rusix/scripts/verify-mm-release.py')
 textcheck=load('archive_base',BASE/'linux-out/archive-mm-construction-001.py').text_file
 zero(RUN/'matrix.exit')
 result=json.loads((RUN/'pair-result.json').read_text())
 need(result==dict(status='PASS',source=SHA,different_settings=['CONFIG_RUSIX_MM_RELEASE_RUST'],combined=80,core=67,release=4,scope='KUnit release lifetime/refcount cases; no ordinary-consumer or allocation-failure claim'),'Pair result differs')
 launcher=hashes(RUN/'launcher.sha256')
 need(set(launcher)=={str(DRAFT/n) for n in ('run.sh','preflight.py','check-results.py','prepare-caches.py')},'Launcher inventory')
 for p,h in launcher.items():need(digest(Path(p))==h,'Launcher changed')
 before=json.loads((RUN/'source-before.json').read_text())
 need(before==json.loads((RUN/'source-after.json').read_text()) and before['source']==SHA,'Source changed')
 for p,h in before['input_sha256'].items():need(digest(SOURCE/p)==h,'Source input changed '+p)
 raw={};configs=[]
 for label in ('c','rust','pair'):
  zero(RUN/(label+'-postcheck.exit'));need(not (RUN/(label+'-postcheck.stderr')).read_bytes(),'Pinned postcheck diagnostics')
  need((RUN/(label+'-postcheck-image.txt')).read_text().strip()==before['image'],'Pinned inspection image differs')
 for side in ('c','rust'):
  logs=RUN/side/'logs';build=RUN/side/'builds'/('ci-mm-release-'+side)
  def resolve(name):
   p=Path(name);need(p.is_absolute() and '..' not in p.parts,'Invalid path')
   if p.is_relative_to('/src'):return SOURCE/p.relative_to('/src')
   if p.is_relative_to('/out'):return RUN/side/p.relative_to('/out')
   raise ValueError('Unexpected mount '+name)
  def bind(mapping):
   for p,h in mapping.items():
    actual=resolve(p);need(digest(actual)==h,'Artifact changed '+p)
    if Path(p).is_relative_to('/out'):raw[str(actual)]=h
  for name in ('container.exit','ci.exit','launcher.exit'):zero(logs/name)
  need(json.loads((logs/'postchecks.json').read_text())==dict(status='PASS',side=side),'Side postcheck')
  need(json.loads((logs/'source-before.json').read_text())==before,'Side source identity')
  matches=list(logs.glob('ci-mm-release-'+side+'-build.*'));need(len(matches)==1,'Ambiguous build');proof=matches[0]
  zero(proof/'build.exit');need(not (proof/'source-after.status').read_bytes(),'Dirty build source')
  need((proof/'source-after.commit').read_text().strip()==SHA,'Build source')
  for name in ('build.log','config.log'):
   need(not re.search(r'warning:|error:|objtool.*warning',(proof/name).read_text(),re.I),'Compiler diagnostic')
  rows=hashes(proof/'build.sha256')
  need(set(rows)=={f'/out/builds/ci-mm-release-{side}/'+n for n in ('.config','vmlinux','vmlinux.map','arch/x86/boot/bzImage')},'Build inventory');bind(rows)
  selected=json.loads((proof/'mm-release-selection.json').read_text())
  need(selected['status']=='PASS' and selected['implementation']==side,'Selection')
  need(set(selected['input_sha256'])=={str(p) for p in sel.input_paths(Path('/out/builds/ci-mm-release-'+side),Path('/src'),side=='rust')},'Selection input inventory')
  bind(selected['input_sha256']);bind(selected['archive_member_sha256'])
  pre=sel.preprocessor;cb=Path('/out/builds/ci-mm-release-'+side)
  expected=dict(argv=pre.command((build/'kernel/.fork.o.cmd').read_text(),cb/'kernel/fork.i'),cwd=str(cb),input_sha256={str(p):digest(resolve(str(p))) for p in pre.inputs(cb,Path('/src'))},output=str(cb/'kernel/fork.i'),preprocessed_sha256=digest(build/'kernel/fork.i'))
  need(json.loads((proof/'mm-release-preprocess.json').read_text())==expected,'Preprocess identity')
  sel.original_policy((SOURCE/'kernel/fork.c').read_text());sel.check_preprocessed((build/'kernel/fork.i').read_text(),side=='rust')
  for suffix,count in (('',80),('-completion',67),('-mm-release',4)):
   label='ci-mm-release-'+side+suffix
   for stage in ('qemu','parse','gate'):zero(logs/(label+'-'+stage+'.exit'))
   console=logs/(label+'-console.log');need(not re.search(r'\b(WARNING|BUG)\b|Oops:|Kernel panic|CPU feature dependency check failure|ACPI (?:BIOS )?(?:Error|Exception|Warning)|ACPI: Unable to load',console.read_text()),'Guest diagnostics')
   parsed=json.loads((logs/(label+'-kunit.json')).read_text())
   n=gate.completion.validate(parsed) if suffix=='-completion' else gate.validate(parsed,suffix=='')
   need(n==count,'Case count')
   import tempfile
   with tempfile.TemporaryDirectory(dir=BASE/'linux-out',prefix='release-reparse-') as td:
    dest=Path(td)/'parsed.json'
    run=subprocess.run([sys.executable,str(SOURCE/'tools/testing/kunit/kunit.py'),'parse',str(console),'--json='+str(dest)],capture_output=True,text=True)
    need(run.returncode==0 and dest.exists() and json.loads(dest.read_text())==parsed,'Console reparse differs')
   bind(hashes(logs/(label+'-inputs.sha256')));bind(hashes(logs/(label+'-boot.run')/'scripts.sha256'))
  configs.append(sel.config_values((build/'.config').read_text()))
  sel.check_config('mm-release-'+side,configs[-1],sel.config_values((SOURCE/'rusix/configs/x86_64-server.config').read_text()))
 need(sel.compare(*configs)==['CONFIG_RUSIX_MM_RELEASE_RUST'],'Config pair')
 for n in ('packages.lock','toolchain.log','container-image-id.txt'):
  need((RUN/'c/logs'/n).read_bytes()==(RUN/'rust/logs'/n).read_bytes(),'Tools differ')
 prior={}
 for n in ('mm-release-initial-evidence','mm-release-warnings-evidence'):
  p=BASE/'linux-out'/n/'manifest.json';m=json.loads(p.read_text())
  for rel,h in m['files'].items():need(digest(p.parent/rel)==h,'Prior failure changed')
  prior[n]=dict(manifest_sha256=digest(p),source=m.get('source'),status=m.get('status'))
 files={}
 for path in RUN.rglob('*'):
  rel=path.relative_to(RUN)
  if path.is_file() and ('builds' not in rel.parts) and not any(part.endswith('-tmp') for part in rel.parts):files['records/'+str(rel)]=path
 for p in DRAFT.iterdir():
  if p.is_file():files['launcher/'+p.name]=p
 files['launcher/archive-mm-release-003.py']=Path(__file__).resolve()
 dependency=BASE/'linux-out/archive-mm-construction-001.py';files['launcher/dependency-archive-mm-construction-001.py']=dependency
 staged={n:hashlib.sha256(textcheck(p)).hexdigest() for n,p in files.items()}
 OUT.mkdir()
 for n,p in files.items():
  q=OUT/n;q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q);need(digest(q)==staged[n] and digest(p)==staged[n],'Copy differs')
 manifest=dict(status='PASS',source=SHA,controller_session=54466,result=result,raw_output=str(RUN),files=staged,raw_artifact_sha256=raw,prior_failures=prior,scope='Four real-MM release lifecycle KUnit cases on both selections, plus 80 combined and 67 isolated core; no ordinary-consumer, allocation-failure or arbitrary live-futex quiescence coverage',archive_verification='Rehashed actual artifacts, source and preprocessing; reparsed all six consoles and reapplied strict gates/config comparison. Retains completed pinned LLVM postchecks; archiver does not rerun LLVM or guests.')
 (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
 print(json.dumps(dict(status='PASS',files=len(staged),raw_artifacts=len(raw),archive=str(OUT))))
if __name__=='__main__':main()
