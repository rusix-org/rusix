#!/usr/bin/env python3
"""Explicit, reviewed kernel-only cache copying; never invokes a compiler/VM."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import stat
import subprocess
from preflight import BASE,SOURCE,EXPECTED,RUN,source_record,digest
SEED_SOURCE='42318e69e5f27a2f2363c0fea285cca59f710baf'
OLD=BASE/'linux-out/mm-release-verification-002'
INITIAL=BASE/'linux-out/mm-release-verification-001'
ARCHIVES=(BASE/'linux-out/mm-release-initial-evidence',BASE/'linux-out/mm-release-warnings-evidence')
# Root must replace this with the exact independently reviewed local comment
# and attribute after committing; no source delta is accepted by implication.
ANNOTATION="// The pinned bindgen MM/work types can reach GNU empty sched_statistics.\n// The observed lint concerns that nested type, but all aggregates in this block\n// cross only as raw pointers (including the callback's work_struct pointer).\n// Scalar results are C bool or void; no foreign aggregate crosses by value or\n// has its layout read by Rust. Keep this audited ABI exception local.\n#[allow(improper_ctypes)]\n"
INVALIDATE=['kernel/fork.i','kernel/fork.o','kernel/.fork.o.cmd',
 'kernel/mm_release_rust.o','kernel/.mm_release_rust.o.cmd',
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
FIFO=OLD/'rust/builds/tmp/GMfifo1162'


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
        elif stat.S_ISFIFO(kind) and p==FIFO:
            # Known interrupted make jobserver, outside either selected cache.
            # Metadata only: never open, read or copy a FIFO.
            result[rel]=dict(type='fifo',mode=stat.S_IMODE(kind),inode=info.st_ino,device=info.st_dev)
        else:raise ValueError('Unexpected filesystem type: '+str(p))
    return result


def original():
    if not re.fullmatch('[0-9a-f]{40}',EXPECTED) or ANNOTATION.startswith('PENDING_'):
        raise ValueError('Root-reviewed source/annotation identity still pending')
    archives={}
    for root,source,exitcode,count in zip(ARCHIVES,('fc7317e898853c95e4584d55e3477c4d7e755122',SEED_SOURCE),(2,137),(70,188)):
        record=json.loads((root/'manifest.json').read_text())
        if record['source']!=source or record['status']!='FAIL' or record['matrix_exit']!=exitcode or len(record['files'])!=count:raise ValueError('Failure archive identity differs')
        for name,value in record['files'].items():
            if digest(root/name)!=value:raise ValueError('Archived text changed')
        for name,value in record['retained_artifacts'].items():
            p=Path(name)
            if digest(p)!=value['sha256'] or p.stat().st_size!=value['bytes']:raise ValueError('Retained artifact changed')
        archives[str(root)]=dict(manifest_sha256=digest(root/'manifest.json'),inventory=inventory(root))
    if (INITIAL/'matrix.exit').read_text().strip()!='2' or (OLD/'matrix.exit').read_text().strip()!='137':raise ValueError('Original statuses differ')
    if (OLD/'c/logs/container.exit').read_text().strip()!='0' or (OLD/'rust/logs/container.exit').read_text().strip()!='137':raise ValueError('Seed side statuses differ')
    if json.loads((OLD/'c/logs/postchecks.json').read_text())!={'status':'PASS','side':'c'}:raise ValueError('Seed C postcheck is not complete')
    if (OLD/'rust/logs/postchecks.json').exists():raise ValueError('Unexpected Rust postcheck')
    delta=subprocess.check_output(['git','-C',str(SOURCE),'diff','--name-only',SEED_SOURCE,EXPECTED],text=True).splitlines()
    if set(delta)!={'kernel/mm_release_rust.rs','rusix/PROGRESS.md'}:raise ValueError('Unexpected source delta')
    old=subprocess.check_output(['git','-C',str(SOURCE),'show',SEED_SOURCE+':kernel/mm_release_rust.rs'],text=True)
    new=subprocess.check_output(['git','-C',str(SOURCE),'show',EXPECTED+':kernel/mm_release_rust.rs'],text=True)
    if new.count(ANNOTATION)!=1 or new.replace(ANNOTATION,'')!=old:raise ValueError('Delta exceeds exact local ABI annotation')
    return dict(seed_source=SEED_SOURCE,retry_source=EXPECTED,source_delta=delta,
                annotation_sha256=hashlib.sha256(ANNOTATION.encode()).hexdigest(),archives=archives,
                original_trees={str(root):inventory(root) for root in (INITIAL,OLD)},
                scope='C complete80/67/4 and Rust interrupted137 caches only; no evidence reuse')


def prepare():
    source_record();prior=original()
    if RUN.exists():raise ValueError('Destination already exists')
    RUN.mkdir();record=dict(provenance=prior,copied={},invalidations=INVALIDATE)
    for side in ('c','rust'):
        seed=OLD/side/'builds'/('ci-mm-release-'+side);dest=RUN/side/'builds'/('ci-mm-release-'+side)
        entries=inventory(seed)
        if any(item['type']=='fifo' for item in entries.values()):raise ValueError('FIFO inside selected kernel cache')
        dest.parent.mkdir(parents=True);(RUN/side/'logs').mkdir()
        shutil.copytree(seed,dest,symlinks=True,copy_function=shutil.copy2)
        copied=inventory(dest)
        if copied!=entries:raise ValueError('Copied build cache differs')
        removed={}
        for name in INVALIDATE:
            p=dest/name
            if p.is_symlink():raise ValueError('Unexpected symlink at invalidation path')
            if p.exists():
                if not p.is_file():raise ValueError('Unexpected nonfile invalidation')
                removed[name]=copied[name];p.unlink()
        record['copied'][side]=dict(seed=str(seed),destination=str(dest),all_copied=copied,removed=removed,prepared=inventory(dest))
    if original()!=prior:raise ValueError('Original attempts changed during copy')
    (RUN/'cache-preparation.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
    verify_prepared()


def verify_original():
    record=json.loads((RUN/'cache-preparation.json').read_text())
    if original()!=record['provenance']:raise ValueError('Original trees/archives changed')
    source_record()
    return {'status':'PASS','scope':'Original001/002 trees and archives unchanged'}


def verify_prepared():
    verify_original();record=json.loads((RUN/'cache-preparation.json').read_text())
    if set(p.name for p in RUN.iterdir())!={'c','rust','cache-preparation.json'}:raise ValueError('Retry output already used')
    for side in ('c','rust'):
        if list((RUN/side/'logs').iterdir()):raise ValueError('Retry logs not empty')
        item=record['copied'][side];dest=Path(item['destination'])
        if inventory(dest)!=item['prepared']:raise ValueError('Prepared cache changed')
        if any((dest/name).exists() or (dest/name).is_symlink() for name in INVALIDATE):raise ValueError('Invalidated output survived')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    choice=parser.add_mutually_exclusive_group(required=True)
    choice.add_argument('--execute',action='store_true');choice.add_argument('--verify-original',action='store_true')
    args=parser.parse_args()
    if args.execute:prepare()
    else:print(json.dumps(verify_original(),indent=2))
