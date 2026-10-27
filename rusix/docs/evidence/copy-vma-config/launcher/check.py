#!/usr/bin/env python3
"""Configuration-only check of an immutable reviewed source snapshot."""
import hashlib,importlib.util,json,os,re,subprocess,sys
from pathlib import Path
SOURCE=Path('/src');OUT=Path('/out')
PROFILES=('copy-vma-c','copy-vma-rust')

def digest(path):
 with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def inputs():
 result={}
 for p in sorted(SOURCE.rglob('*')):
  if p.is_symlink():result[str(p.relative_to(SOURCE))]={'symlink':os.readlink(p)}
  elif p.is_file():result[str(p.relative_to(SOURCE))]={'sha256':digest(p),'mode':p.stat().st_mode&0o777}
 return result

def main():
 source=os.environ.get('RUSIX_CONFIG_SOURCE','')
 overrides=('MAKEFLAGS','MFLAGS','CC','HOSTCC','HOSTCFLAGS','HOSTLDFLAGS','LLVM','LLVM_IAS','ARCH','CROSS_COMPILE','KCONFIG_CONFIG','KCONFIG_ALLCONFIG')
 environment={key:os.environ.get(key) for key in (*overrides,'PATH','TMPDIR','RUSIX_CONFIG_SOURCE')}
 (OUT/'environment.json').write_text(json.dumps(environment,indent=2,sort_keys=True)+'\n')
 if any(environment[key] for key in overrides):raise ValueError('Unexpected build environment override')
 if not re.fullmatch('[0-9a-f]{40}',source):raise ValueError('Missing reviewed immutable source identity')
 sys.path.insert(0,str(SOURCE/'rusix/scripts'))
 spec=importlib.util.spec_from_file_location('gate',SOURCE/'rusix/scripts/verify-copy-vma.py')
 gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
 if set(gate.PROFILES)!=set(PROFILES):raise ValueError("Wrong configuration validator/profile inventory")
 spec_archive=importlib.util.spec_from_file_location('archive_inputs','/check/archive-inputs.py')
 archive_inputs=importlib.util.module_from_spec(spec_archive);spec_archive.loader.exec_module(archive_inputs)
 archive_record=json.loads(Path('/archive-inputs.json').read_text())
 archive_inputs.verify(SOURCE,archive_record['members'])
 before=inputs();(OUT/'inputs-before.json').write_text(json.dumps(before,indent=2,sort_keys=True)+'\n')
 configs={};commands={};requested={}
 target=gate.config_values((SOURCE/'rusix/configs/x86_64-server.config').read_text())
 for profile in PROFILES:
  build=OUT/profile;build.mkdir();fragment=SOURCE/f'rusix/configs/x86_64-{profile}.config'
  cmd=['make','-C',str(SOURCE),'O='+str(build),'LLVM=1','KCONFIG_ALLCONFIG='+str(fragment),'allnoconfig'];commands[profile]=cmd
  with (OUT/(profile+'.log')).open('x') as log:r=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT)
  (OUT/(profile+'.exit')).write_text(str(r.returncode)+'\n');r.check_returncode()
  if re.search(r'warning:|error:',(OUT/(profile+'.log')).read_text(),re.I):raise ValueError('Configuration diagnostic')
  values=gate.config_values((build/'.config').read_text());wants=gate.config_values(fragment.read_text());requested[profile]=wants
  for name,value in wants.items():
   if values.get(name,'n')!=value:raise ValueError(f'{profile}: requested {name}={value}, got {values.get(name,"n")}')
  if values.get('CONFIG_KUNIT','n')!='n':raise ValueError('Ordinary profiles must disable KUnit')
  if values.get('CONFIG_MEMFD_CREATE')!='y':raise ValueError('Native shmem test requires MEMFD_CREATE')
  if any(key.startswith('CONFIG_RUSIX_') and key.endswith('_TEST') and value!='n' for key,value in values.items()):raise ValueError('Unrelated fixture selected')
  gate.check_config(profile,values,target);configs[profile]=values
 pairs={'ordinary':gate.compare(configs['copy-vma-c'],configs['copy-vma-rust'])}
 archive_inputs.verify(SOURCE,archive_record['members'])
 after=inputs();(OUT/'inputs-after.json').write_text(json.dumps(after,indent=2,sort_keys=True)+'\n')
 if before!=after:raise ValueError('Immutable source changed')
 record={'status':'PASS','source':source,'scope':'Actual Kconfig resolution only; host config utilities, no kernel/guest compilation or VM',
         'environment_sha256':digest(OUT/'environment.json'),'source_archive_sha256':archive_record['archive_sha256'],'archive_inventory_sha256':digest(Path('/archive-inputs.json')),'commands':commands,'requested':requested,'selector_pairs':pairs,
         'config_sha256':{p:digest(OUT/p/'.config') for p in PROFILES},'source_input_count':len(before),
         'inputs_before_sha256':digest(OUT/'inputs-before.json'),'inputs_after_sha256':digest(OUT/'inputs-after.json')}
 (OUT/'result.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')

if __name__=='__main__':main()
