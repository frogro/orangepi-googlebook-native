#!/usr/bin/env python3
"""Read-only direct ELF dependency inventory against recovery library directories."""
import argparse,importlib.util,json,re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('recovery',type=Path);p.add_argument('dump_erofs',type=Path);p.add_argument('output',type=Path);p.add_argument('stages',type=Path,nargs='+');p.add_argument('--runtime-payload',type=Path);a=p.parse_args()
spec=importlib.util.spec_from_file_location('audit',ROOT/'tools/audit-userspace.py');audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
_,parts=audit.partitions(a.recovery)
providers={}
for part,path in [('vendor_a','/lib64'),('system_a','/system/lib64'),('system_ext_a','/lib64')]:
    ext=parts[part]
    if len(ext)!=1:raise ValueError('Non-contiguous partition')
    text=subprocess.check_output([str(a.dump_erofs),'--offset='+str(ext[0]['offset']),'--path='+path,'--ls',str(a.recovery)],text=True)
    for line in text.splitlines():
        match=re.match(r'\s*\d+\s+[13]\s+(\S+)',line)
        if match:providers.setdefault(match[1],[]).append(part+':'+path+'/'+match[1])
if a.runtime_payload:
    text=subprocess.check_output([str(a.dump_erofs),'--path=/lib64/bionic','--ls',str(a.runtime_payload)],text=True)
    for line in text.splitlines():
        match=re.match(r'\s*\d+\s+[13]\s+(\S+)',line)
        if match:providers.setdefault(match[1],[]).append('runtime.apex:/lib64/bionic/'+match[1])
staged=[]
for stage in a.stages:
    for file in (stage/'vendor').rglob('*'):
        if file.is_file():
            with file.open('rb') as f:elf=f.read(4)==b'\x7fELF'
            if elf:
                staged.append(file)
                if 'native_keymint' not in file.parts:
                    providers.setdefault(file.name,[]).insert(0,str(file))
result=[];missing=set()
for file in staged:
    dynamic=subprocess.check_output(['readelf','-d',str(file)],text=True)
    needed=re.findall(r'\(NEEDED\).*\[(.*?)\]',dynamic)
    deps={}
    for name in needed:
        found=providers.get(name,[])
        if file.name=='android.hardware.security.keymint-service' and name=='libcrypto.so':
            found=[str(file.parents[2]/'lib64/native_keymint/libcrypto.so')]
        deps[name]=found
        if not found:missing.add(name)
    result.append({'file':str(file),'direct_dependencies':deps})
report={'status':'DIRECT_FILENAME_INVENTORY_ONLY; namespace access, ELF symbols, transitive dependencies and runtime not proven',
        'missing_direct_library_names':sorted(missing),'files':result}
with a.output.open('x') as f:json.dump(report,f,indent=2);f.write('\n')
print(f'{len(staged)} ELF files inspected; missing names: {sorted(missing)}')
