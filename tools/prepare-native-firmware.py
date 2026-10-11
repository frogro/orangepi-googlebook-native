#!/usr/bin/env python3
"""Stage the distro's unmodified Mali CSF firmware and its redistribution notice."""
import argparse,gzip,hashlib,importlib.util,json,stat,subprocess
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);p.add_argument('--initramfs',type=Path);a=p.parse_args()
source=Path('/usr/lib/firmware/arm/mali/arch10.8/mali_csffw.bin.zst')
resolved=source.resolve(strict=True)
owner=subprocess.check_output(['dpkg-query','-S',str(resolved)],text=True).split(': ')[0]
assert owner=='linux-firmware-misc'
version=subprocess.check_output(['dpkg-query','-W','-f=${Version}',owner],text=True)
data=subprocess.check_output(['zstd','-d','-c',str(resolved)]);assert data
copyright=Path('/usr/share/doc/linux-firmware-misc/copyright').read_text()
license=copyright[copyright.rindex('License: Redistributable-mali_csffw'):].split('\n\n')[0]+'\n'
assert len(license)>500
files={'firmware/arm/mali/arch10.8/mali_csffw.bin':data,'firmware/arm/LICENCE.mali_csffw':license.encode()}
a.output.mkdir(parents=True,exist_ok=False);rows=[]
for name,b in files.items():
 dst=a.output/'vendor'/name;dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(b)
 rows.append({'path':name,'sha256':hashlib.sha256(b).hexdigest(),'mode':'0o644','selinux_type_required':'vendor_firmware_file'})
report={'status':'DISTRO_FIRMWARE_STAGED; unmodified bytes; runtime untested','package':owner,'version':version,'source':str(source),'resolved_source':str(resolved),'compressed_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'directories':{n:'vendor_firmware_file' for n in ['firmware/arm','firmware/arm/mali','firmware/arm/mali/arch10.8']},'files':rows}
(a.output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');print(version,rows[0]['sha256'])

if a.initramfs:
 spec=importlib.util.spec_from_file_location('cpio',Path(__file__).with_name('prepare-native-initramfs.py'));c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
 records=c.read_newc(gzip.decompress(a.initramfs.read_bytes()));names={n for n,f,b in records}
 path='lib/firmware/arm/mali/arch10.8/mali_csffw.bin'
 additions=[(str(x),stat.S_IFDIR|0o755,b'') for x in reversed(Path(path).parents) if str(x) not in ['.'] and str(x) not in names]
 additions.append((path,stat.S_IFREG|0o644,data))
 ino=max(f[0] for n,f,b in records)+1
 for name,mode,body in additions:
  assert name not in names;names.add(name)
  records.append((name,[ino,mode,0,0,1,1230768000,len(body),0,0,0,0,0,0],body));ino+=1
 archive=c.write_newc(records)
 assert [(n,f[:6]+f[7:11],b) for n,f,b in c.read_newc(archive)]==[(n,f[:6]+f[7:11],b) for n,f,b in records]
 target=a.output/'initramfs-native-candidate.cpio.gz';target.write_bytes(gzip.compress(archive,mtime=0))
 report['early_firmware_reason']='Panthor is built-in; firmware must also be available before vendor is mounted'
 report['initramfs_sha256']=hashlib.sha256(target.read_bytes()).hexdigest()
 (a.output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
