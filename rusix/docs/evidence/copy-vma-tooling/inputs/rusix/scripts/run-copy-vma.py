#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Two bounded ordinary guest boots: nine VMA contracts and five native TAP cases."""
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


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SCRIPTS = Path(__file__).resolve().parent
ordinary = load('copy_vma_ordinary', SCRIPTS/'test-exit-mmap-vm.py')
selection = load('copy_vma_selection', SCRIPTS/'verify-copy-vma.py')
native = load('copy_vma_native', SCRIPTS.parent/'tests/copy-vma/gate.py')
common, fixture_tools = ordinary.common, ordinary.fixture_tools
BASELINE = '2926d88bb7fc4608fd942453d929c39e4e5ec006'
NATIVE_FILES = ('tools/testing/selftests/mm/mremap_dontunmap.c',
                'tools/testing/selftests/kselftest.h')
PREPROCESS = ('mm-copy', 'dup-mmap', 'vma-lifecycle', 'exit-mmap')
TOKENS = {'ordinary': 'rusix.vma_lifecycle_probe=1', 'native': 'rusix.copy_vma_probe=1'}


def need(condition, message):
    if not condition:
        raise ValueError(message)


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def accept_console(kind, console, status):
    need(kind in TOKENS, 'Unknown guest kind')
    need(status == 0, f'QEMU failure/timeout: {status}')
    foreign = 'RUSIX_COPY_VMA_' if kind == 'ordinary' else 'RUSIX_VMA_LIFECYCLE_'
    need(foreign not in console, 'Foreign guest markers in console')
    if kind == 'ordinary':
        return ordinary.accept_console(console, status)
    result = native.validate(console)
    return dict(result, qemu_exit=status)


def validate_config(profile, text, target):
    need(profile in ('copy-vma-c', 'copy-vma-rust'), 'Ordinary copy VMA profile required')
    values = selection.config_values(text)
    selection.check_config(profile, values, selection.config_values(target))
    for name in (*ordinary.REQUIRED_CONFIG, 'MEMFD_CREATE'):
        need(values.get('CONFIG_'+name) == 'y', 'Missing guest requirement: '+name)
    need(values.get('CONFIG_KUNIT', 'n') == 'n', 'Ordinary runner rejects KUnit')
    return 'rust' if selection.PROFILES[profile] else 'c'


def upstream_identity(source):
    manifest = json.loads((source/'rusix/tests/copy-vma/upstream.json').read_text())
    need(manifest['baseline'] == BASELINE and set(manifest['files']) == set(NATIVE_FILES),
         'Wrong native baseline/input inventory')
    for name, record in manifest['files'].items():
        original = subprocess.check_output(['git', '-C', str(source), 'show', BASELINE+':'+name])
        blob = subprocess.check_output(['git', '-C', str(source), 'rev-parse', BASELINE+':'+name], text=True).strip()
        need((source/name).read_bytes() == original and common.digest(source/name) == record['sha256']
             and blob == record['git_blob'], 'Native upstream source changed: '+name)
    return manifest


def source_inventory(source, selected):
    # Include the actual selection closure and all local runner/tool modules;
    # prior evidence is referenced by identity, never recursively snapshotted.
    paths = {p for p in (source/'rusix/scripts').iterdir() if p.is_file() and p.suffix in ('.py', '.sh')}
    for fixture in ('copy-vma', 'vma-lifecycle'):
        paths.update(p for p in (source/'rusix/tests'/fixture).iterdir() if p.is_file())
    paths.update(source/name for name in NATIVE_FILES)
    paths.add(source/'rusix/tests/brd-ext4/ext4-packages.lock')
    paths.update(Path(name) for name in selected['input_sha256'] if Path(name).is_relative_to(source))
    return {str(p.relative_to(source)): common.digest(p) for p in sorted(paths)}


def qemu_command(image, archive, kind):
    need(kind in TOKENS, 'Unknown guest kind')
    return ['/usr/bin/timeout', '--kill-after=5s', '180s', '/usr/bin/qemu-system-x86_64',
            '-machine', 'q35', '-accel', 'kvm', '-cpu', 'qemu64', '-m', '512M', '-smp', '2',
            '-display', 'none', '-serial', 'stdio', '-monitor', 'none', '-nic', 'none', '-no-reboot',
            '-kernel', str(image), '-initrd', str(archive), '-append',
            f'console=ttyS0 rdinit=/init {TOKENS[kind]} panic=-1 kunit.enable=0 printk.time=0 loglevel=7']


def copy_prerequisites(proof, destination):
    destination.mkdir()
    hashes = {}
    for prefix in PREPROCESS:
        for suffix in ('json', 'log', 'exit'):
            name = prefix+'-preprocess.'+suffix
            src = proof/name
            hashes[str(src)] = common.digest(src)
            shutil.copyfile(src, destination/name)
            need(common.digest(destination/name) == hashes[str(src)], 'Preprocess record copy drift')
    return hashes


def check_inputs(source, source_hashes, selected, artifact_hashes):
    ordinary.verify_source_hashes(source, source_hashes)
    for name, digest in {**selected['input_sha256'], **artifact_hashes}.items():
        need(common.digest(Path(name)) == digest, 'Selection/guest artifact changed: '+name)


def compile_and_boot(kind, paths, image, artifacts, evidence, revision, source_hashes, selected):
    artifacts.mkdir(); evidence.mkdir()
    fixture = paths.project/'tests'/('vma-lifecycle' if kind == 'ordinary' else 'copy-vma')
    init, probe = artifacts/'init', artifacts/'probe'
    ordinary.compile_guest('init', ['/usr/bin/rustc', '--edition', '2021', '--target',
        'x86_64-unknown-linux-gnu', '-C', 'target-feature=+crt-static', '-C', 'panic=abort',
        '-C', 'opt-level=2', str(fixture/'init.rs'), '-o', str(init)], init, evidence)
    if kind == 'ordinary':
        command = ['/usr/bin/gcc', '-std=gnu11', '-O2', '-Wall', '-Wextra', '-Werror',
                   '-static', str(fixture/'probe.c'), '-o', str(probe)]
    else:
        command = ['/usr/bin/gcc', '-std=gnu11', '-O2', '-Wall', '-Wunreachable-code',
                   '-U_FORTIFY_SOURCE', '-Werror', '-static', str(paths.source/NATIVE_FILES[0]), '-o', str(probe)]
    ordinary.compile_guest('probe', command, probe, evidence)
    init.chmod(0o644); probe.chmod(0o644)
    check_inputs(paths.source, source_hashes, selected, {})
    need(common.source_state(paths.source) == revision, 'Source changed during compilation')
    archive = artifacts/'initramfs.cpio'
    # Includes /work needed by existing nine-case guest; harmless for native five.
    archive.write_bytes(ordinary.make_initramfs(init.read_bytes(), probe.read_bytes()))
    hashes = {str(p): common.digest(p) for p in (image, init, probe, archive)}
    write_json(evidence/'artifacts.json', hashes)
    command = qemu_command(image, archive, kind)
    (evidence/'command.sh').write_text(shlex.join(command)+'\n')
    with (evidence/'console.log').open('wb') as log:
        guest = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
    (evidence/'qemu.exit').write_text(str(guest.returncode)+'\n')
    result = accept_console(kind, (evidence/'console.log').read_text(errors='replace'), guest.returncode)
    check_inputs(paths.source, source_hashes, selected, hashes)
    need(common.source_state(paths.source) == revision, 'Source changed during verification')
    write_json(evidence/'result.json', result)
    return result, hashes


def run(args, paths, evidence):
    revision = common.source_state(paths.source)
    need(os.environ.get('RUSIX_QEMU_ACCEL') == 'kvm', 'Copy VMA verification requires KVM')
    image_id = fixture_tools.fixture_identity(evidence, paths.project/'tests/brd-ext4/ext4-packages.lock')
    build, proof = args.build.resolve(), args.build_evidence.resolve()
    kernel, config = build/'arch/x86/boot/bzImage', build/'.config'
    need((proof/'build.exit').read_text().strip() == '0', 'Kernel build failed')
    need(common.first_line(proof/'environment.log') == revision == common.first_line(proof/'source-after.commit'), 'Build source mismatch')
    need(not (proof/'source-after.status').read_bytes(), 'Dirty build source')
    need(not re.search(r'warning:|error:|objtool.*warning', (proof/'build.log').read_text(), re.I), 'Build diagnostics')
    profile = common.first_line(proof/'profile.txt')
    implementation = validate_config(profile, config.read_text(), (paths.project/'configs/x86_64-server.config').read_text())
    common.check_hashes(proof/'build.sha256', [kernel, config, build/'vmlinux'])
    need(config.read_bytes() == (proof/'config').read_bytes(), 'Build config changed')
    upstream = upstream_identity(paths.source)
    artifacts = paths.output/'builds'/f'copy-vma-vm-{args.label}'
    artifacts.mkdir(parents=True, exist_ok=False)
    image = artifacts/'bzImage'; shutil.copyfile(kernel, image)
    need(common.digest(image) == common.digest(kernel), 'Copied kernel changed')
    reinspection = evidence/'selection-recheck'
    prerequisite_hashes = copy_prerequisites(proof, reinspection)
    prior = proof/'copy-vma-selection.json'
    selected_before = json.loads(prior.read_text())
    prerequisite_hashes[str(prior)] = common.digest(prior)
    for name in ('build.sha256', 'config', 'profile.txt', 'environment.log', 'build.exit', 'build.log', 'source-after.commit', 'source-after.status'):
        prerequisite_hashes[str(proof/name)] = common.digest(proof/name)
    write_json(evidence/'build-reference.json', {'source': revision, 'input_sha256': prerequisite_hashes})
    command = ['bash', str(paths.project/'scripts/with-local-tools.sh'), 'python3',
               str(paths.project/'scripts/verify-copy-vma.py'), 'objects', '--profile', profile,
               '--source', str(paths.source), '--build', str(build), '--evidence', str(reinspection)]
    (evidence/'selection-command.sh').write_text(shlex.join(command)+'\n')
    checked = subprocess.run(command, capture_output=True, text=True)
    (evidence/'selection.exit').write_text(str(checked.returncode)+'\n')
    (evidence/'selection.stderr').write_text(checked.stderr)
    (evidence/'selection.json').write_text(checked.stdout)
    need(checked.returncode == 0 and not checked.stderr, 'Selection verifier failure/diagnostics')
    selected = json.loads(checked.stdout)
    need(selected == selected_before and selected['status'] == 'PASS' and selected['implementation'] == implementation, 'Actual selection differs from build')
    need(set(selected['input_sha256']) == {str(p) for p in selection.input_paths(build, paths.source, implementation == 'rust')}, 'Incomplete selection input inventory')
    source_hashes = source_inventory(paths.source, selected)
    write_json(evidence/'sources-before.json', source_hashes)
    for name, argv in (('rustc', ['/usr/bin/rustc', '--version', '--verbose']), ('gcc', ['/usr/bin/gcc', '--version']),
                       ('readelf', ['/usr/bin/readelf', '--version']), ('qemu', ['/usr/bin/qemu-system-x86_64', '--version'])):
        tool = subprocess.run(argv, capture_output=True, text=True)
        (evidence/f'{name}-version.log').write_text(tool.stdout)
        (evidence/f'{name}-version.stderr').write_text(tool.stderr)
        need(tool.returncode == 0 and not tool.stderr, 'Tool identity failure')
    metadata = dict(source_revision=revision, profile=profile, implementation=implementation,
                    container_image=image_id, config_sha256=common.digest(config), sources=source_hashes,
                    selection=selected, native_upstream=upstream)
    write_json(evidence/'inputs.json', metadata)
    results, artifact_hashes = {}, {}
    for kind in ('ordinary', 'native'):
        results[kind], hashes = compile_and_boot(kind, paths, image, artifacts/kind, evidence/kind,
                                                revision, source_hashes, selected)
        artifact_hashes.update(hashes)
    check_inputs(paths.source, source_hashes, selected, artifact_hashes | prerequisite_hashes)
    need(common.source_state(paths.source) == revision and upstream_identity(paths.source) == upstream, 'Final source/native identity changed')
    common.check_hashes(proof/'build.sha256', [kernel, config, build/'vmlinux'])
    result = dict(status='PASS', source_revision=revision, implementation=implementation,
                  ordinary_cases=results['ordinary']['cases'], native_cases=results['native']['cases'],
                  boots=2, cases=14, results=results, artifacts=artifact_hashes)
    write_json(evidence/'result.json', result)
    print(f'Copy VMA {implementation}: nine ordinary and five native cases passed; evidence {evidence}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('build', type=Path); parser.add_argument('label')
    parser.add_argument('--build-evidence', type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'[a-zA-Z0-9_-]+', args.label):
        parser.error('Use letters, numbers, underscore and hyphen in labels')
    paths = resolve_paths()
    evidence = paths.output/'logs'/f'{args.label}-copy-vma.run'
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.mkdir(exist_ok=False)
    status = 1
    try:
        run(args, paths, evidence); status = 0
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        (evidence/'error.log').write_text(str(error)+'\n')
        print(f'Copy VMA verification failed: {error}; evidence {evidence}', file=sys.stderr)
    finally:
        (evidence/'runner.exit').write_text(str(status)+'\n')
    return status


if __name__ == '__main__':
    sys.exit(main())
