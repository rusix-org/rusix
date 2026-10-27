from pathlib import Path
import subprocess,json,hashlib,shutil
BASE=Path('/home/aaron/code/rusix');REPO=BASE/'linux-mm-vma-modify';RAW=BASE/'linux-out/vma-modify-source-checks-001';DEST=REPO/'rusix/docs/evidence/vma-modify-source'
BASE_COMMIT='99fd3dd96ac0b6131c34501dff9626e95b063037'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def run(name,args,*,expected=0):
 p=subprocess.run(args,capture_output=True,text=True,cwd=REPO)
 (RAW/(name+'.stdout')).write_text(p.stdout);(RAW/(name+'.stderr')).write_text(p.stderr)
 (RAW/(name+'.exit')).write_text(str(p.returncode)+'\n')
 commands[name]=args
 assert p.returncode==expected,(name,p.returncode,p.stdout[-1000:],p.stderr[-1000:])
 return p
assert not RAW.exists() and not DEST.exists();RAW.mkdir();DEST.mkdir(parents=True)
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()==BASE_COMMIT
indep=BASE/'linux-out/vma-modify-independent-review-001';review=json.loads((indep/'review.json').read_text())
for name,h in review['source_sha256'].items():assert sha(REPO/name)==h,name
source_files=set(review['source_sha256'])|{'MAINTAINERS','rusix/PROGRESS.md','rusix/experiments/vma-modify/README.md','rusix/tests/vma-modify/init.rs','rusix/tests/vma-modify/gate.py','rusix/tests/vma-modify/upstream.json','rusix/tests/vma-modify/README.md','rusix/tests/test_vma_modify_native_gate.py'}
native=json.loads((REPO/'rusix/tests/vma-modify/upstream.json').read_text())
for name,r in native['files'].items():
 assert sha(REPO/name)==r['sha256'];assert hashlib.sha256(subprocess.check_output(['git','show',native['baseline']+':'+name],cwd=REPO)).hexdigest()==r['sha256'];source_files.add(name)
before={name:sha(REPO/name) for name in sorted(source_files)}
(RAW/'inputs-before.json').write_text(json.dumps(before,indent=2)+'\n');commands={}
run('native-restoration',['python3','-B',str(BASE/'linux-out/mm-next-policy-scout-001/review-source.py')])
run('rustfmt-production',['rustfmt','--edition','2021','--check','mm/vma_modify_rust.rs'])
run('rustfmt-fixture',['rustfmt','--edition','2021','--check','rusix/tests/vma-modify/init.rs'])
run('diff-check',['git','diff','--check'])
run('fixture-host-parser',['python3','-B','rusix/tests/test_vma_modify_native_gate.py'])
run('format-tool-version',['rustfmt','--version'])
run('python-version',['python3','--version'])
patch=subprocess.check_output(['git','diff','--','MAINTAINERS','mm/vma.c','mm/Makefile','init/Kconfig'],cwd=REPO)
for f in ['mm/vma_modify.h','mm/vma_modify_impl.h','mm/vma_modify_rust.rs']:
 p=subprocess.run(['git','diff','--no-index','--','/dev/null',f],cwd=REPO,capture_output=True);assert p.returncode==1;patch+=p.stdout
(RAW/'production.patch').write_bytes(patch)
run('checkpatch',['perl','scripts/checkpatch.pl','--no-tree','--terse',str(RAW/'production.patch')])
after={name:sha(REPO/name) for name in sorted(source_files)};assert before==after
(RAW/'inputs-after.json').write_text(json.dumps(after,indent=2)+'\n');(RAW/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
files={};raw_inputs={}
def copy(src,rel):
 target=DEST/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,target);files[rel]=sha(target);raw_inputs[str(src)]=sha(src)
for name in sorted(source_files):copy(REPO/name,'source/'+name)
for p in sorted(RAW.iterdir()):copy(p,'checks/'+p.name)
scout=BASE/'linux-out/mm-next-policy-scout-001'
for name in ['README.md','source-review.json','implementation-source-review.json','review-source.py','candidate-production-initial.patch','checkpatch-initial.log','checkpatch-current.log']:
 copy(scout/name,'scout/'+name)
for name in ['REVIEW.md','review.json','check.py']:copy(indep/name,'independent/'+name)
copy(Path(__file__),'archive-script.py')
compile_root=BASE/'linux-out/vma-modify-fixtures-compile-002';compiled=json.loads((compile_root/'evidence/result.json').read_text())
for name,h in compiled['fixture_sha256'].items():
 if name.endswith('README.md'):continue
 assert sha(REPO/name)==h,name
manifest={'status':'SOURCE_CHECKPOINT_REVIEWED_NOT_KERNEL_COMPILED','source_base':BASE_COMMIT,'baseline':native['baseline'],'working_changes':'Uncommitted candidate source snapshots; no claim this kernel was compiled or executed','scope':'Eleven-policy C restoration and source review, formatting/checkpatch, sixteen synthetic fixture-parser tests; compilation evidence is separately attributed','source_sha256':before,'files':files,'raw_input_sha256':raw_inputs,'result':{'native_policies':11,'native_primitives':70,'rust_lines':len((REPO/'mm/vma_modify_rust.rs').read_text().splitlines()),'fixture_parser_cases':16,'commands_passed':sorted(commands),'production_source_unchanged_since_independent_review':True},'fixture_compile_reference':{'path':'rusix/docs/evidence/vma-modify-fixtures/manifest.json','source':'Final executable fixture bytes match pinned static compile002; this archive does not rerun compilation','current_readme_sha256':sha(REPO/'rusix/tests/vma-modify/README.md'),'compiled_readme_sha256':compiled['fixture_sha256']['rusix/tests/vma-modify/README.md'],'readme_delta':'Status documentation only, after static compilation; immutable compile archive keeps earlier README'},'historical_records':{'scout/README.md':'Read-only recommendation before implementation','scout/source-review.json':'Native function identity scout at99fd before implementation','scout/candidate-production-initial.patch':'Initial generated C declaration formatting failure, not final source','scout/checkpatch-initial.log':'52 style errors/5warnings on retained initial patch; fixed before review','scout/checkpatch-current.log':'Intermediate zero-error check before explicit MAINTAINERS pattern; final check is checks/checkpatch.stdout'},'limitations':['No candidate Kconfig resolution, kernel compilation, object/linked ownership or VM execution','No failure/concurrency/optional-config/architecture/performance acceptance','Independent review is agent source review, not human signoff'],'prior_evidence_policy':'Base and baseline commits referenced; no recursive prior evidence copied'}
(DEST/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n');print(json.dumps({'manifest':str(DEST/'manifest.json'),'sha256':sha(DEST/'manifest.json'),'records':len(files)},indent=2))
