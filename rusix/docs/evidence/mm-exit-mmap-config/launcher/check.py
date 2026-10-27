#!/usr/bin/env python3
"""Configuration-only check of an immutable reviewed source snapshot."""
import hashlib,importlib.util,json,os,re,subprocess,sys
from pathlib import Path
SOURCE=Path('/src');OUT=Path('/out')
PROFILES=('exit-mmap-c','exit-mmap-rust','exit-mmap-kunit-c','exit-mmap-kunit-rust')
EXPECTED_DELTA={
 'CONFIG_KUNIT':('n','y'), 'CONFIG_RUNTIME_TESTING_MENU':('n','y'),
 'CONFIG_KUNIT_DEFAULT_ENABLED':('n','y'), 'CONFIG_KUNIT_AUTORUN_ENABLED':('n','y'),
 'CONFIG_KUNIT_DEFAULT_TIMEOUT':('n','300'), 'CONFIG_RUSIX_EXIT_MMAP_TEST':('n','y')}

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
 if not re.fullmatch('[0-9a-f]{40}',source):raise ValueError('Missing reviewed immutable source identity')
 sys.path.insert(0,str(SOURCE/'rusix/scripts'))
 spec=importlib.util.spec_from_file_location('gate',SOURCE/'rusix/scripts/verify-exit-mmap.py')
 gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
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
  if values.get('CONFIG_RUSIX_MM_RELEASE_TEST','n')!='n':raise ValueError('Unrelated release fixture selected')
  if values.get('CONFIG_KUNIT')!=('y' if '-kunit-' in profile else 'n'):raise ValueError('Wrong ordinary/KUnit selection')
  if values.get('CONFIG_RUSIX_EXIT_MMAP_TEST','n')!=('y' if '-kunit-' in profile else 'n'):raise ValueError('Wrong fixture selection')
  gate.check_config(profile,values,target);configs[profile]=values
 pairs={kind:gate.compare(configs['exit-mmap-'+kind+'c'],configs['exit-mmap-'+kind+'rust']) for kind in ('','kunit-')}
 axes={}
 for side in ('c','rust'):
  a=configs['exit-mmap-'+side];b=configs['exit-mmap-kunit-'+side]
  delta={k:(a.get(k,'n'),b.get(k,'n')) for k in a.keys()|b.keys() if a.get(k,'n')!=b.get(k,'n')}
  if delta!=EXPECTED_DELTA:raise ValueError('Unexpected ordinary/KUnit resolved delta: '+repr(delta))
  axes[side]=delta
 archive_inputs.verify(SOURCE,archive_record['members'])
 after=inputs();(OUT/'inputs-after.json').write_text(json.dumps(after,indent=2,sort_keys=True)+'\n')
 if before!=after:raise ValueError('Immutable source changed')
 record={'status':'PASS','source':source,'scope':'Actual Kconfig resolution only; host config utilities, no kernel/guest compilation or VM',
         'source_archive_sha256':archive_record['archive_sha256'],'archive_inventory_sha256':digest(Path('/archive-inputs.json')),'commands':commands,'requested':requested,'selector_pairs':pairs,'ordinary_kunit_delta':axes,
         'config_sha256':{p:digest(OUT/p/'.config') for p in PROFILES},'source_input_count':len(before),
         'inputs_before_sha256':digest(OUT/'inputs-before.json'),'inputs_after_sha256':digest(OUT/'inputs-after.json')}
 (OUT/'result.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')

if __name__=='__main__':main()
