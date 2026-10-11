#!/usr/bin/env python3
"""Fetch the pinned official donor for userspace compatibility analysis."""
import hashlib,json,re,subprocess,sys,urllib.request
from pathlib import Path
root=Path(__file__).resolve().parents[1]
s=json.loads((root/'sources.json').read_text())['cuttlefish']
out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=True)
p=out/s['artifact']
if not p.exists():
    html=urllib.request.urlopen(s['page'],timeout=60).read(2<<20).decode()
    info=json.loads(re.search(r'var JSVariables = (\{.*?\});',html).group(1))
    url=info['artifactUrl']
    if not url.startswith('https://'):raise SystemExit('Unexpected non-HTTPS artifact')
    partial=p.with_suffix('.zip.part')
    subprocess.run(['curl','-fL','--retry','3','-C','-','-o',str(partial),url],check=True)
    with partial.open('rb') as f: digest=hashlib.file_digest(f,'sha256').hexdigest()
    if digest!=s['sha256']:raise SystemExit('Donor checksum mismatch')
    partial.rename(p)
else:
    with p.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
    if digest!=s['sha256']:raise SystemExit('Donor checksum mismatch')
print('Verified donor:',p)
