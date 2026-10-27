from pathlib import Path
import subprocess,hashlib,json,re
base=Path('/home/aaron/code/rusix');r=base/'linux-mm-vma-modify';out=base/'linux-out/mm-next-policy-scout-001';commit='99fd3dd96ac0b6131c34501dff9626e95b063037'
s=(r/'mm/vma.c').read_text();original=subprocess.check_output(['git','-C',str(r),'show',commit+':mm/vma.c'],text=True)
# Exact added includes are separate from body alternatives.
for block in ['\n#ifdef CONFIG_RUSIX_VMA_MODIFY_RUST\n#include "vma_modify.h"\n#endif\n','\n#ifdef CONFIG_RUSIX_VMA_MODIFY_RUST\n#include "vma_modify_impl.h"\n#endif\n']:
 assert s.count(block)==1;s=s.replace(block,'')
lines=s.splitlines(keepends=True);restored=[];selected=[];inside=False;keep=True;branches=0
for line in lines:
 if line in ['#ifdef CONFIG_RUSIX_VMA_MODIFY_RUST\n','#ifndef CONFIG_RUSIX_VMA_MODIFY_RUST\n']:
  assert not inside;inside=True;keep=line.startswith('#ifndef');branches+=1
 elif line=='#else\n' and inside:keep=not keep
 elif line=='#endif /* CONFIG_RUSIX_VMA_MODIFY_RUST */\n':assert inside;inside=False
 elif not inside or keep:restored.append(line)
assert not inside and branches==11
assert ''.join(restored)==original,'Native restoration differs'
new=(r/'mm/vma_modify_rust.rs').read_text();header=(r/'mm/vma_modify.h').read_text();impl=(r/'mm/vma_modify_impl.h').read_text()
helpers=re.findall(r'^\w[^\n]*\b(rusix_\w+)\([^;]*\)\n\{',impl,re.M)
assert len(helpers)==70 and len(set(helpers))==70
for name in helpers:
 assert len(re.findall(r'\b'+name+r'\(',header))==1,name
 assert len(re.findall(r'fn '+name+r'\(',new))==1,name
rust_entries=re.findall(r'pub unsafe extern "C" fn (\w+)\(',new)
assert len(rust_entries)==10 and len(set(rust_entries))==10
for name in rust_entries:
 if name!='split_vma':assert len(re.findall(r'\b'+name+r'\(',header))==1,name
assert 'unsafe fn modify(' in new
assert 'fn rusix_vma_close' not in new and 'fn rusix_remove_close' not in new
for p in [r/'mm/vma_modify.h',r/'mm/vma_modify_impl.h',r/'mm/vma_modify_rust.rs']:
 assert all(line.rstrip()==line for line in p.read_text().splitlines()),p
files=['MAINTAINERS','mm/vma.c','mm/vma_modify.h','mm/vma_modify_impl.h','mm/vma_modify_rust.rs','init/Kconfig','mm/Makefile']
record={'status':'SOURCE_CHECKS_PASS_NOT_COMPILED','source_base':commit,'native_vma_sha256':hashlib.sha256(original.encode()).hexdigest(),'native_body_alternatives':branches,'native_primitives':len(helpers),'rust_abi_entries':rust_entries,'private_rust_policy':'modify','candidate_sha256':{p:hashlib.sha256((r/p).read_bytes()).hexdigest() for p in files},'scope':'Exact eleven-guard C restoration, helper declaration/name inventory, callback-close omission, formatting whitespace; no compiler/object/runtime acceptance'}
(out/'implementation-source-review.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record,indent=2))
