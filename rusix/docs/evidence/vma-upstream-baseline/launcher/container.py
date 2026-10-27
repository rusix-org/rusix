#!/usr/bin/env python3
"""Run only the pristine upstream userspace harness inside the pinned container."""
import json,os,shlex,shutil,subprocess,time
from pathlib import Path
from check import inputs,sha,CASES,SOURCE,IMAGE,OVERRIDES,COMMANDS,built_tree

def main():
 if os.environ.get('RUSIX_VMA_BASELINE_IMAGE')!=IMAGE or not Path('/inputs/manifest.json').is_file():raise ValueError('Pinned container/input guard absent')
 env={name:os.environ.get(name) for name in OVERRIDES}
 if any(value is not None for value in env.values()):raise ValueError('Unexpected build/sanitizer override: '+repr(env))
 Path('/out/build-environment.json').write_text(json.dumps(env,indent=2)+'\n')
 out=Path('/out');m=inputs(Path('/inputs'))
 if (out/'tree').exists():raise ValueError('Fresh build tree required')
 shutil.copytree('/inputs/tree',out/'tree',symlinks=True,copy_function=shutil.copy2)
 for name,cmd in [('gcc',['gcc','--version']),('make',['make','--version']),('liburcu',['pkg-config','--modversion','liburcu'])]:
  r=subprocess.run(cmd,capture_output=True,text=True);(out/(name+'-version.log')).write_text(r.stdout+r.stderr);r.check_returncode()
 packages=subprocess.check_output(['dpkg-query','-W','-f=${Package}\t${Version}\t${Architecture}\n'])
 packages=subprocess.check_output(['sort'],input=packages)
 (out/'packages.lock').write_bytes(packages)
 if packages!=Path('/tooling/packages.lock').read_bytes():raise ValueError('Actual package inventory differs')
 for name,cmd in COMMANDS:
  (out/(name+'-command.sh')).write_text(shlex.join(cmd)+'\n')
  with (out/('build.log' if name=='build' else 'test.stdout')).open('wb') as log:
   if name=='build':r=subprocess.run(cmd,cwd=out/'tree',stdout=log,stderr=subprocess.STDOUT)
   else:
    with (out/'test.stderr').open('wb') as err:r=subprocess.run(cmd,cwd=out/'tree',stdout=log,stderr=err)
  (out/(name+'.exit')).write_text(str(r.returncode)+'\n');r.check_returncode()
 inputs(Path('/inputs'))
 artifacts=built_tree(out/'tree',m)
 (out/'result.json').write_text(json.dumps(dict(source=SOURCE,image=IMAGE,cases=list(CASES),binary_sha256=sha(out/'tree/tools/testing/vma/vma'),generated_artifacts=artifacts,sanitizers='Upstream ASan+UBSan flags and default runtime settings; no suppression'),indent=2)+'\n')
if __name__=='__main__':main()
