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
ordinary = load('vma_modify_ordinary', SCRIPTS/'test-vma-lifecycle-vm.py')
selection = load('vma_modify_selection', SCRIPTS/'verify-vma-modify.py')
native = load('vma_modify_native', SCRIPTS.parent/'tests/vma-modify/gate.py')
common, fixture_tools = ordinary.common, ordinary.fixture_tools
BASELINE = '2926d88bb7fc4608fd942453d929c39e4e5ec006'
NATIVE_FILES = ('tools/testing/selftests/mm/merge.c',
                'tools/testing/selftests/mm/vm_util.c', 'tools/testing/selftests/mm/vm_util.h',
                'tools/testing/selftests/mm/thp_settings.c', 'tools/testing/selftests/mm/thp_settings.h',
                'tools/testing/selftests/kselftest.h', 'tools/testing/selftests/kselftest_harness.h')
NATIVE_UNITS = ('merge', 'vm_util', 'thp_settings')
EXPECTED_NATIVE_DEPENDENCIES = 187
PINNED_IMAGE = 'sha256:c02eb3929889b3f0cc035d57a02c844e0c74c71d24fbda1311249faeb8257f63'
GCC_FLAGS = ('-std=gnu11', '-O2', '-Wall', '-Wunreachable-code', '-U_FORTIFY_SOURCE', '-Werror')
PREPROCESS = ('mm-copy', 'dup-mmap', 'vma-lifecycle', 'exit-mmap')
TOKENS = {'ordinary': 'rusix.vma_lifecycle_probe=1', 'native': 'rusix.vma_modify_probe=1'}


def need(condition, message):
    if not condition:
        raise ValueError(message)


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def accept_console(kind, console, status):
    need(kind in TOKENS, 'Unknown guest kind')
    need(status == 0, f'QEMU failure/timeout: {status}')
    prefix = 'VMA_LIFECYCLE_' if kind == 'ordinary' else 'VMA_MODIFY_'
    need(not re.search(r'RUSIX_(?!'+prefix+r')', console), 'Foreign guest markers in console')
    if kind == 'ordinary':
        return ordinary.accept_console(console, status)
    result = native.validate(console)
    return dict(result, qemu_exit=status)


def validate_config(profile, text, target):
    need(profile in ('vma-modify-c', 'vma-modify-rust'), 'Ordinary copy VMA profile required')
    values = selection.config_values(text)
    selection.check_config(profile, values, selection.config_values(target))
    for name in (*ordinary.REQUIRED_CONFIG, 'MEMFD_CREATE'):
        need(values.get('CONFIG_'+name) == 'y', 'Missing guest requirement: '+name)
    need(values.get('CONFIG_KUNIT', 'n') == 'n', 'Ordinary runner rejects KUnit')
    return 'rust' if selection.PROFILES[profile] else 'c'


def upstream_identity(source):
    manifest = json.loads((source/'rusix/tests/vma-modify/upstream.json').read_text())
    need(manifest['baseline'] == BASELINE and set(manifest['files']) == set(NATIVE_FILES),
         'Wrong native baseline/input inventory')
    for name, record in manifest['files'].items():
        original = subprocess.check_output(['git', '-C', str(source), 'show', BASELINE+':'+name])
        blob = subprocess.check_output(['git', '-C', str(source), 'rev-parse', BASELINE+':'+name], text=True).strip()
        need((source/name).read_bytes() == original and common.digest(source/name) == record['sha256']
             and blob == record['blob'], 'Native upstream source changed: '+name)
    need(manifest['required_cases'] == list(native.CASES), 'Wrong native five-case inventory')
    need(manifest['argv'] == [arg for name in native.CASES for arg in ('-r', name)],
         'Native filter arguments differ')
    return manifest


def source_inventory(source, selected):
    # Include the actual selection closure and all local runner/tool modules;
    # prior evidence is referenced by identity, never recursively snapshotted.
    paths = {p for p in (source/'rusix/scripts').iterdir() if p.is_file() and p.suffix in ('.py', '.sh')}
    for fixture in ('vma-modify', 'vma-lifecycle'):
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


def record_command(label, argv, artifacts, evidence, *, output=False):
    """Only build/inspection tools run here; generated guest binaries never do."""
    need(argv[0] in ('/usr/bin/gcc', '/usr/bin/rustc', '/usr/bin/readelf', '/usr/bin/dpkg-query'),
         'Unexpected fixture build/inspection executable')
    write_json(evidence/(label+'-command.json'), argv)
    try:
        result = subprocess.run(argv, capture_output=True, text=True)
    finally:
        for name in ('init', 'probe'):
            if (artifacts/name).exists():
                (artifacts/name).chmod(0o644)
    (evidence/(label+'.stdout')).write_text(result.stdout)
    (evidence/(label+'.stderr')).write_text(result.stderr)
    (evidence/(label+'.exit')).write_text(str(result.returncode)+'\n')
    need(result.returncode == 0 and not result.stderr and (output or not result.stdout),
         'Fixture command failed or emitted diagnostics: '+label)
    return result.stdout


def dependency_records(text, target, unit, source):
    target_text, body = text.replace('\\\n', ' ').split(':', 1)
    need(target_text == str(target), 'Wrong native dependency target')
    names = shlex.split(body)
    need(str(unit) in names and len(names) == len(set(names)), 'Missing/duplicate native dependency')
    approved = {(source/name).resolve() for name in NATIVE_FILES}
    result = {}
    for name in names:
        path = Path(name)
        need(path.is_absolute(), 'Relative native/system dependency')
        resolved = path.resolve(strict=True)
        need(resolved in approved or resolved.is_relative_to('/usr'), 'Unexpected native/system dependency root')
        need(resolved.is_file(), 'Dependency is not a regular file')
        result[name] = {'resolved': str(resolved), 'sha256': common.digest(resolved),
                        'bytes': resolved.stat().st_size}
    return result


def unchanged_dependencies(records):
    for name, record in records.items():
        path = Path(name)
        need(str(path.resolve(strict=True)) == record['resolved'] and
             common.digest(path) == record['sha256'] and path.stat().st_size == record['bytes'],
             'Native/system dependency changed: '+name)


def native_compile(source, artifacts, evidence):
    # Discover and hash the actual compiler's full header closure BEFORE building.
    # -M and -MD use the same flags; emitted dependency files must agree afterward.
    dependencies, objects = {}, []
    for name in NATIVE_UNITS:
        unit = source/'tools/testing/selftests/mm'/(name+'.c')
        obj, dep = artifacts/(name+'.o'), evidence/(name+'-before.d')
        argv = ['/usr/bin/gcc', *GCC_FLAGS, '-M', '-MF', str(dep), '-MT', str(obj), str(unit)]
        record_command(name+'-dependencies', argv, artifacts, evidence)
        found = dependency_records(dep.read_text(), obj, unit, source)
        need(all(name not in dependencies or dependencies[name] == value for name, value in found.items()),
             'Dependency changed while discovering compiler inputs')
        dependencies.update(found)
        objects.append(obj)
    need(len(dependencies) == EXPECTED_NATIVE_DEPENDENCIES, 'Native dependency inventory differs from pinned compile contract')
    need({str((source/n).resolve()) for n in NATIVE_FILES}.issubset(
        {r['resolved'] for r in dependencies.values()}), 'Seven native baseline inputs missing from compiler dependencies')
    write_json(evidence/'native-header-inputs-before.json', dependencies)
    for name, obj in zip(NATIVE_UNITS, objects):
        unit, dep = source/'tools/testing/selftests/mm'/(name+'.c'), evidence/(name+'.d')
        record_command(name+'-compile', ['/usr/bin/gcc', *GCC_FLAGS, '-MD', '-MF', str(dep),
            '-MT', str(obj), '-c', str(unit), '-o', str(obj)], artifacts, evidence)
        actual = dependency_records(dep.read_text(), obj, unit, source)
        prior = dependency_records((evidence/(name+'-before.d')).read_text(), obj, unit, source)
        need(actual == prior, 'Actual compile dependency closure differs')
        unchanged_dependencies(dependencies)
    trace = record_command('probe-link', ['/usr/bin/gcc', '-static', *map(str, objects),
        '-lrt', '-lpthread', '-lm', '-Wl,-t', '-o', str(artifacts/'probe')], artifacts, evidence, output=True)
    # Retain actual static link inputs as well as package and header provenance.
    linked = {}
    for name in trace.splitlines():
        path = Path(name)
        need(path.is_absolute() and path.is_file(), 'Unrecognized linker input trace')
        resolved = path.resolve(strict=True)
        need(resolved.is_relative_to('/usr') or resolved in objects, 'Unexpected linker input')
        linked[str(resolved)] = common.digest(resolved)
    need(set(map(str, objects)).issubset(linked), 'Native link omitted a required translation unit')
    write_json(evidence/'native-link-inputs.json', linked)
    unchanged_dependencies(dependencies)
    write_json(evidence/'native-header-inputs-after.json', dependencies)
    return dependencies, linked


def nested_build_proofs(proof, selected):
    copy = selected['copy_vma_selection']
    teardown = copy['exit_mmap_selection']
    vma = teardown['vma_lifecycle_selection']
    dup = vma['dup_mmap_selection']
    expected = {'vma-modify-copy-selection.json': copy, 'copy-vma-exit-selection.json': teardown,
                'exit-mmap-vma-selection.json': vma, 'vma-lifecycle-dup-selection.json': dup,
                'dup-mmap-mm-copy-selection.json': dup['mm_copy_selection']}
    for name, value in expected.items():
        need(json.loads((proof/name).read_text()) == value, 'Saved nested build proof differs: '+name)
    return {str(proof/name): common.digest(proof/name) for name in expected}


def recheck_for_boot(paths, build, proof, profile, selected, evidence):
    reinspection = evidence/'selection-recheck'
    before = copy_prerequisites(proof, reinspection)
    before.update(nested_build_proofs(proof, selected))
    command = ['bash', str(paths.project/'scripts/with-local-tools.sh'), 'python3',
               str(paths.project/'scripts/verify-vma-modify.py'), 'objects', '--profile', profile,
               '--source', str(paths.source), '--build', str(build), '--evidence', str(reinspection)]
    write_json(evidence/'selection-command.json', command)
    result = subprocess.run(command, capture_output=True, text=True)
    (evidence/'selection.exit').write_text(str(result.returncode)+'\n')
    (evidence/'selection.stderr').write_text(result.stderr)
    (evidence/'selection.json').write_text(result.stdout)
    need(result.returncode == 0 and not result.stderr, 'Per-boot actual selection failed')
    need(json.loads(result.stdout) == selected and selected['source_context'] == 'vma-modify-v1',
         'Per-boot actual modification selection differs')
    for name, value in before.items():
        need(common.digest(Path(name)) == value, 'Per-boot original proof changed')
    write_json(evidence/'build-reference.json', before)
    return before


def compile_and_boot(kind, paths, image, artifacts, evidence, revision, source_hashes, selected,
                     build, proof, profile):
    artifacts.mkdir(); evidence.mkdir()
    proof_hashes = recheck_for_boot(paths, build, proof, profile, selected, evidence)
    fixture = paths.project/'tests'/('vma-lifecycle' if kind == 'ordinary' else 'vma-modify')
    init, probe = artifacts/'init', artifacts/'probe'
    rustlib = Path(record_command('rust-target-libdir', ['/usr/bin/rustc', '--target',
        'x86_64-unknown-linux-gnu', '--print', 'target-libdir'], artifacts, evidence, output=True).strip())
    need(rustlib.is_absolute() and rustlib.is_relative_to('/usr'), 'Unexpected Rust target libraries')
    rustlibs = {str(p): common.digest(p) for p in sorted(rustlib.iterdir()) if p.is_file()}
    need(rustlibs, 'Missing Rust target libraries')
    write_json(evidence/'rust-library-inputs.json', rustlibs)
    record_command('init-compile', ['/usr/bin/rustc', '--edition', '2021', '--target',
        'x86_64-unknown-linux-gnu', '-C', 'target-feature=+crt-static', '-C', 'panic=abort',
        '-C', 'opt-level=2', str(fixture/'init.rs'), '-o', str(init)], artifacts, evidence)
    dependencies, linked = {}, {}
    if kind == 'ordinary':
        record_command('probe-compile', ['/usr/bin/gcc', '-std=gnu11', '-O2', '-Wall', '-Wextra',
            '-Werror', '-static', str(fixture/'probe.c'), '-o', str(probe)], artifacts, evidence)
    else:
        dependencies, linked = native_compile(paths.source, artifacts, evidence)
    for name in ('init', 'probe'):
        binary = artifacts/name
        need(binary.stat().st_mode & 0o777 == 0o644, 'Guest artifact must remain non-executable on host')
        elf = record_command(name+'-readelf', ['/usr/bin/readelf', '-W', '-h', '-l', '-d', str(binary)],
                             artifacts, evidence, output=True)
        ordinary.static_elf(elf)
    check_inputs(paths.source, source_hashes, selected, proof_hashes | rustlibs | linked)
    unchanged_dependencies(dependencies)
    need(common.source_state(paths.source) == revision, 'Source changed during compilation')
    archive = artifacts/'initramfs.cpio'
    archive.write_bytes(ordinary.make_initramfs(init.read_bytes(), probe.read_bytes()))
    hashes = {str(p): common.digest(p) for p in (image, init, probe, archive)}
    write_json(evidence/'artifacts.json', hashes)
    write_json(evidence/'artifact-metadata.json', {name: {'mode': oct((artifacts/name).stat().st_mode & 0o777),
        'bytes': (artifacts/name).stat().st_size, 'host_executed': False} for name in ('init', 'probe')})
    command = qemu_command(image, archive, kind)
    (evidence/'command.sh').write_text(shlex.join(command)+'\n')
    try:
        with (evidence/'console.log').open('wb') as log:
            guest = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
        (evidence/'qemu.exit').write_text(str(guest.returncode)+'\n')
        result = accept_console(kind, (evidence/'console.log').read_text(errors='replace'), guest.returncode)
    finally:
        check_inputs(paths.source, source_hashes, selected, hashes | proof_hashes | rustlibs | linked)
        unchanged_dependencies(dependencies)
        need(common.source_state(paths.source) == revision, 'Source changed during verification')
    write_json(evidence/'result.json', result)
    return result, hashes | proof_hashes | rustlibs | linked

def run(args, paths, evidence):
    revision = common.source_state(paths.source)
    need(os.environ.get('RUSIX_QEMU_ACCEL') == 'kvm', 'VMA modification verification requires KVM')
    image_id = fixture_tools.fixture_identity(evidence, paths.project/'tests/brd-ext4/ext4-packages.lock')
    need(image_id == PINNED_IMAGE, 'VMA modification runtime requires reviewed pinned image')
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
    artifacts = paths.output/'builds'/f'vma-modify-vm-{args.label}'
    artifacts.mkdir(parents=True, exist_ok=False)
    image = artifacts/'bzImage'; shutil.copyfile(kernel, image)
    need(common.digest(image) == common.digest(kernel), 'Copied kernel changed')
    reinspection = evidence/'selection-recheck'
    prerequisite_hashes = copy_prerequisites(proof, reinspection)
    prior = proof/'vma-modify-selection.json'
    selected_before = json.loads(prior.read_text())
    prerequisite_hashes[str(prior)] = common.digest(prior)
    for name in ('build.sha256', 'config', 'profile.txt', 'environment.log', 'build.exit', 'build.log', 'source-after.commit', 'source-after.status'):
        prerequisite_hashes[str(proof/name)] = common.digest(proof/name)
    write_json(evidence/'build-reference.json', {'source': revision, 'input_sha256': prerequisite_hashes})
    command = ['bash', str(paths.project/'scripts/with-local-tools.sh'), 'python3',
               str(paths.project/'scripts/verify-vma-modify.py'), 'objects', '--profile', profile,
               '--source', str(paths.source), '--build', str(build), '--evidence', str(reinspection)]
    (evidence/'selection-command.sh').write_text(shlex.join(command)+'\n')
    checked = subprocess.run(command, capture_output=True, text=True)
    (evidence/'selection.exit').write_text(str(checked.returncode)+'\n')
    (evidence/'selection.stderr').write_text(checked.stderr)
    (evidence/'selection.json').write_text(checked.stdout)
    need(checked.returncode == 0 and not checked.stderr, 'Selection verifier failure/diagnostics')
    selected = json.loads(checked.stdout)
    need(selected.get('source_context') == 'vma-modify-v1', 'Explicit modification source context required')
    prerequisite_hashes.update(nested_build_proofs(proof, selected))
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
    packages = subprocess.run(['/usr/bin/dpkg-query', '-W', '-f=${Package}\t${Version}\t${Architecture}\n'],
                              capture_output=True, text=True)
    (evidence/'package-inventory.log').write_text(packages.stdout)
    (evidence/'package-inventory.stderr').write_text(packages.stderr)
    (evidence/'package-inventory.exit').write_text(str(packages.returncode)+'\n')
    need(packages.returncode == 0 and not packages.stderr, 'Package inventory diagnostics')
    fixture_tools.validate_inventory('\n'.join(sorted(packages.stdout.splitlines()))+'\n',
                                     (evidence/'rootfs-packages.lock').read_text(),
                                     (paths.project/'tests/brd-ext4/ext4-packages.lock').read_text())
    metadata = dict(source_revision=revision, profile=profile, implementation=implementation,
                    container_image=image_id, config_sha256=common.digest(config), sources=source_hashes,
                    selection=selected, native_upstream=upstream)
    write_json(evidence/'inputs.json', metadata)
    results, artifact_hashes = {}, {}
    for kind in ('ordinary', 'native'):
        results[kind], hashes = compile_and_boot(kind, paths, image, artifacts/kind, evidence/kind,
                                                revision, source_hashes, selected, build, proof, profile)
        artifact_hashes.update(hashes)
    check_inputs(paths.source, source_hashes, selected, artifact_hashes | prerequisite_hashes)
    need(common.source_state(paths.source) == revision and upstream_identity(paths.source) == upstream, 'Final source/native identity changed')
    common.check_hashes(proof/'build.sha256', [kernel, config, build/'vmlinux'])
    result = dict(status='PASS', source_revision=revision, implementation=implementation,
                  ordinary_cases=results['ordinary']['cases'], native_cases=results['native']['cases'],
                  boots=2, cases=14, results=results, artifacts=artifact_hashes)
    write_json(evidence/'result.json', result)
    print(f'VMA modification {implementation}: nine ordinary and five native cases passed; evidence {evidence}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('build', type=Path); parser.add_argument('label')
    parser.add_argument('--build-evidence', type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'[a-zA-Z0-9_-]+', args.label):
        parser.error('Use letters, numbers, underscore and hyphen in labels')
    paths = resolve_paths()
    evidence = paths.output/'logs'/f'{args.label}-vma-modify.run'
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.mkdir(exist_ok=False)
    status = 1
    try:
        run(args, paths, evidence); status = 0
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        (evidence/'error.log').write_text(str(error)+'\n')
        print(f'VMA modification verification failed: {error}; evidence {evidence}', file=sys.stderr)
    finally:
        (evidence/'runner.exit').write_text(str(status)+'\n')
    return status


if __name__ == '__main__':
    sys.exit(main())
