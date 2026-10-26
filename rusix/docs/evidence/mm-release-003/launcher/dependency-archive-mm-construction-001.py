#!/usr/bin/env python3
"""Archive only a completed, independently rechecked MM-construction001 pair.

Prepared source only. Root must observe execution session15626 terminal before
invocation; matrix.exit is the launcher's final persisted terminal status.
No builds, guests, source changes or binary payload copies.
"""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
sys.dont_write_bytecode=True
BASE=Path('/home/aaron/code/rusix')
RUN=BASE/'linux-out/mm-construction-verification-001'
DRAFT=BASE/'linux-out/mm-construction-verification-draft'
OUTPUT=BASE/'linux-out/mm-construction-001-evidence'
SOURCE='00c4ef1c190349a671a2a72ce4736c6bfb58210e'
CASES=['anonymous_private_fork_cow','child_mapping_survives_parent_unmap','repeated_fork_exec_reap','mdwe_inherited_fork_exec','mdwe_no_inherit_fork_exec']


def need(value,message):
    if not value:raise ValueError(message)


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def text_file(path):
    need(not path.is_symlink() and path.is_file(),'Refuse symlink/non-file '+str(path))
    need(path.suffix not in {'.o','.a','.ko','.elf','.bin','.cpio','.gz','.xz','.bz2','.zst','.png','.jpg','.pdf'},'Refuse binary suffix '+str(path))
    data=path.read_bytes()
    need(not data.startswith((b'\x7fELF',b'!<arch>',b'!<thin>',b'070701',b'\x1f\x8b')), 'Refuse binary magic '+str(path))
    decoded=data.decode('utf-8',errors='strict')
    need(all(ord(c)>=32 or c in '\t\r\n\x1b\b' for c in decoded),'Refuse binary/control payload '+str(path))
    return data


def launcher_hashes():
    expected={str(DRAFT/name) for name in ('run.sh','preflight.py','check-results.py')}
    rows={}
    for line in (RUN/'launcher.sha256').read_text().splitlines():
        match=re.fullmatch(r'([0-9a-f]{64})  (.+)',line)
        need(match and match[2] not in rows,'Malformed launcher hash record')
        rows[match[2]]=match[1]
    need(set(rows)==expected,'Launcher inventory differs')
    for name,value in rows.items():need(digest(Path(name))==value,'Reviewed launcher changed')
    return rows


def main():
    need(not OUTPUT.exists(),'Archive destination already exists')
    need((RUN/'matrix.exit').read_text().strip()=='0','Session15626 matrix has not completed successfully')
    scripts=launcher_hashes()
    # This exact reviewed checker validates all actual build/object/fixture hashes,
    # preprocessing, five literal cases, source/image/tool inputs, selector-only
    # config difference. No allocation-failure result is implied.
    command=[sys.executable,'-B',str(DRAFT/'check-results.py')]
    checked=subprocess.run(command,check=True,capture_output=True,text=True)
    need(not checked.stderr,'Pair checker diagnostics')
    result=json.loads(checked.stdout)
    need(result==json.loads((RUN/'pair-result.json').read_text()),'Stored pair result differs from recheck')
    need(result['status']=='PASS' and result['source']==SOURCE and result['cases']==CASES,'Wrong source/case inventory')
    need(result['different_settings']==['CONFIG_RUSIX_MM_CONSTRUCTION_RUST'],'Unexpected comparison axis')
    files={}
    for side in ('c','rust'):
        for path in sorted((RUN/side/'logs').rglob('*')):
            if path.is_file() or path.is_symlink():files['records/'+str(path.relative_to(RUN))]=path
    for name in ('matrix.exit','pair-result.json','source-before.json','launcher.sha256','launcher-after.log'):
        files['records/'+name]=RUN/name
    for path in sorted((RUN/'guest-source').iterdir()):files['records/guest-source/'+path.name]=path
    for name in ('run.sh','preflight.py','check-results.py','README.md'):
        files['launcher/'+name]=DRAFT/name
    files['launcher/archive-mm-construction-001.py']=Path(__file__).resolve()
    # Validate every payload before creating the no-overwrite destination.
    hashes={name:hashlib.sha256(text_file(path)).hexdigest() for name,path in files.items()}
    raw={}
    for side in ('c','rust'):
        output=RUN/side
        proofs=list((output/'logs').glob(f'ci-mm-construction-{side}-build.*'))
        need(len(proofs)==1,'Ambiguous build proof')
        selection=json.loads((proofs[0]/'mm-selection.json').read_text())
        fixture=json.loads((output/'logs'/f'ci-mm-construction-{side}-mm-construction.run'/'inputs.json').read_text())
        for mapping in (selection['input_sha256'],fixture['artifacts']):
            for name,value in mapping.items():
                p=Path(name)
                if p.is_relative_to('/out'):
                    host=output/p.relative_to('/out')
                    need(digest(host)==value,'Actual retained artifact changed')
                    raw[str(host)]=value
    OUTPUT.mkdir()
    for name,path in files.items():
        destination=OUTPUT/name;destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(path,destination)
        need(digest(destination)==hashes[name] and digest(path)==hashes[name],'Copy/source changed')
    need(launcher_hashes()==scripts,'Launcher changed during archive')
    need((RUN/'matrix.exit').read_text().strip()=='0','Matrix status changed')
    for name,value in raw.items():need(digest(Path(name))==value,'Retained artifact changed during archive')
    (OUTPUT/'recheck.json').write_text(json.dumps(dict(command=command,status=checked.returncode,result=result),indent=2)+'\n')
    hashes['recheck.json']=digest(OUTPUT/'recheck.json')
    manifest=dict(status='PASS',source=SOURCE,controller_session=15626,raw_output=str(RUN),
                  scope='Matched five ordinary address-space/COW/exec/MDWE consumers; no allocation-failure coverage',
                  result=result,files=hashes,raw_artifact_sha256=raw)
    (OUTPUT/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    print(json.dumps(dict(status='PASS',archive=str(OUTPUT),files=len(hashes)),indent=2))
if __name__=='__main__':main()
