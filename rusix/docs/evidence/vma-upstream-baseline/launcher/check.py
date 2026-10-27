#!/usr/bin/env python3
"""Read-only input/result checks; never executes the upstream test binary."""
from pathlib import Path
import argparse,hashlib,json,re,stat,shlex
BASE=Path('/home/aaron/code/rusix')
RUN=BASE/'linux-out/vma-upstream-baseline-001'
IMAGE='sha256:3cb67848e1aad76fb1451ebd3b1952961ee9665f73620d4ca8a467aa5e5eb55e'
SOURCE='2926d88bb7fc4608fd942453d929c39e4e5ec006'
MANIFEST='951c7bd0d8c0faab72e8c0f3d714b41ca1131a5dbb6481bb9e8a727bfadff0a3'
CASES=('simple_merge','simple_modify','simple_expand','simple_shrink','merge_new','vma_merge_special_flags','vma_merge_with_close','vma_merge_new_with_close','merge_existing','anon_vma_non_mergeable','dup_anon_vma','vmi_prealloc_fail','merge_extend','copy_vma','expand_only_mode','mmap_region_basic')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
OVERRIDES=('CFLAGS','CPPFLAGS','LDFLAGS','EXTRA_CFLAGS','MAKEFLAGS','MFLAGS','SHIFT','LONG_BIT','BUILD','CC','CXX','LD_LIBRARY_PATH','ASAN_OPTIONS','UBSAN_OPTIONS','LSAN_OPTIONS','LD_PRELOAD')
COMMANDS=[('build',['timeout','--kill-after=5s','600s','make','-C','tools/testing/vma','-j2','CC=gcc']),('test',['timeout','--kill-after=5s','120s','./tools/testing/vma/vma'])]
def tree_records(tree):
 records={}
 for p in tree.rglob('*'):
  name=str(p.relative_to(tree))
  if p.is_symlink():records[name]={'type':'symlink','target':str(p.readlink())}
  elif p.is_file():records[name]={'type':'file','sha256':sha(p),'mode':stat.S_IMODE(p.stat().st_mode)}
  elif not p.is_dir():raise ValueError('Unexpected special file: '+name)
 return records

def built_tree(tree,m):
 records=tree_records(tree)
 for name,item in m['files'].items():
  if records.get(name)!=item:raise ValueError('Build changed original source/type/mode: '+name)
 return {name:item for name,item in records.items() if name not in m['files']}

def inputs(root):
 manifest=root/'manifest.json'
 if sha(manifest)!=MANIFEST:raise ValueError('Prepared manifest changed')
 m=json.loads(manifest.read_text());tree=root/'tree'
 tooling=Path('/tooling') if root==Path('/inputs') else BASE/'linux-out/vma-tooling-001'
 for name,value in m['tooling_provenance_sha256'].items():
  if sha(tooling/name)!=value:raise ValueError('Tooling provenance changed: '+name)
 if m['source']!=SOURCE or m['image']!=IMAGE:raise ValueError('Source/image differs')
 if sha(root/'upstream.tar')!=m['archive_sha256']:raise ValueError('Archive changed')
 present={str(p.relative_to(tree)) for p in tree.rglob('*') if not p.is_dir() or p.is_symlink()}
 if present!=set(m['files']):raise ValueError('Copied input inventory differs')
 for name,item in m['files'].items():
  p=tree/name
  if item['type']=='file':
   if p.is_symlink() or not p.is_file() or sha(p)!=item['sha256'] or stat.S_IMODE(p.stat().st_mode)!=item['mode']:raise ValueError('Input changed: '+name)
  elif not p.is_symlink() or str(p.readlink())!=item['target']:raise ValueError('Symlink changed')
 text=(tree/'tools/testing/vma/vma.c').read_text();main=text[text.index('int main(void)'):]
 if tuple(re.findall(r'^\s*TEST\((\w+)\);',main,re.M))!=CASES:raise ValueError('Literal upstream inventory changed')
 return m

def results(root,prepared):
 inputs(prepared)
 for name in ('container.exit','build.exit','test.exit'):
  if (root/name).read_text().strip()!='0':raise ValueError('Failed '+name)
 stdout=(root/'test.stdout').read_text();stderr=(root/'test.stderr').read_text();build=(root/'build.log').read_text()
 if re.findall(r'^\d+ tests run, \d+ passed, \d+ failed\.$',stdout,re.M)!=['16 tests run, 16 passed, 0 failed.']:raise ValueError('Wrong/missing/duplicate aggregate')
 if stderr or re.search(r'warning:|error:|Assert FAILED|Test .* FAILED|AddressSanitizer|LeakSanitizer|UndefinedBehaviorSanitizer|runtime error:',stdout+'\n'+build,re.I):raise ValueError('Diagnostics require review')
 record=json.loads((root/'result.json').read_text())
 if record['source']!=SOURCE or record['image']!=IMAGE or record['cases']!=list(CASES) or record['binary_sha256']!=sha(root/'tree/tools/testing/vma/vma'):raise ValueError('Execution artifact identity changed')
 if (root/'image-id.txt').read_text().strip()!=IMAGE:raise ValueError('Wrong image record')
 if (root/'packages.lock').read_bytes()!=(BASE/'linux-out/vma-tooling-001/packages.lock').read_bytes():raise ValueError('Tool package inventory differs')
 for name,cmd in COMMANDS:
  if (root/(name+'-command.sh')).read_text()!=shlex.join(cmd)+'\n':raise ValueError('Command changed')
 env=json.loads((root/'build-environment.json').read_text())
 if env!={name:None for name in OVERRIDES}:raise ValueError('Build environment override')
 if built_tree(root/'tree',inputs(prepared))!=record['generated_artifacts']:raise ValueError('Generated artifact inventory/content changed')
 return dict(status='PASS',source=SOURCE,tests=16,scope='Pristine upstream C userspace VMA harness with ASan/UBSan; no Rust/kernel runtime proof')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--results',action='store_true');args=p.parse_args()
 print(json.dumps(results(RUN/'execution',RUN/'inputs') if args.results else dict(status='PREPARED_NOT_RUN',files=len(inputs(RUN/'inputs')['files'])),indent=2))
