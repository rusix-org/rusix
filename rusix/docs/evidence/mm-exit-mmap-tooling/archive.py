#!/usr/bin/env python3
"""Preserve reviewed host regressions and their exact text inputs, no binaries."""
import hashlib,json,shutil
from pathlib import Path
BASE=Path('/home/aaron/code/rusix')
RAW=BASE/'linux-out/mm-exit-mmap-tooling-host-002'
SOURCE=BASE/'linux-mm-exit-mmap'
OUT=BASE/'linux-out/mm-exit-mmap-tooling-evidence'
DEST=SOURCE/'rusix/docs/evidence/mm-exit-mmap-tooling'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
record=json.loads((RAW/'result.json').read_text())
assert record['status']=='PASS' and record['inputs_stable'] and record['diff_check_exit']==0
assert len(record['suites'])==29 and record['cases']==308
assert record['input_sha256']==record['after_sha256']
assert all(x['exit']==0 for x in record['suites'])
assert not OUT.exists() and not DEST.exists()
files={}
for p in RAW.iterdir():
    assert p.is_file() and not p.is_symlink()
    files['host-002/'+p.name]=p
for name,expected in record['input_sha256'].items():
    assert name.startswith(('rusix/scripts/','rusix/tests/','rusix/configs/'))
    p=SOURCE/name;assert digest(p)==expected,name
    files['inputs/'+name]=p
files['initial-fixture-failure.txt']=BASE/'linux-out/mm-exit-mmap-tooling-host-001/initial-failure.txt'
files['archive.py']=Path(__file__).resolve()
for p in files.values():
    assert not p.is_symlink();data=p.read_bytes();assert b'\0' not in data;data.decode('utf-8')
OUT.mkdir();records={}
for name,p in sorted(files.items()):
    q=OUT/name;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(p.read_bytes())
    records[name]={'sha256':digest(q),'bytes':q.stat().st_size,'original':str(p)}
manifest={'status':'PASS','scope':'Host tooling regression evidence only: 29 suites / 308 cases. No candidate compilation, kernel build or VM execution.',
          'production_base':'14bc4e7ebc2ac339dbf1ed962f4e59aa8ba16fb4',
          'tooling_snapshot':'Uncommitted input hashes in host-002/result.json, not attributed to production_base as tested tooling.',
          'excluded_scope':['mm/exit_mmap_test.c','init/Kconfig','mm/Makefile','native teardown fixture implementation or execution'],
          'suites':29,'cases':308,'inputs_stable':True,'initial_fixture_setup_failure_retained':True,
          'files':records,'input_sha256':record['input_sha256']}
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
for name,item in records.items():assert digest(OUT/name)==item['sha256']
shutil.copytree(OUT,DEST)
for p in OUT.rglob('*'):
    if p.is_file():assert digest(p)==digest(DEST/p.relative_to(OUT))
print(json.dumps({'status':'PASS','files':len(records),'inputs':len(record['input_sha256']),'manifest_sha256':digest(OUT/'manifest.json')},indent=2))
