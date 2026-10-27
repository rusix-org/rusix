#!/usr/bin/env python3
"""Audit and archive static-only guest compilation; never run guest binaries."""
import hashlib
import json
from pathlib import Path
import shutil
import stat
import subprocess

BASE = Path('/home/aaron/code/rusix')
RAW = BASE/'linux-out/copy-vma-fixtures-001'
SOURCE = BASE/'linux-mm-copy-vma'
DEST = SOURCE/'rusix/docs/evidence/copy-vma-fixtures'
SCRATCH = BASE/'linux-out/copy-vma-fixtures-evidence'

def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def need(value, message):
    if not value:
        raise ValueError(message)

r = json.loads((RAW/'result.json').read_text())
need(r['status'] == 'PASS', 'Compile result failed')
for name, sha in r['record_sha256'].items():
    need(digest(RAW/name) == sha, 'Retained record drift: '+name)
inputs = json.loads((RAW/'inputs.json').read_text())
need(inputs['sha256'] == r['source_sha256'] == json.loads((RAW/'inputs-after.json').read_text()), 'Input inventories disagree')
for name, sha in inputs['sha256'].items():
    need(digest(RAW/'source'/name) == sha, 'Frozen source drift')
    need(digest(SOURCE/name) == sha, 'Working fixture changed before checkpoint')
upstream = json.loads((RAW/'source/rusix/tests/copy-vma/upstream.json').read_text())
for name, record in upstream['files'].items():
    original = subprocess.check_output(['git', '-C', str(SOURCE), 'show', upstream['baseline']+':'+name])
    need(hashlib.sha256(original).hexdigest() == record['sha256'] == digest(RAW/'source'/name), 'Native baseline mismatch')
container = json.loads((RAW/'container-inspect.json').read_text())[0]
host = container['HostConfig']
need(container['Image'] == r['image'] and container['State']['ExitCode'] == 0 and not container['State']['OOMKilled'], 'Container identity/status differs')
need(host['NanoCpus'] == 1000000000 and host['Memory'] == host['MemorySwap'] == 1073741824, 'Resource limits differ')
need(host['NetworkMode'] == 'none' and host['CapDrop'] == ['ALL'] and not host['Devices'] and host['ReadonlyRootfs'], 'Isolation differs')
need((RAW/'container.exit').read_text().strip() == '0', 'Launcher failure')
artifacts = {}
for name in ('init', 'probe'):
    path = RAW/'artifacts'/name
    need(digest(path) == r['artifacts'][name]['sha256'] and path.stat().st_size == r['artifacts'][name]['bytes'], 'Binary changed')
    need(stat.S_IMODE(path.stat().st_mode) == 0o644, 'Binary executable mode')
    for kind in ('compile', 'readelf'):
        need((RAW/'evidence'/f'{name}-{kind}.exit').read_text().strip() == '0', 'Compiler/ELF inspector failure')
    need(not (RAW/'evidence'/f'{name}-compile.log').read_bytes() and not (RAW/'evidence'/f'{name}-readelf.stderr').read_bytes(), 'Diagnostics')
    elf = (RAW/'evidence'/f'{name}-readelf.log').read_text()
    need('ELF64' in elf and 'Advanced Micro Devices X86-64' in elf and 'INTERP' not in elf and '(NEEDED)' not in elf, 'Not a static x86-64 ELF')
    artifacts[str(path)] = r['artifacts'][name]
need('Ran 13 tests' in (RAW/'host-tests.log').read_text() and '\nOK\n' in (RAW/'host-tests.log').read_text(), 'Host test inventory differs')
need(not DEST.exists() and not SCRATCH.exists(), 'Archive destination already exists')
SCRATCH.mkdir()
for name in [*r['record_sha256'], 'result.json']:
    target = SCRATCH/'records'/name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(RAW/name, target)
shutil.copyfile(__file__, SCRATCH/'archive-script.py')
files = {str(p.relative_to(SCRATCH)): digest(p) for p in SCRATCH.rglob('*') if p.is_file()}
manifest = dict(status='PASS', source_head=inputs['source_head'], fixture_state='Uncommitted fixture snapshot, exact hashes in records/inputs.json',
                baseline=upstream['baseline'], image=r['image'], files=files,
                retained_binary_sha256=artifacts, raw_result_sha256=digest(RAW/'result.json'),
                scope='13 synthetic parser tests; static compilation and ELF inspection of PID1 and unchanged upstream five-case test. Neither guest binary executed; no kernel build, VM, rollback or Rust-selection evidence.')
(SCRATCH/'manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True)+'\n')
shutil.copytree(SCRATCH, DEST)
for tree in (SCRATCH, DEST):
    for name, sha in files.items():
        need(digest(tree/name) == sha, 'Archive copy hash mismatch')
need(digest(SCRATCH/'manifest.json') == digest(DEST/'manifest.json'), 'Manifest copy mismatch')
print(json.dumps(dict(status='PASS', records=len(files), binary_artifacts=len(artifacts), manifest_sha256=digest(DEST/'manifest.json')), indent=2))
