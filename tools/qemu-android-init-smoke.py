#!/usr/bin/env python3
"""Boot the real kernel/initramfs/system in QEMU; never open a physical disk.
This exercises generic early init, not RK3588 firmware, DT or GPU hardware.
"""
import argparse,gzip,hashlib,importlib.util,json,lzma,os,stat,subprocess,time
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--bundle',type=Path,required=True);p.add_argument('--initramfs',type=Path,required=True)
p.add_argument('--disk',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
p.add_argument('--timeout',type=int,default=180)
p.add_argument('--diagnostic-skip-avb',action='store_true',help='QEMU-only: remove AVB fstab flags in the temporary initramfs; never a production fix')
a=p.parse_args();a.bundle=a.bundle.resolve();a.disk=a.disk.resolve();a.initramfs=a.initramfs.resolve();a.output=a.output.resolve()
for f in [a.disk,a.initramfs,a.bundle/'Image']:
 if not stat.S_ISREG(f.stat().st_mode):raise SystemExit('Regular files required')
a.output.mkdir(parents=True,exist_ok=False)
spec=importlib.util.spec_from_file_location('cpio',Path(__file__).with_name('prepare-native-initramfs.py'));cpio=importlib.util.module_from_spec(spec);spec.loader.exec_module(cpio)
records=cpio.read_newc(gzip.decompress(a.initramfs.read_bytes()))
avb_changes=[]
if a.diagnostic_skip_avb:
 for i,(name,fields,body) in enumerate(records):
  if not name.startswith('first_stage_ramdisk/fstab.'):
   continue
  lines=[]
  for line in body.decode().splitlines():
   cols=line.split()
   if len(cols)>=5 and not line.lstrip().startswith('#'):
    flags=cols[4].split(',');removed=[x for x in flags if x=='avb' or x.startswith('avb=') or x.startswith('avb_keys=')]
    if removed:
     avb_changes.append({'file':name,'source':cols[0],'removed':removed})
     cols[4]=','.join(x for x in flags if x not in removed);line=' '.join(cols)
   lines.append(line)
  records[i]=(name,fields,('\n'.join(lines)+'\n').encode())
 if not avb_changes:raise SystemExit('No AVB flags found for diagnostic override')
(a.output/'diagnostic-overrides.json').write_text(json.dumps(avb_changes,indent=2)+'\n')
modules=[];release=(a.bundle/'kernel.release').read_text().strip()
for name in ['virtio_mmio','virtio_scsi','sd_mod']:
 lines=subprocess.check_output(['modprobe','--show-depends','-d',str(a.bundle/'modules'),'-S',release,name],text=True).splitlines()
 for line in lines:
  if not line.startswith('insmod '):continue
  src=Path(line.split()[1]);body=src.read_bytes()
  if src.suffix=='.xz':body=lzma.decompress(body)
  elif src.suffix=='.zst':body=subprocess.check_output(['zstd','-dc',str(src)])
  target='qemu-'+src.name.split('.ko')[0]+'.ko'
  if target not in [x[0] for x in modules]:modules.append((target,body))
source='''#define _GNU_SOURCE
#include <sys/mount.h>
#include <sys/syscall.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
static void load(const char *p) { int f=open(p,O_RDONLY); if(f<0 || syscall(SYS_finit_module,f,"",0)<0) {perror(p);_exit(101);} close(f); }
int main(void) {
 mkdir("/dev",0755); mount("devtmpfs","/dev","devtmpfs",0,0);
 int c=open("/dev/console",O_RDWR); if(c>=0){dup2(c,0);dup2(c,1);dup2(c,2);}
 puts("QEMU_SMOKE_WRAPPER_STARTED");
 LOAD_MODULES
 puts("QEMU_SMOKE_VIRTIO_READY"); fflush(stdout);
 umount("/dev");
 execl("/init","/init",NULL);perror("exec Android init");return 102;
}
'''.replace('LOAD_MODULES','\n'.join('load("/'+n+'");' for n,b in modules))
(a.output/'wrapper.c').write_text(source)
subprocess.run(['aarch64-linux-gnu-gcc','-static','-Os',str(a.output/'wrapper.c'),'-o',str(a.output/'qemu-init')],check=True)
for idx,(name,body) in enumerate(modules+[('qemu-init',(a.output/'qemu-init').read_bytes())]):
 if any(n==name for n,f,b in records):raise SystemExit('Archive collision')
 records.append((name,[900000+idx,stat.S_IFREG|0o755,0,0,1,0,0,0,0,0,0,0,0],body))
ram=a.output/'qemu-initramfs.cpio.gz';ram.write_bytes(gzip.compress(cpio.write_newc(records),mtime=0))
overlay=a.output/'disk.qcow2'
subprocess.run(['qemu-img','create','-f','qcow2','-F','raw','-b',str(a.disk),str(overlay)],check=True)
table=json.loads(subprocess.check_output(['sfdisk','--json',str(a.disk)]))['partitiontable']
boot_uuid=next(x['uuid'].lower() for x in table['partitions'] if x.get('name')=='super')
args=['qemu-system-aarch64','-M','virt','-cpu','max','-smp','2','-m','2048','-nographic','-no-reboot','-net','none','-kernel',str(a.bundle/'Image'),'-initrd',str(ram),'-append','console=ttyAMA0 earlycon rdinit=/qemu-init panic=0 androidboot.hardware=android-desktop androidboot.hardware.platform=android-desktop androidboot.boot_part_uuid='+boot_uuid+' androidboot.slot_suffix=_a androidboot.force_normal_boot=1 androidboot.verifiedbootstate=orange androidboot.selinux=enforcing','-drive','if=none,id=os,format=qcow2,file='+str(overlay),'-device','virtio-scsi-device,id=scsi','-device','scsi-hd,drive=os,bus=scsi.0']
(a.output/'command.json').write_text(json.dumps(args,indent=2)+'\n')
before=a.disk.stat();timedout=False
with (a.output/'console.log').open('wb') as log:
 proc=subprocess.Popen(args,stdout=log,stderr=subprocess.STDOUT)
 try:
  deadline=time.monotonic()+a.timeout
  while proc.poll() is None:
   text=(a.output/'console.log').read_text(errors='replace')
   if 'end Kernel panic' in text: break
   if time.monotonic()>=deadline: timedout=True;break
   time.sleep(1)
 finally:
  if proc.poll() is None:
   proc.terminate()
   try:proc.wait(timeout=5)
   except subprocess.TimeoutExpired:proc.kill();proc.wait()
 rc=proc.returncode
after=a.disk.stat();assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns)
s=(a.output/'console.log').read_text(errors='replace')
report={'diagnostic_skip_avb':a.diagnostic_skip_avb,'release':release,'returncode':rc,'timeout':timedout,'wrapper_started':'QEMU_SMOKE_WRAPPER_STARTED' in s,'virtio_ready':'QEMU_SMOKE_VIRTIO_READY' in s,'verity_arg_failure':'Invalid number of feature args' in s,'kernel_panic':'Kernel panic' in s,'system_logical_created':'Created logical partition system_a' in s,'second_stage_started':'init second stage started!' in s,'scope':'Real kernel and Android early init with virtual storage; no board firmware/DT/GPU validation','base_disk_metadata_unchanged':True}
report['bootstrap_apexd_failed']='bootstrap-apexd-failed' in s
report['guest_reboot']='reboot: Restarting system' in s
report['cgroup_setup_failed']='createProcessGroup' in s and 'failed for service' in s
(a.output/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
# A created device or a timeout alone is never a successful Android boot.
raise SystemExit(1 if any(report[k] for k in ['kernel_panic','bootstrap_apexd_failed','guest_reboot','cgroup_setup_failed']) else (0 if report['second_stage_started'] else 2))
