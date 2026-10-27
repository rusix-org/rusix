from pathlib import Path
import re,json,hashlib
s=Path('/home/aaron/code/rusix/linux-mm-vma-merge');o=Path(__file__).parent;abi=json.loads((o/'abi.json').read_text());r=(s/'mm/vma_merge_rust.rs').read_text();h=(s/'mm/vma_merge.h').read_text();c=(s/'mm/vma_merge_impl.h').read_text()
all_impl='\n'.join(p.read_text() for p in (s/'mm').glob('*impl.h'))+(s/'mm/vma_modify.h').read_text()
for name,sym,ret,args,body in abi['new']+abi['reused']:
 assert f'#[link_name = "{sym}"]' in r,sym
 assert re.search(r'pub fn '+name+r'\(',r),name
 if any(sym==row[1] for row in abi['new']):assert sym in h and sym in c
 else:assert re.search(r'\b'+sym+r'\s*\(',all_impl),sym
assert len(re.findall(r'#\[unsafe\(no_mangle\)\]',r))==6
assert len(re.findall(r'^(?:pub )?unsafe (?:extern "C" )?fn ',r,re.M))==17
assert not re.search(r'\bstruct\s+\w+\s*\{',r)
# Textual selector projection only; never presented as actual compiler .i.
def selected(t,config):
 while True:
  m=re.search(r'^#if(n?def) '+config+r'\n',t,re.M)
  if not m:break
  depth=1;other=None
  for d in re.finditer(r'^#(if(?:def|ndef)?|else|endif)\b[^\n]*\n',t[m.end():],re.M):
   kind=d[1]
   if kind.startswith('if'):depth+=1
   elif kind=='endif':
    depth-=1
    if depth==0:end=m.end()+d.start();finish=m.end()+d.end();break
   elif kind=='else' and depth==1:other=(m.end()+d.start(),m.end()+d.end())
  body=t[m.end():end]
  if m[1]=='def':replace=t[m.end():other[0]] if other else body
  else:replace=t[other[1]:end] if other else ''
  t=t[:m.start()]+replace+t[finish:]
 return t
text=selected(selected((s/'mm/vma.c').read_text(),'CONFIG_RUSIX_VMA_MERGE_RUST'),'CONFIG_RUSIX_VMA_MODIFY_RUST')
removed=['vma_is_fork_child','is_mergeable_vma','is_mergeable_anon_vma','can_vma_merge_before','can_vma_merge_after','can_vma_merge_left','can_vma_merge_right','dup_anon_vma','vmg_adjust_set_range','commit_merge','can_merge_remove_vma','init_multi_vma_prep','init_vma_prep','vma_prepare','vma_complete']
for n in removed:assert not re.search(r'^static [^;{}]*\b'+n+r'\([^;{}]*\)\s*\{',text,re.M),n
files=['mm/vma.c','mm/vma_merge.h','mm/vma_merge_impl.h','mm/vma_merge_rust.rs','mm/Makefile','init/Kconfig','MAINTAINERS','rusix/experiments/vma-merge/README.md','rusix/PROGRESS.md']
result={'status':'PASS','scope':'static inventory/native symbol presence/textual selector projection only; not preprocessing or compiler typecheck','excluded_native_policies_and_redundant_wrappers':removed,'new_primitive_functions':42,'reused_functions':31,'new_constants':6,'reused_constants':2,'rust_entries':6,'rust_policies':17,'input_sha256':{f:hashlib.sha256((s/f).read_bytes()).hexdigest() for f in files}}
(o/'inventory-check.json').write_text(json.dumps(result,indent=2)+'\n');print('static inventory and selected native exclusions PASS')
