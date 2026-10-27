import subprocess,json,hashlib,os
from pathlib import Path
source=Path('/source/rusix/tests/copy-vma');out=Path('/out');e=out/'evidence';a=out/'artifacts'
for name,args in [('rustc',['/usr/bin/rustc','--version','--verbose']),('gcc',['/usr/bin/gcc','--version']),('readelf',['/usr/bin/readelf','--version'])]:
 p=subprocess.run(args,capture_output=True,text=True);(e/(name+'-version.log')).write_text(p.stdout);(e/(name+'-version.stderr')).write_text(p.stderr);assert p.returncode==0 and not p.stderr
for name in ['init','probe']:
 if name=='probe':args=['/usr/bin/gcc','-std=gnu11','-O2','-Wall','-Wunreachable-code','-U_FORTIFY_SOURCE','-Werror','-static','/source/tools/testing/selftests/mm/mremap_dontunmap.c','-o',str(a/name)]
 else:args=['/usr/bin/rustc','--edition','2021','--target','x86_64-unknown-linux-gnu','-C','target-feature=+crt-static','-C','panic=abort','-C','opt-level=2',str(source/(name+'.rs')),'-o',str(a/name)]
 (e/(name+'-command.json')).write_text(json.dumps(args)+'\n');p=subprocess.run(args,capture_output=True,text=True);(e/(name+'-compile.log')).write_text(p.stdout+p.stderr);(e/(name+'-compile.exit')).write_text(str(p.returncode)+'\n')
 if (a/name).exists():(a/name).chmod(0o644)
 assert p.returncode==0 and not p.stdout and not p.stderr,'Compiler failure or diagnostics'
 args=['/usr/bin/readelf','-h','-l','-d','--wide',str(a/name)];(e/(name+'-readelf-command.json')).write_text(json.dumps(args)+'\n');p=subprocess.run(args,capture_output=True,text=True);(e/(name+'-readelf.log')).write_text(p.stdout);(e/(name+'-readelf.stderr')).write_text(p.stderr);(e/(name+'-readelf.exit')).write_text(str(p.returncode)+'\n');assert p.returncode==0 and not p.stderr
 assert 'ELF64' in p.stdout and 'Advanced Micro Devices X86-64' in p.stdout and 'INTERP' not in p.stdout and '(NEEDED)' not in p.stdout
 print(name+': compile and static ELF inspection PASS; never executed',flush=True)
