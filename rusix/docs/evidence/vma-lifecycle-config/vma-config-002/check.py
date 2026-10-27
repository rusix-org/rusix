import hashlib,importlib.util,json,subprocess,sys
from pathlib import Path
root=Path('/src');out=Path('/out')
sys.path.insert(0,str(root/'rusix/scripts'))
spec=importlib.util.spec_from_file_location('gate',root/'rusix/scripts/verify-vma-lifecycle.py');g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
inputs=[root/'init/Kconfig',root/'rusix/scripts/verify-vma-lifecycle.py',root/'rusix/configs/x86_64-server.config']+[root/f'rusix/configs/x86_64-vma-lifecycle-{s}.config' for s in ('c','rust')]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
before={str(p):sha(p) for p in inputs};configs={};commands={}
for side in ('c','rust'):
 profile='vma-lifecycle-'+side;fragment=root/f'rusix/configs/x86_64-{profile}.config';build=out/side;build.mkdir()
 cmd=['make','-C',str(root),'O='+str(build),'LLVM=1','KCONFIG_ALLCONFIG='+str(fragment),'allnoconfig'];commands[side]=cmd
 r=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True);(out/(side+'.log')).write_text(r.stdout);(out/(side+'.exit')).write_text(str(r.returncode)+'\n');r.check_returncode()
 values=g.config_values((build/'.config').read_text());requested=g.config_values(fragment.read_text())
 for name,value in requested.items():
  assert values.get(name,'n')==value,(side,name,value,values.get(name))
 g.check_config(profile,values,g.config_values((root/'rusix/configs/x86_64-server.config').read_text()));configs[side]=values
changes=g.compare(configs['c'],configs['rust']);assert before=={str(p):sha(p) for p in inputs}
(out/'result.json').write_text(json.dumps(dict(status='PASS',source='7b07b88aa88ad6d5fceb61c875768c08a6417caf',scope='Actual Kconfig resolution only; no kernel compilation or guest execution',commands=commands,input_sha256=before,config_sha256={side:sha(out/side/'.config') for side in configs},different_settings=changes),indent=2)+'\n')
