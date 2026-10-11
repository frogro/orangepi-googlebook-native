#!/usr/bin/env python3
"""Install a validated ARM64 EFI loader into a regular native disk image only."""
import argparse, hashlib, json, os, stat, struct, subprocess, tempfile
from pathlib import Path

def digest(f, start, size):
    h=hashlib.sha256(); f.seek(start)
    while size:
        b=f.read(min(size,4<<20))
        if not b: raise ValueError('Short image')
        h.update(b); size-=len(b)
    return h.hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('image',type=Path); p.add_argument('loader',type=Path)
    a=p.parse_args()
    if not stat.S_ISREG(a.image.stat().st_mode): raise ValueError('Regular image required')
    b=a.loader.read_bytes(); off=struct.unpack_from('<I',b,0x3c)[0]
    if b[:2]!=b'MZ' or b[off:off+4]!=b'PE\0\0' or struct.unpack_from('<H',b,off+4)[0]!=0xaa64:
        raise ValueError('Not an ARM64 PE/COFF loader')
    report=a.image.with_suffix(a.image.suffix+'.json'); r=json.loads(report.read_text())
    esp=r['efi_system_partition']; start=esp['offset']; size=esp['bytes']
    if start<0 or size!=512<<20 or start+size>a.image.stat().st_size: raise ValueError('Invalid ESP bounds')
    with a.image.open('r+b') as image, tempfile.TemporaryDirectory(dir=a.image.parent,prefix='efi-stage-') as tmp:
        if digest(image,start,size)!=r['partition_sha256']['EFI']: raise ValueError('ESP differs from verified base')
        fat=Path(tmp)/'esp.img'; image.seek(start)
        with fat.open('xb') as out:
            left=size
            while left:
                b=image.read(min(left,4<<20)); out.write(b); left-=len(b)
        subprocess.run(['mmd','-i',str(fat),'::/EFI','::/EFI/BOOT'],check=True)
        subprocess.run(['mcopy','-i',str(fat),str(a.loader),'::/EFI/BOOT/BOOTAA64.EFI'],check=True)
        check=Path(tmp)/'readback.efi'
        subprocess.run(['mcopy','-i',str(fat),'::/EFI/BOOT/BOOTAA64.EFI',str(check)],check=True)
        if check.read_bytes()!=a.loader.read_bytes(): raise ValueError('FAT readback differs')
        with fat.open('rb') as f:
            expected=digest(f,0,size); f.seek(0); image.seek(start)
            while b:=f.read(4<<20): image.write(b)
        image.flush(); os.fsync(image.fileno())
        if digest(image,start,size)!=expected: raise ValueError('Written ESP differs')
    r['partition_sha256']['EFI']=expected
    r['efi_loader_sha256']=hashlib.sha256(a.loader.read_bytes()).hexdigest()
    r['status']='VERIFIED_BASE_WITH_EFI_LOADER; kernel/DTB/initramfs/native.cfg and native Android HAL integration still required'
    pending=report.with_suffix('.json.tmp')
    with pending.open('x') as out: json.dump(r,out,indent=2); out.write('\n')
    pending.replace(report)
    print('ARM64 loader staged and read back; OS payload still pending')

if __name__=='__main__': main()
