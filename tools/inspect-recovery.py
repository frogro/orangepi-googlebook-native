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
base=work/'artifacts/mica/normal'
sys.path.insert(0,str(work/'scripts'))
from cpio_tools import read
facts={'recovery_sha256':digest,'boot_files':{},'fstab':{},'module_load_lists':{}}
for cpio in base.glob('*.cpio'):
    entries=read(cpio.read_bytes())
    facts['boot_files'][cpio.name]=sorted(entries)
    for name,(mode,data) in entries.items():
        if 'fstab' in Path(name).name:
            facts['fstab'][cpio.name+':'+name]=data.decode('utf-8',errors='replace')
        if Path(name).name.startswith('modules.load'):
            facts['module_load_lists'][cpio.name+':'+name]=data.decode('utf-8',errors='replace')
facts['native_gate']='Kernel prepared separately; native vendor/HAL, VINTF, SELinux and security compatibility remain to be validated. No complete native image assembled.'
(work/'native-audit.json').write_text(json.dumps(facts,indent=2)+'\n')
print('Boot extraction and native audit complete:',work/'native-audit.json')
