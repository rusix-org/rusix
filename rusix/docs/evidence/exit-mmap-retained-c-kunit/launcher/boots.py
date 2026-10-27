#!/usr/bin/env python3
import json,os,subprocess
from pathlib import Path
from check import check,SOURCE,RAW,DRAFT,IMAGE
OUT=Path(os.environ['RUSIX_OUTPUT_ROOT'])
assert os.environ['RUSIX_PINNED_POSTCHECK_IMAGE']==IMAGE
status=1
try:
 (OUT/'prerequisite-before.json').write_text(json.dumps(check(),indent=2)+'\n')
 records=[]
 for mode,label in [('--exit-mmap-combined','retained-c-combined'),('--exit-mmap','retained-c-isolated')]:
  argv=['bash',str(SOURCE/'rusix/scripts/boot-kunit.sh'),mode,str(RAW/'builds/ci-exit-mmap-kunit-c'),label]
  (OUT/(label+'-argv.json')).write_text(json.dumps(argv)+'\n')
  with (OUT/(label+'-runner.log')).open('w') as log:r=subprocess.run(argv,stdout=log,stderr=subprocess.STDOUT)
  (OUT/(label+'-runner.exit')).write_text(str(r.returncode)+'\n')
  records.append({'mode':mode,'label':label,'exit':r.returncode})
  (OUT/'boots.json').write_text(json.dumps(records,indent=2)+'\n')
  if r.returncode:raise RuntimeError('Strict native boot/parser/gate failed: '+label)
 status=0
finally:
 (OUT/'prerequisite-after.json').write_text(json.dumps(check(),indent=2)+'\n')
 (OUT/'boots.exit').write_text(str(status)+'\n')
