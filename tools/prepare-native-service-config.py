#!/usr/bin/env python3
"""Extend the graphics stage with narrowly scoped native platform configuration."""
import argparse,hashlib,json,shutil,subprocess
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for n in ['graphics_stage','vendor','dump_erofs','output']:p.add_argument(n,type=Path)
a=p.parse_args();assert not a.output.exists();shutil.copytree(a.graphics_stage,a.output)
report=json.loads((a.output/'manifest.json').read_text())
def original(path):return subprocess.check_output([str(a.dump_erofs),'--cat','--path=/'+path,str(a.vendor)])
def add(path,data,label='vendor_configs_file',mode='0o644'):
 dst=a.output/'vendor'/path;dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(data)
 report['files']=[f for f in report['files'] if f['path']!=path]
 report['files'].append({'path':path,'sha256':hashlib.sha256(data).hexdigest(),'mode':mode,'selinux_type_required':label})
props=(a.output/'vendor/build.prop').read_bytes()
key=b'ro.vendor.apex.com.android.hardware.keymint.strongbox.desktop='
assert not any(l.startswith(key) for l in props.splitlines())
entry=next(f for f in report['files'] if f['path']=='build.prop')
add('build.prop',props+b'\n# RK3588 test platform has no provisioned StrongBox implementation.\n'+key+b'none\n',entry['selinux_type_required'],entry['mode'])
path='etc/init/hw/init.qti.kernel.rc';data=original(path)
old=b'on post-fs-data\n    # Late attach SOCCP and start ADSP and CDSP\n    wait_for_prop vendor.all.modules.ready 1\n    restart start-subsys'
assert data.count(old)==1
# Keep the section explicitly gated, preserving all unrelated actions.
new=b'on post-fs-data && property:ro.boot.native.qti_subsystems=1\n    # Only applicable to Qualcomm subsystems, absent on RK3588.\n    wait_for_prop vendor.all.modules.ready 1\n    restart start-subsys'
add(path,data.replace(old,new))
path='etc/selinux/vendor_file_contexts';data=original(path)
extra=(Path(__file__).resolve().parents[1]/'config/native-graphics-file-contexts').read_bytes()
assert extra.strip() not in data
add(path,data+b'\n# Native graphics paths, using existing policy types.\n'+extra)
report['status']='NATIVE_SERVICE_CANDIDATE; StrongBox unselected; QTI coprocessor wait gated; other HAL compatibility pending'
(a.output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
