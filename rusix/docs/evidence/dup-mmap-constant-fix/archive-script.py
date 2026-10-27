#!/usr/bin/env python3
"""Archive completed host/actual-ELF recheck, not a new kernel or VM result."""
from pathlib import Path
import hashlib,json,gzip,shutil,re
BASE=Path('/home/aaron/code/rusix');SOURCE=BASE/'linux-mm-dup-mmap';OUT=BASE/'linux-out'
HOST=OUT/'dup-mmap-constant-fix-host-001';FULL=OUT/'dup-mmap-constant-selection-001'
DEST=OUT/'dup-mmap-constant-fix-evidence';TRACKED=SOURCE/'rusix/docs/evidence/dup-mmap-constant-fix'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
host=json.loads((HOST/'result.json').read_text());full=json.loads((FULL/'result.json').read_text())
assert host['status']==full['status']=='PASS' and full['container_exit']==0
for name,sha in host['fix_input_sha256'].items():assert digest(SOURCE/name)==sha
for name,sha in host['retained_input_sha256'].items():assert digest(Path(name))==sha
for name,sha in host['logs_sha256'].items():assert digest(HOST/name)==sha
for name,sha in full['input_sha256_before_after'].items():assert digest(Path(name))==sha
for name,sha in full['evidence_sha256'].items():assert digest(FULL/name)==sha
assert full['compiled_source']=='9cf27ef36d1d58cb65bd866d9f046ed2e56b045a'
assert full['verifier_base']=='105d6b4eaddaffa1ca5aa1c04d28f29adfc1f59b'
assert (FULL/'container.log').read_bytes()==b''
assert not DEST.exists() and not TRACKED.exists()
DEST.mkdir();files={};raw={};count=0

def record(path,relative):
    global count
    data=path.read_bytes();data.decode('utf-8') # reject binaries
    target=DEST/relative;target.parent.mkdir(parents=True,exist_ok=True)
    original={'path':str(path),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
    if len(data)>256*1024:
        target=target.with_name(target.name+'.gz');target.write_bytes(gzip.compress(data,mtime=0))
        assert gzip.decompress(target.read_bytes())==data
        original['compression']='gzip';original['original_relative_path']=str(relative)
    else:target.write_bytes(data)
    files[str(target.relative_to(DEST))]=dict(sha256=digest(target),bytes=target.stat().st_size,original=original);count+=1

for prefix,folder in [('host',HOST),('selection',FULL)]:
    for path in sorted(folder.rglob('*')):
        if path.is_file():record(path,Path(prefix)/path.relative_to(folder))
for name in host['fix_input_sha256']:record(SOURCE/name,Path('source')/name)
record(Path(__file__),Path('archive-script.py'))
# These binaries remain in their original build outputs; only their identities
# are included. Source/tool/config inputs remain separately attributed above.
for name,sha in full['input_sha256_before_after'].items():
    p=Path(name)
    if p.suffix in ('.o','.a') or p.name=='vmlinux':raw[name]={'sha256':sha,'bytes':p.stat().st_size}
checks={}
for path in HOST.glob('test_*.log'):
    if 'before-parameter' in path.name:continue
    match=re.search(r'Ran (\d+) tests?',path.read_text());assert match and path.read_text().rstrip().endswith('OK')
    checks[path.name]=int(match[1])
manifest={'status':'PASS','scope':'Verifier correction: synthetic host gates and full pinned actual-object/linked selection recheck against retained kernel. No kernel build or VM; original failed matrix unchanged.',
 'compiled_source':full['compiled_source'],'verifier_base':full['verifier_base'],'verifier_changes':full['verifier_dirty_status'],'verifier_input_sha256':host['fix_input_sha256'],
 'image':full['image'],'host_tests':checks,'selected_inputs':full['selection_input_count'],'raw_artifacts':raw,'records':files,'record_count':len(files)}
(DEST/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
shutil.copytree(DEST,TRACKED)
for folder in [DEST,TRACKED]:
    for name,entry in files.items():
        p=folder/name;assert digest(p)==entry['sha256']
        if entry['original'].get('compression')=='gzip':assert hashlib.sha256(gzip.decompress(p.read_bytes())).hexdigest()==entry['original']['sha256']
    assert digest(folder/'manifest.json')==digest(DEST/'manifest.json')
print(json.dumps({'status':'PASS','records':len(files),'raw_artifacts':len(raw),'host_tests':checks,'manifest_sha256':digest(DEST/'manifest.json')},indent=2))
