from pathlib import Path
import subprocess,hashlib,json,re
B=Path('/home/aaron/code/rusix');R=B/'linux-mm-vma-merge';O=Path(__file__).resolve().parent
BASE='f70b5bc41e8f31e93dd4fb04e4559dced57de0c0'
text=(R/'mm/vma.c').read_text()
for name in ('vma_merge.h','vma_merge_impl.h'):
 block='\n#ifdef CONFIG_RUSIX_VMA_MERGE_RUST\n#include "'+name+'"\n#endif\n'
 assert text.count(block)==1
 text=text.replace(block,'')
lines=text.splitlines(keepends=True);count=0
# Evaluate only the newly introduced merge selector, retaining every byte of
# unrelated conditionals, comments and baseline native policy.
def restore(lines):
 global count
 out=[];i=0
 while i<len(lines):
  m=re.fullmatch(r'#(ifdef|ifndef) CONFIG_RUSIX_VMA_MERGE_RUST\n',lines[i])
  if not m:out.append(lines[i]);i+=1;continue
  count+=1;start=i+1;j=start;depth=1;otherwise=None
  while depth:
   line=lines[j]
   if re.match(r'#\s*(?:if|ifdef|ifndef)\b',line):depth+=1
   elif re.match(r'#\s*endif\b',line):depth-=1
   elif re.match(r'#\s*else\b',line) and depth==1:otherwise=j
   j+=1
  end=j-1
  selected=lines[start:otherwise if otherwise is not None else end] if m[1]=='ifndef' else (lines[otherwise+1:end] if otherwise is not None else [])
  out.extend(restore(selected));i=j
 return out
actual=''.join(restore(lines)).encode();expected=subprocess.check_output(['git','-C',str(R),'show',BASE+':mm/vma.c']);assert actual==expected
files=['MAINTAINERS','init/Kconfig','mm/Makefile','mm/vma.c','mm/vma_merge.h','mm/vma_merge_impl.h','mm/vma_merge_rust.rs','rusix/PROGRESS.md','rusix/experiments/vma-merge/README.md']
hashes={n:hashlib.sha256((R/n).read_bytes()).hexdigest() for n in files}
rust=(R/'mm/vma_merge_rust.rs').read_text();native=(R/'mm/vma_merge_impl.h').read_text();links=re.findall(r'#\[link_name = "([^"]+)"\]',rust);new=[n for n in links if n.startswith('rusix_merge_')];entries=re.findall(r'pub unsafe extern "C" fn (rusix_merge_\w+)',rust)
assert len(new)==48 and len(entries)==6 and len(links)==81
assert len(re.findall(r'^(?:pub )?unsafe (?:extern "C" )?fn ',rust,re.M))==17
assert not any(n in native for n in ['commit_merge(', 'vma_expand(', 'vma_merge_existing_range('])
result={'status':'PASS source restoration/inventory','base':BASE,'restored_vma_sha256':hashlib.sha256(actual).hexdigest(),'merge_conditionals':count,'whole_policies':17,'native_entry_wrappers':6,'new_primitives':42,'new_constants':6,'reused_functions':31,'reused_constants':2,'source_sha256':hashes,'scope':'Source-only independent review; no build or runtime claim'}
(O/'source-check.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
