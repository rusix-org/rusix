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


selection = load('task_selection', 'verify-mm-release.py')
release_gate = load('release_gate', 'validate-mm-release-kunit.py')
core_gate = load('core_gate', 'validate-completion-kunit.py')


def check(side):
    output = RUN/side; profile = 'mm-release-'+side
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
    selected = json.loads((proof/'mm-release-selection.json').read_text())
    container_build = Path('/out/builds')/('ci-'+profile)
    dependency_set = {str(p) for p in selection.input_paths(container_build, Path('/src'), side == 'rust')}
    if set(selected['input_sha256']) != dependency_set: raise ValueError('Selection dependency inventory differs')
    if selected['status'] != 'PASS' or selected['implementation'] != side:
        raise ValueError('Wrong selected implementation')
    for name, expected in selected['input_sha256'].items():
        if digest(resolve(name)) != expected: raise ValueError('Selection input changed: '+name)
    pre=selection.preprocessor
    record=dict(argv=pre.command((build/'kernel/.fork.o.cmd').read_text(),container_build/'kernel/fork.i'),
                cwd=str(container_build),input_sha256={str(p):digest(resolve(str(p))) for p in pre.inputs(container_build,Path('/src'))},
                output=str(container_build/'kernel/fork.i'),preprocessed_sha256=digest(build/'kernel/fork.i'))
    if json.loads((proof/'mm-release-preprocess.json').read_text())!=record:raise ValueError('Actual preprocessor inputs/command differ')
    if (proof/'mm-release-preprocess.exit').read_text().strip()!='0' or re.search(r'warning:|error:',(proof/'mm-release-preprocess.log').read_text(),re.I):raise ValueError('Preprocessor failure/diagnostics')
    for name,implementation in (('selection.log','brd-rust'),('completion-selection.log','completion-rust'),('swait-selection.log','swait-rust'),('wake-selection.log','wake-rust'),('wait-bit-selection.log','wait-bit-rust')):
        text=(proof/name).read_text()
        if text.splitlines()[0]!='implementation='+implementation:raise ValueError('Inherited Rust selection differs: '+name)
        hashes={}
        for value,path in re.findall(r'^([0-9a-f]{64})  (.+)$',text,re.M):
            if path in hashes or digest(resolve(path))!=value:raise ValueError('Inherited selection hash differs: '+path)
            hashes[path]=value
        if not hashes:raise ValueError('Missing inherited selection input hashes')
    if (proof/'brd-reference.diff').read_bytes():raise ValueError('Baseline C BRD differs')
    if selected.get('task_implementation') != 'rust' or selected.get('mm_construction_implementation') != 'rust':
        raise ValueError('Rust constructors are not retained')
    if (logs/'container-image-id.txt').read_text().strip() != IMAGE:
        raise ValueError('Image identity differs')
    for rel in ('kernel/mm_release_test.c','rust/helpers/mm_release_test.c','rust/kernel/mm/release_tests.rs'):
        if (RUN/'fixture-source'/rel).read_bytes() != (SOURCE/rel).read_bytes():
            raise ValueError('Compiled fixture source differs')
    selection.original_policy((SOURCE/'kernel/fork.c').read_text())
    selection.check_preprocessed((build/'kernel/fork.i').read_text(),side=='rust')
    # Re-read actual selected objects, not just a trusted PASS record. These
    # read-only LLVM commands never execute kernel code. Fail on any diagnostics.
    import subprocess
    def actual(argv):
        result=subprocess.run(argv,check=True,capture_output=True,text=True)
        if result.stderr:raise ValueError('Object inspection diagnostic: '+result.stderr)
        return result.stdout
    archive=build/'kernel/built-in.a'
    members=actual(['llvm-ar','t',str(archive)])
    selection.archive_members(members,side=='rust')
    objects=['fork','task_construction_rust','mm_construction_rust','mm_release_test']+(['mm_release_rust'] if side=='rust' else [])
    hashes={};symbols={}
    for obj in objects:
        path=build/f'kernel/{obj}.o';member=next(row for row in members.splitlines() if Path(row).name==path.name)
        # Pinned llvm-ar expands thin paths under the remapped output; proof keys use
        # container paths. Match the unique basename, then bind actual payload.
        saved=[key for key in selected['archive_member_sha256'] if Path(key).name==path.name]
        if len(saved)!=1:raise ValueError('Missing/ambiguous recorded archive member')
        hashes[saved[0]]=selection.task.archive_member_hash(archive,member,path)
        symbols[obj]=actual(['llvm-nm','--defined-only',str(path)])
        if symbols[obj]!=(proof/f'mm-release-{obj}-symbols.txt').read_text():
            raise ValueError('Saved object symbols differ from actual object')
        selection.definitions(symbols[obj],selection.PUBLIC if obj==('mm_release_rust' if side=='rust' else 'fork') else ())
        selection.mm.definitions(symbols[obj],selection.mm.MM_SYMBOLS if obj=='mm_construction_rust' else ())
        selection.task.bridge_definition(symbols[obj],obj=='task_construction_rust')
    if hashes!=selected['archive_member_sha256']:raise ValueError('Archive payload proof differs')
    linked=actual(['llvm-nm','--defined-only',str(build/'vmlinux')])
    if linked!=(proof/'mm-release-kernel-symbols.txt').read_text():raise ValueError('Saved linked symbols differ')
    selection.definitions(linked,selection.PUBLIC);selection.mm.definitions(linked,selection.mm.MM_SYMBOLS);selection.task.bridge_definition(linked,True)
    owner='mm_release_rust' if side=='rust' else 'fork'
    cb=selection.callback(symbols[owner],side=='rust')
    if cb!=selected['callback'] or selection.callback(linked,side=='rust')!=cb:raise ValueError('Callback ownership differs')
    for obj in objects:
        if obj!=owner and 'mmput_async_fn' in symbols[obj]:raise ValueError('Callback in alternate object')
    dis=actual(['llvm-objdump','-dr',str(build/f'kernel/{owner}.o')])
    # objdump's filename heading differs after remapping; semantics are validated
    # directly rather than comparing that incidental heading byte-for-byte.
    policy=build/f'kernel/{owner}.o'
    metadata=json.loads(actual(['llvm-readobj','--elf-output-style=JSON','--sections','--symbols',str(policy)]))
    saved=json.loads((proof/'mm-release-policy-elf.json').read_text())
    expected_policy=str(container_build/f'kernel/{owner}.o')
    if len(saved)!=1 or len(metadata)!=1 or saved[0]['FileSummary']['File']!=expected_policy or metadata[0]['FileSummary']['File']!=str(policy):
        raise ValueError('ELF metadata filename identity differs')
    # Normalize only the exact verified input filename. Section indices, symbol
    # values/types and every other structured ELF field must remain identical.
    normalized=json.loads(json.dumps(metadata))
    normalized[0]['FileSummary']['File']=expected_policy
    if saved!=normalized:raise ValueError('Saved ELF metadata differs from actual object')
    if digest(policy)!=selected['input_sha256'][expected_policy]:raise ValueError('Policy object changed during metadata inspection')
    selection.registration(dis,cb,side=='rust',metadata)
    selection.mm.check_relocations(actual(['llvm-objdump','-dr',str(build/'kernel/fork.o')]),True)
    if side=='rust':
        helpers=re.findall(r'fn (rusix_mm_[a-z_]+)\(', (SOURCE/'kernel/mm_release_rust.rs').read_text())
        for helper in helpers:
            for table in (symbols['fork'],linked):
                rows=[row.split() for row in table.splitlines() if row.split() and row.split()[-1]==helper]
                if len(rows)!=1 or rows[0][1]!='T':raise ValueError('Missing typed primitive')
    def hash_records(file,expected_names):
        rows={}
        for line in file.read_text().splitlines():
            match=re.fullmatch(r'([0-9a-f]{64})  (.+)',line)
            if not match or match[2] in rows:raise ValueError('Malformed/duplicate hash input')
            rows[match[2]]=match[1]
        if set(rows)!=set(expected_names):raise ValueError('Hash inventory mismatch: '+str(file))
        for name,value in rows.items():
            if digest(resolve(name))!=value:raise ValueError('Hash input changed: '+name)
    versions=[]
    for suffix, mode, filt, count in (('', 'mm-release-combined','rusix_*',80),('-completion','completion','rusix_completion_*',67),('-mm-release','mm-release','rusix_mm_release',4)):
        label='ci-'+profile+suffix;boot=logs/(label+'-boot.run')
        if (boot/'mode.txt').read_text().strip()!=mode:raise ValueError('Wrong boot mode')
        for stage in ('qemu','parse','gate'):
            if (logs/f'{label}-{stage}.exit').read_text().strip()!='0':raise ValueError('Boot stage failed: '+stage)
        console=(logs/f'{label}-console.log').read_text()
        if re.search(r'\b(WARNING|BUG)\b|Oops:|Kernel panic|CPU feature dependency check failure|ACPI (?:BIOS )?(?:Error|Exception|Warning)|ACPI: Unable to load',console):raise ValueError('Guest diagnostics')
        parsed=json.loads((logs/f'{label}-kunit.json').read_text())
        actual_count=core_gate.validate(parsed) if mode=='completion' else release_gate.validate(parsed,mode=='mm-release-combined')
        if actual_count!=count:raise ValueError('Wrong literal case total')
        # Reparse raw serial output to bind the accepted JSON to this boot.
        import tempfile
        with tempfile.TemporaryDirectory(prefix='mm-release-reparse-',dir=RUN) as tmp:
            output_json=Path(tmp)/'kunit.json'
            reparsed=subprocess.run(['python3',str(SOURCE/'tools/testing/kunit/kunit.py'),'parse',str(logs/f'{label}-console.log'),'--json='+str(output_json)],capture_output=True,text=True)
            if reparsed.returncode or not output_json.is_file() or json.loads(output_json.read_text())!=parsed:raise ValueError('Raw console/parsed result mismatch')
        command=['bash','/src/rusix/scripts/with-local-tools.sh','timeout','--kill-after=5s','180s','qemu-system-x86_64','-machine','q35','-accel','kvm','-cpu','qemu64','-m','512M','-smp','2','-display','none','-serial','stdio','-monitor','none','-nic','none','-no-reboot','-kernel',f'/out/builds/ci-{profile}/arch/x86/boot/bzImage','-append',f'console=ttyS0 kunit.enable=1 kunit.autorun=1 kunit.filter_glob={filt} kunit_shutdown=reboot panic=-1']
        if shlex.split((boot/'command.sh').read_text())!=command:raise ValueError('QEMU command differs from exact bounded template')
        hash_records(logs/f'{label}-inputs.sha256',[f'/out/builds/ci-{profile}/arch/x86/boot/bzImage',f'/out/builds/ci-{profile}/.config'])
        scripts=['boot-kunit.sh','validate-completion-kunit.py','validate-brd-kunit.py']
        if mode!='completion':scripts.append('validate-mm-release-kunit.py')
        hash_records(boot/'scripts.sha256',['/src/rusix/scripts/'+s for s in scripts])
        version=(boot/'qemu-version.txt').read_text()
        if not version.strip():raise ValueError('Missing QEMU version')
        versions.append(version)
    if len(set(versions))!=1:raise ValueError('QEMU version changed between boots')
    selection.check_config(profile,selection.config_values((build/'.config').read_text()),selection.config_values((SOURCE/'rusix/configs/x86_64-server.config').read_text()))
    if source_record()!=json.loads((RUN/'source-before.json').read_text()):raise ValueError('Frozen source changed')
    if json.loads((logs/'source-before.json').read_text())!=source_record():raise ValueError('Per-side source snapshot differs')
    return build,versions[0]


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--side',choices=('c','rust'));args=ap.parse_args()
    if os.environ.get('RUSIX_PINNED_POSTCHECK_IMAGE')!=IMAGE:
        raise ValueError('Postchecks require pinned container; host LLVM is not accepted')
    sides=[args.side] if args.side else ['c','rust']
    for side in sides:
        for name in ('packages.lock','toolchain.log'):
            if (Path('/opt/rusix')/name).read_bytes()!=(RUN/side/'logs'/name).read_bytes():
                raise ValueError('Postcheck container tool/package identity differs')
    tools={name:subprocess.check_output([name,'--version'],text=True) for name in ('llvm-ar','llvm-nm','llvm-objdump','llvm-readobj')}
    (RUN/('postcheck-tools-'+(args.side or 'pair')+'.json')).write_text(json.dumps(tools,indent=2)+'\n')
    if args.side:
        check(args.side);print(json.dumps(dict(status='PASS',side=args.side)));return
    for side in ('c','rust'):
        if (RUN/(side+'-postcheck.exit')).read_text().strip()!='0' or (RUN/(side+'-postcheck.stderr')).read_bytes():
            raise ValueError('Per-side pinned postcheck failed')
    cb,cv=check('c');rb,rv=check('rust')
    differences=selection.compare(selection.config_values((cb/'.config').read_text()),selection.config_values((rb/'.config').read_text()))
    for name in ('packages.lock','toolchain.log','container-image-id.txt'):
        left=RUN/'c/logs'/name;right=RUN/'rust/logs'/name
        if not left.read_bytes() or left.read_bytes()!=right.read_bytes():raise ValueError('Pair container tools/packages differ: '+name)
    if cv!=rv:raise ValueError('Pair QEMU versions differ')
    for side in ('c','rust'):
        if (RUN/side/'logs/launcher.exit').read_text().strip()!='0':raise ValueError('Launcher did not complete')
    print(json.dumps(dict(status='PASS',source=EXPECTED,different_settings=differences,combined=80,core=67,release=4,scope='KUnit release lifetime/refcount cases; no ordinary-consumer or allocation-failure claim'),indent=2))


if __name__=='__main__':main()
