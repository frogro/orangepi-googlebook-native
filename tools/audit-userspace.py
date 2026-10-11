#!/usr/bin/env python3
"""Read-only GPT/LP/EROFS metadata audit. No image writes or mounts."""
import argparse, hashlib, json, struct, subprocess, xml.etree.ElementTree as ET, zlib
from pathlib import Path
U=lambda b,o:struct.unpack_from('<I',b,o)[0]
def partitions(image):
    with image.open('rb') as f:
        f.seek(512); h=f.read(512)
        assert h[:8]==b'EFI PART'
        hc=bytearray(h[:U(h,12)]); hc[16:20]=bytes(4)
        assert zlib.crc32(hc)==U(h,16)
        lba,count,size=struct.unpack_from('<QII',h,72)
        assert 128<=size<=4096 and count*size<=16<<20
        f.seek(lba*512); es=f.read(count*size)
        assert zlib.crc32(es)==U(h,88)
        gpt={}
        for i in range(count):
            e=es[i*size:(i+1)*size]
            if not any(e[:16]):continue
            name=e[56:128].decode('utf-16le').rstrip('\0')
            start,end=struct.unpack_from('<QQ',e,32)
            assert 0<start<=end and (end+1)*512<=image.stat().st_size
            gpt[name]=(start*512,(end+1)*512)
        base,end=gpt['super']
        f.seek(base+4096); g=f.read(4096)
        assert U(g,0)==0x616c4467 and 52<=U(g,4)<=4096
        gc=bytearray(g[:U(g,4)]); gc[8:40]=bytes(32)
        assert hashlib.sha256(gc).digest()==g[8:40]
        sz,count,bs=struct.unpack_from('<III',g,40)
        assert 128<=sz<=16<<20
        f.seek(base+12288); m=f.read(sz)
        assert U(m,0)==0x414c5030
        hs=U(m,8); assert 128<=hs<=sz
        header=bytearray(m[:hs]); header[12:44]=bytes(32)
        assert hashlib.sha256(header).digest()==m[12:44]
        assert hs+U(m,44)<=sz
        assert hashlib.sha256(m[hs:hs+U(m,44)]).digest()==m[48:80]
        po,pc,ps=struct.unpack_from('<III',m,80)
        eo,ec,es=struct.unpack_from('<III',m,92)
        assert ps>=52 and es>=24 and po+pc*ps<=U(m,44) and eo+ec*es<=U(m,44)
        logical={}
        for i in range(pc):
            p=hs+po+i*ps; name=m[p:p+36].split(b'\0')[0].decode()
            first,num=struct.unpack_from('<II',m,p+40); assert first+num<=ec
            ext=[]
            for j in range(first,first+num):
                n,k,t,s=struct.unpack_from('<QIQI',m,hs+eo+j*es)
                assert k==0 and s==0, 'Only linear extents on super are supported'
                assert base<=base+t*512<base+(t+n)*512<=end
                ext.append({'offset':base+t*512,'bytes':n*512})
            logical[name]=ext
        return gpt,logical

def main():
    a=argparse.ArgumentParser();a.add_argument('image',type=Path);a.add_argument('output',type=Path)
    a.add_argument('--dump-erofs',required=True); args=a.parse_args()
    root=Path(__file__).resolve().parents[1];src=json.loads((root/'sources.json').read_text())
    with args.image.open('rb') as f: digest=hashlib.file_digest(f,'sha256').hexdigest()
    if digest!=src['googlebook']['raw_sha256']:raise SystemExit('Recovery checksum mismatch')
    gpt,logical=partitions(args.image)
    def read(part,path):
        ext=logical[part]
        if len(ext)!=1: raise ValueError('EROFS direct reading requires exactly one contiguous extent')
        return subprocess.check_output([args.dump_erofs,'--offset='+str(ext[0]['offset']),'--path='+path,'--cat',str(args.image)])
    args.output.mkdir(parents=True,exist_ok=True)
    result={'recovery_sha256':digest,'gpt':gpt,'logical_partitions':logical,'properties':{},'matrices':{}}
    for part,path in [('system_a','/system/build.prop'),('vendor_a','/build.prop')]:
        props=dict(l.split('=',1) for l in read(part,path).decode().splitlines() if '=' in l and not l.startswith('#'))
        result['properties'][part]={k:v for k,v in props.items() if any(x in k for x in ['version.sdk','version.release','api_level','security_patch','board.platform'])}
    for name in ['8','202504','202604','device']:
        data=read('system_a','/system/etc/vintf/compatibility_matrix.'+name+'.xml')
        (args.output/('compatibility_matrix.'+name+'.xml')).write_bytes(data)
        node=ET.fromstring(data)
        result['matrices'][name]={'attributes':node.attrib,'kernel_requirements':[x.attrib for x in node.findall('kernel')]}
    result['vendor_manifest']=ET.fromstring(read('vendor_a','/etc/vintf/manifest.xml')).attrib
    result['vendor_selinux_version']=read('vendor_a','/etc/selinux/plat_sepolicy_vers.txt').decode().strip()
    result['status']='Metadata audit only; no VINTF/HAL runtime compatibility claim'
    (args.output/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
if __name__=='__main__': main()
