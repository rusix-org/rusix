import ast,hashlib,json,subprocess
from pathlib import Path
BASE=Path('/home/aaron/code/rusix');SRC=BASE/'linux-mm-vma-modify';OUT=BASE/'linux-out/vma-modify-tooling-propagation-001'
FIX='13e0ddc71a57d7576e9cc6f34603bd96d5bbfa08';OLD='0ff7a933c198dda0c3e2c0005e4bb97db3867acc'
def blob(commit,name):return subprocess.check_output(['git','-C',str(SRC),'show',commit+':'+name])
def sha(b):return hashlib.sha256(b).hexdigest()
def node(text,name):
 found=[x for x in ast.walk(ast.parse(text)) if isinstance(x,(ast.FunctionDef,ast.AsyncFunctionDef)) and x.name==name]
 assert len(found)==1,name
 return found[0]
def extract(text,name):
 n=node(text,name);return ''.join(text.splitlines(keepends=True)[n.lineno-1:n.end_lineno])
def replace(text,name,new):
 n=node(text,name);lines=text.splitlines(keepends=True);lines[n.lineno-1:n.end_lineno]=[new];return ''.join(lines)
assert not OUT.exists();OUT.mkdir()
review=json.loads((BASE/'linux-out/vma-modify-tooling-independent-review-001/reviewed-files.json').read_text())
for p,v in review.items():assert sha((SRC/p).read_bytes())==v,p
names=['rusix/scripts/verify-exit-mmap.py','rusix/scripts/exit_kunit_elf.py','rusix/tests/test_exit_mmap_selection.py','rusix/tests/test_exit_kunit_elf.py']
before={p:(SRC/p).read_bytes() for p in names}
for p in ('rusix/scripts/exit_kunit_elf.py','rusix/tests/test_exit_kunit_elf.py'):
 assert before[p]==blob(OLD,p),'Not exact old helper/test: '+p
 (SRC/p).write_bytes(blob(FIX,p))
p=names[0];old=before[p].decode();approved=blob(FIX,p).decode()
updated=replace(old,'archive_members',extract(approved,'archive_members'))
needle='archive_members(members,rust)';assert updated.count(needle)==1
updated=updated.replace(needle,'archive_members(members,rust,test_context=context)');(SRC/p).write_text(updated)
p=names[2];updated=before[p].decode();approved=blob(FIX,p).decode()
methods=['test_kunit_archive_requires_exact_fixture_in_explicit_context','test_archive_unknown_context_rejected_with_or_without_fixture']
anchor='    def test_callback_transfer_not_data_reference_or_unsupported_target(self):'
assert updated.count(anchor)==1
updated=updated.replace(anchor,'\n'.join(extract(approved,n) for n in methods)+'\n'+anchor);(SRC/p).write_text(updated)
checks={}
for p,functions in [(names[0],['archive_members']), (names[1],['sentinel_contract','layout','registration']), (names[2],methods), (names[3],['test_canonical_sentinel_rejects_zero_speed_status_pointer_and_padding','test_sentinel_relocations_and_truncation','test_pinned_enum_and_constructor_contract'])]:
 actual=(SRC/p).read_text();expected=blob(FIX,p).decode()
 for name in functions:
  a=ast.dump(node(actual,name),include_attributes=False);b=ast.dump(node(expected,name),include_attributes=False)
  assert a==b,(p,name);checks[p+':'+name]=sha(a.encode())
# The caller must pass its already-validated test context, not source context.
calls=[n for n in ast.walk(node((SRC/names[0]).read_text(),'verify')) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='archive_members']
assert len(calls)==1 and ast.unparse(calls[0])=='archive_members(members, rust, test_context=context)'
for p in names:
 q=OUT/'before'/p;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(before[p])
 q=OUT/'after'/p;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes((SRC/p).read_bytes())
manifest_path='rusix/docs/evidence/exit-mmap-fixture-gate-fix/manifest.json';manifest=blob(FIX,manifest_path)
record={'status':'APPLIED_APPROVED_TARGETED_PROPAGATION','fix_commit':FIX,'fix_manifest_path':manifest_path,'fix_manifest_sha256':sha(manifest),'source_base':subprocess.check_output(['git','-C',str(SRC),'rev-parse','HEAD'],text=True).strip(),'before_sha256':{p:sha(b) for p,b in before.items()},'after_sha256':{p:sha((SRC/p).read_bytes()) for p in names},'ast_equivalent_to_approved_fix':checks,'full_file_equal_to_fix':[names[1],names[3]],'validated_call':'archive_members(members, rust, test_context=context)','scope':'Approved tooling-only propagation; retained teardown ELF proof stays attributed to its original kernel; no new VMA-modify execution'}
(OUT/'propagation.json').write_text(json.dumps(record,indent=2)+'\n')
(OUT/'delta.patch').write_bytes(subprocess.check_output(['diff','-ru',str(OUT/'before'),str(OUT/'after')]) if False else b'')
for p in names:
 import difflib
 with (OUT/'delta.patch').open('a') as f:f.writelines(difflib.unified_diff(before[p].decode().splitlines(True),(SRC/p).read_text().splitlines(True),fromfile='before/'+p,tofile='after/'+p))
print(json.dumps(record,indent=2))
