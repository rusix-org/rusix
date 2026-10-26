#!/usr/bin/env python3
"""Fail-closed post-run evidence and pair checks; no kernel or guest execution."""
import argparse
import importlib.util
import json
import re
import shlex
from pathlib import Path
import sys
from preflight import SOURCE, EXPECTED, IMAGE, RUN, digest, source_record
sys.path.insert(0, str(SOURCE/'rusix/scripts'))


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, SOURCE/'rusix/scripts'/filename)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod


selection = load('task_selection', 'verify-mm-construction.py')
guest = load('task_guest', 'test-mm-construction-vm.py')


def check(side):
    output = RUN/side; profile = 'mm-construction-'+side
    logs = output/'logs'; build = output/'builds'/('ci-'+profile)
    def resolve(name):
        p = Path(name)
        if p.is_relative_to('/src'): return SOURCE/p.relative_to('/src')
        if p.is_relative_to('/out'): return output/p.relative_to('/out')
        raise ValueError('Unrecognized proof path: '+name)
    for file in ('container.exit', 'ci.exit'):
        if (logs/file).read_text().strip() != '0': raise ValueError('Failed '+file)
    ci = (logs/'ci-inputs.log').read_text().splitlines()
    if ci[0] != EXPECTED or 'profile='+profile not in ci or 'acceleration=kvm' not in ci:
        raise ValueError('Wrong CI source/profile/acceleration')
    matches = list(logs.glob('ci-'+profile+'-build.*'))
    if len(matches) != 1: raise ValueError('Missing/ambiguous build evidence')
    proof = matches[0]
    if (proof/'build.exit').read_text().strip() != '0': raise ValueError('Build failed')
    if (proof/'environment.log').read_text().splitlines()[0] != EXPECTED or (proof/'source-after.commit').read_text().strip() != EXPECTED:
        raise ValueError('Build source identity differs')
    if (proof/'source-after.status').read_bytes(): raise ValueError('Dirty post-build source')
    if (proof/'profile.txt').read_text().strip() != profile: raise ValueError('Wrong build profile')
    if (proof/'config').read_bytes() != (build/'.config').read_bytes(): raise ValueError('Build config snapshot differs')
    for name in ('build.log', 'config.log'):
        if re.search(r'warning:|error:|objtool.*warning', (proof/name).read_text(), re.I):
            raise ValueError('Build/config diagnostics require review')
    records = {}
    for line in (proof/'build.sha256').read_text().splitlines():
        match = re.fullmatch(r'([0-9a-f]{64})  (.+)', line)
        if not match or match[2] in records: raise ValueError('Malformed/duplicate build hash record')
        records[match[2]] = match[1]
    names = {f'/out/builds/ci-{profile}/'+name for name in ('.config', 'arch/x86/boot/bzImage', 'vmlinux', 'vmlinux.map')}
    if set(records) != names: raise ValueError('Build hash inventory differs from exact four artifacts')
    for name, expected in records.items():
        if digest(resolve(name)) != expected: raise ValueError('Actual build artifact changed: '+name)
    selected = json.loads((proof/'mm-selection.json').read_text())
    container_build = Path('/out/builds')/('ci-'+profile)
    dependency_set = {str(p) for p in selection.input_paths(container_build, Path('/src'), side == 'rust')}
    if set(selected['input_sha256']) != dependency_set: raise ValueError('Selection dependency inventory differs')
    if selected['status'] != 'PASS' or selected['implementation'] != side:
        raise ValueError('Wrong selected implementation')
    for name, expected in selected['input_sha256'].items():
        if digest(resolve(name)) != expected: raise ValueError('Selection input changed: '+name)
    run = logs/('ci-'+profile+'-mm-construction.run')
    for name in ('runner.exit', 'qemu.exit', 'selection.exit', 'init-compile.exit', 'probe-compile.exit'):
        if (run/name).read_text().strip() != '0': raise ValueError('Failed '+name)
    result = json.loads((run/'result.json').read_text())
    console = guest.accept_console((run/'console.log').read_text(), 0)
    if result != console | dict(implementation=side, source_revision=EXPECTED):
        raise ValueError('Guest result differs from literal console acceptance')
    for name in ('selection.stderr', 'init-compile.log', 'probe-compile.log'):
        if re.search(r'warning:|error:', (run/name).read_text(), re.I): raise ValueError('Guest/selection diagnostics')
    if (run/'selection.stderr').read_bytes(): raise ValueError('Selection diagnostics')
    if (run/'config').read_bytes() != (build/'.config').read_bytes(): raise ValueError('Guest config differs')
    artifacts = f'/out/builds/mm-construction-vm-ci-{profile}'
    command = ['/usr/bin/timeout', '--kill-after=5s', '180s', '/usr/bin/qemu-system-x86_64',
               '-machine', 'q35', '-accel', 'kvm', '-cpu', 'qemu64', '-m', '512M', '-smp', '2',
               '-display', 'none', '-serial', 'stdio', '-monitor', 'none', '-nic', 'none', '-no-reboot',
               '-kernel', artifacts+'/bzImage', '-initrd', artifacts+'/initramfs.cpio', '-append',
               'console=ttyS0 rdinit=/init rusix.mm_construction_probe=1 panic=-1 kunit.enable=0 printk.time=0 loglevel=7']
    if shlex.split((run/'command.sh').read_text()) != command: raise ValueError('QEMU command differs from exact bounded template')
    if digest(resolve(artifacts+'/bzImage')) != digest(build/'arch/x86/boot/bzImage'):
        raise ValueError('Copied guest kernel differs from actual build')
    metadata = json.loads((run/'inputs.json').read_text())
    exact_artifacts = {artifacts+'/'+name for name in ('bzImage','init','probe','initramfs.cpio')}
    if set(metadata['artifacts']) != exact_artifacts: raise ValueError('Guest artifact inventory differs')
    sources = {'rusix/scripts/'+name for name in ('test-mm-construction-vm.py',
               'test-task-construction-vm.py','test-brd-vm.py','test-brd-ext4-vm.py',
               'verify-mm-construction.py','verify-task-construction.py',
               'rusix_paths.py','server_target.py','saved_clang_command.py',
               'preprocess-mm-construction.py','preprocess-task-construction.py','with-local-tools.sh')}
    sources.add('rusix/tests/brd-ext4/ext4-packages.lock')
    sources.update('rusix/tests/mm-construction/'+name for name in ('README.md','init.rs','probe.c'))
    if json.loads((run/'sources-before.json').read_text()) != metadata['sources']:
        raise ValueError('Precompile guest sources differ from recorded compiled inputs')
    if selected.get('task_implementation') != 'rust': raise ValueError('Task construction is not retained Rust')
    if set(metadata['sources']) != sources: raise ValueError('Guest source inventory differs')
    if (run/'container-image-id.txt').read_text().strip() != IMAGE or (logs/'container-image-id.txt').read_text().strip() != IMAGE:
        raise ValueError('Recorded image identity differs')
    if (run/'rootfs-packages.lock').read_bytes() != (SOURCE/'rusix/tests/brd-ext4/ext4-packages.lock').read_bytes():
        raise ValueError('Guest packages differ from pinned fixture')
    if (metadata['source_revision'], metadata['profile'], metadata['implementation'], metadata['container_image']) != (EXPECTED, profile, side, IMAGE):
        raise ValueError('Guest provenance differs')
    if metadata['config_sha256'] != digest(build/'.config'): raise ValueError('Guest configuration hash differs')
    for name in ('init.rs', 'probe.c'):
        if (RUN/'guest-source'/name).read_bytes() != (SOURCE/'rusix/tests/mm-construction'/name).read_bytes():
            raise ValueError('Compiled guest source snapshot differs')
    if metadata['selection'] != selected or json.loads((run/'selection.json').read_text()) != selected:
        raise ValueError('Build/runtime selection proof mismatch')
    for name, expected in metadata['sources'].items():
        if digest(SOURCE/name) != expected: raise ValueError('Guest source changed: '+name)
    for name, expected in metadata['artifacts'].items():
        if digest(resolve(name)) != expected: raise ValueError('Guest artifact changed: '+name)
    selection.check_config(profile, selection.config_values((build/'.config').read_text()),
                           selection.config_values((SOURCE/'rusix/configs/x86_64-server.config').read_text()))
    if source_record() != json.loads((RUN/'source-before.json').read_text()):
        raise ValueError('Frozen source changed')
    return metadata, build


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--side', choices=('c', 'rust')); args = ap.parse_args()
    if args.side:
        check(args.side); print(json.dumps(dict(status='PASS', side=args.side))); return
    c, cb = check('c'); r, rb = check('rust')
    differences = selection.compare(selection.config_values((cb/'.config').read_text()), selection.config_values((rb/'.config').read_text()))
    for name in ('packages.lock', 'toolchain.log', 'container-image-id.txt'):
        if (RUN/'c/logs'/name).read_bytes() != (RUN/'rust/logs'/name).read_bytes():
            raise ValueError('Pair container tools/packages differ: '+name)
    for name in ('rustc-version.log', 'gcc-version.log', 'readelf-version.log', 'qemu-version.log', 'rootfs-packages.lock', 'container-image-id.txt'):
        left = RUN/'c/logs/ci-mm-construction-c-mm-construction.run'/name
        right = RUN/'rust/logs/ci-mm-construction-rust-mm-construction.run'/name
        if not left.read_bytes() or left.read_bytes() != right.read_bytes():
            raise ValueError('Pair guest tool/image identity differs: '+name)
    if c['sources'] != r['sources']: raise ValueError('Guest source identities differ')
    for name in ('init', 'probe', 'initramfs.cpio'):
        left = [v for k,v in c['artifacts'].items() if Path(k).name == name]
        right = [v for k,v in r['artifacts'].items() if Path(k).name == name]
        if len(left) != 1 or left != right: raise ValueError('Guest binary fixture differs: '+name)
    for side in ('c', 'rust'):
        if (RUN/side/'logs/launcher.exit').read_text().strip() != '0': raise ValueError('Launcher did not complete')
    print(json.dumps(dict(status='PASS', source=EXPECTED, different_settings=differences,
                         cases=list(guest.CASES), scope='Five ordinary address-space/COW/exec/MDWE consumers; no allocation-failure coverage'), indent=2))


if __name__ == '__main__': main()
