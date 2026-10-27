#!/usr/bin/env python3
"""Compact tooling-only evidence; references prior archives, never copies them."""
import gzip,hashlib,json,re,shutil,subprocess
from pathlib import Path
BASE=Path('/home/aaron/code/rusix');SRC=BASE/'linux-mm-vma-modify'
OUT=BASE/'linux-out/vma-modify-tooling-evidence';STAGE=OUT.with_name(OUT.name+'.staging')
DEST=SRC/'rusix/docs/evidence/vma-modify-tooling'
HEAD='966869b130e8d453b00dc24224e4ff59a415379a';FIX='13e0ddc71a57d7576e9cc6f34603bd96d5bbfa08'
HOST=BASE/'linux-out/vma-modify-tooling-host-002';REVIEW=BASE/'linux-out/vma-modify-tooling-independent-review-001';PROP=BASE/'linux-out/vma-modify-tooling-propagation-001'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def digest(b):return hashlib.sha256(b).hexdigest()
def need(v,m):
 if not v:raise ValueError(m)
def git(*a):return subprocess.check_output(['git','-C',str(SRC),*a])
def read(p):return json.loads(p.read_text())
need(not any(p.exists() for p in (OUT,STAGE,DEST)),'Fresh archive required')
need(git('rev-parse','HEAD').decode().strip()==HEAD,'Source HEAD changed')
need(not git('diff','--name-only','--','mm','kernel','rust','init','MAINTAINERS'),'Production changed')
final=read(HOST/'results.json');before=read(HOST/'inputs-before.json');after=read(HOST/'inputs-after.json')
need(final['status']=='PASS' and final['suites']==39 and final['cases']==421 and final['stable_inputs']==4157 and before==after,'Final host result differs')
for p,v in after.items():need(sha(SRC/p)==v,'Final tested input changed: '+p)
for row in final['results']:
 need(row['exit']==0,'Final suite failed');log=(HOST/(Path(row['path']).stem+'.log')).read_text();need(re.findall(r'Ran (\d+) tests?',log)==[str(row['cases'])] and '\nOK\n' in log,'Final host count/log mismatch')
old=read(REVIEW/'full-interval/results.json');old_inputs=read(REVIEW/'full-interval/before.json')
need(old['cases']==416 and old['stable_inputs']==4157 and old['all_pass'] and old['head_before']==HEAD==old['head_after'],'Historical review result differs')
review_manifest=read(REVIEW/'manifest.json')
for p,v in review_manifest['records'].items():need(sha(REVIEW/p)==v,'Historical review changed: '+p)
prop=read(PROP/'propagation.json');need(prop['fix_commit']==FIX and prop['source_base']==HEAD,'Propagation identity differs')
fix_blob=git('show',FIX+':'+prop['fix_manifest_path']);need(digest(fix_blob)==prop['fix_manifest_sha256'],'Approved fix manifest differs')
fix_manifest=json.loads(fix_blob)
for p,v in prop['after_sha256'].items():need(sha(SRC/p)==v,'Propagated file changed')
changes={p:{'pre_fix':old_inputs.get(p),'final':after.get(p)} for p in old_inputs.keys()|after.keys() if old_inputs.get(p)!=after.get(p)}
need(set(changes)==set(prop['after_sha256']),'Unexpected changes since independent review')
# These four original production/scaffold identities remain separate from the fix.
reviewed=read(REVIEW/'reviewed-files.json')
for p,v in reviewed.items():
 if p not in changes:need(sha(SRC/p)==v,'Reviewed tooling changed outside approved propagation')
STAGE.mkdir();files={};records={};raw={}
def add_bytes(data,name):
 data.decode('utf-8');need(b'\0' not in data,'Non-text archive input')
 original=digest(data);stored=name
 if len(data)>65536:
  stored='compressed/'+original+'.gz';payload=gzip.compress(data,mtime=0)
 else:payload=data
 q=STAGE/stored;q.parent.mkdir(parents=True,exist_ok=True)
 if q.exists():need(q.read_bytes()==payload,'Archive collision')
 else:q.write_bytes(payload)
 files[stored]=sha(q);records[name]={'stored':stored,'sha256':original,'bytes':len(data),'encoding':'gzip' if stored!=name else 'utf-8'}
def add(p,name):raw[str(p)]=sha(p);add_bytes(p.read_bytes(),name)
# Final project snapshots, once. Native source is exhaustively hash-bound to HEAD.
for p in sorted((HOST/'source').rglob('*')):
 if p.is_file():
  relative=str(p.relative_to(HOST/'source'));need(sha(p)==after[relative],'Final source snapshot mismatch');add(p,'source/'+relative)
for p in sorted(HOST.iterdir()):
 if p.is_file():add(p,'host/final/'+p.name)
# Pre-fix logs/identities are historical, never relabeled to final propagated source.
for p in sorted(REVIEW.rglob('*')):
 if p.is_file() and 'inputs' not in p.relative_to(REVIEW).parts:
  add(p,'host/pre-fix-independent/'+str(p.relative_to(REVIEW)))
# Only four changed historical snapshots are needed; all unchanged project
# snapshots are already available under source/ and identified by the old map.
for name in changes:
 p=PROP/'before'/name;need(sha(p)==old_inputs[name],'Pre-fix snapshot mismatch');add(p,'source-pre-fix/'+name)
for p in sorted(PROP.iterdir()):
 if p.is_file():add(p,'propagation/'+p.name)
# Implementation's early after-only sweep is explicitly retained with lesser scope.
early=BASE/'linux-out/vma-modify-tooling-host-001'
for p in sorted(early.iterdir()):
 if p.is_file():add(p,'host/early-after-only/'+p.name)
add(BASE/'linux-out/vma-modify-tooling-archive-draft/propagate.py','propagation/script.py')
add(BASE/'linux-out/vma-modify-tooling-archive-draft/run-host.py','host/final/runner.py')
add(Path(__file__),'archive-script.py')
prior={}
for name in ('vma-modify-source','vma-modify-fixtures'):
 p='rusix/docs/evidence/'+name+'/manifest.json';prior[name]={'commit':HEAD,'path':p,'sha256':digest(git('show',HEAD+':'+p))}
inherited={'commit':FIX,'path':prop['fix_manifest_path'],'sha256':prop['fix_manifest_sha256'],'compiled_kernel_source':fix_manifest['kernel_source'],'scope':fix_manifest['scope'],'prior_failure':fix_manifest['prior_failure']}
add_bytes((json.dumps(inherited,indent=2)+'\n').encode(),'inherited-fix.json')
readme='''# VMA modification tooling checkpoint

Final host regressions: 39 suites / 421 cases, 4,157 unchanged inputs. Earlier
independent 39/416 results and the implementer after-only sweep retain their own
identities and scope. The only post-review source changes are the four approved
teardown archive/sentinel gate and regression files, tracked by AST equivalence
and full-file equality where appropriate. Production remains committed 966869b.

This verifies tooling source/models, not an emitted VMA-modify kernel. Build-only
profiles preserve CI refusal until the actual ordinary runner exists. Ten Rust
exports represent eleven native policies (the shared modify policy can inline);
actual selection proof is implemented but has not run on this candidate.

The referenced teardown fix was inspected against retained source0ff7 KUnit C
artifacts, not a new VMA-modify build. The original teardown attempt failed and
requires its own retry. Do not infer VM acceptance from that ELF reinspection.

Prior evidence is referenced by commit and manifest, never recursively included.
Native dependency inputs are exhaustive hashes bound to unchanged source HEAD;
project source/config/test/tool snapshots are included once. Pre-fix project
sources reconstruct from the final snapshots plus four source-pre-fix files.
No generated build tree, binaries, VM, hosted CI, staging or commit was produced
by this archive operation.
'''
add_bytes(readme.encode(),'README.md')
manifest={'status':'PASS_HOST_TOOLING_ONLY','source_base':HEAD,'state':'Uncommitted reviewed tooling on unchanged production checkpoint','final':{k:final[k] for k in ('suites','cases','stable_inputs','inputs_unchanged','scope')},'pre_fix':{'suites':39,'cases':416,'stable_inputs':4157,'independent_manifest_sha256':sha(REVIEW/'manifest.json')},'between_review_and_final_changes':changes,'final_input_sha256':after,'production_source_unchanged':True,'prior_evidence':prior,'inherited_fix':inherited,'propagation':prop,'records':records,'files':files,'raw_input_sha256':raw,'scope':'Source/config/tooling review and host regressions only. No new Kconfig resolution, VMA-modify compilation, actual ELF ownership or VM execution; prior retained teardown reinspection remains separately attributed.'}
(STAGE/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
for p,v in raw.items():need(sha(Path(p))==v,'Raw record changed during archive')
for p,v in files.items():need(sha(STAGE/p)==v,'Staged record changed')
for p,v in after.items():need(sha(SRC/p)==v,'Tested source changed during archive')
STAGE.rename(OUT);shutil.copytree(OUT,DEST)
for p,v in files.items():need(sha(DEST/p)==v,'Tracked copy differs')
need(sha(DEST/'manifest.json')==sha(OUT/'manifest.json'),'Manifest copy differs')
print(json.dumps({'status':'PASS','records':len(records),'stored_files':len(files),'manifest_sha256':sha(DEST/'manifest.json')},indent=2))
