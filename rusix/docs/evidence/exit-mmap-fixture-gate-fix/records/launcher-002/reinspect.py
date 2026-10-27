#!/usr/bin/env python3
"""Inspect retained failed-run artifacts using separately attributed metadata gate fixes."""
import hashlib, importlib.util, json, os, re, shutil, subprocess, sys
from pathlib import Path
from types import SimpleNamespace
BASE=Path('/home/aaron/code/rusix')
DRAFT=Path(__file__).resolve().parent
SOURCE=BASE/'linux-mm-exit-mmap'
FIX=BASE/'linux-mm-exit-mmap-fix'
RAW=BASE/'linux-out/mm-exit-mmap-verification-001/kunit-c'
BUILD=RAW/'builds/ci-exit-mmap-kunit-c'
PROOF=RAW/'logs/ci-exit-mmap-kunit-c-build.Rvh4zoui'
OUT=BASE/'linux-out/exit-mmap-fixture-gate-reinspection-002'
EXPECTED='0ff7a933c198dda0c3e2c0005e4bb97db3867acc'
IMAGE='sha256:c02eb3929889b3f0cc035d57a02c844e0c74c71d24fbda1311249faeb8257f63'
def need(value,message):
    if not value:raise ValueError(message)
def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()
def raw_hashes():return {str(p.relative_to(RAW)):digest(p) for p in sorted(RAW.rglob('*')) if p.is_file()}
def git(*args):return subprocess.check_output(['git','-C',str(SOURCE),*args],text=True).strip()
def main():
    ready=json.loads((DRAFT/'ready.json').read_text())
    need(ready['enabled'] is True,'Read-only reinspection awaits root review')
    need(os.environ.get('RUSIX_PINNED_POSTCHECK_IMAGE')==IMAGE,'Pinned inspection image required')
    for name,value in ready['draft_sha256'].items():need(digest(DRAFT/name)==value,'Draft changed')
    pins=json.loads((DRAFT/'inputs.json').read_text())
    need(git('rev-parse','HEAD')==EXPECTED and git('status','--porcelain','--untracked-files=all')=='','Original source identity changed')
    for name,value in pins['original_source_sha256'].items():need(digest(SOURCE/name)==value,'Original source changed: '+name)
    for name,value in pins['fixed_tooling_sha256'].items():need(digest(FIX/name)==value,'Fixed tooling changed: '+name)
    before=raw_hashes();need(before==pins['raw_sha256'],'Retained failed-run raw inputs changed')
    need((RAW/'logs/container.exit').read_text().strip()=='1','Original failed exit changed')
    need('ValueError: Unexpected teardown object' in (RAW/'logs/container.log').read_text(),'Original failure missing')
    need((PROOF/'exit-mmap-selection.json').read_bytes()==b'','Unexpected prior top-level PASS')
    # Only the newly created output directory is writable. No original record is edited.
    evidence=OUT/'actual';evidence.mkdir()
    sys.path.insert(0,str(FIX/'rusix/scripts'))
    spec=importlib.util.spec_from_file_location('fixed_exit_selection',FIX/'rusix/scripts/verify-exit-mmap.py')
    selection=importlib.util.module_from_spec(spec);spec.loader.exec_module(selection)
    cb=Path('/out/builds/ci-exit-mmap-kunit-c');pre=selection.preprocessor
    def resolve(name):
        p=Path(name);need(p.is_absolute() and '..' not in p.parts,'Noncanonical input path')
        if p.is_relative_to('/src'):return SOURCE/p.relative_to('/src')
        if p.is_relative_to('/out'):return RAW/p.relative_to('/out')
        raise ValueError('Unknown original path: '+name)
    for parser,prefix,unit in ((pre.copy,'mm-copy','kernel/fork'),(pre.dup,'dup-mmap','mm/mmap'),(pre.vma,'vma-lifecycle','mm/vma_init')):
        cmd=BUILD/Path(unit).parent/('.'+Path(unit).name+'.o.cmd');output=BUILD/(unit+'.i');co=cb/(unit+'.i')
        original=dict(argv=parser.command(cmd.read_text(),co),cwd=str(cb),input_sha256={str(p):digest(resolve(str(p))) for p in parser.inputs(cb,Path('/src'))},output=str(co),preprocessed_sha256=digest(output))
        need(json.loads((PROOF/(prefix+'-preprocess.json')).read_text())==original,'Original preprocessing differs: '+prefix)
        remapped=dict(argv=parser.command(cmd.read_text(),output),cwd=str(BUILD),input_sha256={str(p):digest(p) for p in parser.inputs(BUILD,SOURCE)},output=str(output),preprocessed_sha256=digest(output))
        (evidence/(prefix+'-preprocess.json')).write_text(json.dumps(remapped,indent=2)+'\n')
    original=dict(input_sha256={str(p):digest(resolve(str(p))) for p in pre.inputs(cb,Path('/src'))},argv=pre.command((BUILD/'mm/.vma.o.cmd').read_text(),cb/'mm/vma.i'),cwd=str(cb),output=str(cb/'mm/vma.i'),preprocessed_sha256=digest(BUILD/'mm/vma.i'),prerequisite_outputs={str(cb/name):digest(BUILD/name) for name in ('kernel/fork.i','mm/mmap.i','mm/vma_init.i')})
    need(json.loads((PROOF/'exit-mmap-preprocess.json').read_text())==original,'Original four-unit provenance differs')
    (evidence/'exit-mmap-preprocess.json').write_text(json.dumps(pre.record(BUILD,SOURCE),indent=2)+'\n')
    for prefix in ('mm-copy','dup-mmap','vma-lifecycle','exit-mmap'):
        need((PROOF/(prefix+'-preprocess.exit')).read_text().strip()=='0','Preprocessing failed')
        need(not re.search('warning:|error:',(PROOF/(prefix+'-preprocess.log')).read_text(),re.I),'Preprocessing diagnostics')
        for suffix in ('log','exit'):shutil.copyfile(PROOF/(prefix+'-preprocess.'+suffix),evidence/(prefix+'-preprocess.'+suffix))
    saved=json.loads((PROOF/'exit-mmap-vma-selection.json').read_text());dup=saved['dup_mmap_selection']
    for filename,value in [('vma-lifecycle-dup-selection.json',dup),('dup-mmap-mm-copy-selection.json',dup['mm_copy_selection'])]:
        need(json.loads((PROOF/filename).read_text())==value,'Saved nested proof mismatch: '+filename)
    # Calls the entire original nested chain and actual fixture ELF/payload graph,
    # changing only the reviewed archive gate and canonical sentinel checks.
    actual=selection.verify(SimpleNamespace(source=SOURCE,build=BUILD,evidence=evidence,profile='exit-mmap-kunit-c'))
    need(actual['status']=='PASS' and actual['implementation']=='c' and actual['test_context']==selection.TEST_CONTEXT,'Wrong actual result scope')
    def canonical(name):
        p=Path(name);need(p.is_absolute() and '..' not in p.parts,'Noncanonical inspected path')
        for host,old in ((SOURCE,Path('/src')),(RAW,Path('/out'))):
            if p.is_relative_to(host):return str(old/p.relative_to(host))
        raise ValueError('Unknown inspected path: '+name)
    def normalize(value):
        if not isinstance(value,dict):return
        for field,child in value.items():
            if field in ('input_sha256','archive_member_sha256'):
                mapped={canonical(k):v for k,v in child.items()};need(len(mapped)==len(child),'Remap collision');value[field]=mapped
            elif isinstance(child,dict):normalize(child)
    nested=json.loads(json.dumps(actual['vma_lifecycle_selection']));normalize(nested)
    need(nested==saved,'Entire reinspected nested proof differs')
    need(raw_hashes()==before,'Retained failed run mutated')
    need(git('rev-parse','HEAD')==EXPECTED and git('status','--porcelain','--untracked-files=all')=='','Original source changed during inspection')
    for name,value in pins['original_source_sha256'].items():need(digest(SOURCE/name)==value,'Original source changed during inspection')
    for name,value in pins['fixed_tooling_sha256'].items():need(digest(FIX/name)==value,'Tooling changed during inspection')
    (OUT/'actual-selection.json').write_text(json.dumps(actual,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':'PASS','original_source':EXPECTED,'fixed_tooling_sha256':pins['fixed_tooling_sha256'],'raw_records':len(before),'scope':'Retained KUnit C object/fixture reinspection only; original run remains failed, no guest executed, fresh retry required'},indent=2))
if __name__=='__main__':main()
