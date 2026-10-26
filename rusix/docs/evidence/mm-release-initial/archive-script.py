#!/usr/bin/env python3
"""Retain failed release attempt as text plus hashes; never copy build binaries."""
from pathlib import Path
import hashlib,json,subprocess
BASE=Path('/home/aaron/code/rusix')
RUN=BASE/'linux-out/mm-release-verification-001'
OUT=BASE/'linux-out/mm-release-initial-evidence'
SOURCE=BASE/'linux-mm-release'
EXPECTED='fc7317e898853c95e4584d55e3477c4d7e755122'
def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as stream:
  for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
 return h.hexdigest()
def git(*args):return subprocess.check_output(['git','-C',str(SOURCE),*args],text=True).strip()
assert not OUT.exists(),'Never overwrite evidence'
assert git('rev-parse','HEAD')==EXPECTED and not git('status','--porcelain')
assert (RUN/'matrix.exit').read_text().strip()=='2'
assert not (RUN/'rust').exists(),'Rust unexpectedly started'
proofs=list((RUN/'c/logs').glob('ci-mm-release-c-build.*'));assert len(proofs)==1
proof=proofs[0]
assert (proof/'build.exit').read_text().strip()=='2'
assert 'call to undeclared function \'mt_empty\'' in (proof/'build.log').read_text()
assert not list((RUN/'c/logs').glob('*-boot.run')),'Unexpected VM'
files={};artifacts={};missing=[]
OUT.mkdir()
def copy(path,target):
 assert path.is_file() and not path.is_symlink(),str(path)
 raw=path.read_bytes();assert b'\0' not in raw,'Binary copy rejected: '+str(path)
 raw.decode('utf-8',errors='strict')
 dest=OUT/target;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
 files[str(target)]=hashlib.sha256(raw).hexdigest()
# Every existing record outside build/tmp trees, including all raw logs,
# statuses, original source snapshots, fixture text and launcher hash record.
for path in sorted(RUN.rglob('*')):
 if not path.is_file():continue
 rel=path.relative_to(RUN)
 if 'builds' in rel.parts or 'tmp' in rel.parts:continue
 copy(path,Path('records')/rel)
for line in (RUN/'launcher.sha256').read_text().splitlines():
 value,name=line.split('  ',1);p=Path(name);assert sha(p)==value,'Launcher changed since run'
 copy(p,Path('launcher')/p.name)
for name in ('kernel/fork.c','kernel/mm_release_test.c','kernel/mm_release_rust.rs','kernel/mm_release_impl.h',
             'kernel/mm_construction_rust.rs','kernel/mm_construction_impl.h','kernel/task_construction_rust.rs',
             'kernel/Makefile','init/Kconfig','include/linux/maple_tree.h','rust/kernel/mm/release_tests.rs',
             'rust/helpers/mm_release_test.c','rust/helpers/helpers.c','rust/kernel/mm.rs',
             'rusix/scripts/build-kernel.sh','rusix/ci/run.sh','rusix/scripts/boot-kunit.sh',
             'rusix/scripts/verify-mm-release.py','rusix/scripts/validate-mm-release-kunit.py',
             'rusix/configs/x86_64-mm-release-c.config','rusix/configs/x86_64-mm-release-rust.config'):
 copy(SOURCE/name,Path('source')/name)
copy(Path(__file__),Path('archive-script.py'))
build=RUN/'c/builds/ci-mm-release-c'
for path in sorted(build.rglob('*')):
 if path.is_file() and not path.is_symlink() and (path.suffix in ('.o','.a') or path.name in ('vmlinux','vmlinux.map','bzImage','.config')):
  before=path.stat();value=sha(path);after=path.stat();assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns)
  artifacts[str(path)]={'sha256':value,'bytes':after.st_size,'scope':'Retained partial build artifact; not a completed or verified kernel'}
for name in ('arch/x86/boot/bzImage','vmlinux','vmlinux.map','kernel/mm_release_test.o'):
 if not (build/name).is_file():missing.append(name)
assert git('rev-parse','HEAD')==EXPECTED and not git('status','--porcelain')
for name,value in files.items():assert sha(OUT/name)==value
manifest=dict(status='FAIL',source=EXPECTED,matrix_exit=2,c_build_exit=2,rust_started=False,vm_started=False,
 scope='C fixture compilation failed on undeclared mt_empty; no completed kernel or runtime acceptance',
 raw_output=str(RUN),files=files,retained_artifacts=artifacts,missing_outputs=missing,
 artifact_inventory='All existing regular .o/.a files and kernel/config/map outputs in the C build; hashes only')
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
print(json.dumps({'text_records':len(files),'retained_partial_artifact_hashes':len(artifacts),'missing_outputs':missing,'manifest_sha256':sha(OUT/'manifest.json')},indent=2))
