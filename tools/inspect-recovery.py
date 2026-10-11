#!/usr/bin/env python3
"""Inspect verified recovery boot material without mounting or modifying it."""
import hashlib,json,shutil,subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
raw=Path(sys.argv[1]).resolve(); work=Path(sys.argv[2]).resolve()
with raw.open('rb') as f: digest=hashlib.file_digest(f,'sha256').hexdigest()
if digest!=json.loads((root/'sources.json').read_text())['googlebook']['raw_sha256']:
    sys.exit('Recovery checksum mismatch')
(work/'scripts').mkdir(parents=True,exist_ok=True)
(work/'artifacts/mica').mkdir(parents=True,exist_ok=True)
link=work/'artifacts/mica-recovery.raw'
if not link.exists(): link.symlink_to(raw)
if link.resolve()!=raw: sys.exit('Workspace refers to a different recovery')
for name in ('extract_mica_normal.py','cpio_tools.py'):
    shutil.copy2(root/'third_party/gbos-vm'/name,work/'scripts'/name)
subprocess.run([sys.executable,str(work/'scripts/extract_mica_normal.py')],check=True)
print('Boot extraction complete:',work/'artifacts/mica/normal')
