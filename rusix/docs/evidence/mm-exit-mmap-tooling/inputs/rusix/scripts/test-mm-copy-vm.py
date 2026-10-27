#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Compile static guest fixtures and run MM contracts only in bounded KVM."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
from rusix_paths import resolve_paths


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


task_runner = load('mm_shared_task_runner', 'test-task-construction-vm.py')
common = task_runner.common
fixture_tools = task_runner.fixture_tools
selection = load('mm_selection', 'verify-mm-copy.py')
CASES = ('shared_clone_write_and_exit', 'shared_clone_exec_detaches_mm', 'private_fork_cow')
TOKEN = 'rusix.mm_copy_probe=1'
REQUIRED_CONFIG = ('64BIT', 'MMU', 'PROC_FS', 'SMP', 'MULTIUSER', 'BINFMT_ELF',
                   'BLK_DEV_INITRD', 'SERIAL_8250_CONSOLE')
static_elf = task_runner.static_elf
make_initramfs = task_runner.make_initramfs
compile_guest = task_runner.compile_guest


def accept_console(console, qemu_exit):
    if qemu_exit != 0:
        raise ValueError(f'QEMU failed or timed out: {qemu_exit}')
    if re.search(r'(?i:\bwarning\b)|\bBUG\b|Oops:|Kernel panic|CPU feature dependency check failure|ACPI (?:BIOS )?(?:Error|Exception|Warning)|ACPI: Unable to load', console):
        raise ValueError('Kernel diagnostics in guest console')
    expected = [f'RUSIX_MM_COPY_CASE {name} PASS' for name in CASES]
    expected += ['RUSIX_MM_COPY_PASS']
    markers = [line for line in console.splitlines() if 'RUSIX_MM_COPY_' in line]
    if markers != expected:
        raise ValueError(f'MM-copy case inventory/order mismatch: {markers!r}')
    return {'status': 'PASS', 'cases': list(CASES), 'qemu_exit': qemu_exit}


def validate_config(profile, config, target):
    values = selection.config_values(config)
    selection.check_config(profile, values, selection.config_values(target))
    for name in REQUIRED_CONFIG:
        if values.get('CONFIG_' + name) != 'y':
            raise ValueError('Missing guest requirement: ' + name)
    return 'rust' if selection.PROFILES[profile] else 'c'


def verify_source_hashes(source, hashes):
    for path, digest in hashes.items():
        if common.digest(source / path) != digest:
            raise ValueError('Fixture/tool source changed: ' + path)


def run(args, paths, evidence):
    revision = common.source_state(paths.source)
    if os.environ.get('RUSIX_QEMU_ACCEL') != 'kvm':
        raise ValueError('MM copy verification requires RUSIX_QEMU_ACCEL=kvm')
    image_id = fixture_tools.fixture_identity(evidence, paths.project / 'tests/brd-ext4/ext4-packages.lock')
    build, proof = args.build.resolve(), args.build_evidence.resolve()
    kernel, config = build / 'arch/x86/boot/bzImage', build / '.config'
    if (proof / 'build.exit').read_text().strip() != '0':
        raise ValueError('Kernel build did not pass')
    if common.first_line(proof / 'environment.log') != revision or common.first_line(proof / 'source-after.commit') != revision:
        raise ValueError('Kernel source identity differs')
    if (proof / 'source-after.status').read_bytes():
        raise ValueError('Kernel source was dirty after build')
    if re.search(r'warning:|error:|objtool.*warning', (proof / 'build.log').read_text(), re.I):
        raise ValueError('Kernel build diagnostics require review')
    profile = common.first_line(proof / 'profile.txt')
    implementation = validate_config(profile, config.read_text(),
                                      (paths.project / 'configs/x86_64-server.config').read_text())
    common.check_hashes(proof / 'build.sha256', [kernel, config, build / 'vmlinux'])
    if config.read_bytes() != (proof / 'config').read_bytes():
        raise ValueError('Resolved config differs from recorded build')
    artifacts = paths.output / 'builds' / f'mm-copy-vm-{args.label}'
    artifacts.mkdir(parents=True, exist_ok=False)
    shutil.copytree(proof, evidence / 'kernel-build')
    shutil.copy2(config, evidence / 'config')
    image = artifacts / 'bzImage'
    shutil.copy2(kernel, image)
    if common.digest(image) != common.digest(kernel):
        raise ValueError('Kernel changed while copying')
    wrapper = ['bash', str(paths.project / 'scripts/with-local-tools.sh')]
    # Recheck actual object/preprocessor evidence into our copied proof, never
    # overwrite the original build record. No compiler runs in this verifier.
    command = wrapper + ['python3', str(paths.project / 'scripts/verify-mm-copy.py'),
                         'objects', '--profile', profile, '--source', str(paths.source),
                         '--build', str(build), '--evidence', str(evidence / 'kernel-build')]
    (evidence / 'selection-command.sh').write_text(shlex.join(command) + '\n')
    checked = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    (evidence / 'selection.exit').write_text(f'{checked.returncode}\n')
    (evidence / 'selection.stderr').write_text(checked.stderr)
    (evidence / 'selection.json').write_text(checked.stdout)
    checked.check_returncode()
    if checked.stderr:
        raise ValueError('Selection verifier emitted diagnostics')
    selected = json.loads(checked.stdout)
    if selected != json.loads((proof / 'mm-copy-selection.json').read_text()) or selected.get('status') != 'PASS' or selected.get('implementation') != implementation:
        raise ValueError('Actual MM-copy selection differs from build proof')
    fixture = paths.project / 'tests/mm-copy'
    init, probe = artifacts / 'init', artifacts / 'probe'
    sources = {Path(__file__).resolve(), Path(common.__file__), Path(fixture_tools.__file__),
               Path(selection.__file__), Path(task_runner.__file__),
               paths.project / 'scripts/verify-task-construction.py',
               paths.project / 'scripts/preprocess-task-construction.py',
               paths.project / 'scripts/rusix_paths.py',
               paths.project / 'scripts/server_target.py', paths.project / 'scripts/saved_clang_command.py',
               paths.project / 'scripts/preprocess-mm-copy.py',
               paths.project / 'scripts/preprocess-mm-release.py',
               paths.project / 'scripts/preprocess-mm-construction.py',
               paths.project / 'scripts/verify-mm-release.py',
               paths.project / 'scripts/verify-mm-construction.py',
               paths.project / 'scripts/with-local-tools.sh',
               paths.project / 'tests/brd-ext4/ext4-packages.lock'}
    sources.update(path for path in fixture.iterdir() if path.is_file())
    source_hashes = {str(path.relative_to(paths.source)): common.digest(path) for path in sorted(sources)}
    (evidence / 'sources-before.json').write_text(json.dumps(source_hashes, indent=2, sort_keys=True) + '\n')
    for name, command in (('rustc', ['/usr/bin/rustc', '--version', '--verbose']),
                          ('gcc', ['/usr/bin/gcc', '--version']),
                          ('readelf', ['/usr/bin/readelf', '--version']),
                          ('qemu', ['/usr/bin/qemu-system-x86_64', '--version'])):
        (evidence / f'{name}-version.log').write_text(subprocess.check_output(command, text=True))
    compile_guest('init', ['/usr/bin/rustc', '--edition', '2021', '--target', 'x86_64-unknown-linux-gnu',
                          '-C', 'target-feature=+crt-static', '-C', 'panic=abort', '-C', 'opt-level=2',
                          str(fixture / 'init.rs'), '-o', str(init)], init, evidence)
    compile_guest('probe', ['/usr/bin/gcc', '-std=gnu11', '-O2', '-Wall', '-Wextra', '-Werror',
                           '-static', str(fixture / 'probe.c'), '-o', str(probe)], probe, evidence)
    verify_source_hashes(paths.source, source_hashes)
    if common.source_state(paths.source) != revision:
        raise ValueError('Source changed during guest compilation')
    archive = artifacts / 'initramfs.cpio'
    archive.write_bytes(make_initramfs(init.read_bytes(), probe.read_bytes()))
    metadata = {'source_revision': revision, 'profile': profile, 'implementation': implementation,
                'container_image': image_id, 'config_sha256': common.digest(config),
                'sources': source_hashes,
                'selection': selected,
                'artifacts': {str(path): common.digest(path) for path in (image, init, probe, archive)}}
    (evidence / 'inputs.json').write_text(json.dumps(metadata, indent=2, sort_keys=True) + '\n')
    command = ['/usr/bin/timeout', '--kill-after=5s', '180s', '/usr/bin/qemu-system-x86_64',
               '-machine', 'q35', '-accel', 'kvm', '-cpu', 'qemu64', '-m', '512M', '-smp', '2',
               '-display', 'none', '-serial', 'stdio', '-monitor', 'none', '-nic', 'none', '-no-reboot',
               '-kernel', str(image), '-initrd', str(archive), '-append',
               f'console=ttyS0 rdinit=/init {TOKEN} panic=-1 kunit.enable=0 printk.time=0 loglevel=7']
    (evidence / 'command.sh').write_text(shlex.join(command) + '\n')
    with (evidence / 'console.log').open('wb') as log:
        guest = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
    (evidence / 'qemu.exit').write_text(f'{guest.returncode}\n')
    result = accept_console((evidence / 'console.log').read_text(errors='replace'), guest.returncode)
    if common.source_state(paths.source) != revision:
        raise ValueError('Source changed during verification')
    verify_source_hashes(paths.source, source_hashes)
    for path, digest in metadata['artifacts'].items():
        if common.digest(Path(path)) != digest:
            raise ValueError('Guest artifact changed')
    for path, digest in selected['input_sha256'].items():
        if common.digest(Path(path)) != digest:
            raise ValueError('Selection artifact changed')
    common.check_hashes(proof / 'build.sha256', [kernel, config, build / 'vmlinux'])
    result.update(implementation=implementation, source_revision=revision)
    (evidence / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(f'MM copy {implementation}: three cases passed; evidence {evidence}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('build', type=Path)
    parser.add_argument('label')
    parser.add_argument('--build-evidence', type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'[a-zA-Z0-9_-]+', args.label):
        parser.error('Use only letters, numbers, underscore and hyphen in labels')
    paths = resolve_paths()
    evidence = paths.output / 'logs' / f'{args.label}-mm-copy.run'
    evidence.parent.mkdir(parents=True, exist_ok=True)
    try:
        evidence.mkdir()
    except FileExistsError:
        parser.error('Evidence label already used')
    status = 1
    try:
        run(args, paths, evidence)
        status = 0
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        (evidence / 'error.log').write_text(str(error) + '\n')
        print(f'MM copy verification failed: {error}; evidence {evidence}', file=sys.stderr)
    finally:
        (evidence / 'runner.exit').write_text(f'{status}\n')
    return status


if __name__ == '__main__':
    sys.exit(main())
