import hashlib,json,re,subprocess
from pathlib import Path
root=Path('/home/aaron/code/rusix/linux-mm-vma-modify');out=Path(__file__).parent
base='99fd3dd96ac0b6131c34501dff9626e95b063037';pinned='2926d88bb7fc4608fd942453d929c39e4e5ec006'
def sha(x):return hashlib.sha256(x).hexdigest()
def blob(rev,path):return subprocess.check_output(['git','-C',str(root),'show',rev+':'+path])
text=(root/'mm/vma.c').read_text()
for include in ('vma_modify.h','vma_modify_impl.h'):
 block='#ifdef CONFIG_RUSIX_VMA_MODIFY_RUST\n#include "'+include+'"\n#endif\n'
 assert text.count(block)==1
 text=text.replace(block+'\n','',1) if include=='vma_modify.h' else text.removesuffix('\n'+block)
lines=text.splitlines(keepends=True); restored=[];i=0;regions=0
while i<len(lines):
 s=lines[i].strip()
 if s in ('#ifdef CONFIG_RUSIX_VMA_MODIFY_RUST','#ifndef CONFIG_RUSIX_VMA_MODIFY_RUST'):
  regions+=1; negative='ifndef' in s; depth=1;j=i+1;mid=None
  while depth:
   v=lines[j].strip()
   if re.match(r'#\s*if(?:def|ndef)?\b',v):depth+=1
   elif v.startswith('#endif'):depth-=1
   elif v=='#else' and depth==1:mid=j
   if depth:j+=1
  assert lines[j].strip()=='#endif /* CONFIG_RUSIX_VMA_MODIFY_RUST */'
  if negative:assert mid is None;restored+=lines[i+1:j]
  else:assert mid is not None;restored+=lines[mid+1:j]
  i=j+1
 else:restored.append(lines[i]);i+=1
raw=''.join(restored).encode();assert raw==blob(base,'mm/vma.c');assert regions==11
names=('init_multi_vma_prep','init_vma_prep','vma_prepare','vma_complete','__split_vma','split_vma','vma_modify','vma_modify_flags','vma_modify_name','vma_modify_policy','vma_modify_flags_uffd')
def body(data,name):
 matches=list(re.finditer(r'\b'+name+r'\s*\([^;{}]*\)\s*\{',data))
 assert len(matches)==1,(name,len(matches))
 m=matches[0];start=m.end()-1;depth=1;j=start+1
 while depth:
  if data[j]=='{':depth+=1
  elif data[j]=='}':depth-=1
  j+=1
 return data[m.start():j].encode()
original=raw.decode(); old=blob(pinned,'mm/vma.c').decode()
functions={}
for n in names:
 b=body(original,n);assert b==body(old,n),n;functions[n]=sha(b)
files=['mm/vma.c','mm/vma_modify.h','mm/vma_modify_impl.h','mm/vma_modify_rust.rs','init/Kconfig','mm/Makefile','mm/vma.h','mm/vma_internal.h','mm/copy_vma_impl.h','mm/remove_vma_impl.h','mm/rmap.c','include/linux/mm_types.h','rust/Makefile']
record={'status':'SOURCE_REVIEW_NO_BLOCKER','base':base,'pinned_baseline':pinned,'exact_vma_c_restoration_sha256':sha(raw),'guarded_policy_regions':regions,'eleven_function_identity_to_pinned':functions,'source_sha256':{p:sha((root/p).read_bytes()) for p in files},'scope':'Read-only independent source review. No compiler, actual ELF, Kconfig resolution, guest, concurrency or failure-injection execution.'}
(out/'review.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps({'restoration':'PASS','policies':len(functions),'scope':record['scope']},indent=2))
