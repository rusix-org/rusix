#!/usr/bin/env python3
"""Read-only validation of terminal retry002; never invokes LLVM, builds or guests.

Reuse its pinned checker for source/config/guest validation, substituting only
recorded-proof rehash/comparison for its mutating ELF reinspection routine.
This is prerequisite evidence validation, not a new actual ELF verification.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

BASE = Path('/home/aaron/code/rusix')
RUN = BASE/'linux-out/vma-lifecycle-verification-002'
DRAFT = BASE/'linux-out/vma-lifecycle-retry-draft'
SOURCE = BASE/'linux-vma-lifecycle'
EXPECTED = 'e0632d27293ba2e5b2eff3bc8baec405d8d4a233'
IMAGE = 'sha256:c02eb3929889b3f0cc035d57a02c844e0c74c71d24fbda1311249faeb8257f63'
PINNED = {'check-results.py':'0b7fc86cfde9125b16cd38242f56ad060d08530e96d6d9a692fad6706d5540f5',
          'preflight.py':'14ae540b99b7e5e82862ea126393d91b640191ed572264f2462cc97cc00b1e47'}


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def need(ok, message):
    if not ok:
        raise ValueError(message)


def load_json(path):
    return json.loads(path.read_text())


def validate():
    # First refusal is authoritative terminal state, before importing the checker.
    need((RUN/'matrix.exit').read_text().strip() == '0', 'Lifecycle matrix not successful')
    for name, expected in PINNED.items():
        need(digest(DRAFT/name) == expected, 'Prerequisite checker changed: '+name)
    for label in ('c','rust','pair'):
        need((RUN/(label+'-postcheck.exit')).read_text().strip() == '0', 'Lifecycle postcheck failed')
        need(not (RUN/(label+'-postcheck.stderr')).read_bytes(), 'Lifecycle postcheck diagnostics')
        need((RUN/(label+'-postcheck-image.txt')).read_text().strip() == IMAGE, 'Postcheck image differs')
        versions = load_json(RUN/('postcheck-tools-'+label+'.json'))
        need(set(versions) == {'llvm-ar','llvm-nm','llvm-objdump','llvm-readobj'}, 'Postcheck tool inventory differs')
        need(all(re.search(r'(?:LLVM|Debian LLVM) version 19\.', v) for v in versions.values()), 'Postcheck LLVM version differs')
    need((RUN/'source-before.json').read_bytes() == (RUN/'source-after.json').read_bytes(), 'Lifecycle source changed')
    need((RUN/'prerequisite-before.json').read_bytes() == (RUN/'prerequisite-after.json').read_bytes(), 'Lifecycle baseline prerequisite changed')
    snapshot = load_json(RUN/'source-before.json')
    need(snapshot['source'] == EXPECTED and snapshot['image'] == IMAGE, 'Wrong lifecycle source/image')
    for name, sha in snapshot['input_sha256'].items():
        need(digest(SOURCE/name) == sha, 'Lifecycle source hash changed: '+name)
    launch = {}
    for line in (RUN/'launcher.sha256').read_text().splitlines():
        match = re.fullmatch(r'([0-9a-f]{64})  (.+)', line)
        need(match and match[2] not in launch, 'Malformed lifecycle launcher inventory')
        launch[match[2]] = match[1]
        need(digest(Path(match[2])) == match[1], 'Lifecycle launcher hash changed')
    need(set(launch) == {str(DRAFT/n) for n in ('run.sh','preflight.py','check-results.py','README')}, 'Lifecycle launcher inventory differs')
    sys.path.insert(0,str(DRAFT))
    spec = importlib.util.spec_from_file_location('lifecycle_retry_checker',DRAFT/'check-results.py')
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    need((checker.SOURCE,checker.EXPECTED,checker.RUN,checker.IMAGE)==(SOURCE,EXPECTED,RUN,IMAGE), 'Imported checker endpoints differ')
    proof_records = {}

    def recorded_reinspection(side, build, proof, selected, resolve):
        cb = Path('/out/builds')/('ci-vma-lifecycle-'+side)
        preprocess = []
        for parser, prefix, unit in ((checker.selection.dup.copy.preprocessor, 'mm-copy', 'kernel/fork'),
                                     (checker.selection.dup.preprocessor, 'dup-mmap', 'mm/mmap'),
                                     (checker.selection.preprocessor, 'vma-lifecycle', 'mm/vma_init')):
            cmd = build/Path(unit).parent/('.'+Path(unit).name+'.o.cmd')
            output = build/(unit+'.i')
            co = cb/(unit+'.i')
            original = dict(argv=parser.command(cmd.read_text(),co),cwd=str(cb),
                            input_sha256={str(p):digest(resolve(str(p))) for p in parser.inputs(cb,Path('/src'))},
                            output=str(co),preprocessed_sha256=digest(output))
            need(load_json(proof/(prefix+'-preprocess.json')) == original, 'Original preprocessing provenance differs')
            need((proof/(prefix+'-preprocess.exit')).read_text().strip() == '0', 'Original preprocessing failed')
            need(not re.search('warning:|error:',(proof/(prefix+'-preprocess.log')).read_text(),re.I), 'Original preprocessing diagnostics')
            remapped = dict(argv=parser.command(cmd.read_text(),output),cwd=str(build),
                            input_sha256={str(p):digest(p) for p in parser.inputs(build,SOURCE)},
                            output=str(output),preprocessed_sha256=digest(output))
            preprocess.append((prefix,remapped))
        need(load_json(proof/'vma-lifecycle-dup-selection.json') == selected['dup_mmap_selection'], 'Saved inherited dup proof differs')
        need(load_json(proof/'dup-mmap-mm-copy-selection.json') == selected['dup_mmap_selection']['mm_copy_selection'], 'Saved inherited MM-copy proof differs')
        def normalize(record):
            for field in ('input_sha256','archive_member_sha256'):
                normalized = {}
                for name, sha in record[field].items():
                    path = Path(name)
                    need(path.is_absolute() and '..' not in path.parts, 'Noncanonical actual proof path')
                    need(path.is_relative_to(SOURCE) or path.is_relative_to(RUN/side), 'Unrecognized actual proof path')
                    need(digest(path) == sha, 'Recorded actual proof input changed: '+name)
                    target = str(Path('/src')/path.relative_to(SOURCE)) if path.is_relative_to(SOURCE) else str(Path('/out')/path.relative_to(RUN/side))
                    need(target not in normalized, 'Proof normalization collision')
                    normalized[target] = sha
                record[field] = normalized
            for child in ('dup_mmap_selection','mm_copy_selection'):
                if child in record:
                    normalize(record[child])
        for label in (side,'pair'):
            directory = RUN/('postcheck-reinspection-'+label+'-'+side)
            for prefix, remapped in preprocess:
                need(load_json(directory/(prefix+'-preprocess.json')) == remapped, 'Recorded remapped preprocessing differs')
                for suffix in ('.exit','.log'):
                    need((directory/(prefix+'-preprocess'+suffix)).read_bytes() == (proof/(prefix+'-preprocess'+suffix)).read_bytes(), 'Recorded preprocessing exit/log differs')
            actual = load_json(directory/'actual-selection.json')
            normalize(actual)
            need(actual == selected, 'Recorded actual ELF proof differs from build proof')
            for path in directory.rglob('*'):
                if path.is_file():
                    proof_records[str(path)] = digest(path)
    checker.reinspection = recorded_reinspection
    metadata = {}; builds = {}
    for side in ('c','rust'):
        need(load_json(RUN/side/'logs/postchecks.json') == {'status':'PASS','side':side}, 'Per-side postcheck result differs')
        need((RUN/side/'logs/launcher.exit').read_text().strip() == '0', 'Per-side launcher failed')
        metadata[side],builds[side] = checker.check(side)
    differences = checker.selection.compare(checker.selection.config_values((builds['c']/'.config').read_text()),checker.selection.config_values((builds['rust']/'.config').read_text()))
    expected = dict(status='PASS',source=EXPECTED,different_settings=differences,cases=list(checker.CASES),scope='Nine ordinary sharing/COW/VMA inheritance, split/restore and forced movement consumers; no allocation-failure coverage')
    need(load_json(RUN/'pair-result.json') == expected, 'Lifecycle pair result differs from exact schema')
    need(metadata['c']['sources'] == metadata['rust']['sources'], 'Lifecycle guest sources differ')
    for name in ('init','probe','initramfs.cpio'):
        left=[v for k,v in metadata['c']['artifacts'].items() if Path(k).name==name]
        right=[v for k,v in metadata['rust']['artifacts'].items() if Path(k).name==name]
        need(len(left)==1 and left==right, 'Lifecycle fixture binaries differ')
    for name in ('packages.lock','toolchain.log','container-image-id.txt'):
        need((RUN/'c/logs'/name).read_bytes() == (RUN/'rust/logs'/name).read_bytes(), 'Lifecycle build tools differ')
    for name in ('rustc-version.log','gcc-version.log','readelf-version.log','qemu-version.log','rootfs-packages.lock','container-image-id.txt'):
        c=RUN/'c/logs/ci-vma-lifecycle-c-vma-lifecycle.run'/name
        r=RUN/'rust/logs/ci-vma-lifecycle-rust-vma-lifecycle.run'/name
        need(c.read_bytes() and c.read_bytes()==r.read_bytes(), 'Lifecycle guest tools differ')
    records={str(p):digest(p) for p in RUN.iterdir() if p.is_file() and p.suffix != '.cid'}
    records.update(proof_records)
    for side in ('c','rust'):
        logs=RUN/side/'logs'
        for p in logs.rglob('*'):
            if p.is_file() and p.suffix != '.cid':records[str(p)]=digest(p)
    return dict(status='PASS',source=EXPECTED,run=str(RUN),pair=expected,record_sha256=records,
                source_sha256=snapshot['input_sha256'],config_sha256={s:digest(b/'.config') for s,b in builds.items()},
                artifacts={s:metadata[s]['artifacts'] for s in ('c','rust')},
                checker_sha256=PINNED,scope='Terminal lifecycle prerequisite rehash and recorded actual proof comparison; no new ELF invocation or kernel/VM')


if __name__ == '__main__':
    print(json.dumps(validate(),indent=2,sort_keys=True))
