#!/usr/bin/env python3
"""Build Android dlkm candidates from one kernel artifact, without device writes."""
import argparse,hashlib,json,lzma,shutil,subprocess
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for n in ['artifact','contexts','erofs_tools','output']:p.add_argument(n,type=Path)
a=p.parse_args();release=(a.artifact/'kernel.release').read_text().strip()
assert release and '/' not in release
a.output.mkdir(parents=True,exist_ok=False)
base=a.output/'depmod-root';mods=base/'lib/modules'/release;mods.mkdir(parents=True)
source=a.artifact/'modules/lib/modules'/release
rows=[]
for src in sorted(source.rglob('*.ko.xz')):
 rel=src.relative_to(source).with_suffix('');dst=mods/rel;dst.parent.mkdir(parents=True,exist_ok=True)
 data=lzma.decompress(src.read_bytes());assert data.startswith(b'\x7fELF')
 assert b'vermagic='+release.encode()+b' ' in data,src
 assert data.endswith(b'~Module signature appended~\n'),src
 dst.write_bytes(data);rows.append({'path':str(rel),'sha256':hashlib.sha256(data).hexdigest()})
assert rows,'No modules found'
for name in ['modules.builtin','modules.builtin.modinfo','modules.order']:
 shutil.copyfile(source/name,mods/name)
subprocess.run(['depmod','-b',str(base),release],check=True)
# Android modprobe reads text indexes; compressed .ko.xz files would not match
# the existing Android pathname labels and are unpacked without changing ELF bytes.
for line in (mods/'modules.dep').read_text().splitlines():
 for path in line.replace(':',' ').split():assert (mods/path).is_file(),path
(mods/'modules.load').write_text('# Native drivers are built in or loaded through uevent aliases.\n')
vroot=a.output/'vendor_dlkm-root';(vroot/'lib').mkdir(parents=True)
shutil.copytree(mods,vroot/'lib/modules')
sroot=a.output/'system_dlkm-root';(sroot/'lib/modules').mkdir(parents=True)
(sroot/'lib/modules/modules.load').write_text('# All loadable native modules reside in vendor_dlkm.\n')
for name,root in [('vendor_dlkm',vroot),('system_dlkm',sroot)]:
 image=a.output/(name+'.erofs')
 subprocess.run([str(a.erofs_tools/'mkfs.erofs'),'-zlz4hc','-T1230768000','--all-root','--mount-point=/'+name,'--file-contexts='+str(a.contexts),str(image),str(root)],check=True,stdout=subprocess.DEVNULL)
 subprocess.run([str(a.erofs_tools/'fsck.erofs'),str(image)],check=True)
for row in rows:
 b=subprocess.check_output([str(a.erofs_tools/'dump.erofs'),'--cat','--path=/lib/modules/'+row['path'],str(a.output/'vendor_dlkm.erofs')])
 assert hashlib.sha256(b).hexdigest()==row['sha256'],row['path']
report={'status':'OFFLINE_MODULE_CANDIDATES; not installed; signature acceptance and runtime not tested','release':release,'module_count':len(rows),'all_module_bytes_read_back':True,'modules':rows}
(a.output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');print(release,len(rows),'modules verified')
