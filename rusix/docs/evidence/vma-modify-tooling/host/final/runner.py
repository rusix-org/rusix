import hashlib,json,re,subprocess
from pathlib import Path
BASE=Path('/home/aaron/code/rusix');SRC=BASE/'linux-mm-vma-modify';OUT=BASE/'linux-out/vma-modify-tooling-host-002'
EXPECTED='966869b130e8d453b00dc24224e4ff59a415379a'
def git(*a):return subprocess.check_output(['git','-C',str(SRC),*a],text=True).strip()
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert not OUT.exists();OUT.mkdir()
paths=set(json.loads((BASE/'linux-out/vma-modify-tooling-independent-review-001/full-interval/before.json').read_text()))
paths.update(git('ls-files','--others','--exclude-standard').splitlines())
assert all(not p.startswith('rusix/docs/evidence/') for p in paths)
before={p:sha(SRC/p) for p in sorted(paths)}
assert git('rev-parse','HEAD')==EXPECTED
assert not git('diff','--name-only','--','mm','kernel','rust','init','MAINTAINERS')
(OUT/'inputs-before.json').write_text(json.dumps(before,indent=2)+'\n')
(OUT/'source-status.txt').write_text(git('status','--porcelain')+'\n')
(OUT/'tracked-diff.patch').write_text(git('diff','--binary')+'\n')
# Snapshot tested project text; production/dependency content stays hash-bound to
# unchanged committed source, with no recursive prior evidence copy.
for name in before:
 if name.startswith(('rusix/scripts/','rusix/tests/','rusix/configs/','rusix/ci/')):
  p=OUT/'source'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((SRC/name).read_bytes())
results=[];cases=0
for p in sorted((SRC/'rusix/tests').glob('test_*.py')):
 command=['python3','-B',str(p)]
 r=subprocess.run(command,capture_output=True,text=True,timeout=90)
 log=r.stdout+r.stderr;(OUT/(p.stem+'.log')).write_text(log)
 matches=re.findall(r'Ran (\d+) tests?',log)
 assert len(matches)==1,p
 cases+=int(matches[0]);results.append({'path':str(p.relative_to(SRC)),'command':command,'exit':r.returncode,'cases':int(matches[0])})
 if r.returncode:print(p.name,log[-2000:])
shell=subprocess.run(['bash','-n',str(SRC/'rusix/scripts/build-kernel.sh')],capture_output=True,text=True)
(OUT/'shell.log').write_text(shell.stdout+shell.stderr)
white=subprocess.run(['git','-C',str(SRC),'diff','--check'],capture_output=True,text=True)
(OUT/'diff-check.log').write_text(white.stdout+white.stderr)
after={p:sha(SRC/p) for p in sorted(paths)}
(OUT/'inputs-after.json').write_text(json.dumps(after,indent=2)+'\n')
result={'status':'PASS' if all(x['exit']==0 for x in results) and not shell.returncode and not white.returncode and before==after else 'FAIL','source_base':EXPECTED,'head_after':git('rev-parse','HEAD'),'stable_inputs':len(before),'inputs_unchanged':before==after,'suites':len(results),'cases':cases,'results':results,'shell_exit':shell.returncode,'diff_check_exit':white.returncode,'scope':'Post-propagation host source/model tests only; no new actual ELF/kernel/VM'}
(OUT/'results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='results'}))
assert result['status']=='PASS' and result['head_after']==EXPECTED
