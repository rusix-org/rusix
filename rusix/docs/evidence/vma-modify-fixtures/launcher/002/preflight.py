#!/usr/bin/env python3
"""Read-only frozen native source and fixture snapshot checks."""
import argparse,hashlib,json,subprocess
from pathlib import Path
BASE=Path('/home/aaron/code/rusix')
SOURCE=BASE/'linux-mm-copy-vma'
EXPECTED='99fd3dd96ac0b6131c34501dff9626e95b063037'
DRAFT=BASE/'linux-out/vma-modify-fixtures-compile-final-draft'
OUT=BASE/'linux-out/vma-modify-fixtures-compile-002'
IMAGE='sha256:c02eb3929889b3f0cc035d57a02c844e0c74c71d24fbda1311249faeb8257f63'
REVIEWED_LAUNCH_READY=True
def sha(path):
 with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--require-fresh',action='store_true');a=p.parse_args()
 if a.require_fresh:
  if not REVIEWED_LAUNCH_READY:raise ValueError('Root compile-only launcher review pending')
  if OUT.exists():raise ValueError('Fresh compile output required')
 git=lambda *args:subprocess.check_output(['git','-C',str(SOURCE),*args],text=True).strip()
 if git('rev-parse','HEAD')!=EXPECTED or git('status','--porcelain'):raise ValueError('Native source must remain exact clean99fd')
 review=json.loads((DRAFT/'fixture-review.json').read_text())
 if review['native_source']!=EXPECTED:raise ValueError('Native fixture attribution differs')
 for name,value in review['native_sha256'].items():
  if sha(SOURCE/name)!=value:raise ValueError('Native source changed: '+name)
 for name,value in review['fixture_sha256'].items():
  if sha(DRAFT/'fixture'/name)!=value:raise ValueError('Frozen fixture changed: '+name)
 print(json.dumps(dict(native_source=EXPECTED,native_tree=git('rev-parse','HEAD^{tree}'),image=IMAGE,native_sha256=review['native_sha256'],fixture_sha256=review['fixture_sha256'],fixture_review_sha256=sha(DRAFT/'fixture-review.json'),scope='Frozen native99fd and exact fixture snapshots; mutable production candidate never mounted'),indent=2,sort_keys=True))
if __name__=='__main__':main()
