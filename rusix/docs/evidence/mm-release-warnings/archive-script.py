#!/usr/bin/env python3
from pathlib import Path
import hashlib,json,subprocess,re
B=Path('/home/aaron/code/rusix'); R=B/'linux-out/mm-release-verification-002'; O=B/'linux-out/mm-release-warnings-evidence'; S=B/'linux-mm-release'; E='42318e69e5f27a2f2363c0fea285cca59f710baf'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def git(*a):return subprocess.check_output(['git','-C',str(S),*a],text=True).strip()
assert not O.exists();assert git('rev-parse','HEAD')==E and not git('status','--porcelain')
assert (R/'matrix.exit').read_text().strip()=='137'
assert json.loads((R/'c/logs/postchecks.json').read_text())=={'status':'PASS','side':'c'}
rp=list((R/'rust/logs').glob('ci-mm-release-rust-build.*'));assert len(rp)==1
log=(rp[0]/'build.log').read_text(); warnings=re.findall(r'^warning:.*$',log,re.M)
assert len(warnings)==34 and warnings[-1]=='warning: 33 warnings emitted' and all('sched_statistics' in w for w in warnings[:-1])
O.mkdir(); files={}; artifacts={}
def cp(p,rel):
 assert p.is_file() and not p.is_symlink(),str(p)
 raw=p.read_bytes();assert b'\0' not in raw,str(p);raw.decode('utf8')
 d=O/rel;d.parent.mkdir(parents=True,exist_ok=True)
 with d.open('xb') as f:f.write(raw)
 files[str(rel)]=hashlib.sha256(raw).hexdigest()
for p in sorted(R.rglob('*')):
 rel=p.relative_to(R)
 if 'builds' in rel.parts or any(x=='tmp' or x.endswith('-tmp') for x in rel.parts):continue
 assert not p.is_symlink(),str(p)
 if p.is_file():cp(p,Path('records')/rel)
for line in (R/'launcher.sha256').read_text().splitlines():
 h,n=line.split('  ',1);p=Path(n);assert sha(p)==h;cp(p,Path('launcher')/p.name)
for n in git('ls-files','kernel/mm_release*','kernel/mm_construction*','kernel/task_construction_rust.rs','kernel/fork.c','rust/kernel/mm/release_tests.rs','rust/helpers/mm_release_test.c','rusix/scripts/verify-mm-release.py','rusix/scripts/build-kernel.sh','rusix/ci/run.sh','rusix/configs/x86_64-mm-release-c.config','rusix/configs/x86_64-mm-release-rust.config').splitlines():cp(S/n,Path('source')/n)
cp(Path(__file__),Path('archive-script.py'))
for side in ('c','rust'):
 build=R/side/'builds'/('ci-mm-release-'+side)
 for p in sorted(build.rglob('*')):
  if p.is_file() and not p.is_symlink() and (p.suffix in ('.o','.a') or p.name in ('vmlinux','vmlinux.map','bzImage','.config')):
   a=p.stat();h=sha(p);z=p.stat();assert (a.st_size,a.st_mtime_ns)==(z.st_size,z.st_mtime_ns)
   artifacts[str(p)]={'sha256':h,'bytes':z.st_size,'scope':'C completed kernel with C-only KUnit evidence' if side=='c' else 'Interrupted Rust build artifact; not verified Rust kernel; may be inherited cache'}
assert git('rev-parse','HEAD')==E and not git('status','--porcelain')
for n,h in files.items():assert sha(O/n)==h
m=dict(status='FAIL',source=E,matrix_exit=137,rust_warning_count=33,c_postcheck='PASS',scope='C 80 combined/67 core/4 release KUnit passed; Rust interrupted after pointer-only FFI warnings, no Rust runtime acceptance',raw_output=str(R),files=files,retained_artifacts=artifacts,artifact_inventory='All regular .o/.a and config/kernel/map outputs; hashes only, no binary copied')
(O/'manifest.json').write_text(json.dumps(m,indent=2,sort_keys=True)+'\n');print(json.dumps({'records':len(files),'raw_artifact_hashes':len(artifacts),'manifest_sha256':sha(O/'manifest.json')}))
