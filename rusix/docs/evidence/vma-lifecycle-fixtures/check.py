import hashlib,json,subprocess
from pathlib import Path
root=Path('/src');out=Path('/out');fixture=root/'rusix/tests/vma-lifecycle'
files=[fixture/n for n in ('init.rs','probe.c','README.md')]
hashfile=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
before={str(p):hashfile(p) for p in files};commands={}
def run(name,cmd):
 commands[name]=cmd;r=subprocess.run(cmd,capture_output=True,text=True)
 (out/(name+'.log')).write_text(r.stdout+r.stderr);(out/(name+'.exit')).write_text(str(r.returncode)+'\n')
 assert r.returncode==0,(name,r.returncode,r.stderr)
 if name.endswith("-compile"): assert not r.stdout and not r.stderr,(name,"unexpected diagnostics")
 return r.stdout
for name in ('rustc','gcc','readelf','objdump'):
 run(name+'-version',['/usr/bin/'+name,'--version'])
run('init-compile',['/usr/bin/rustc','--edition','2021','--target','x86_64-unknown-linux-gnu','-C','target-feature=+crt-static','-C','panic=abort','-C','opt-level=2',str(fixture/'init.rs'),'-o',str(out/'init')])
(out/'init').chmod(0o644)
run('probe-compile',['/usr/bin/gcc','-std=gnu11','-O2','-Wall','-Wextra','-Werror','-static',str(fixture/'probe.c'),'-o',str(out/'probe')])
(out/'probe').chmod(0o644)
for name in ('init','probe'):
 hdr=run(name+'-elf',['/usr/bin/readelf','-h','-l','-d',str(out/name)])
 assert 'Advanced Micro Devices X86-64' in hdr and 'INTERP' not in hdr and '(NEEDED)' not in hdr
run('child-disassembly',['/usr/bin/objdump','-d','--disassemble=shared_child',str(out/'probe')])
assert before=={str(p):hashfile(p) for p in files}
(out/'result.json').write_text(json.dumps({'status':'PASS','scope':'Pinned static guest compilation only; binaries never executed','source':'620b34e0c9181b1563fb2a7ba80766616afeb73b','image':'sha256:c02eb3929889b3f0cc035d57a02c844e0c74c71d24fbda1311249faeb8257f63','commands':commands,'sources':before,'artifacts':{name:hashfile(out/name) for name in ('init','probe')}},indent=2)+'\n')
print('Static VMA lifecycle fixtures compiled; not executed')
