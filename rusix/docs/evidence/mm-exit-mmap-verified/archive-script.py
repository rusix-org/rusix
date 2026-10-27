#!/usr/bin/env python3
"""Archive terminal matrix002 only after explicit root authorization."""
from pathlib import Path
import hashlib,json,gzip,stat,subprocess,sys,os,re,importlib.util
sys.dont_write_bytecode=True
BASE=Path('/home/aaron/code/rusix');RUN=BASE/'linux-out/mm-exit-mmap-verification-002';SRC=BASE/'linux-mm-exit-mmap-fix';OUT=BASE/'linux-mm-exit-mmap-verified/rusix/docs/evidence/mm-exit-mmap-verified';SOURCE='8b6ab8382784f5873e416d5bdadae62b4565bb2d'
assert os.environ.get('RUSIX_ARCHIVE_TERMINAL_AUTHORIZED')=='1','Root terminal confirmation required'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def git(*a):return subprocess.check_output(['git','-C',str(SRC),*a],text=True).strip()
assert git('rev-parse','HEAD')==SOURCE and not git('status','--porcelain')
assert (RUN/'matrix.exit').read_text().strip()=='0'
assert (RUN/'source-before.json').read_bytes()==(RUN/'source-after.json').read_bytes()
for kind in ['config','lifecycle','retained-c']:
 assert (RUN/(kind+'-prerequisite-before.json')).read_bytes()==(RUN/(kind+'-prerequisite-after.json')).read_bytes()
source=json.loads((RUN/'source-before.json').read_text());assert source['source']==SOURCE
for n,h in source['input_sha256'].items():assert sha(SRC/n)==h,n
pair=json.loads((RUN/'pair-result.json').read_text());assert pair['status']=='PASS' and pair['source']==SOURCE and pair['ordinary_cases_per_side']==9 and pair['kunit_combined']==79 and pair['kunit_isolated']==3
for axis in pair['pair_differences'].values():assert axis==['CONFIG_RUSIX_EXIT_MMAP_RUST']
sys.path.insert(0,str(SRC/'rusix/scripts'))
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
guest=load('archived_exit_guest',SRC/'rusix/scripts/test-exit-mmap-vm.py');gate=load('archived_exit_gate',SRC/'rusix/scripts/validate-exit-mmap-kunit.py')
sys.path.insert(0,str(SRC/'tools/testing/kunit'));import kunit_parser,kunit_json,kunit_printer
for key in ['ordinary-c','ordinary-rust','kunit-c','kunit-rust','pair']:
 assert (RUN/(key+'-postcheck.exit')).read_text().strip()=='0' and not (RUN/(key+'-postcheck.stderr')).read_bytes()
 if key=='pair':continue
 profile='exit-mmap-'+key.replace('ordinary-','');logs=RUN/key/'logs';build,=logs.glob('ci-'+profile+'-build.*')
 for n in ['container.exit','ci.exit','launcher.exit']:assert (logs/n).read_text().strip()=='0'
 assert (build/'build.exit').read_text().strip()=='0'
 for n in ['build.log','config.log']:assert not re.search(r'warning:|error:|objtool.*warning',(build/n).read_text(),re.I)
 proof=json.loads((build/'exit-mmap-selection.json').read_text());assert proof['status']=='PASS' and proof['implementation']==key.rsplit('-',1)[1]
 def resolve(n):
  if n.startswith('/src/'):return SRC/n[5:]
  if n.startswith('/out/'):return RUN/key/n[5:]
  return Path(n)
 def hashes(obj):
  if isinstance(obj,dict):
   for k,v in obj.items():
    if k in ['input_sha256','archive_member_sha256']:
     for n,h in v.items():assert sha(resolve(n))==h,n
    else:hashes(v)
  elif isinstance(obj,list):
   for v in obj:hashes(v)
 hashes(proof)
 if key.startswith('ordinary'):
  run=logs/('ci-'+profile+'-exit-mmap.run');result=json.loads((run/'result.json').read_text());accepted=guest.accept_console((run/'console.log').read_text(),0);assert result==accepted|{'implementation':key.rsplit('-',1)[1],'source_revision':SOURCE}
  for n in ['runner.exit','qemu.exit','selection.exit']:assert (run/n).read_text().strip()=='0'
  inp=json.loads((run/'inputs.json').read_text());hashes(inp['selection'])
  for n,h in inp['artifacts'].items():assert sha(resolve(n))==h,n
 else:
  for suffix,count,combined in [('',79,True),('-exit-mmap',3,False)]:
   label='ci-'+profile+suffix
   for n in ['qemu','parse','gate']:assert (logs/(label+'-'+n+'.exit')).read_text().strip()=='0'
   text=(logs/(label+'-console.log')).read_text();assert not re.search(r'\b(WARNING|BUG)\b|Oops:|Kernel panic|CPU feature dependency check failure|ACPI (?:BIOS )?(?:Error|Exception|Warning)|ACPI: Unable to load',text)
   parsed=kunit_parser.parse_run_tests(text.splitlines(),kunit_printer.null_printer);fresh=json.loads(kunit_json.get_json_result(test=parsed,metadata=kunit_json.Metadata()));assert fresh==json.loads((logs/(label+'-kunit.json')).read_text());assert gate.validate(fresh,combined)==count
assert not OUT.exists();OUT.mkdir(parents=True);files={};raw={};compressed={};artifacts={};special={}
def copy(p,n):
 data=p.read_bytes();data.decode('utf8');assert b'\0' not in data,p
 h=hashlib.sha256(data).hexdigest();raw[str(p)]=h
 if len(data)>4*1024*1024:
  n=Path(str(n)+'.gz');compressed[str(n)]={'sha256':h,'bytes':len(data),'raw_path':str(p)};data=gzip.compress(data,compresslevel=6,mtime=0)
 target=OUT/n;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data);files[str(n)]=sha(target)
for p in sorted(RUN.rglob('*')):
 info=p.lstat();rel=p.relative_to(RUN)
 if stat.S_ISREG(info.st_mode):
  h=sha(p);after=p.stat();assert (info.st_size,info.st_mtime_ns)==(after.st_size,after.st_mtime_ns);artifacts[str(p)]={'sha256':h,'bytes':info.st_size,'mode':stat.S_IMODE(info.st_mode)}
  if 'builds' not in rel.parts and 'tmp' not in rel.parts and not any(n.endswith('-tmp') for n in rel.parts):copy(p,Path('records')/rel)
 elif stat.S_ISLNK(info.st_mode):special[str(p)]={'type':'symlink','target':os.readlink(p)}
 elif not stat.S_ISDIR(info.st_mode):special[str(p)]={'type':'special','mode':info.st_mode}
for line in (RUN/'launcher.sha256').read_text().splitlines():
 h,n=line.split('  ',1);p=Path(n);assert sha(p)==h;copy(p,Path('launcher')/p.name)
for n,h in source['input_sha256'].items():
 if not n.startswith('rusix/docs/evidence/'):copy(SRC/n,Path('source')/n)
copy(Path(__file__),Path('archive-script.py'))
prior={}
for name in ['mm-exit-mmap-config','mm-exit-mmap-fixtures','mm-exit-mmap-kunit-tooling','mm-exit-mmap-tooling','lifecycle-verifier-fix','exit-mmap-fixture-gate-fix','exit-mmap-retained-c-kunit']:
 n='rusix/docs/evidence/'+name+'/manifest.json';prior[n]={'commit':SOURCE,'sha256':sha(SRC/n)}
for n,h in raw.items():assert sha(Path(n))==h,n
for n,r in artifacts.items():assert sha(Path(n))==r['sha256'] and Path(n).stat().st_size==r['bytes'],n
for n,h in files.items():assert sha(OUT/n)==h,n
assert git('rev-parse','HEAD')==SOURCE and not git('status','--porcelain')
m={'status':'PASS','source':SOURCE,'matrix_exit':0,'scope':'Four fresh kernels/six boots: ordinary C/Rust nine cases each, combined79 and isolated3 native KUnit cases on each side. Paired selected teardown policy only; not whole-MM or full-kernel completion.','pair':pair,'files':files,'raw_input_sha256':raw,'compressed_text':compressed,'raw_artifacts':artifacts,'special_artifacts':special,'prior_evidence':prior,'raw_output':str(RUN),'audit':'Strict ordinary and native KUnit consoles reparsed, nested emitted-selection input hashes checked; exhaustive raw inventory rehashed before publication. No compiler/VM invoked by archiver.'}
(OUT/'manifest.json').write_text(json.dumps(m,indent=2,sort_keys=True)+'\n');print(json.dumps({'stored':len(files),'raw':len(artifacts),'compressed':len(compressed),'manifest':sha(OUT/'manifest.json')},indent=2))
