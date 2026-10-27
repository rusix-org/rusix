#!/usr/bin/env python3
"""Fail-closed post-run evidence and pair checks; no kernel or guest execution."""
import argparse
import os
import shutil
import subprocess
from types import SimpleNamespace
import importlib.util
import json
import re
import shlex
from pathlib import Path
import sys
from preflight import SOURCE, EXPECTED, IMAGE, RUN, DRAFT, digest, source_record
sys.path.insert(0, str(SOURCE/'rusix/scripts'))


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, SOURCE/'rusix/scripts'/filename)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod


selection = load('task_selection', 'verify-dup-mmap.py')
guest = load('task_guest', 'test-mm-dup-mmap-vm.py')
CASES = ('shared_clone_write_and_exit', 'shared_clone_exec_detaches_mm', 'private_fork_cow',
         'dontfork_omits_only_advised_range', 'wipeonfork_clears_child_and_grandchild',
         'private_file_mapping_cow_and_lifetime', 'shared_file_mapping_survives_parent_unmap')
if tuple(guest.CASES) != CASES:
    raise ValueError('Guest literal case inventory changed')
CHECK_LABEL = 'unset'


def constant_proof(selected, side):
    expected = ({'rusix_dup_dontcopy': 1 << 17, 'rusix_dup_account': 1 << 20,
                 'rusix_dup_wipeonfork': 1 << 25} if side == 'rust' else {})
    if selected.get('constant_values') != expected:
        raise ValueError('Native constant storage/value proof differs')
    for name in ('verify-brd-parameter-owner.py', 'measure-kernel-languages.py'):
        path = '/src/rusix/scripts/' + name
        if selected['input_sha256'].get(path) != digest(SOURCE/'rusix/scripts'/name):
            raise ValueError('Missing/changed indexed ELF reader dependency: '+name)


def reinspection(side, build, proof, selected, resolve):
    """Validate recorded container identities, then rerun actual ELF proof.

    The second proof has explicit host-remapped identities in a new directory;
    original build evidence is never rewritten or represented as that recheck.
    """
    cb = Path('/out/builds')/('ci-mm-dup-mmap-'+side)
    directory = RUN/('postcheck-reinspection-'+CHECK_LABEL+'-'+side)
    directory.mkdir()
    for pre, prefix, unit in ((selection.copy.preprocessor, 'mm-copy', 'kernel/fork'),
                              (selection.preprocessor, 'dup-mmap', 'mm/mmap')):
        cmd = build/Path(unit).parent/('.'+Path(unit).name+'.o.cmd')
        output = build/(unit+'.i')
        container_output = cb/(unit+'.i')
        original = dict(argv=pre.command(cmd.read_text(),container_output),cwd=str(cb),
                        input_sha256={str(p):digest(resolve(str(p))) for p in pre.inputs(cb,Path('/src'))},
                        output=str(container_output),preprocessed_sha256=digest(output))
        if json.loads((proof/(prefix+'-preprocess.json')).read_text()) != original:
            raise ValueError('Recorded '+prefix+' preprocessing provenance differs')
        if (proof/(prefix+'-preprocess.exit')).read_text().strip() != '0' or re.search(
                'warning:|error:',(proof/(prefix+'-preprocess.log')).read_text(),re.I):
            raise ValueError('Original preprocessing failed or emitted diagnostics')
        for suffix in ('.exit','.log'):
            shutil.copyfile(proof/(prefix+'-preprocess'+suffix),directory/(prefix+'-preprocess'+suffix))
        remapped = dict(argv=pre.command(cmd.read_text(),output),cwd=str(build),
                        input_sha256={str(p):digest(p) for p in pre.inputs(build,SOURCE)},
                        output=str(output),preprocessed_sha256=digest(output))
        (directory/(prefix+'-preprocess.json')).write_text(json.dumps(remapped,indent=2)+'\n')
    if json.loads((proof/'dup-mmap-mm-copy-selection.json').read_text()) != selected['mm_copy_selection']:
        raise ValueError('Saved inherited MM-copy proof differs')
    actual = selection.verify(SimpleNamespace(source=SOURCE,build=build,evidence=directory,profile='mm-dup-mmap-'+side))
    (directory/'actual-selection.json').write_text(json.dumps(actual,indent=2)+'\n')
    def container_path(name):
        p=Path(name)
        if not p.is_absolute() or '..' in p.parts:
            raise ValueError('Noncanonical verification path')
        for host,old in ((SOURCE,Path('/src')),(RUN/side,Path('/out'))):
            if p.is_relative_to(host):return str(old/p.relative_to(host))
        raise ValueError('Unknown actual verification path: '+name)
    def normalize(record):
        # Normalize only hash-map keys whose meanings are recorded input/member
        # paths, including the nested original MM-copy proof. All values,
        # implementation labels, callback identities and scope remain exact.
        for key in ('input_sha256','archive_member_sha256'):
            mapped = {container_path(k):v for k,v in record[key].items()}
            if len(mapped) != len(record[key]):
                raise ValueError('Path remapping collision')
            record[key] = mapped
        if 'mm_copy_selection' in record:
            normalize(record['mm_copy_selection'])
    normalize(actual)
    if actual != selected:
        raise ValueError('Actual remapped ELF selection differs from recorded proof')


def check(side):
    output = RUN/side; profile = 'mm-dup-mmap-'+side
    logs = output/'logs'; build = output/'builds'/('ci-'+profile)
    def resolve(name):
        p = Path(name)
        if not p.is_absolute() or '..' in p.parts:
            raise ValueError('Noncanonical proof path')
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
    selected = json.loads((proof/'dup-mmap-selection.json').read_text())
    constant_proof(selected, side)
    container_build = Path('/out/builds')/('ci-'+profile)
    dependency_set = {str(p) for p in selection.input_paths(container_build, Path('/src'), side == 'rust')}
    if set(selected['input_sha256']) != dependency_set: raise ValueError('Selection dependency inventory differs')
    if selected['status'] != 'PASS' or selected['implementation'] != side:
        raise ValueError('Wrong selected implementation')
    for name, expected in selected['input_sha256'].items():
        if digest(resolve(name)) != expected: raise ValueError('Selection input changed: '+name)
    for name, implementation in (('selection.log','brd-rust'),('completion-selection.log','completion-rust'),('swait-selection.log','swait-rust'),('wake-selection.log','wake-rust'),('wait-bit-selection.log','wait-bit-rust')):
        text = (proof/name).read_text()
        if text.splitlines()[0] != 'implementation='+implementation:
            raise ValueError('Inherited Rust selection differs: '+name)
        hashes = {}
        for value, path in re.findall(r'^([0-9a-f]{64})  (.+)$', text, re.M):
            if path in hashes or digest(resolve(path)) != value:
                raise ValueError('Inherited selection artifact changed: '+path)
            hashes[path] = value
        if not hashes:
            raise ValueError('Inherited selection hashes missing')
    if (proof/'brd-reference.diff').read_bytes():
        raise ValueError('Pristine reference C BRD differs')
    reinspection(side, build, proof, selected, resolve)
    run = logs/('ci-'+profile+'-mm-dup-mmap.run')
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
    artifacts = f'/out/builds/mm-dup-mmap-vm-ci-{profile}'
    command = ['/usr/bin/timeout', '--kill-after=5s', '180s', '/usr/bin/qemu-system-x86_64',
               '-machine', 'q35', '-accel', 'kvm', '-cpu', 'qemu64', '-m', '512M', '-smp', '2',
               '-display', 'none', '-serial', 'stdio', '-monitor', 'none', '-nic', 'none', '-no-reboot',
               '-kernel', artifacts+'/bzImage', '-initrd', artifacts+'/initramfs.cpio', '-append',
               'console=ttyS0 rdinit=/init rusix.mm_dup_mmap_probe=1 panic=-1 kunit.enable=0 printk.time=0 loglevel=7']
    if shlex.split((run/'command.sh').read_text()) != command: raise ValueError('QEMU command differs from exact bounded template')
    if digest(resolve(artifacts+'/bzImage')) != digest(build/'arch/x86/boot/bzImage'):
        raise ValueError('Copied guest kernel differs from actual build')
    metadata = json.loads((run/'inputs.json').read_text())
    exact_artifacts = {artifacts+'/'+name for name in ('bzImage','init','probe','initramfs.cpio')}
    if set(metadata['artifacts']) != exact_artifacts: raise ValueError('Guest artifact inventory differs')
    sources = {'rusix/scripts/'+name for name in ('test-mm-dup-mmap-vm.py',
               'test-task-construction-vm.py','test-brd-vm.py','test-brd-ext4-vm.py',
               'verify-dup-mmap.py','verify-mm-copy.py','verify-task-construction.py',
               'verify-mm-release.py','verify-mm-construction.py',
               'rusix_paths.py','server_target.py','saved_clang_command.py',
               'preprocess-dup-mmap.py','preprocess-mm-copy.py','preprocess-mm-release.py','preprocess-mm-construction.py',
               'preprocess-task-construction.py','with-local-tools.sh')}
    sources.add('rusix/tests/brd-ext4/ext4-packages.lock')
    sources.update('rusix/tests/mm-dup-mmap/'+name for name in ('README.md','init.rs','probe.c'))
    if json.loads((run/'sources-before.json').read_text()) != metadata['sources']:
        raise ValueError('Precompile guest sources differ from recorded compiled inputs')
    if selected['mm_copy_selection'].get('status') != 'PASS' or selected['mm_copy_selection'].get('implementation') != 'rust':
        raise ValueError('Required inherited Rust MM-copy selection differs')
    if any(selected['mm_copy_selection'].get(key) != 'rust' for key in ('task_implementation','mm_construction_implementation','mm_release_implementation')):
        raise ValueError('Required Rust task/construction/release selection differs')
    if set(metadata['sources']) != sources: raise ValueError('Guest source inventory differs')
    if (run/'container-image-id.txt').read_text().strip() != IMAGE or (logs/'container-image-id.txt').read_text().strip() != IMAGE:
        raise ValueError('Recorded image identity differs')
    if (run/'rootfs-packages.lock').read_bytes() != (SOURCE/'rusix/tests/brd-ext4/ext4-packages.lock').read_bytes():
        raise ValueError('Guest packages differ from pinned fixture')
    if (metadata['source_revision'], metadata['profile'], metadata['implementation'], metadata['container_image']) != (EXPECTED, profile, side, IMAGE):
        raise ValueError('Guest provenance differs')
    if metadata['config_sha256'] != digest(build/'.config'): raise ValueError('Guest configuration hash differs')
    for name in ('init.rs', 'probe.c'):
        if (RUN/'guest-source'/name).read_bytes() != (SOURCE/'rusix/tests/mm-dup-mmap'/name).read_bytes():
            raise ValueError('Compiled guest source snapshot differs')
    if metadata['selection'] != selected or json.loads((run/'selection.json').read_text()) != selected:
        raise ValueError('Build/runtime selection proof mismatch')
    for name, expected in metadata['sources'].items():
        if digest(SOURCE/name) != expected: raise ValueError('Guest source changed: '+name)
    for name, expected in metadata['artifacts'].items():
        if digest(resolve(name)) != expected: raise ValueError('Guest artifact changed: '+name)
    selection.check_config(profile, selection.config_values((build/'.config').read_text()),
                           selection.config_values((SOURCE/'rusix/configs/x86_64-server.config').read_text()))
    if source_record() != json.loads((logs/'source-before.json').read_text()):
        raise ValueError('Per-side frozen source snapshot differs')
    if source_record() != json.loads((RUN/'source-before.json').read_text()):
        raise ValueError('Frozen source changed')
    return metadata, build


def main():
    global CHECK_LABEL
    ap = argparse.ArgumentParser(); ap.add_argument('--side', choices=('c', 'rust')); args = ap.parse_args()
    CHECK_LABEL = args.side or 'pair'
    if os.environ.get('RUSIX_PINNED_POSTCHECK_IMAGE') != IMAGE:
        raise ValueError('Postchecks require exact pinned image, not host LLVM')
    for side in ([args.side] if args.side else ['c', 'rust']):
        for name in ('packages.lock', 'toolchain.log'):
            if (Path('/opt/rusix')/name).read_bytes() != (RUN/side/'logs'/name).read_bytes():
                raise ValueError('Pinned postcheck package/tool identity differs')
    tools = {}
    for name in ('llvm-ar','llvm-nm','llvm-objdump','llvm-readobj'):
        result = subprocess.run([name, '--version'], check=True, capture_output=True, text=True)
        if result.stderr or not re.search(r'(?:LLVM|Debian LLVM) version 19\.', result.stdout):
            raise ValueError('Expected diagnostic-free pinned LLVM19: '+name)
        tools[name] = result.stdout
    with (RUN/('postcheck-tools-'+CHECK_LABEL+'.json')).open('x') as f:
        json.dump(tools, f, indent=2)
    launcher_hashes = {}
    for line in (RUN/'launcher.sha256').read_text().splitlines():
        match = re.fullmatch(r'([0-9a-f]{64})  (.+)', line)
        if not match or match[2] in launcher_hashes or digest(Path(match[2])) != match[1]:
            raise ValueError('Launcher changed before postcheck')
        launcher_hashes[match[2]] = match[1]
    if set(launcher_hashes) != {str(DRAFT/n) for n in ('run.sh','preflight.py','check-results.py','README')}:
        raise ValueError('Launcher dependency inventory differs')
    if not args.side:
        for side in ('c','rust'):
            if (RUN/(side+'-postcheck.exit')).read_text().strip() != '0' or (RUN/(side+'-postcheck.stderr')).read_bytes():
                raise ValueError('Pinned per-side postcheck did not pass')
    if args.side:
        check(args.side); print(json.dumps(dict(status='PASS', side=args.side))); return
    c, cb = check('c'); r, rb = check('rust')
    differences = selection.compare(selection.config_values((cb/'.config').read_text()), selection.config_values((rb/'.config').read_text()))
    for name in ('packages.lock', 'toolchain.log', 'container-image-id.txt'):
        if (RUN/'c/logs'/name).read_bytes() != (RUN/'rust/logs'/name).read_bytes():
            raise ValueError('Pair container tools/packages differ: '+name)
    for name in ('rustc-version.log', 'gcc-version.log', 'readelf-version.log', 'qemu-version.log', 'rootfs-packages.lock', 'container-image-id.txt'):
        left = RUN/'c/logs/ci-mm-dup-mmap-c-mm-dup-mmap.run'/name
        right = RUN/'rust/logs/ci-mm-dup-mmap-rust-mm-dup-mmap.run'/name
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
                         cases=list(CASES), scope='Seven ordinary sharing/COW/VMA inheritance/file-lifetime consumers; no allocation-failure coverage'), indent=2))


if __name__ == '__main__': main()
