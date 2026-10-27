#!/usr/bin/env python3
"""Read-only acceptance of the actual retained original-C KUnit runtime."""
from pathlib import Path
import hashlib,importlib.util,json,re,shlex,sys
BASE=Path('/home/aaron/code/rusix');DRAFT=Path(__file__).resolve().parent
RUN=BASE/'linux-out/exit-mmap-retained-c-kunit-001'
LAUNCH=BASE/'linux-out/exit-mmap-retained-c-kunit-draft'
SOURCE=BASE/'linux-mm-exit-mmap'
BUILD=BASE/'linux-out/mm-exit-mmap-verification-001/kunit-c/builds/ci-exit-mmap-kunit-c'
EXPECTED='0ff7a933c198dda0c3e2c0005e4bb97db3867acc'
IMAGE='sha256:c02eb3929889b3f0cc035d57a02c844e0c74c71d24fbda1311249faeb8257f63'
def need(v,msg):
 if not v:raise ValueError(msg)
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def hashes(path,names):
 rows={}
 for line in path.read_text().splitlines():
  m=re.fullmatch(r'([0-9a-f]{64})  (.+)',line);need(m and m[2] not in rows,'Malformed/duplicate hash record');rows[m[2]]=m[1]
 need(set(rows)=={str(p) for p in names},'Wrong hash-record inventory')
 for n,h in rows.items():need(sha(Path(n))==h,'Changed hashed input: '+n)
 return rows
def validate():
 pins=json.loads((DRAFT/'retained-c-records.json').read_text())
 before={str(p.relative_to(RUN)):sha(p) for p in sorted(RUN.rglob('*')) if p.is_file()}
 need(before==pins['runtime_sha256'],'Retained runtime record inventory or contents changed')
 for name,h in pins['launcher_sha256'].items():need(sha(LAUNCH/name)==h,'Retained launcher changed')
 hashes(RUN/'launcher.sha256',[LAUNCH/n for n in ('run.sh','boots.py','check.py','inputs.json','ready.json','README.md')])
 for n in ('container.exit','container-inspect.exit','host-after-check.exit','launcher.exit','boots.exit'):
  need((RUN/n).read_text().strip()=='0','Nonzero/missing terminal stage: '+n)
 need(not (RUN/'host-after-check.stderr').read_bytes(),'Host postcheck diagnostics')
 prereq=load('retained_original_inputs',LAUNCH/'check.py').check()
 need(prereq['source']==EXPECTED and prereq['status']=='PASS','Wrong original source proof')
 for name in ('prerequisite-before.json','prerequisite-after.json','host-after-check.json'):
  need(json.loads((RUN/name).read_text())==prereq,'Before/after input proof mismatch')
 container=json.loads((RUN/'container-inspect.json').read_text())[0];state=container['State'];resources=container['HostConfig']
 need(container['Image']==IMAGE and state['ExitCode']==0 and not state['OOMKilled'] and not state['Running'] and state['Pid']==0,'Runtime container not successful/terminal')
 need(resources['NanoCpus']==2*10**9 and resources['Memory']==2**31 and resources['MemorySwap']==2**31 and resources['PidsLimit']==256,'Runtime resource bounds differ')
 need(resources['NetworkMode']=='none' and resources['CapDrop']==['ALL'] and resources['ReadonlyRootfs'],'Runtime isolation differs')
 need(resources['Devices']==[{'PathOnHost':'/dev/kvm','PathInContainer':'/dev/kvm','CgroupPermissions':'rwm'}],'Unexpected runtime device')
 need('no-new-privileges' in resources['SecurityOpt'],'Missing privilege restriction')
 need(all(not m['RW'] or m['Destination']==str(RUN) for m in container['Mounts']),'Unexpected writable runtime mount')
 need(container['Config']['Cmd']==['python3','-B',str(LAUNCH/'boots.py')],'Unexpected container executable')
 sys.path.insert(0,str(SOURCE/'tools/testing/kunit'))
 import kunit_parser,kunit_json,kunit_printer
 gate=load('retained_original_gate',SOURCE/'rusix/scripts/validate-exit-mmap-kunit.py')
 modes=[('--exit-mmap-combined','retained-c-combined','exit-mmap-combined','rusix_*',79,True),('--exit-mmap','retained-c-isolated','exit-mmap','rusix_exit_mmap',3,False)]
 need(json.loads((RUN/'boots.json').read_text())==[{'mode':arg,'label':label,'exit':0} for arg,label,*_ in modes],'Wrong actual two-boot inventory')
 versions=[];counts={}
 for arg,label,mode,filt,count,combined in modes:
  logs=RUN/'logs';boot=logs/(label+'-boot.run')
  need((RUN/(label+'-runner.exit')).read_text().strip()=='0','Boot runner failed')
  need(json.loads((RUN/(label+'-argv.json')).read_text())==['bash',str(SOURCE/'rusix/scripts/boot-kunit.sh'),arg,str(BUILD),label],'Unexpected boot script invocation')
  need((boot/'mode.txt').read_text().strip()==mode,'Wrong boot mode')
  for stage in ('qemu','parse','gate'):need((logs/f'{label}-{stage}.exit').read_text().strip()=='0','KUnit stage failure: '+stage)
  text=(logs/f'{label}-console.log').read_text()
  need(not re.search(r'\b(WARNING|BUG)\b|Oops:|Kernel panic|CPU feature dependency check failure|ACPI (?:BIOS )?(?:Error|Exception|Warning)|ACPI: Unable to load',text),'Console diagnostic')
  fresh_test=kunit_parser.parse_run_tests(text.splitlines(),kunit_printer.null_printer)
  fresh=json.loads(kunit_json.get_json_result(test=fresh_test,metadata=kunit_json.Metadata()))
  saved=json.loads((logs/f'{label}-kunit.json').read_text());need(fresh==saved,'Actual console parse differs from retained JSON')
  need(gate.validate(fresh,combined)==count,'Wrong actual exact required count')
  need((logs/f'{label}-gate.log').read_text()==f'mapping teardown KUnit acceptance passed: {count} required cases, all PASS\n','Wrong retained gate result')
  command=['bash',str(SOURCE/'rusix/scripts/with-local-tools.sh'),'timeout','--kill-after=5s','180s','qemu-system-x86_64','-machine','q35','-accel','kvm','-cpu','qemu64','-m','512M','-smp','2','-display','none','-serial','stdio','-monitor','none','-nic','none','-no-reboot','-kernel',str(BUILD/'arch/x86/boot/bzImage'),'-append',f'console=ttyS0 kunit.enable=1 kunit.autorun=1 kunit.filter_glob={filt} kunit_shutdown=reboot panic=-1']
  need(shlex.split((boot/'command.sh').read_text())==command,'QEMU resource/filter/kernel command differs')
  hashes(logs/f'{label}-inputs.sha256',[BUILD/'arch/x86/boot/bzImage',BUILD/'.config'])
  hashes(boot/'scripts.sha256',[SOURCE/'rusix/scripts'/n for n in ('boot-kunit.sh','validate-exit-mmap-kunit.py','validate-brd-kunit.py','validate-completion-kunit.py')])
  version=(boot/'qemu-version.txt').read_text();need(bool(version),'Missing QEMU identity');versions.append(version);counts[mode]=count
 need(versions[0]==versions[1],'QEMU identity changed between boots')
 need(before=={str(p.relative_to(RUN)):sha(p) for p in sorted(RUN.rglob('*')) if p.is_file()},'Runtime records changed during validation')
 need(load('retained_original_inputs_after',LAUNCH/'check.py').check()==prereq,'Source/artifacts changed during validation')
 return {'status':'PASS','kernel_source':EXPECTED,'checker_fix_commit':'13e0ddc71a57d7576e9cc6f34603bd96d5bbfa08','counts':counts,'runtime_record_sha256':before,'source_and_objects':prereq,'kernel_sha256':sha(BUILD/'arch/x86/boot/bzImage'),'config_sha256':sha(BUILD/'.config'),'qemu_version':versions[0],'scope':'Actual retained original-C KUnit79+3 runtime only; no new fixed-source build, no Rust teardown KUnit result; original matrix remains failed'}
if __name__=='__main__':print(json.dumps(validate(),indent=2,sort_keys=True))
