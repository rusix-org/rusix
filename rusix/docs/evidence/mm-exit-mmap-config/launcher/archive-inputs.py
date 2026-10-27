#!/usr/bin/env python3
"""Bind an extracted immutable Git archive to its original member bytes/modes."""
import argparse,hashlib,json,os,stat,tarfile
from pathlib import Path,PurePosixPath

def file_hash(stream):return hashlib.file_digest(stream,'sha256').hexdigest()

def archive_inventory(path):
 result={}
 with tarfile.open(path,'r:') as archive:
  for member in archive.getmembers():
   name=member.name.rstrip('/');rel=PurePosixPath(name)
   if not name or rel.is_absolute() or '..' in rel.parts or name in result:raise ValueError('Unsafe/duplicate archive member')
   record={'mode':member.mode&0o777}
   if member.isdir():record['type']='directory'
   elif member.isfile():
    record.update(type='file',sha256=file_hash(archive.extractfile(member)),bytes=member.size)
   elif member.issym():record.update(type='symlink',target=member.linkname)
   else:raise ValueError('Unsupported Git archive member')
   result[name]=record
 return result

def snapshot_inventory(root):
 result={}
 for base,dirs,files in os.walk(root,followlinks=False):
  for name in dirs+files:
   path=Path(base)/name;info=path.lstat();record={'mode':stat.S_IMODE(info.st_mode)}
   if stat.S_ISLNK(info.st_mode):record.update(type='symlink',target=os.readlink(path))
   elif stat.S_ISDIR(info.st_mode):record['type']='directory'
   elif stat.S_ISREG(info.st_mode):
    with path.open('rb') as stream:record.update(type='file',sha256=file_hash(stream),bytes=info.st_size)
   else:raise ValueError('Unsupported snapshot entry')
   result[str(path.relative_to(root))]=record
 return result

def verify(root,expected):
 actual=snapshot_inventory(root)
 if actual!=expected:raise ValueError('Extracted source differs from archive content/modes/symlinks')
 return actual

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--archive',type=Path,required=True);parser.add_argument('--source',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
 expected=archive_inventory(args.archive);verify(args.source,expected)
 with args.archive.open('rb') as stream:archive_hash=file_hash(stream)
 with args.output.open('x') as f:json.dump({'archive_sha256':archive_hash,'members':expected},f,indent=2,sort_keys=True);f.write('\n')

if __name__=='__main__':main()
