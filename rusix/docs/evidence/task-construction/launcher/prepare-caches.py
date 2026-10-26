#!/usr/bin/env python3
"""Explicit kernel-only cache preparation. Never launches a compiler or guest."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import stat
import subprocess
from preflight import BASE, SOURCE, EXPECTED, RUN, source_record, digest
SEED_SOURCE='0af2d8b944b2d6a3175269c52f10d85ce67a7d3d'
OLD=BASE/'linux-out/task-construction-verification-002'
INITIAL=BASE/'linux-out/task-construction-verification-001'
FAILURE=BASE/'linux-out/task-construction-warnings-evidence'
ANNOTATION = """// task_struct contains GNU empty structs (for example sched_statistics when
// SCHEDSTATS=n). Every aggregate in this block crosses the ABI only as a raw
// pointer; no layout, field, or by-value aggregate is used by Rust. The canonical
// C prototypes retain task_struct pointer types. Keep this exception local to
// these reviewed declarations, as in the generated bindings crate.
#[allow(improper_ctypes)]
"""
INVALIDATE=['kernel/fork.i','kernel/fork.o','kernel/.fork.o.cmd','kernel/built-in.a','kernel/.built-in.a.cmd','kernel/task_construction_rust.o','kernel/.task_construction_rust.o.cmd']


def inventory(root):
    result={}
    for p in sorted(root.rglob('*')):
        if p.is_symlink(): result[str(p.relative_to(root))]=dict(type='symlink',target=str(p.readlink()))
        elif p.is_file(): result[str(p.relative_to(root))]=dict(type='file',sha256=digest(p))
        elif stat.S_ISFIFO(p.lstat().st_mode) and p == OLD/'rust/builds/tmp/GMfifo1083':
            # Interrupted GNU make left its jobserver FIFO outside the selected
            # build cache. Preserve metadata only; never read/open/copy a FIFO.
            info=p.lstat()
            result[str(p.relative_to(root))]=dict(type='fifo',mode=stat.S_IMODE(info.st_mode),inode=info.st_ino,device=info.st_dev)
        elif not p.is_dir(): raise ValueError('Unsupported cache file type: '+str(p))
    return result


def original():
    archives={}
    for root,count,status,key in [(BASE/'linux-out/task-construction-initial-evidence',69,'FAIL','compiled_artifacts_not_copied'),
                                  (FAILURE,181,'STOPPED_WITH_DIAGNOSTICS','raw_artifact_sha256')]:
        record=json.loads((root/'manifest.json').read_text())
        if record['status']!=status or len(record['files'])!=count: raise ValueError('Original archive identity differs')
        for name,expected in record['files'].items():
            if digest(root/name)!=expected: raise ValueError('Original archive changed')
        for name,expected in record[key].items():
            if digest(Path(name))!=expected: raise ValueError('Original artifact changed')
        archives[str(root)]=dict(manifest_sha256=digest(root/'manifest.json'),record=record)
    if (INITIAL/'matrix.exit').read_text().strip()!='1' or (OLD/'matrix.exit').read_text().strip()!='137':
        raise ValueError('Original failure statuses differ')
    if (OLD/'c/logs/container.exit').read_text().strip()!='0' or (OLD/'rust/logs/container.exit').read_text().strip()!='137':
        raise ValueError('Original002 side statuses differ')
    delta=subprocess.check_output(['git','-C',str(SOURCE),'diff','--name-only',SEED_SOURCE,EXPECTED],text=True).splitlines()
    if set(delta)!={'rusix/PROGRESS.md','kernel/task_construction_rust.rs'}:
        raise ValueError('Unexpected source delta')
    old=subprocess.check_output(['git','-C',str(SOURCE),'show',SEED_SOURCE+':kernel/task_construction_rust.rs'],text=True)
    new=subprocess.check_output(['git','-C',str(SOURCE),'show',EXPECTED+':kernel/task_construction_rust.rs'],text=True)
    if new.count(ANNOTATION)!=1 or new.replace(ANNOTATION,'')!=old:
        raise ValueError('Change exceeds exact reviewed pointer-only ABI annotation')
    return dict(seed_source=SEED_SOURCE,retry_source=EXPECTED,source_delta=delta,
                c_seed_status='COMPLETED_C_BUILD_AND_FIVE_CONSUMERS_CACHE_ONLY',
                rust_seed_status='INTERRUPTED_137_WITH_36_WARNINGS_PARTIAL_OBJECTS_INHERITED_C_LINKED_IMAGES_CACHE_ONLY',
                original_trees={str(root):inventory(root) for root in (INITIAL,OLD)},archives=archives,
                annotation_sha256=hashlib.sha256(ANNOTATION.encode()).hexdigest())


def prepare():
    source_record()
    prior=original()
    if RUN.exists(): raise ValueError('Retry destination already exists')
    RUN.mkdir()
    record=dict(provenance=prior,copied={},invalidations=INVALIDATE)
    for side in ('c','rust'):
        seed_path=OLD/side/'builds'/f'ci-task-construction-{side}'
        seed=inventory(seed_path)
        destination=RUN/side/'builds'/f'ci-task-construction-{side}'
        destination.parent.mkdir(parents=True)
        (RUN/side/'logs').mkdir()
        shutil.copytree(seed_path,destination,symlinks=True,copy_function=shutil.copy2)
        copied=inventory(destination)
        if copied!=seed: raise ValueError('Kernel cache copy differs')
        removed=[]
        for name in INVALIDATE:
            candidate=destination/name
            if candidate.exists():
                candidate.unlink(); removed.append(name)
        record['copied'][side]=dict(seed=str(seed_path),destination=str(destination),all_copied= copied,removed=removed,
                                    prepared=inventory(destination))
    if original()!=prior: raise ValueError('Original files changed while preparing cache')
    (RUN/'cache-preparation.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
    verify_prepared()


def verify_prepared():
    record=json.loads((RUN/'cache-preparation.json').read_text())
    if original()!=record['provenance']: raise ValueError('Original001/002 files changed')
    if set(p.name for p in RUN.iterdir())!={'c','rust','cache-preparation.json'}: raise ValueError('Retry output already used')
    for side in ('c','rust'):
        if list((RUN/side/'logs').iterdir()): raise ValueError('Retry logs not fresh')
        item=record['copied'][side]
        if inventory(Path(item['destination']))!=item['prepared']: raise ValueError('Prepared cache changed')
        if any((Path(item['destination'])/name).exists() for name in INVALIDATE): raise ValueError('Stale constructor object/preprocessing survived')
    source_record()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true');args=p.parse_args()
    if not args.execute: p.error('Explicit --execute required; preparation has not run')
    prepare()
