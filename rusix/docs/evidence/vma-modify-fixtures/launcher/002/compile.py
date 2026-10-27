#!/usr/bin/env python3
"""Compile/inspect only. NEVER execute init, probe or any native test binary."""
import hashlib,json,re,shlex,subprocess
from pathlib import Path
SRC=Path('/source');FIX=Path('/fixture');OUT=Path('/out');E=OUT/'evidence';A=OUT/'artifacts'
def sha(path):
 with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def command(label,argv,*,quiet=True):
 (E/(label+'-command.json')).write_text(json.dumps(argv)+'\n')
 result=subprocess.run(argv,capture_output=True,text=True)
 (E/(label+'.stdout')).write_text(result.stdout);(E/(label+'.stderr')).write_text(result.stderr);(E/(label+'.exit')).write_text(str(result.returncode)+'\n')
 for name in ('init','probe'):
  if (A/name).exists():(A/name).chmod(0o644)
 if result.returncode or result.stderr or (quiet and result.stdout):raise ValueError('Command failed or emitted diagnostics: '+label)
 return result.stdout

def main():
 review=json.loads((FIX/'fixture-review.json').read_text())
 before={str(SRC/n):sha(SRC/n) for n in review['native_sha256']}
 before.update({str(FIX/n):sha(FIX/n) for n in review['fixture_sha256']})
 if {n:sha(SRC/n) for n in review['native_sha256']}!=review['native_sha256']:raise ValueError('Native source drift')
 if {n:sha(FIX/n) for n in review['fixture_sha256']}!=review['fixture_sha256']:raise ValueError('Fixture snapshot drift')
 (E/'inputs-before.json').write_text(json.dumps(before,indent=2,sort_keys=True)+'\n')
 for name,argv in [('rustc',['/usr/bin/rustc','--version','--verbose']),('gcc',['/usr/bin/gcc','--version']),('readelf',['/usr/bin/readelf','--version']),('packages',['/usr/bin/dpkg-query','-W','-f=${binary:Package}\t${Version}\n'])]:command(name+'-version',argv,quiet=False)
 for name in ('packages.lock','toolchain.log'):(E/name).write_bytes((Path('/opt/rusix')/name).read_bytes())
 rustlib=Path(command('rust-target-libdir',['/usr/bin/rustc','--target','x86_64-unknown-linux-gnu','--print','target-libdir'],quiet=False).strip())
 (E/'rust-library-inputs.json').write_text(json.dumps({str(p):sha(p) for p in sorted(rustlib.iterdir()) if p.is_file()},indent=2,sort_keys=True)+'\n')
 dependencies={};objects=[]
 for name in ('merge','vm_util','thp_settings'):
  source=SRC/'tools/testing/selftests/mm'/(name+'.c');obj=A/(name+'.o');dep=E/(name+'.d');objects.append(obj)
  argv=['/usr/bin/gcc','-std=gnu11','-O2','-Wall','-Wunreachable-code','-U_FORTIFY_SOURCE','-Werror','-MD','-MF',str(dep),'-MT',str(obj),'-c',str(source),'-o',str(obj)]
  command(name+'-compile',argv)
  text=dep.read_text().replace('\\\n',' ');target,body=text.split(':',1)
  if target!=str(obj):raise ValueError('Wrong dependency target')
  paths=shlex.split(body)
  if not paths or str(source) not in paths:raise ValueError('Native dependency inventory incomplete')
  for value in paths:
   p=Path(value)
   if not p.is_absolute() or '..' in p.parts:
    # GCC may spell relative header includes with ..; resolve without executing.
    p=p.resolve(strict=True)
   dependencies[value]={'resolved':str(p.resolve(strict=True)),'sha256':sha(p),'bytes':p.stat().st_size}
 (E/'native-header-inputs.json').write_text(json.dumps(dependencies,indent=2,sort_keys=True)+'\n')
 command('probe-link',['/usr/bin/gcc','-static',*[str(p) for p in objects],'-lrt','-lpthread','-lm','-Wl,-t','-o',str(A/'probe')],quiet=False)
 command('init-compile',['/usr/bin/rustc','--edition','2021','--target','x86_64-unknown-linux-gnu','-C','target-feature=+crt-static','-C','panic=abort','-C','opt-level=2',str(FIX/'rusix/tests/vma-modify/init.rs'),'-o',str(A/'init')])
 artifacts={}
 for name in ('init','probe'):
  binary=A/name;binary.chmod(0o644)
  output=command(name+'-readelf',['/usr/bin/readelf','-h','-l','-d','--wide',str(binary)],quiet=False)
  if 'ELF64' not in output or 'Advanced Micro Devices X86-64' not in output or 'INTERP' in output or '(NEEDED)' in output:raise ValueError('Expected static x86-64 ELF')
  artifacts[name]={'sha256':sha(binary),'bytes':binary.stat().st_size,'mode':oct(binary.stat().st_mode&0o777),'executed':False}
 after={name:sha(Path(name)) for name in before}
 (E/'inputs-after.json').write_text(json.dumps(after,indent=2,sort_keys=True)+'\n')
 if after!=before:raise ValueError('Inputs changed during compilation')
 for name,record in dependencies.items():
  if sha(Path(record['resolved']))!=record['sha256']:raise ValueError('Native header dependency changed')
 (E/'result.json').write_text(json.dumps(dict(status='PASS',native_source=review['native_source'],baseline=review['baseline'],fixture_sha256=review['fixture_sha256'],artifacts=artifacts,scope='Static compilation and readelf inspection only; neither binary executed; no kernel or VM'),indent=2)+'\n')
 print('Both guest fixtures compiled and inspected; never executed',flush=True)
if __name__=='__main__':main()
