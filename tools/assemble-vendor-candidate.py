#!/usr/bin/env python3
"""Merge audited native stages into an offline vendor EROFS, preserving metadata.
Does not modify the source disk, partition tables, AVB, or any device.
Uses the MIT-licensed gbos-vm EROFS metadata reader.
"""
import argparse, hashlib, importlib.util, io, json, os, stat, struct, subprocess, tarfile
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--source',type=Path,required=True);p.add_argument('--offset',type=int,required=True)
p.add_argument('--tools',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
p.add_argument('--stage',type=Path,action='append',required=True)
a=p.parse_args()
if not stat.S_ISREG(a.source.stat().st_mode):raise SystemExit('Source must be a regular image file')
a.output.mkdir(parents=True,exist_ok=False)
spec=importlib.util.spec_from_file_location('erofs_metadata',Path(__file__).resolve().parents[1]/'third_party/gbos-vm/erofs_metadata.py')
e=importlib.util.module_from_spec(spec);spec.loader.exec_module(e);e.D=a.tools/'dump.erofs'
def meta(path):return e.metadata(a.source,path,a.offset)
def cat(image,path,offset=0):return subprocess.check_output([str(e.D),f'--offset={offset}','--path='+path,'--cat',str(image)])
files={};dirs={'.'};newdirs={}
for stage in a.stage:
 manifest=json.loads((stage/'manifest.json').read_text())
 for name,label in manifest.get('directories',{}).items():
  assert name.startswith('firmware/arm') and '..' not in Path(name).parts and label=='vendor_firmware_file'
  newdirs[name]=label;dirs.add(name)
 for f in json.loads((stage/'manifest.json').read_text())['files']:
  name=f['path'];rel=Path(name)
  if rel.is_absolute() or '..' in rel.parts or name in files:raise ValueError('Unsafe or duplicate path: '+name)
  b=(stage/'vendor'/name).read_bytes()
  if hashlib.sha256(b).hexdigest()!=f['sha256']:raise ValueError('Stage digest mismatch: '+name)
  files[name]=(b,f)
  dirs.update(str(x) for x in rel.parents)
original={}
with tarfile.open(a.output/'overlay.tar','w',format=tarfile.PAX_FORMAT) as t:
 for name in sorted(dirs,key=lambda n:(len(Path(n).parts),n)):
  path='/' if name=='.' else '/'+name
  # The only directory added by current stages; all other ancestors must exist.
  if name in newdirs:m={'mode':0o40755,'uid':0,'gid':0,'mtime':1230768000,'xattrs':{'security.selinux':('u:object_r:'+newdirs[name]+':s0').encode()}}
  elif name=='lib64/native_keymint':m={'mode':0o40755,'uid':0,'gid':0,'mtime':1230768000,'xattrs':{'security.selinux':b'u:object_r:vendor_file:s0'}}
  else:m=meta(path);original[path]=m
  ti=tarfile.TarInfo(name);ti.type=tarfile.DIRTYPE;ti.mode=m['mode']&0o7777;ti.uid=m['uid'];ti.gid=m['gid'];ti.mtime=m['mtime']
  ti.pax_headers={} if name=='.' else {'SCHILY.xattr.'+k:v.decode() for k,v in m['xattrs'].items()};t.addfile(ti)
 for name,(b,f) in sorted(files.items()):
  ti=tarfile.TarInfo(name);ti.size=len(b);ti.mode=int(f['mode'],8);ti.uid=ti.gid=0;ti.mtime=1230768000
  ti.pax_headers={'SCHILY.xattr.security.selinux':'u:object_r:'+f['selinux_type_required']+':s0'};t.addfile(ti,io.BytesIO(b))
v=a.output/'vendor.erofs'
with a.source.open('rb') as src,v.open('xb') as dst:
 src.seek(a.offset+1024);sb=src.read(128)
 assert sb[:4]==bytes.fromhex('e2e1f5e0') and sb[12]==12
 size=struct.unpack_from('<I',sb,36)[0]*4096
 root=struct.unpack_from('<H',sb,14)[0]*32+struct.unpack_from('<I',sb,40)[0]*4096
 src.seek(a.offset+root);old=src.read(64)
 # Restrict restoration to compact root inode with its original xattr body.
 assert not(old[0]&1)
 xbytes=12+(struct.unpack_from('<H',old,2)[0]-1)*4
 assert 0<xbytes<=32
 src.seek(a.offset+root+32);xattrs=src.read(xbytes)
 src.seek(a.offset);remaining=size
 while remaining:
  b=src.read(min(4*1024*1024,remaining));assert b;dst.write(b);remaining-=len(b)
subprocess.run([str(a.tools/'mkfs.erofs'),'--incremental=data','--tar=f','-x0','-b4096','-T1230768000','-zlz4hc',str(v),str(a.output/'overlay.tar')],check=True)
with v.open('r+b') as f:
 f.seek(1024);new_sb=f.read(128)
 assert new_sb[14:16]==sb[14:16] and new_sb[40:48]==sb[40:48]
 f.seek(root);new=f.read(32);assert old[2:4]==new[2:4] and not(new[0]&1)
 f.seek(root+32);f.write(xattrs)
 f.seek(1024);b=bytearray(f.read(3072));b[4:8]=bytes(4);crc=0xffffffff
 for value in b:
  crc^=value
  for _ in range(8):crc=(crc>>1)^(0x82f63b78 if crc&1 else 0)
 f.seek(1028);f.write(struct.pack('<I',crc));f.flush();os.fsync(f.fileno())
subprocess.run([str(a.tools/'fsck.erofs'),str(v)],check=True)
for name,(b,f) in files.items():
 assert cat(v,'/'+name)==b,name
 m=e.metadata(v,'/'+name)
 assert m['mode']&0o7777==int(f['mode'],8) and m['uid']==m['gid']==0,name
 assert m['xattrs']['security.selinux'].rstrip(b'\0')==('u:object_r:'+f['selinux_type_required']+':s0').encode(),name
for path,m in original.items():assert e.metadata(v,path)==m,path
for path in ['/etc/init/hw/init.android-desktop.rc','/etc/selinux/precompiled_sepolicy']:
 assert cat(v,path)==cat(a.source,path,a.offset),path
report={'status':'OFFLINE_VENDOR_CANDIDATE; HAL selection, modules, fstab and policy integration pending; not bootable', 'files_verified':len(files),'directories_preserved':len(original),'vendor_bytes':v.stat().st_size,'sha256':hashlib.file_digest(v.open('rb'),'sha256').hexdigest(),'stages':[str(s.resolve()) for s in a.stage]}
(a.output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
