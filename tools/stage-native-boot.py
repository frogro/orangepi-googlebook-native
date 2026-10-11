#!/usr/bin/env python3
"""Wire the native ARM64 kernel, DTB and initramfs into an integrated file image."""
import argparse,hashlib,importlib.util,json,os,stat,subprocess,tempfile
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for n in ['image','artifact','initramfs']:p.add_argument(n,type=Path)
p.add_argument('--config',type=Path);a=p.parse_args();assert stat.S_ISREG(a.image.stat().st_mode)
report=json.loads(a.image.with_suffix('.integration.json').read_text());assert report['status'].startswith('PARTITIONS_INTEGRATED')
spec=importlib.util.spec_from_file_location('audit',Path(__file__).with_name('audit-userspace.py'));audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
gpt,_=audit.partitions(a.image);start,end=gpt['EFI']
kernel=a.artifact/'Image';dtb=a.artifact/'rk3588-orangepi-5-plus.dtb'
assert kernel.read_bytes()[56:60]==b'ARM\x64';assert dtb.read_bytes()[:4]==bytes.fromhex('d00dfeed')
assert a.initramfs.read_bytes()[:2]==b'\x1f\x8b'
# Firmware must hand the native device tree to the kernel. Never reuse QTI bootargs.
config=b'''set timeout=5
set default=0
menuentry 'Googlebook native RK3588 - experimental' {
    search --no-floppy --label GBNATIVE --set=root
    devicetree /boot/rk3588-orangepi-5-plus.dtb
    linux /boot/Image root=/dev/ram0 init=/init console=ttyS2,1500000 console=tty0 androidboot.hardware=android-desktop androidboot.hardware.platform=android-desktop androidboot.boot_devices=fe2c0000.mmc androidboot.slot_suffix=_a androidboot.force_normal_boot=1 androidboot.verifiedbootstate=orange androidboot.selinux=enforcing firmware_class.path=/vendor/firmware
    initrd /boot/initramfs-native.cpio.gz
}
'''
if a.config:
 config=a.config.read_bytes()
 subprocess.run(['grub-script-check',str(a.config)],check=True)
files={'Image':kernel,'rk3588-orangepi-5-plus.dtb':dtb,'initramfs-native.cpio.gz':a.initramfs}
with tempfile.TemporaryDirectory(dir=a.image.parent,prefix='native-boot-') as temp:
 temp=Path(temp);fat=temp/'esp.img'
 with a.image.open('rb') as src,fat.open('xb') as dst:
  src.seek(start);left=end-start
  while left:
   b=src.read(min(left,4<<20));assert b;dst.write(b);left-=len(b)
 if 'esp_sha256' in report:
  assert hashlib.file_digest(fat.open('rb'),'sha256').hexdigest()==report['esp_sha256'],'ESP changed since last verified boot stage'
 else:
  subprocess.run(['mmd','-i',str(fat),'::/boot','::/boot/grub'],check=True)
 files['grub/native.cfg']=temp/'native.cfg';files['grub/native.cfg'].write_bytes(config)
 hashes={}
 for name,src in files.items():
  subprocess.run(['mcopy','-o','-i',str(fat),str(src),'::/boot/'+name],check=True)
  back=temp/('readback-'+Path(name).name)
  subprocess.run(['mcopy','-i',str(fat),'::/boot/'+name,str(back)],check=True)
  digest=hashlib.file_digest(src.open('rb'),'sha256').hexdigest();assert hashlib.file_digest(back.open('rb'),'sha256').hexdigest()==digest
  hashes[name]=digest
 with a.image.open('r+b') as dst,fat.open('rb') as src:
  dst.seek(start)
  while b:=src.read(4<<20):dst.write(b)
  dst.flush();os.fsync(dst.fileno());dst.seek(start);h=hashlib.sha256();left=end-start
  while left:
   b=dst.read(min(left,4<<20));assert b;h.update(b);left-=len(b)
  assert h.hexdigest()==hashlib.file_digest(fat.open('rb'),'sha256').hexdigest()
 report['boot_files']=hashes;report['esp_sha256']=h.hexdigest()
 report['status']='PARTITIONS_INTEGRATED; native boot files installed; NOT DEVICE-TESTED; HAL/linker/policy checks pending'
 a.image.with_suffix('.integration.json').write_text(json.dumps(report,indent=2)+'\n')
print('Native boot files installed and read back; device boot not tested')
