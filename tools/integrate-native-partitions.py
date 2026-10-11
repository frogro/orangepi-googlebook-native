#!/usr/bin/env python3
"""Clone a regular test disk and relocate reviewed LP replacements into free super space.
Preserves all other extents, validates every metadata copy, and reads replacements back.
Never opens a block device and never overwrites an existing output.
"""
import argparse,hashlib,importlib.util,json,os,stat,struct,subprocess
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('output',type=Path)
p.add_argument('--replace',action='append',required=True);p.add_argument('--update-candidate',action='store_true');a=p.parse_args()
assert stat.S_ISREG(a.source.stat().st_mode)
replacements={}
for arg in a.replace:
 name,path=arg.split('=',1);path=Path(path)
 assert name in ['vendor_a','vendor_dlkm_a','system_dlkm_a'] and name not in replacements
 assert stat.S_ISREG(path.stat().st_mode);replacements[name]=path
spec=importlib.util.spec_from_file_location('audit',Path(__file__).with_name('audit-userspace.py'));audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
gpt,logical=audit.partitions(a.source);base,end=gpt['super'];u=audit.U
records=[];ranges=[]
with a.source.open('rb') as f:
 f.seek(base+4096);g=f.read(4096);sz,count,bs=struct.unpack_from('<III',g,40)
 assert 0<count<=8 and bs==4096
 f.seek(base+8192);assert f.read(4096)==g,'Geometry backup differs'
 for slot in range(count*2):
  pos=base+12288+slot*sz;f.seek(pos);m=bytearray(f.read(sz));assert u(m,0)==0x414c5030
  hs=u(m,8);h=bytearray(m[:hs]);h[12:44]=bytes(32);assert hashlib.sha256(h).digest()==m[12:44]
  assert hashlib.sha256(m[hs:hs+u(m,44)]).digest()==m[48:80]
  po,pc,ps=struct.unpack_from('<III',m,80);eo,ec,es=struct.unpack_from('<III',m,92)
  go,gc,gs=struct.unpack_from('<III',m,104)
  assert hs+u(m,44)<=sz and po+pc*ps<=u(m,44) and eo+ec*es<=u(m,44) and go+gc*gs<=u(m,44)
  lengths={};targets={};groups={}
  for i in range(ec):
   n,k,t,s=struct.unpack_from('<QIQI',m,hs+eo+i*es);assert k==s==0
   lengths[i]=n*512
   if n:
    assert base<=base+t*512<base+(t+n)*512<=end
    ranges.append((base+t*512,base+(t+n)*512))
  for i in range(pc):
   off=hs+po+i*ps;name=m[off:off+36].split(b'\0')[0].decode();first,num,group=struct.unpack_from('<III',m,off+40)
   assert first+num<=ec and group<gc
   length=sum(lengths[j] for j in range(first,first+num))
   if name in replacements:
    assert num==1;targets[name]=hs+eo+first*es;length=(replacements[name].stat().st_size+bs-1)//bs*bs
   groups[group]=groups.get(group,0)+length
  assert set(targets)==set(replacements)
  for group,length in groups.items():
   maximum=struct.unpack_from('<Q',m,hs+go+group*gs+40)[0]
   assert maximum==0 or length<=maximum,'LP group capacity exceeded'
  records.append((pos,m,hs,targets))
start=(max(e for s,e in ranges)+(1<<20)-1)//(1<<20)*(1<<20);plan={}
for name,path in replacements.items():
 length=(path.stat().st_size+bs-1)//bs*bs
 assert start+length<=end and all(start>=e or start+length<=s for s,e in ranges)
 plan[name]={'offset':start,'bytes':length,'source_bytes':path.stat().st_size,'sha256':hashlib.file_digest(path.open('rb'),'sha256').hexdigest()};start=(start+length+(1<<20)-1)//(1<<20)*(1<<20)
history=None
if a.update_candidate:
 assert a.source.resolve()==a.output.resolve()
 history=json.loads(a.source.with_suffix('.integration.json').read_text())
 assert history['status'].startswith('PARTITIONS_INTEGRATED')
 with a.source.open('rb') as f:
  for name,r in history['replacements'].items():
   assert logical[name]==[{'offset':r['offset'],'bytes':r['bytes']}]
   f.seek(r['offset']);left=r['source_bytes'];h=hashlib.sha256()
   while left:
    b=f.read(min(left,4<<20));assert b;h.update(b);left-=len(b)
   assert h.hexdigest()==r['sha256']
else:
 # Exclusive create before copying; base source never opened for writing.
 with a.output.open('xb'):pass
 subprocess.run(['cp','--reflink=auto','--sparse=always',str(a.source),str(a.output)],check=True)
with a.output.open('r+b') as f:
 for name,path in replacements.items():
  r=plan[name];f.seek(r['offset'])
  with path.open('rb') as src:
   while b:=src.read(4<<20):f.write(b)
  f.write(bytes(r['bytes']-r['source_bytes']))
 for pos,m,hs,targets in records:
  for name,ep in targets.items():
   r=plan[name];struct.pack_into('<QIQI',m,ep,r['bytes']//512,0,(r['offset']-base)//512,0)
  m[48:80]=hashlib.sha256(m[hs:hs+u(m,44)]).digest();m[12:44]=bytes(32);m[12:44]=hashlib.sha256(m[:hs]).digest()
  f.seek(pos);f.write(m)
 f.flush();os.fsync(f.fileno())
 for pos,m,hs,targets in records:f.seek(pos);assert f.read(len(m))==m
 for name,r in plan.items():
  f.seek(r['offset']);left=r['source_bytes'];h=hashlib.sha256()
  while left:
   b=f.read(min(left,4<<20));assert b;h.update(b);left-=len(b)
  assert h.hexdigest()==r['sha256']
new_gpt,new_logical=audit.partitions(a.output);assert new_gpt==gpt
for name,extents in logical.items():
 if name not in replacements:assert new_logical[name]==extents,name
subprocess.run(['sgdisk','-v',str(a.output)],check=True)
report={'status':'PARTITIONS_INTEGRATED; boot and HAL integration still pending; not for flashing','source':str(a.source.resolve()),'replacements':{**(history['replacements'] if history else {}),**plan},'previous_integration':history,'metadata_copies_updated':len(records),'unmodified_extent_maps_preserved':True}
if history:
 for key in ['boot_files','esp_sha256']:
  if key in history:report[key]=history[key]
a.output.with_suffix('.integration.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
