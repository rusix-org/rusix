#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Compile static guest fixtures and run task contracts only in bounded KVM."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import stat
import subprocess
import sys

sys.dont_write_bytecode = True
from rusix_paths import resolve_paths


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


common = load('task_common', 'test-brd-vm.py')
fixture_tools = load('task_fixture_tools', 'test-brd-ext4-vm.py')
selection = load('task_selection', 'verify-task-construction.py')
generator = load('task_fault_generator', 'generate-task-fault-calibration.py')
fault_gate = generator.gate
TOKEN = 'rusix.task_faults=1'
REQUIRED_CONFIG = ('64BIT', 'PROC_FS', 'SMP', 'MULTIUSER', 'BINFMT_ELF',
                   'BLK_DEV_INITRD', 'SERIAL_8250_CONSOLE', 'DEBUG_FS', 'SYSFS',
                   'FAULT_INJECTION', 'FAILSLAB', 'FAIL_PAGE_ALLOC',
                   'FAULT_INJECTION_DEBUG_FS', 'FAULT_INJECTION_STACKTRACE_FILTER',
                   'STACKTRACE', 'KPROBES', 'KPROBE_EVENTS', 'TRACING', 'KALLSYMS')
LABELS = ['calibration','slab-1'] + [f'stack-{n}' for n in range(1,17)]
FORMATS = ['page_decision','slab_decision','pages_result','kmem_kmem_cache_alloc',
           'kmem_kmem_cache_free','sched_sched_process_fork']
ARTIFACTS = ['calibration.tsv'] + [f'{n}.format' for n in FORMATS] + [
    f'{label}.{ext}' for label in LABELS for ext in ('worker','trace','probes','cpu0','cpu1')]


def decode_console(console, qemu_exit):
    if qemu_exit != 0:
        raise ValueError(f'QEMU failed or timed out: {qemu_exit}')
    if re.search(r'(?i:\bwarning\b)|\bBUG\b|Oops:|Kernel panic|CPU feature dependency check failure|ACPI (?:BIOS )?(?:Error|Exception|Warning)|ACPI: Unable to load', console):
        raise ValueError('Kernel diagnostics in guest console')
    lines = [line for line in console.splitlines() if 'RUSIX_TASK_FAULT_' in line]
    expected = len(ARTIFACTS)
    if len(lines) != expected+2 or lines[-2:] != ['RUSIX_TASK_FAULT_CAPTURE_COMPLETE','RUSIX_TASK_FAULT_INIT_COMPLETE']:
        raise ValueError('Capture/cleanup/init terminal inventory differs')
    result={}
    for name,line in zip(ARTIFACTS,lines[:-2]):
        match=re.fullmatch(r'RUSIX_TASK_FAULT_ARTIFACT ([a-z0-9_.-]+) ([0-9a-f]*)',line)
        if not match or match[1] != name or len(match[2]) % 2 or len(match[2]) > 4*1024*1024:
            raise ValueError('Artifact inventory/order/encoding/size differs')
        result[name]=bytes.fromhex(match[2])
    return result


def attribute(records, cal):
    attempts=[]; seen=set()
    for label in LABELS:
        get=lambda ext:records[f'{label}.{ext}'].decode()
        fault_gate.attempt_identity(label,get('worker'),seen)
        attempts.append(dict(label=label,**fault_gate.classify(get('worker'),get('trace'),cal,[get('cpu0'),get('cpu1')],get('probes'))))
    fault_gate.need(attempts[0]['classification']=='uninjected-control','Missing actual successful allocation calibration')
    fault_gate.need(attempts[1]['classification']=='task-slab-failure','Missing task allocation failure')
    fault_gate.need(any(r['classification']=='stack-page-failure' for r in attempts[2:]),'No attributable stack failure')
    return attempts


def validate_config(profile, config, target):
    if profile not in ('task-construction-fault-c','task-construction-fault-rust'):
        raise ValueError('Fault runner requires explicit diagnostic profile')
    values = selection.config_values(config)
    selection.check_config(profile, values, selection.config_values(target))
    for name in REQUIRED_CONFIG:
        if values.get('CONFIG_' + name) != 'y':
            raise ValueError('Missing guest requirement: ' + name)
    return 'rust' if selection.PROFILES[profile] else 'c'


def static_elf(text):
    interpreter, needed = fixture_tools.parse_elf(text)
    if interpreter or needed:
        raise ValueError('Guest executable must be static x86_64 without dependencies')


def make_initramfs(init, controller, worker, calibration):
    entries=[(name,stat.S_IFDIR|0o755,b'',0,0) for name in ('dev','proc','sys')]
    entries += [('dev/console',stat.S_IFCHR|0o600,b'',5,1)]
    entries += [(name,stat.S_IFREG|mode,data,0,0) for name,mode,data in [
        ('init',0o755,init),('fault-controller',0o755,controller),
        ('fault-worker',0o755,worker),('calibration.tsv',0o444,calibration)]]
    return common.newc(entries+[('TRAILER!!!',0,b'',0,0)])


def qemu_command(image, archive):
    return ['/usr/bin/timeout', '--kill-after=5s', '300s', '/usr/bin/qemu-system-x86_64',
               '-machine', 'q35', '-accel', 'kvm', '-cpu', 'qemu64', '-m', '512M', '-smp', '2',
               '-display', 'none', '-serial', 'stdio', '-monitor', 'none', '-nic', 'none', '-no-reboot',
               '-kernel', str(image), '-initrd', str(archive), '-append',
               f'console=ttyS0 rdinit=/init {TOKEN} nokaslr panic=-1 kunit.enable=0 printk.time=0 loglevel=7']


def compile_guest(name, command, artifact, evidence):
    (evidence / f'{name}-compile-command.sh').write_text(shlex.join(command) + '\n')
    with (evidence / f'{name}-compile.log').open('w') as log:
        result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
    (evidence / f'{name}-compile.exit').write_text(f'{result.returncode}\n')
    result.check_returncode()
    if re.search(r'warning:|error:', (evidence / f'{name}-compile.log').read_text(), re.I):
        raise ValueError('Guest compiler diagnostics')
    elf = subprocess.check_output(['/usr/bin/readelf', '-W', '-h', '-l', '-d', str(artifact)], text=True)
    (evidence / f'{name}-elf.log').write_text(elf)
    static_elf(elf)


def run(args, paths, evidence):
    revision = common.source_state(paths.source)
    if os.environ.get('RUSIX_QEMU_ACCEL') != 'kvm':
        raise ValueError('Task fault verification requires RUSIX_QEMU_ACCEL=kvm')
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
    artifacts = paths.output / 'builds' / f'task-faults-vm-{args.label}'
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
    command = wrapper + ['python3', str(paths.project / 'scripts/verify-task-construction.py'),
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
    if selected != json.loads((proof / 'task-selection.json').read_text()) or selected.get('status') != 'PASS' or selected.get('implementation') != implementation:
        raise ValueError('Actual constructor selection differs from build proof')
    fixture = paths.project / 'tests/task-construction-faults'
    sources = {Path(__file__).resolve(), Path(common.__file__), Path(fixture_tools.__file__),
               paths.project / 'scripts/compare-task-fault-runs.py', Path(selection.__file__), Path(generator.__file__), Path(fault_gate.__file__), paths.project / 'scripts/rusix_paths.py',
               paths.project / 'scripts/server_target.py', paths.project / 'scripts/saved_clang_command.py',
               paths.project / 'scripts/preprocess-task-construction.py',
               paths.project / 'scripts/with-local-tools.sh',
               paths.project / 'tests/brd-ext4/ext4-packages.lock'}
    sources.update(path for path in fixture.iterdir() if path.is_file())
    source_hashes={str(path.relative_to(paths.source)): common.digest(path) for path in sorted(sources)}
    init, controller, worker = artifacts/'init', artifacts/'controller', artifacts/'worker'
    calibration_dir=evidence/'calibration'
    cal=generator.generate(build/'vmlinux',config,revision,implementation,calibration_dir)
    for name, command in (('rustc', ['/usr/bin/rustc', '--version', '--verbose']),
                          ('gcc', ['/usr/bin/gcc', '--version']),
                          ('readelf', ['/usr/bin/readelf', '--version']),
                          ('qemu', ['/usr/bin/qemu-system-x86_64', '--version'])):
        (evidence / f'{name}-version.log').write_text(subprocess.check_output(command, text=True))
    compile_guest('init', ['/usr/bin/rustc', '--edition', '2021', '--target', 'x86_64-unknown-linux-gnu',
                          '-C', 'target-feature=+crt-static', '-C', 'panic=abort', '-C', 'opt-level=2',
                          str(fixture / 'init.rs'), '-o', str(init)], init, evidence)
    compile_guest('controller', ['/usr/bin/rustc', '--edition', '2021', '--target', 'x86_64-unknown-linux-gnu',
                          '-C', 'target-feature=+crt-static', '-C', 'panic=abort', '-C', 'opt-level=2',
                          str(fixture / 'controller.rs'), '-o', str(controller)], controller, evidence)
    compile_guest('worker', ['/usr/bin/gcc', '-std=gnu11', '-O2', '-Wall', '-Wextra', '-Werror',
                           '-static', str(fixture / 'worker.c'), '-o', str(worker)], worker, evidence)
    if common.source_state(paths.source) != revision:
        raise ValueError('Source changed during fixture compilation')
    for name,digest in source_hashes.items():
        if common.digest(paths.source/name) != digest:
            raise ValueError('Fixture input changed during compilation')
    archive = artifacts / 'initramfs.cpio'
    archive.write_bytes(make_initramfs(init.read_bytes(), controller.read_bytes(), worker.read_bytes(), (calibration_dir/'calibration.tsv').read_bytes()))
    metadata = {'source_revision': revision, 'source_root': str(paths.source), 'profile': profile, 'implementation': implementation,
                'container_image': image_id, 'config_sha256': common.digest(config),
                'sources': source_hashes,
                'selection': selected,
                'artifacts': {str(path): common.digest(path) for path in (image, init, controller, worker, archive)}}
    (evidence / 'inputs.json').write_text(json.dumps(metadata, indent=2, sort_keys=True) + '\n')
    command = qemu_command(image,archive)
    (evidence / 'command.sh').write_text(shlex.join(command) + '\n')
    with (evidence / 'console.log').open('wb') as log:
        guest = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
    (evidence / 'qemu.exit').write_text(f'{guest.returncode}\n')
    records = decode_console((evidence/'console.log').read_text(errors='strict'), guest.returncode)
    decoded=evidence/'records'; decoded.mkdir()
    for name,data in records.items(): (decoded/name).write_bytes(data)
    if records['calibration.tsv'] != (calibration_dir/'calibration.tsv').read_bytes():
        raise ValueError('Running guest calibration differs')
    verified,_=fault_gate.load_reviewed_calibration(calibration_dir/'packet.json')
    if verified != cal: raise ValueError('Calibration changed')
    result=dict(status='PASS',scope='Diagnostic guest allocation-failure attribution with successful control and cleanup',
                attempts=attribute(records,cal),qemu_exit=guest.returncode)

    if common.source_state(paths.source) != revision:
        raise ValueError('Source changed during verification')
    for path, digest in metadata['sources'].items():
        if common.digest(paths.source / path) != digest:
            raise ValueError('Fixture source changed')
    for path, digest in metadata['artifacts'].items():
        if common.digest(Path(path)) != digest:
            raise ValueError('Guest artifact changed')
    for path, digest in selected['input_sha256'].items():
        if common.digest(Path(path)) != digest:
            raise ValueError('Selection artifact changed')
    common.check_hashes(proof / 'build.sha256', [kernel, config, build / 'vmlinux'])
    result.update(implementation=implementation, source_revision=revision)
    (evidence / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(f'Task fault {implementation}: slab and stack failure attribution passed; evidence {evidence}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('build', type=Path)
    parser.add_argument('label')
    parser.add_argument('--build-evidence', type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'[a-zA-Z0-9_-]+', args.label):
        parser.error('Use only letters, numbers, underscore and hyphen in labels')
    paths = resolve_paths()
    evidence = paths.output / 'logs' / f'{args.label}-task-faults.run'
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
        print(f'Task fault verification failed: {error}; evidence {evidence}', file=sys.stderr)
    finally:
        (evidence / 'runner.exit').write_text(f'{status}\n')
    return status


if __name__ == '__main__':
    sys.exit(main())
