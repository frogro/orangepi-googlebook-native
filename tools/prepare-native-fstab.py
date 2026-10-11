#!/usr/bin/env python3
"""Synchronize native candidate mount tables without changing userdata encryption."""
import argparse,gzip,hashlib,importlib.util,json
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('initramfs',type=Path);p.add_argument('vendor_fstab',type=Path);p.add_argument('output',type=Path);p.add_argument('--modified-partition',action='append',choices=['vendor','vendor_dlkm','system_dlkm'],required=True);a=p.parse_args()
spec=importlib.util.spec_from_file_location('cpio',Path(__file__).with_name('prepare-native-initramfs.py'));c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
records=c.read_newc(gzip.decompress(a.initramfs.read_bytes()))
name='first_stage_ramdisk/fstab.android-desktop'
record=next(r for r in records if r[0]==name)
def adapt(data):
 lines=[]
 for line in data.decode().splitlines():
  f=line.split()
  if not f or f[0].startswith('#'):lines.append(line);continue
  if f[0] in ['/dev/block/by-name/modem','/dev/block/by-name/dsp','/dev/block/by-name/bluetooth']:continue
  if f[0] in a.modified_partition:
   assert len(f)==5
   opts=f[4].split(',');assert 'avb=vbmeta' in opts
   f[4]=','.join(o for o in opts if o!='avb=vbmeta');line=' '.join(f)
  lines.append(line)
 return ('\n'.join(lines)+'\n').encode()
first=adapt(record[2]);second=adapt(a.vendor_fstab.read_bytes())
assert first==second,'Mount tables differ beyond the reviewed modifications'
for data in [record[2],a.vendor_fstab.read_bytes()]:
 before=[l for l in data.splitlines() if b' /data ' in l]
 assert before==[l for l in first.splitlines() if b' /data ' in l] and len(before)==1
assert b'fileencryption=aes-256-xts:aes-256-cts' in first
out=[(n,f,first if n==name else b) for n,f,b in records]
archive=c.write_newc(out)
assert [(n,f[:6]+f[7:11],b) for n,f,b in c.read_newc(archive)]==[(n,f[:6]+f[7:11],b) for n,f,b in out]
a.output.mkdir(parents=True,exist_ok=False)
(a.output/'initramfs-native-candidate.cpio.gz').write_bytes(gzip.compress(archive,mtime=0))
target=a.output/'vendor/etc/fstab.android-desktop';target.parent.mkdir(parents=True);target.write_bytes(second)
report={'status':'CANDIDATE_ONLY; AVB omitted only for explicitly modified partitions; other AVB entries and userdata flags unchanged', 'modified_partitions':a.modified_partition, 'files':[{'path':'etc/fstab.android-desktop','sha256':hashlib.sha256(second).hexdigest(),'mode':'0o644','selinux_type_required':'vendor_configs_file'}]}
(a.output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
print('First/second-stage mount tables identical; userdata unchanged; explicit modified-partition AVB exceptions')
