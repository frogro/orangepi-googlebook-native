#!/usr/bin/env python3
"""Prepare a first-stage candidate, preserving newc ownership/device metadata."""
import argparse, gzip, hashlib, json, stat
from pathlib import Path


def read_newc(data):
    records=[]; pos=0
    while pos<len(data):
        while pos<len(data) and data[pos]==0: pos+=1
        if pos==len(data): break
        magic=data[pos:pos+6]
        if magic not in (b'070701',b'070702'): raise ValueError('Invalid newc header')
        fields=[int(data[pos+6+i*8:pos+14+i*8],16) for i in range(13)]
        size,ns=fields[6],fields[11]
        if ns<1 or pos+110+ns>len(data): raise ValueError('Invalid name bounds')
        raw=data[pos+110:pos+110+ns]
        if raw[-1:]!=b'\0': raise ValueError('Unterminated name')
        name=raw[:-1].decode(); start=(pos+110+ns+3)&~3
        if start+size>len(data): raise ValueError('Invalid data bounds')
        body=data[start:start+size]; pos=(start+size+3)&~3
        if magic==b'070702' and sum(body)&0xffffffff!=fields[12]: raise ValueError('CPIO CRC mismatch')
        if name=='TRAILER!!!': continue
        if name.startswith('/') or '..' in Path(name).parts: raise ValueError('Unsafe archive path')
        records.append((name,fields,body))
    return records


def write_newc(records):
    result=bytearray()
    for name,fields,body in records+[('TRAILER!!!',[0,stat.S_IFREG,0,0,1,0,0,0,0,0,0,0,0],b'')]:
        f=fields.copy(); raw=name.encode()+b'\0'; f[6]=len(body); f[11]=len(raw); f[12]=0
        result+=b'070701'+b''.join(f'{v:08x}'.encode() for v in f)+raw
        result+=bytes(-len(result)%4); result+=body; result+=bytes(-len(result)%4)
    return bytes(result)


def prepare(normal,config,out):
    if out.exists(): raise ValueError('Output directory must be new')
    cfg=dict(l.split('=',1) for l in config.read_text().splitlines() if l.startswith('CONFIG_') and '=' in l)
    for key in ['BLK_DEV_INITRD','RD_GZIP','MMC','MMC_BLOCK','MMC_DW_ROCKCHIP','MMC_SDHCI_OF_DWCMSHC','EXT4_FS','EROFS_FS','BLK_DEV_DM','DM_VERITY','ANDROID_BINDER_IPC']:
        if cfg.get('CONFIG_'+key)!='y': raise ValueError('Required built-in kernel option: '+key)
    records=[]; names=set(); deleted=[]; source_hashes={}
    for idx,filename in enumerate(['init_ramdisk.cpio','vendor_0_platform.cpio']):
        data=(normal/filename).read_bytes(); source_hashes[filename]=hashlib.sha256(data).hexdigest()
        inode_map={}
        for name,f,body in read_newc(data):
            if name=='lib/modules' or name.startswith('lib/modules/'):
                deleted.append(name); continue
            if name in names:
                previous=next(r for r in records if r[0]==name)
                if stat.S_ISDIR(f[1]) and f[1:4]==previous[1][1:4] and not body:
                    continue
                raise ValueError('Conflicting archive name: '+name)
            names.add(name)
            # Preserve hardlink groups within each archive without cross-archive collisions.
            identity=(f[7],f[8],f[0]); inode_map.setdefault(identity,len(inode_map)+1)
            f[0]=(idx+1)*100000+inode_map[identity]
            if name=='first_stage_ramdisk/fstab.android-desktop':
                lines=body.decode().splitlines()
                excluded=['/dev/block/by-name/modem','/dev/block/by-name/dsp','/dev/block/by-name/bluetooth']
                body=('\n'.join(l for l in lines if not l.split() or l.split()[0] not in excluded)+'\n').encode()
                if b'fileencryption=aes-256-xts:aes-256-cts' not in body: raise ValueError('Encryption settings lost')
            records.append((name,f,body))
    if 'init' not in names: raise ValueError('Generic Android init missing')
    archive=write_newc(records)
    verify=read_newc(archive)
    if [(n,f[:6]+f[7:11],b) for n,f,b in verify]!=[(n,f[:6]+f[7:11],b) for n,f,b in records]:
        raise ValueError('CPIO round trip failed')
    out.mkdir(parents=True)
    payload=gzip.compress(archive,mtime=0)
    (out/'initramfs-native-candidate.cpio.gz').write_bytes(payload)
    report={'status':'FIRST_STAGE_CANDIDATE_ONLY; second-stage vendor/HAL/security integration pending',
            'source_sha256':source_hashes,'kernel_config_sha256':hashlib.sha256(config.read_bytes()).hexdigest(),
            'sha256':hashlib.sha256(payload).hexdigest(),'records':len(records),'removed_original_module_entries':deleted,
            'pending':['Replace Qualcomm vendor/system_dlkm modules and load services with matching native modules.',
                       'Synchronize second-stage vendor fstab and native VINTF/SELinux/HAL configuration.',
                       'Provide KeyMint/Gatekeeper suitable for isolated fresh encrypted userdata.',
                       'Supply board-specific boot-device selection and command line; do not copy Qualcomm boot arguments.',
                       'Verify native display/input/network/audio on a separate test card.']}
    (out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'Candidate: {len(records)} records; removed {len(deleted)} old module entries; no device boot claimed')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('normal',type=Path);p.add_argument('kernel_config',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();prepare(a.normal,a.kernel_config,a.output)
