#!/usr/bin/env python3
"""Create a pristine tracked upstream copytree; never build or run its code."""
from pathlib import Path,PurePosixPath
import hashlib,json,posixpath,subprocess,tarfile,sys
BASE=Path('/home/aaron/code/rusix');REPO=BASE/'linux-mm-dup-mmap'
OUT=BASE/'linux-out/vma-upstream-baseline-001';DRAFT=BASE/'linux-out/vma-upstream-baseline-draft'
PINNED='2926d88bb7fc4608fd942453d929c39e4e5ec006';REVIEWED='9cf27ef36d1d58cb65bd866d9f046ed2e56b045a'
PATHS=['tools/testing/vma','tools/testing/shared','tools/include','tools/arch/x86/include','tools/lib','tools/scripts/Makefile.arch','include','lib','mm/vma.c','mm/vma_init.c','mm/vma_exec.c','mm/vma.h','mm/vma_internal.h']
EXACT=['tools/testing/vma','tools/testing/shared','mm/vma.c','mm/vma_init.c','mm/vma_exec.c','mm/vma.h','mm/vma_internal.h']
IMAGE='sha256:3cb67848e1aad76fb1451ebd3b1952961ee9665f73620d4ca8a467aa5e5eb55e'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def git(*args):return subprocess.check_output(['git','-C',str(REPO),*args])
def main():
 resume=sys.argv[1:]==['--resume-after-data-filter-mode-failure']
 if OUT.exists() and not (resume and (OUT/'preparation-failure.json').is_file() and not (OUT/'inputs/manifest.json').exists()):raise ValueError('Fresh input destination required')
 if git('rev-parse','HEAD').decode().strip()!=REVIEWED or git('status','--porcelain'):raise ValueError('Reviewed checkout changed')
 subprocess.run(['git','-C',str(REPO),'diff','--exit-code',PINNED,REVIEWED,'--',*EXACT],check=True)
 if not resume:OUT.mkdir()
 inputs=OUT/'inputs';archive=inputs/'upstream.tar';tree=inputs/'tree'
 if not resume:
  inputs.mkdir();tree.mkdir()
  subprocess.run(['git','-C',str(REPO),'archive','--format=tar','--output='+str(archive),PINNED,*PATHS],check=True)
 else:
  if hashlib.sha256(git('archive','--format=tar',PINNED,*PATHS)).hexdigest()!=sha(archive):raise ValueError('Partial archive differs from exact Git source')
 records={}
 with tarfile.open(archive) as tar:
  for member in tar.getmembers():
   path=PurePosixPath(member.name)
   if path.is_absolute() or '..' in path.parts:raise ValueError('Escaping archive path')
   if member.isdir():continue
   if member.isfile():
    data=tar.extractfile(member).read();records[member.name]=dict(type='file',mode=member.mode,sha256=hashlib.sha256(data).hexdigest())
   elif member.issym():
    target=posixpath.normpath(posixpath.join(str(path.parent),member.linkname))
    if member.linkname.startswith('/') or target=='..' or target.startswith('../'):raise ValueError('Escaping symlink')
    records[member.name]=dict(type='symlink',target=member.linkname)
   else:raise ValueError('Special archive member rejected')
  if not resume:tar.extractall(tree,filter='data')
 for name,item in records.items():
  p=tree/name
  if item['type']=='file':
   if p.is_symlink() or sha(p)!=item['sha256']:raise ValueError('Extracted input differs')
   # Restore only validated Git regular-file mode, after safe data extraction.
   p.chmod(item['mode'])
   if p.stat().st_mode&0o777!=item['mode']:raise ValueError('Input mode differs')
  elif not p.is_symlink() or str(p.readlink())!=item['target']:raise ValueError('Symlink differs')
  if p.is_symlink() and not p.resolve().is_relative_to(tree.resolve()):raise ValueError('Symlink leaves input tree')
 tools=BASE/'linux-out/vma-tooling-001';toolhash={str(p.relative_to(tools)):sha(p) for p in sorted(tools.iterdir()) if p.is_file()}
 if (tools/'image-id.txt').read_text().strip()!=IMAGE:raise ValueError('Tool image identity differs')
 result=dict(status='PREPARED_NOT_BUILT',source=PINNED,reviewed_branch_source=REVIEWED,image=IMAGE,archive_sha256=sha(archive),closure=PATHS,files=records,
             vma_shared_equality='git diff --exit-code pinned reviewed -- exact harness/shared/VMA paths: PASS',
             unrelated_branch_closure_delta=git('diff','--name-only',PINNED,REVIEWED,'--',*PATHS).decode().splitlines(),
             tooling_provenance_sha256=toolhash)
 (inputs/'manifest.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
 print(json.dumps({'status':result['status'],'files':len(records),'archive_bytes':archive.stat().st_size,'archive_sha256':result['archive_sha256'],'manifest_sha256':sha(inputs/'manifest.json')}))
if __name__=='__main__':main()
