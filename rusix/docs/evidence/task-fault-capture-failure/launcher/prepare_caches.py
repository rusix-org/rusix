#!/usr/bin/env python3
"""Disabled until root review: kernel-only C cache; never builds or runs guests."""
import argparse,fcntl,json,re,shutil,stat,subprocess
from pathlib import Path
from preflight import BASE,SOURCE,EXPECTED,RUN,REVIEWED_LAUNCH_READY,source_record,digest
SEED_SOURCE='8acd1a79a9cde4064f8b7ad3f967b48c52b60770'
FIX='c59986edf69556715bd1094521c8d8d1a49ebaab'
OLD=BASE/'linux-out/task-fault-verification-001'
ARCHIVE=BASE/'linux-out/task-fault-initial-evidence'
MANIFEST='d90549560f750b2fabcdfc4595fbcda597e6f1e89c103bdb665e5c3275848675'
FIX_FILES={'rusix/scripts/generate-task-fault-calibration.py','rusix/scripts/validate-task-fault-trace.py','rusix/tests/test_task_fault_trace.py','rusix/tests/test_task_fault_pipeline.py'}
INVALIDATE=['kernel/fork.i','kernel/fork.o','kernel/.fork.o.cmd',

 'kernel/built-in.a','kernel/.built-in.a.cmd','vmlinux.a','.vmlinux.a.cmd',
 'vmlinux.o','.vmlinux.o.cmd','vmlinux','.vmlinux.cmd','vmlinux.map','System.map',
 '.tmp_vmlinux.kallsyms1','.tmp_vmlinux.kallsyms1.o','.tmp_vmlinux.kallsyms1.S',
 '.tmp_vmlinux.kallsyms2','.tmp_vmlinux.kallsyms2.o','.tmp_vmlinux.kallsyms2.S',
 '.tmp_vmlinux.kallsyms3','.tmp_vmlinux.kallsyms3.o','.tmp_vmlinux.kallsyms3.S',
 '.tmp_System.map','arch/x86/boot/bzImage','arch/x86/boot/.bzImage.cmd',
 'arch/x86/boot/vmlinux.bin','arch/x86/boot/.vmlinux.bin.cmd',
 'arch/x86/boot/compressed/vmlinux','arch/x86/boot/compressed/.vmlinux.cmd',
 'arch/x86/boot/compressed/vmlinux.bin','arch/x86/boot/compressed/vmlinux.bin.gz',
 'arch/x86/boot/compressed/vmlinux.bin.xz','arch/x86/boot/compressed/vmlinux.bin.zst',
 'arch/x86/boot/compressed/piggy.o','arch/x86/boot/compressed/.piggy.o.cmd']
# Observed pinned link-vmlinux outputs use numbered temporary names.
INVALIDATE += ['vmlinux.unstripped', '.vmlinux.unstripped.cmd', '.tmp_vmlinux.nm-sort']
for index in range(3):
    INVALIDATE += [f'.tmp_vmlinux{index}' + suffix for suffix in ('', '.syms', '.kallsyms.S', '.kallsyms.o')]

def inventory(root):
    result={}
    for p in sorted(root.rglob('*')):
        info=p.lstat();rel=str(p.relative_to(root));kind=info.st_mode
        if stat.S_ISLNK(kind):result[rel]=dict(type='symlink',target=str(p.readlink()))
        elif stat.S_ISREG(kind):
            value=digest(p);after=p.lstat()
            if (info.st_size,info.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):raise ValueError('Cache changed while hashing')
            result[rel]=dict(type='file',sha256=value,bytes=info.st_size,mtime_ns=info.st_mtime_ns,mode=stat.S_IMODE(kind))
        elif stat.S_ISDIR(kind):continue
        else:raise ValueError('Unexpected filesystem type: '+str(p))
    return result


def original():
    if digest(ARCHIVE/'manifest.json')!=MANIFEST:raise ValueError('Failure manifest changed')
    m=json.loads((ARCHIVE/'manifest.json').read_text())
    if (m['source'],m['status'],m['matrix_exit'],m['c_build_exit'],m['rust_started'],m['vm_started'])!=(SEED_SOURCE,'FAIL',1,0,False,False):raise ValueError('Failure provenance differs')
    for name,value in m['files'].items():
        if digest(ARCHIVE/name)!=value:raise ValueError('Failure archive changed')
    for name,value in m['retained_artifacts'].items():
        p=Path(name)
        if digest(p)!=value['sha256'] or p.stat().st_size!=value['bytes']:raise ValueError('Retained artifact changed')
    if (OLD/'matrix.exit').read_text().strip()!='1' or (OLD/'rust').exists():raise ValueError('Original matrix changed')
    subprocess.run(['git','-C',str(SOURCE),'merge-base','--is-ancestor',FIX,EXPECTED],check=True)
    delta=subprocess.check_output(['git','-C',str(SOURCE),'diff','--name-only',SEED_SOURCE,EXPECTED],text=True).splitlines()
    for name in delta:
        if name in FIX_FILES:
            if subprocess.check_output(['git','-C',str(SOURCE),'show',EXPECTED+':'+name])!=subprocess.check_output(['git','-C',str(SOURCE),'show',FIX+':'+name]):raise ValueError('Reviewed verifier fix changed')
        elif not (name=='rusix/PROGRESS.md' or name.startswith('rusix/docs/evidence/') or (name.startswith('rusix/') and name.endswith('.md'))):
            raise ValueError('Kernel/config/runtime delta not allowed: '+name)
    return dict(seed_source=SEED_SOURCE,retry_source=EXPECTED,source_delta=delta,manifest_sha256=MANIFEST,original_tree=inventory(OLD),archive_tree=inventory(ARCHIVE),scope='C build cache only; failed calibration/absence of VM remains historical')

def prepare():
    if not REVIEWED_LAUNCH_READY:raise ValueError('Root review/final checkpoint pending')
    source_record();prior=original()
    if RUN.exists():raise ValueError('Fresh output required')
    RUN.mkdir()
    for side in ('c','rust'):(RUN/side/'logs').mkdir(parents=True)
    seed=OLD/'c/builds/ci-task-construction-fault-c';dest=RUN/'c/builds/ci-task-construction-fault-c'
    before=inventory(seed);dest.parent.mkdir();shutil.copytree(seed,dest,symlinks=True,copy_function=shutil.copy2)
    copied=inventory(dest)
    if copied!=before:raise ValueError('Copied cache differs')
    removed={}
    for name in INVALIDATE:
        p=dest/name
        if p.is_symlink():raise ValueError('Unexpected invalidation symlink')
        if p.exists():
            if not p.is_file():raise ValueError('Unexpected invalidation type')
            removed[name]=copied[name];p.unlink()
    record=dict(status='PREPARED_NOT_RUN',provenance=prior,invalidations=INVALIDATE,copied=dict(seed=str(seed),destination=str(dest),all_copied=copied,removed=removed,prepared=inventory(dest)),rust='FRESH_NO_CACHE')
    if original()!=prior:raise ValueError('Original failure evidence changed during copy')
    (RUN/'cache-preparation.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
    verify_prepared()

def verify_original():
    record=json.loads((RUN/'cache-preparation.json').read_text())
    if record['provenance']!=original():raise ValueError('Original evidence changed')
    source_record()
    return dict(status='PASS',scope='Original001 raw outputs and failure archive unchanged')

def verify_prepared():
    verify_original();r=json.loads((RUN/'cache-preparation.json').read_text())
    if r['status']!='PREPARED_NOT_RUN' or r['rust']!='FRESH_NO_CACHE' or r['invalidations']!=INVALIDATE:raise ValueError('Preparation identity differs')
    if set(p.name for p in RUN.iterdir())!={'c','rust','cache-preparation.json'}:raise ValueError('Output already used')
    if set(p.name for p in (RUN/'c').iterdir())!={'logs','builds'} or set(p.name for p in (RUN/'rust').iterdir())!={'logs'}:raise ValueError('Unexpected cache/output inventory')
    for side in ('c','rust'):
        if list((RUN/side/'logs').iterdir()):raise ValueError('Logs not fresh')
    dest=RUN/'c/builds/ci-task-construction-fault-c'
    if r['copied']['destination']!=str(dest) or inventory(dest)!=r['copied']['prepared']:raise ValueError('Prepared cache changed')
    if any((dest/n).exists() or (dest/n).is_symlink() for n in INVALIDATE):raise ValueError('Invalidated output survived')

if __name__=='__main__':
    ap=argparse.ArgumentParser();g=ap.add_mutually_exclusive_group(required=True);g.add_argument('--execute',action='store_true');g.add_argument('--verify-original',action='store_true');a=ap.parse_args()
    if a.execute:
        with (BASE/'linux-out/.wait-owner-remaining.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            prepare()
    else:
        # Launcher already owns the matrix lock; this path is read-only.
        print(json.dumps(verify_original(),indent=2))
