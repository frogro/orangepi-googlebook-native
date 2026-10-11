#!/usr/bin/env python3
"""Fetch a pinned vendor recovery to regular files; never write a device."""
import hashlib,json,os,subprocess,sys,zipfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
s=json.loads((root/'sources.json').read_text())['googlebook']
out=Path(sys.argv[1]).resolve(); out.mkdir(parents=True,exist_ok=True)
def check(path,want):
    with path.open('rb') as f: actual=hashlib.file_digest(f,'sha256').hexdigest()
    if actual!=want: raise RuntimeError(f'Checksum mismatch: {path}')
archive=out/'mica-recovery.zip'
if not archive.exists():
    partial=archive.with_suffix('.zip.part')
    ready=False
    if partial.exists():
        try: check(partial,s['zip_sha256']); ready=True
        except RuntimeError: pass
    if not ready:
        subprocess.run(['curl','-fL','--retry','3','-C','-','-o',str(partial),s['url']],check=True)
        check(partial,s['zip_sha256'])
    partial.rename(archive)
else: check(archive,s['zip_sha256'])
raw=out/'mica-recovery.raw'
if not raw.exists():
    temp=out/'mica-recovery.raw.part'; digest=hashlib.sha256()
    with zipfile.ZipFile(archive) as z, z.open(s['member']) as src, temp.open('wb') as dst:
        while chunk:=src.read(8<<20): dst.write(chunk); digest.update(chunk)
        dst.flush(); os.fsync(dst.fileno())
    if digest.hexdigest()!=s['raw_sha256']: raise RuntimeError('Extracted image checksum mismatch')
    temp.rename(raw)
else: check(raw,s['raw_sha256'])
print('Verified recovery:',raw)
