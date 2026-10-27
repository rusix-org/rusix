#!/usr/bin/env python3
"""Fail-closed post-run evidence and pair checks; no kernel or guest execution."""
import argparse
import os
import subprocess
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


selection = load('task_selection', 'verify-task-construction.py')
comparison = load('fault_comparison', 'compare-task-fault-runs.py')
guest = comparison.vm
preprocessor=load('fault_preprocessor','preprocess-task-construction.py')


def check(side):
    output = RUN/side; profile = 'task-construction-fault-'+side
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
    selected = json.loads((proof/'task-selection.json').read_text())
    container_build = Path('/out/builds')/('ci-'+profile)
    dependency_paths=preprocessor.inputs(container_build,Path('/src'))+[container_build/'kernel/fork.i',container_build/'vmlinux',container_build/'kernel/built-in.a',Path('/src/rusix/configs/x86_64-server.config'),Path('/src/rusix/scripts/verify-task-construction.py')]
    if side=='rust':dependency_paths.append(container_build/'kernel/task_construction_rust.o')
    dependency_set={str(p) for p in dependency_paths}
    if set(selected['input_sha256']) != dependency_set: raise ValueError('Selection dependency inventory differs')
    if selected['status'] != 'PASS' or selected['implementation'] != side:
        raise ValueError('Wrong selected implementation')
    for name, expected in selected['input_sha256'].items():
        if digest(resolve(name)) != expected: raise ValueError('Selection input changed: '+name)
    preprocessed=container_build/'kernel/fork.i'
    prerecord=dict(argv=preprocessor.command((build/'kernel/.fork.o.cmd').read_text(),preprocessed),cwd=str(container_build),input_sha256={str(p):digest(resolve(str(p))) for p in preprocessor.inputs(container_build,Path('/src'))},output=str(preprocessed),preprocessed_sha256=digest(build/'kernel/fork.i'))
    if json.loads((proof/'task-preprocess.json').read_text())!=prerecord:raise ValueError('Actual preprocessing inputs differ')
    if (proof/'task-preprocess.exit').read_text().strip()!='0' or re.search('warning:|error:',(proof/'task-preprocess.log').read_text(),re.I):raise ValueError('Preprocessing diagnostics/failure')
    selection.original_policy((SOURCE/'kernel/fork.c').read_text())
    selection.check_preprocessed((build/'kernel/fork.i').read_text(),side=='rust')
    run=logs/('ci-'+profile+'-task-faults.run')
    metadata,result,binaries=comparison.verify(run,side,comparison.remapper(output,SOURCE))
    if metadata['source_revision']!=EXPECTED or metadata['container_image']!=IMAGE:
        raise ValueError('Wrong diagnostic source or image')
    if len(result['attempts'])!=18 or [a['label'] for a in result['attempts']]!=guest.LABELS:
        raise ValueError('Expected exact eighteen captures, in order')
    if metadata['selection']!=selected or json.loads((run/'kernel-build/task-selection.json').read_text())!=selected:
        raise ValueError('Actual guest selection differs from build proof')
    if set(metadata['selection']['input_sha256'])!=dependency_set:
        raise ValueError('Missing actual selection inputs')
    if (run/'config').read_bytes()!=(build/'.config').read_bytes():raise ValueError('Guest config differs')
    for name in ('runner.exit','qemu.exit','selection.exit','init-compile.exit','controller-compile.exit','worker-compile.exit'):
        if (run/name).read_text().strip()!='0':raise ValueError('Failed '+name)
    if (run/'selection.stderr').read_bytes():raise ValueError('Selection emitted diagnostics')
    for name in ('init','controller','worker'):
        if re.search('warning:|error:',(run/(name+'-compile.log')).read_text(),re.I):raise ValueError('Fixture compiler diagnostics')
    prefix=f'/out/builds/task-faults-vm-ci-{profile}'
    if set(metadata['artifacts'])!={prefix+'/'+n for n in ('bzImage','init','controller','worker','initramfs.cpio')}:raise ValueError('Artifact path inventory differs')
    if digest(resolve(prefix+'/bzImage'))!=digest(build/'arch/x86/boot/bzImage'):raise ValueError('Guest kernel differs')
    expected=guest.qemu_command(Path(prefix+'/bzImage'),Path(prefix+'/initramfs.cpio'))
    if shlex.split((run/'command.sh').read_text())!=expected:raise ValueError('Exact bounded diagnostic command differs')
    sources={'rusix/scripts/'+n for n in ('test-task-faults-vm.py','test-brd-vm.py','test-brd-ext4-vm.py','compare-task-fault-runs.py','verify-task-construction.py','generate-task-fault-calibration.py','validate-task-fault-trace.py','rusix_paths.py','server_target.py','saved_clang_command.py','preprocess-task-construction.py','with-local-tools.sh')}
    sources.add('rusix/tests/brd-ext4/ext4-packages.lock')
    sources.update(str(p.relative_to(SOURCE)) for p in (SOURCE/'rusix/tests/task-construction-faults').iterdir() if p.is_file())
    if set(metadata['sources'])!=sources:raise ValueError('Fixture source inventory differs')
    for name in ('init.rs','controller.rs','worker.c','README.md'):
        if (RUN/'fixture-source'/name).read_bytes()!=(SOURCE/'rusix/tests/task-construction-faults'/name).read_bytes():raise ValueError('Fixture snapshot differs')
    for path in (logs/'container-image-id.txt',run/'container-image-id.txt'):
        if path.read_text().strip()!=IMAGE:raise ValueError('Recorded image differs')
    if (run/'rootfs-packages.lock').read_bytes()!=(SOURCE/'rusix/tests/brd-ext4/ext4-packages.lock').read_bytes():raise ValueError('Pinned fixture packages differ')
    packet=json.loads((run/'calibration/packet.json').read_text())
    # The tracked verifier rereads the actual linked ELF, regenerates symbols,
    # disassembly and notes, and binds exact allocator return PCs. No synthetic
    # calibration, unsupported site or missing causal event becomes success.
    cal,_=guest.fault_gate.load_reviewed_calibration(run/'calibration/packet.json',comparison.remapper(output,SOURCE))
    if cal['build_source']!=EXPECTED:raise ValueError('Calibration source differs')
    for name in ('vmlinux','config'):
        expected_path=f'/out/builds/ci-{profile}/'+('vmlinux' if name=='vmlinux' else '.config')
        if packet['inputs'][name]['path']!=expected_path:raise ValueError('Calibration does not identify actual built kernel')
    if set(p.name for p in (run/'records').iterdir())!=set(guest.ARTIFACTS):raise ValueError('Missing/extra raw capture')
    if source_record()!=json.loads((RUN/'source-before.json').read_text()) or source_record()!=json.loads((logs/'source-before.json').read_text()):raise ValueError('Source changed')
    return run,build,metadata,result,binaries


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--side',choices=('c','rust'));args=ap.parse_args()
    if os.environ.get('RUSIX_PINNED_POSTCHECK_IMAGE')!=IMAGE:
        raise ValueError('Postchecks require the pinned container; host LLVM is not accepted')
    sides=[args.side] if args.side else ['c','rust']
    for side in sides:
        for name in ('packages.lock','toolchain.log'):
            if (Path('/opt/rusix')/name).read_bytes()!=(RUN/side/'logs'/name).read_bytes():
                raise ValueError('Postcheck container tool/package identity differs')
    tool_record={}
    for tool in ('llvm-nm','llvm-objdump','llvm-objcopy'):
        tool_record[tool]=subprocess.check_output([tool,'--version'],text=True)
    (RUN/('postcheck-tools-'+(args.side or 'pair')+'.json')).write_text(json.dumps(tool_record,indent=2)+'\n')
    if args.side:
        check(args.side);print(json.dumps(dict(status='PASS',side=args.side)));return
    for side in ('c','rust'):
        if (RUN/(side+'-postcheck.exit')).read_text().strip()!='0' or (RUN/(side+'-postcheck.stderr')).read_bytes():
            raise ValueError('Per-side pinned postcheck failed')
    c,cb,ci,cr,cf=check('c');r,rb,ri,rr,rf=check('rust')
    comparison.matched_inputs(ci,ri)
    if cf!=rf:raise ValueError('Compiled fixture binaries differ')
    differences=selection.compare(selection.config_values((cb/'.config').read_text()),selection.config_values((rb/'.config').read_text()))
    for name in ('packages.lock','toolchain.log','container-image-id.txt'):
        left=RUN/'c/logs'/name;right=RUN/'rust/logs'/name
        if not left.read_bytes() or left.read_bytes()!=right.read_bytes():raise ValueError('Pair tools/image differ: '+name)
    for name in ('rustc','gcc','readelf','qemu'):
        left=c/f'{name}-version.log';right=r/f'{name}-version.log'
        if not left.read_bytes() or left.read_bytes()!=right.read_bytes():raise ValueError('Guest compiler/tools differ')
    # Use the tracked CLI as well as the per-side API, with explicit container
    # path remapping so packet paths remain truthful after host archival.
    command=['python3',str(SOURCE/'rusix/scripts/compare-task-fault-runs.py'),'--c',str(c),'--rust',str(r),'--c-output-root',str(RUN/'c'),'--rust-output-root',str(RUN/'rust'),'--source-root',str(SOURCE)]
    (RUN/'compare-command.sh').write_text(shlex.join(command)+'\n')
    result=subprocess.run(command,capture_output=True,text=True)
    (RUN/'compare.stdout').write_text(result.stdout);(RUN/'compare.stderr').write_text(result.stderr);(RUN/'compare.exit').write_text(str(result.returncode)+'\n')
    if result.returncode or result.stderr:raise ValueError('Tracked pair comparison failed')
    for side in ('c','rust'):
        if (RUN/side/'logs/launcher.exit').read_text().strip()!='0':raise ValueError('Launcher incomplete')
    print(json.dumps(dict(status='PASS',source=EXPECTED,different_settings=differences,attempts_per_side=18,scope='Diagnostic slab/stack allocation-failure attribution; no general failure coverage'),indent=2))


if __name__=='__main__':main()
