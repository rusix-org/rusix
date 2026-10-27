from pathlib import Path
import hashlib,json,shutil,subprocess
B=Path('/home/aaron/code/rusix');R=B/'linux-mm-vma-merge';O=R/'rusix/docs/evidence/vma-merge-source';O.mkdir(parents=True,exist_ok=False)
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(n,x):
 p=O/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2)+'\n')
def copy(p,n):
 q=O/n;q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q)
review=B/'linux-out/vma-merge-independent-review-001';author=B/'linux-out/vma-merge-source-work';scout=B/'linux-out/mm-after-modify-scout-001'
old=json.loads((review/'source-check.json').read_text());files=list(old['source_sha256']);before={n:sha(R/n) for n in files}
assert all(before[n]==h for n,h in old['source_sha256'].items() if n!='rusix/PROGRESS.md')
for n in files:copy(R/n,'source/'+n)
for n in ('REVIEW.md','check.py','source-check.json','native-policy-sha256.json','final-check.log'):copy(review/n,'independent/'+n)
for n in ('abi.json','baseline-functions.json','check-inventory.py','check-restoration.py','inventory-check.json','restoration.json','checkpatch.log','checkpatch-final.log'):copy(author/n,'author/'+n)
for n in ('SCOUT.md','inputs.json'):copy(scout/n,'scout/'+n)
commands=[['rustfmt','--check','--edition','2021','mm/vma_merge_rust.rs'],['git','diff','--check'],['perl','scripts/checkpatch.pl','--no-tree','--file','mm/vma_merge.h','mm/vma_merge_impl.h']]
results=[]
for i,cmd in enumerate(commands):
 r=subprocess.run(cmd,cwd=R,capture_output=True);(O/f'check-{i}.stdout').write_bytes(r.stdout);(O/f'check-{i}.stderr').write_bytes(r.stderr);results.append({'argv':cmd,'cwd':str(R),'exit':r.returncode});assert r.returncode==0,(cmd,r.stderr)
write('checks.json',results)
assert before=={n:sha(R/n) for n in files}
base=subprocess.check_output(['git','-C',str(R),'rev-parse','HEAD'],text=True).strip();assert base==old['base']
pinned=subprocess.check_output(['git','-C',str(R),'rev-parse','2926d88bb7fc'],text=True).strip()
write('source-identities.json',{'base':base,'pinned_native_reference':pinned,'source_sha256':before,'reviewed_source_sha256':old['source_sha256'],'only_postreview_delta':'PROGRESS review status and archive link; eight other files byte-identical','scout_reference':{'path':str(scout),'manifest_sha256':sha(scout/'manifest.json'),'source':base},'scope':'Source-only; no configuration, compiler/typecheck, actual ELF selection or VM result.'})
(O/'README.md').write_text('''# VMA merge source checkpoint

Seventeen complete merge/expand/shrink policies (708 Rust lines), six native
entry wrappers, 42 new field/operation primitives and 31 reused functions.
The source snapshots bind exactly nine files. Independent review and whole-file
C restoration pass; all 17 native bodies match the pinned reference. Constants
are recorded separately (six new, two reused).

Author and independent records retain their original pre-link PROGRESS identity;
source-identities.json binds the final documentation-only link update. The scout
is referenced by base commit, input hashes and original manifest hash; only its
short report and input inventory are copied. No older evidence tree is embedded.
Author checkpatch.log preserves the initial malformed-SPDX warnings; the corrected
headers pass checkpatch-final.log and the new captured final checks. These style
checks cover the two new C headers. Formatting and whitespace checks are distinct
from compiler validation. The archived restoration check is textual selector
projection, never actual preprocessor output.

This checkpoint establishes source translation/review only. Configuration,
compiler/typecheck, object/archive/linked selection and paired VM tests remain
pending, including the modification prerequisite. Native primitives still execute
C; no subsystem divergence or full compatibility is claimed.
''')
copy(Path(__file__),'archive-generator.py')
manifest={'schema':'vma-merge-source-v1','scope':'source-only','base':base,'pinned_native_reference':pinned,'files':{str(p.relative_to(O)):sha(p) for p in sorted(O.rglob('*')) if p.is_file()}}
write('manifest.json',manifest)
paths=sorted(str(p.relative_to(R)) for p in O.rglob('*') if p.is_file())
(B/'linux-out/vma-merge-source-stage-paths.txt').write_text('\n'.join(paths)+'\n')
print(json.dumps({'manifest_sha256':sha(O/'manifest.json'),'stored_records':len(manifest['files']),'bytes':sum(p.stat().st_size for p in O.rglob('*') if p.is_file()),'source_sha256':before},indent=2))
