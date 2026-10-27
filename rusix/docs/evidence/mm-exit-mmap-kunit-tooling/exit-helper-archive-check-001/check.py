from pathlib import Path
import hashlib,importlib.util,json,subprocess,sys
sys.path.insert(0,'/src/rusix/scripts')
p=Path('/src/rusix/scripts/exit_kunit_elf.py');spec=importlib.util.spec_from_file_location('gate',p);g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
a=Path('/artifacts/built-in.a');o=Path('/artifacts/helpers/helpers.o')
before={str(p):g.digest(p) for p in (a,o)}
r=subprocess.run(['llvm-ar','t',str(a)],capture_output=True,text=True,check=True);assert not r.stderr
value=g.helper_payload(a,r.stdout.splitlines(),o)
assert before=={str(p):g.digest(p) for p in (a,o)}
print(json.dumps({'status':'PASS','scope':'Retained historical archive nested helpers payload only; no new fixture registration proof','inputs':before,'payload_sha256':value,'llvm_ar':subprocess.check_output(['llvm-ar','--version'],text=True)},indent=2))
