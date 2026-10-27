#!/usr/bin/env python3
"""Strict pinned postchecks only: no compiler, guest or kernel execution."""
import argparse
import copy
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
from types import SimpleNamespace
from preflight import SOURCE, EXPECTED, IMAGE, RUN, DRAFT, PROFILES, digest, source_record, config_prerequisite, reviewed_files
sys.path.insert(0,str(SOURCE/'rusix/scripts'))
def load(name,file):
    spec=importlib.util.spec_from_file_location(name,SOURCE/'rusix/scripts'/file)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
selection=load('exit_selection','verify-exit-mmap.py')
guest=load('exit_guest','test-exit-mmap-vm.py')
gate=load('exit_gate','validate-exit-mmap-kunit.py')
CASES=('shared_clone_write_and_exit','shared_clone_exec_detaches_mm','private_fork_cow',
       'dontfork_omits_only_advised_range','wipeonfork_clears_child_and_grandchild',
       'private_file_mapping_cow_and_lifetime','shared_file_mapping_survives_parent_unmap',
       'mprotect_middle_split_and_restore','fixed_mremap_preserves_unlinked_file_mapping')
if tuple(guest.CASES)!=CASES:raise ValueError('Ordinary literal inventory changed')
if tuple(gate.SUITES['rusix_exit_mmap'])!=('empty_final_users_retains_storage','mapped_final_users_closes_before_file_put','fixed_replace_close_dummy_reset'):
    raise ValueError('KUnit literal inventory changed')
CHECK_LABEL='unset'
def need(ok,message):
    if not ok:raise ValueError(message)
def hash_records(path,expected,resolve):
    rows={}
    for line in path.read_text().splitlines():
        m=re.fullmatch(r'([0-9a-f]{64})  (.+)',line)
        need(m and m[2] not in rows,'Malformed/duplicate hashes: '+str(path));rows[m[2]]=m[1]
    need(set(rows)==set(expected),'Exact hash inventory differs: '+str(path))
    for name,value in rows.items():need(digest(resolve(name))==value,'Hash changed: '+name)
    return rows

def reinspection(key,build,proof,selected,resolve):
    profile=PROFILES[key];cb=Path('/out/builds')/('ci-'+profile)
    directory=RUN/('postcheck-reinspection-'+CHECK_LABEL+'-'+key);directory.mkdir()
    pre=selection.preprocessor
    for parser,prefix,unit in ((pre.copy,'mm-copy','kernel/fork'),(pre.dup,'dup-mmap','mm/mmap'),(pre.vma,'vma-lifecycle','mm/vma_init')):
        cmd=build/Path(unit).parent/('.'+Path(unit).name+'.o.cmd');output=build/(unit+'.i');co=cb/(unit+'.i')
        original=dict(argv=parser.command(cmd.read_text(),co),cwd=str(cb),input_sha256={str(p):digest(resolve(str(p))) for p in parser.inputs(cb,Path('/src'))},output=str(co),preprocessed_sha256=digest(output))
        need(json.loads((proof/(prefix+'-preprocess.json')).read_text())==original,'Original '+prefix+' preprocessing differs')
        remapped=dict(argv=parser.command(cmd.read_text(),output),cwd=str(build),input_sha256={str(p):digest(p) for p in parser.inputs(build,SOURCE)},output=str(output),preprocessed_sha256=digest(output))
        (directory/(prefix+'-preprocess.json')).write_text(json.dumps(remapped,indent=2)+'\n')
    original=dict(input_sha256={str(p):digest(resolve(str(p))) for p in pre.inputs(cb,Path('/src'))},argv=pre.command((build/'mm/.vma.o.cmd').read_text(),cb/'mm/vma.i'),cwd=str(cb),output=str(cb/'mm/vma.i'),preprocessed_sha256=digest(build/'mm/vma.i'),prerequisite_outputs={str(cb/name):digest(build/name) for name in ('kernel/fork.i','mm/mmap.i','mm/vma_init.i')})
    need(json.loads((proof/'exit-mmap-preprocess.json').read_text())==original,'Original four-unit provenance differs')
    (directory/'exit-mmap-preprocess.json').write_text(json.dumps(pre.record(build,SOURCE),indent=2)+'\n')
    for prefix in ('mm-copy','dup-mmap','vma-lifecycle','exit-mmap'):
        need((proof/(prefix+'-preprocess.exit')).read_text().strip()=='0','Preprocessing failed')
        need(not re.search('warning:|error:',(proof/(prefix+'-preprocess.log')).read_text(),re.I),'Preprocessing diagnostics')
        for suffix in ('log','exit'):shutil.copyfile(proof/(prefix+'-preprocess.'+suffix),directory/(prefix+'-preprocess.'+suffix))
    nested=selected['vma_lifecycle_selection'];dup=nested['dup_mmap_selection']
    for file,value in [('exit-mmap-vma-selection.json',nested),('vma-lifecycle-dup-selection.json',dup),('dup-mmap-mm-copy-selection.json',dup['mm_copy_selection'])]:
        need(json.loads((proof/file).read_text())==value,'Saved nested proof differs: '+file)
    actual=selection.verify(SimpleNamespace(source=SOURCE,build=build,evidence=directory,profile=profile))
    (directory/'actual-selection.json').write_text(json.dumps(actual,indent=2)+'\n')
    def container_path(name):
        p=Path(name);need(p.is_absolute() and '..' not in p.parts,'Noncanonical remap key')
        for host,old in ((SOURCE,Path('/src')),(RUN/key,Path('/out'))):
            if p.is_relative_to(host):return str(old/p.relative_to(host))
        raise ValueError('Unknown actual proof path: '+name)
    def normalize(value):
        # Only explicitly typed path maps change. Contexts, constant values,
        # source-extension relative hashes and registration targets stay exact.
        if not isinstance(value,dict):return
        for field,child in value.items():
            if field in ('input_sha256','archive_member_sha256'):
                mapped={container_path(k):v for k,v in child.items()}
                need(len(mapped)==len(child),'Remap collision');value[field]=mapped
            elif isinstance(child,dict):normalize(child)
    normalize(actual);need(actual==selected,'Reinspected nested selection differs')
    return directory

def check(key):
    profile=PROFILES[key];side=key.rsplit('-',1)[1];kunit=key.startswith('kunit-');output=RUN/key
    logs=output/'logs';build=output/'builds'/('ci-'+profile);cb=Path('/out/builds')/('ci-'+profile)
    def resolve(name):
        p=Path(name);need(p.is_absolute() and '..' not in p.parts,'Noncanonical input path')
        if p.is_relative_to('/src'):return SOURCE/p.relative_to('/src')
        if p.is_relative_to('/out'):return output/p.relative_to('/out')
        raise ValueError('Unrecognized input path: '+name)
    for file in ('container.exit','ci.exit'):need((logs/file).read_text().strip()=='0','Failed '+file)
    ci=(logs/'ci-inputs.log').read_text().splitlines();need(ci[0]==EXPECTED and 'profile='+profile in ci and 'acceleration=kvm' in ci,'CI identity differs')
    proofs=list(logs.glob('ci-'+profile+'-build.*'));need(len(proofs)==1,'Ambiguous build record');proof=proofs[0]
    need((proof/'build.exit').read_text().strip()=='0','Build failure')
    need((proof/'environment.log').read_text().splitlines()[0]==EXPECTED and (proof/'source-after.commit').read_text().strip()==EXPECTED and not (proof/'source-after.status').read_bytes(),'Build source drift')
    need((proof/'profile.txt').read_text().strip()==profile and (proof/'config').read_bytes()==(build/'.config').read_bytes(),'Build profile/config drift')
    for name in ('build.log','config.log'):need(not re.search(r'warning:|error:|objtool.*warning',(proof/name).read_text(),re.I),'Build diagnostics')
    hash_records(proof/'build.sha256',[str(cb/n) for n in ('.config','arch/x86/boot/bzImage','vmlinux','vmlinux.map')],resolve)
    selected=json.loads((proof/'exit-mmap-selection.json').read_text());context=selection.TEST_CONTEXT if kunit else None
    need(selected['status']=='PASS' and selected['implementation']==side and selected['test_context']==context,'Selection identity differs')
    expected={str(p) for p in selection.input_paths(cb,Path('/src'),side=='rust',kunit=kunit)}
    need(set(selected['input_sha256'])==expected,'Exact selection inputs differ')
    for name,value in selected['input_sha256'].items():need(digest(resolve(name))==value,'Selection input changed')
    child=selected['vma_lifecycle_selection']
    for field in ('dup_mmap_selection','mm_copy_selection',None):
        need(child['status']=='PASS' and child['implementation']=='rust' and child['test_context']==context,'Nested selection/context differs')
        if field:child=child[field]
    need(all(child[n]=='rust' for n in ('task_implementation','mm_construction_implementation','mm_release_implementation')),'Inherited policy selection differs')
    fixture=selected['fixture_selection'];need(fixture['status']=='PASS' and fixture['enabled']==kunit,'Fixture proof differs')
    need(fixture['cases']==(list(gate.SUITES['rusix_exit_mmap']) if kunit else []),'Fixture registration inventory differs')
    for name,implementation in [('selection.log','brd-rust'),('completion-selection.log','completion-rust'),('swait-selection.log','swait-rust'),('wake-selection.log','wake-rust'),('wait-bit-selection.log','wait-bit-rust')]:
        text=(proof/name).read_text();need(text.splitlines()[0]=='implementation='+implementation,'Inherited selection differs')
        rows=re.findall(r'^([0-9a-f]{64})  (.+)$',text,re.M);need(rows and len({p for _,p in rows})==len(rows),'Missing/duplicate inherited hashes')
        for value,path in rows:need(digest(resolve(path))==value,'Inherited artifact changed')
    need(not (proof/'brd-reference.diff').read_bytes(),'Pristine C BRD changed')
    selection.check_config(profile,selection.config_values((build/'.config').read_text()),selection.config_values((SOURCE/'rusix/configs/x86_64-server.config').read_text()))
    recheck=reinspection(key,build,proof,selected,resolve)
    details=kunit_boots(profile,logs,build,recheck,resolve) if kunit else ordinary(profile,side,logs,build,proof,selected,resolve)
    need((logs/'container-image-id.txt').read_text().strip()==IMAGE,'Image differs')
    for name in ('source-before.json',):need(json.loads((logs/name).read_text())==source_record(),'Per-profile source drift')
    need(json.loads((RUN/'source-before.json').read_text())==source_record(),'Matrix source drift')
    for relative in ('rusix/tests/vma-lifecycle/init.rs','rusix/tests/vma-lifecycle/probe.c','rusix/tests/vma-lifecycle/README.md','mm/exit_mmap_test.c','rust/helpers/exit_mmap_test.c','rust/kernel/mm/exit_tests.rs'):
        need((RUN/'fixture-source'/relative).read_bytes()==(SOURCE/relative).read_bytes(),'Fixture snapshot differs')
    return build,details

def ordinary(profile,side,logs,build,proof,selected,resolve):
    run=logs/('ci-'+profile+'-exit-mmap.run')
    for name in ('runner.exit','qemu.exit','selection.exit','init-compile.exit','probe-compile.exit'):need((run/name).read_text().strip()=='0','Guest stage failed: '+name)
    result=json.loads((run/'result.json').read_text());accepted=guest.accept_console((run/'console.log').read_text(),0)
    need(result==accepted|dict(implementation=side,source_revision=EXPECTED),'Guest console/result differ')
    for name in ('selection.stderr','init-compile.log','probe-compile.log'):need(not re.search('warning:|error:',(run/name).read_text(),re.I),'Guest diagnostics')
    need(not (run/'selection.stderr').read_bytes(),'Selection diagnostics')
    need((run/'config').read_bytes()==(build/'.config').read_bytes(),'Guest config differs')
    for prefix in ('mm-copy','dup-mmap','vma-lifecycle','exit-mmap'):
        for suffix in ('json','log','exit'):
            name=prefix+'-preprocess.'+suffix
            need((run/'kernel-build'/name).read_bytes()==(proof/name).read_bytes(),'Copied guest preprocessing differs')
    need(json.loads((run/'kernel-build/exit-mmap-selection.json').read_text())==selected,'Copied guest build selection differs')
    artifacts=f'/out/builds/exit-mmap-vm-ci-{profile}'
    command=['/usr/bin/timeout','--kill-after=5s','180s','/usr/bin/qemu-system-x86_64','-machine','q35','-accel','kvm','-cpu','qemu64','-m','512M','-smp','2','-display','none','-serial','stdio','-monitor','none','-nic','none','-no-reboot','-kernel',artifacts+'/bzImage','-initrd',artifacts+'/initramfs.cpio','-append','console=ttyS0 rdinit=/init rusix.vma_lifecycle_probe=1 panic=-1 kunit.enable=0 printk.time=0 loglevel=7']
    need(shlex.split((run/'command.sh').read_text())==command,'Guest QEMU command differs')
    metadata=json.loads((run/'inputs.json').read_text())
    need((metadata['source_revision'],metadata['profile'],metadata['implementation'],metadata['container_image'])==(EXPECTED,profile,side,IMAGE),'Guest provenance differs')
    need(metadata['config_sha256']==digest(build/'.config'),'Guest config hash differs')
    need(metadata['selection']==selected and json.loads((run/'selection.json').read_text())==selected,'Guest selection differs')
    need(set(metadata['artifacts'])=={artifacts+'/'+n for n in ('bzImage','init','probe','initramfs.cpio')},'Guest artifact inventory differs')
    sources={'rusix/scripts/'+n for n in ('test-exit-mmap-vm.py','test-task-construction-vm.py','test-brd-vm.py','test-brd-ext4-vm.py','verify-exit-mmap.py','verify-task-construction.py','preprocess-task-construction.py','rusix_paths.py','server_target.py','saved_clang_command.py','preprocess-exit-mmap.py','exit_mmap_source.py','verify-vma-lifecycle.py','preprocess-vma-lifecycle.py','verify-dup-mmap.py','verify-brd-parameter-owner.py','measure-kernel-languages.py','preprocess-dup-mmap.py','preprocess-mm-copy.py','verify-mm-copy.py','preprocess-mm-release.py','preprocess-mm-construction.py','verify-mm-release.py','verify-mm-construction.py','with-local-tools.sh')}
    sources.add('rusix/tests/brd-ext4/ext4-packages.lock');sources.update('rusix/tests/vma-lifecycle/'+n for n in ('README.md','init.rs','probe.c'))
    need(set(metadata['sources'])==sources,'Exact guest source inventory differs')
    need(json.loads((run/'sources-before.json').read_text())==metadata['sources'],'Precompile sources differ')
    for name,value in metadata['sources'].items():need(digest(SOURCE/name)==value,'Guest source changed')
    for name,value in metadata['artifacts'].items():need(digest(resolve(name))==value,'Guest artifact changed')
    need(digest(resolve(artifacts+'/bzImage'))==digest(build/'arch/x86/boot/bzImage'),'Copied kernel differs')
    need((run/'container-image-id.txt').read_text().strip()==IMAGE,'Guest image differs')
    need((run/'rootfs-packages.lock').read_bytes()==(SOURCE/'rusix/tests/brd-ext4/ext4-packages.lock').read_bytes(),'Guest packages differ')
    return {'kind':'ordinary','metadata':metadata,'run':str(run),'cases':list(CASES)}

def kunit_boots(profile,logs,build,recheck,resolve):
    versions=[]
    for suffix,mode,filt,count,combined in (('', 'exit-mmap-combined','rusix_*',79,True),('-exit-mmap','exit-mmap','rusix_exit_mmap',3,False)):
        label='ci-'+profile+suffix;boot=logs/(label+'-boot.run')
        need((boot/'mode.txt').read_text().strip()==mode,'Wrong KUnit mode')
        for stage in ('qemu','parse','gate'):need((logs/f'{label}-{stage}.exit').read_text().strip()=='0','KUnit stage failed: '+stage)
        console=logs/f'{label}-console.log'
        need(not re.search(r'\b(WARNING|BUG)\b|Oops:|Kernel panic|CPU feature dependency check failure|ACPI (?:BIOS )?(?:Error|Exception|Warning)|ACPI: Unable to load',console.read_text()),'KUnit diagnostics')
        parsed=json.loads((logs/f'{label}-kunit.json').read_text());need(gate.validate(parsed,combined)==count,'KUnit exact case total differs')
        fresh=recheck/(mode+'-reparsed.json')
        command=['python3',str(SOURCE/'tools/testing/kunit/kunit.py'),'parse',str(console),'--json='+str(fresh)]
        need(not fresh.exists(),'Reparse output already exists');proc=subprocess.run(command,capture_output=True,text=True)
        (recheck/(mode+'-parse.log')).write_text(proc.stdout)
        (recheck/(mode+'-parse.stderr')).write_text(proc.stderr)
        (recheck/(mode+'-parse.exit')).write_text(str(proc.returncode)+'\n')
        need(proc.returncode==0 and not proc.stderr and fresh.is_file() and json.loads(fresh.read_text())==parsed,'Raw KUnit console/JSON differ')
        command=['bash','/src/rusix/scripts/with-local-tools.sh','timeout','--kill-after=5s','180s','qemu-system-x86_64','-machine','q35','-accel','kvm','-cpu','qemu64','-m','512M','-smp','2','-display','none','-serial','stdio','-monitor','none','-nic','none','-no-reboot','-kernel',f'/out/builds/ci-{profile}/arch/x86/boot/bzImage','-append',f'console=ttyS0 kunit.enable=1 kunit.autorun=1 kunit.filter_glob={filt} kunit_shutdown=reboot panic=-1']
        need(shlex.split((boot/'command.sh').read_text())==command,'KUnit QEMU command differs')
        hash_records(logs/f'{label}-inputs.sha256',[f'/out/builds/ci-{profile}/arch/x86/boot/bzImage',f'/out/builds/ci-{profile}/.config'],resolve)
        hash_records(boot/'scripts.sha256',['/src/rusix/scripts/'+n for n in ('boot-kunit.sh','validate-exit-mmap-kunit.py','validate-completion-kunit.py','validate-brd-kunit.py')],resolve)
        version=(boot/'qemu-version.txt').read_bytes();need(version,'Missing QEMU identity');versions.append(version.decode())
    need(versions[0]==versions[1],'KUnit QEMU tool changed')
    return {'kind':'kunit','qemu_version':versions[0],'combined':79,'isolated':3,'suite':'rusix_exit_mmap','cases':list(gate.SUITES['rusix_exit_mmap'])}

def main():
    need(json.loads((RUN/'config-prerequisite-before.json').read_text()) == config_prerequisite(), 'Config prerequisite reference drift')
    global CHECK_LABEL
    ap=argparse.ArgumentParser();ap.add_argument('--key',choices=PROFILES);args=ap.parse_args();CHECK_LABEL=args.key or 'pair'
    need(os.environ.get('RUSIX_PINNED_POSTCHECK_IMAGE')==IMAGE,'Pinned-image postchecks required')
    keys=[args.key] if args.key else list(PROFILES)
    for key in keys:
        for name in ('packages.lock','toolchain.log'):need((Path('/opt/rusix')/name).read_bytes()==(RUN/key/'logs'/name).read_bytes(),'Pinned tool/package identity differs')
    tools={}
    for name in ('llvm-ar','llvm-nm','llvm-objdump','llvm-readobj'):
        proc=subprocess.run([name,'--version'],capture_output=True,text=True)
        need(proc.returncode==0 and not proc.stderr and re.search(r'(?:LLVM|Debian LLVM) version 19\.',proc.stdout),'Pinned LLVM19 differs');tools[name]=proc.stdout
    with (RUN/('postcheck-tools-'+CHECK_LABEL+'.json')).open('x') as stream:json.dump(tools,stream,indent=2)
    hash_records(RUN/'launcher.sha256',[str(DRAFT/n) for n in reviewed_files()],lambda p:Path(p))
    if args.key:
        check(args.key);print(json.dumps({'status':'PASS','profile':PROFILES[args.key]}));return
    for key in keys:
        need((RUN/(key+'-postcheck.exit')).read_text().strip()=='0' and not (RUN/(key+'-postcheck.stderr')).read_bytes(),'Per-profile postcheck incomplete')
        need((RUN/key/'logs/launcher.exit').read_text().strip()=='0','Per-profile launcher incomplete')
    checked={key:check(key) for key in keys};pairs={}
    for kind in ('ordinary','kunit'):
        ck,rk=kind+'-c',kind+'-rust';cb,c=checked[ck];rb,r=checked[rk]
        pairs[kind]=selection.compare(selection.config_values((cb/'.config').read_text()),selection.config_values((rb/'.config').read_text()))
        for name in ('packages.lock','toolchain.log','container-image-id.txt'):
            left=(RUN/ck/'logs'/name).read_bytes();need(left and left==(RUN/rk/'logs'/name).read_bytes(),'Pair tools/image differ')
        if kind=='ordinary':
            need(c['metadata']['sources']==r['metadata']['sources'],'Guest sources differ')
            for name in ('init','probe','initramfs.cpio'):
                a=[v for k,v in c['metadata']['artifacts'].items() if Path(k).name==name];b=[v for k,v in r['metadata']['artifacts'].items() if Path(k).name==name]
                need(len(a)==1 and a==b,'Ordinary fixture bytes differ')
            for name in ('rustc-version.log','gcc-version.log','readelf-version.log','qemu-version.log','rootfs-packages.lock'):
                a=(Path(c['run'])/name).read_bytes();need(a and a==(Path(r['run'])/name).read_bytes(),'Guest tool identity differs')
        else:
            # Independently proved compiled pointers/objects may differ with
            # selector-dependent compilation. Compare semantics, not ELF bytes.
            need(c==r,'KUnit suite/cases/counts/tool identity differs')
    print(json.dumps({'status':'PASS','source':EXPECTED,'pair_differences':pairs,'ordinary_cases_per_side':9,'kunit_combined':79,'kunit_isolated':3,'scope':'Paired mapping teardown consumers and three native lifecycle cases; no general failure/whole-MM claim'},indent=2))
if __name__=='__main__':main()
