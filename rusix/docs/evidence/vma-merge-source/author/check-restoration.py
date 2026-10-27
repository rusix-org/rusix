from pathlib import Path
import re,subprocess,hashlib,json
s=Path('/home/aaron/code/rusix/linux-mm-vma-merge');p=s/'mm/vma.c';t=p.read_text();before=t
while True:
 m=re.search(r'^#if(n?def) CONFIG_RUSIX_VMA_MERGE_RUST\n',t,re.M)
 if not m:break
 depth=1; outer_else=None
 for directive in re.finditer(r'^#(if(?:def|ndef)?|else|endif)\b[^\n]*\n',t[m.end():],re.M):
  kind=directive[1]
  if kind.startswith('if'):depth+=1
  elif kind=='endif':
   depth-=1
   if depth==0:
    end=m.end()+directive.start();endline=m.end()+directive.end();break
  elif kind=='else' and depth==1:outer_else=m.end()+directive.end()
 body=t[m.end():end]
 if m[1]=='ndef':replacement=body
 elif outer_else is not None:replacement=t[outer_else:end]
 else:replacement=''
 t=t[:m.start()]+replacement+t[endline:]
t=t.replace('#include "vma.h"\n\n\n','#include "vma.h"\n\n',1)
assert t.endswith('\n\n');t=t[:-1]
base=subprocess.check_output(['git','-C',str(s),'show','HEAD:mm/vma.c']).decode();assert t==base
out=Path(__file__).parent;records=json.loads((out/'baseline-functions.json').read_text())
for n,r in records.items():assert r['body'] in before,n
r={'status':'PASS','source':'f70b5bc41e8f31e93dd4fb04e4559dced57de0c0','restored_mm_vma_sha256':hashlib.sha256(t.encode()).hexdigest(),'exact_functions':{n:r['sha256'] for n,r in records.items()},'scope':'textual restoration only; no preprocessing or compilation'}
(out/'restoration.json').write_text(json.dumps(r,indent=2)+'\n');print('17 original bodies + full mm/vma.c restoration PASS')
