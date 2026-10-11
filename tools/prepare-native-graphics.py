#!/usr/bin/env python3
"""Stage audited native graphics files; never modifies a vendor image or device."""
import argparse,hashlib,json,struct,subprocess,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ['donor','mesa','recovery','dump_erofs','output']:p.add_argument(n,type=Path)
    a=p.parse_args()
    if a.output.exists():raise ValueError('Output must be new')
    donor=json.loads((ROOT/'docs/donor-graphics-audit.json').read_text())
    mesa=json.loads((ROOT/'docs/native-mesa-audit.json').read_text())
    entries={}
    def add(name,data,label,mode=0o644):
        if name in entries:raise ValueError('Duplicate target')
        entries[name]=(data,label,mode)
    def binary(source,name,sha,label='same_process_hal_file',mode=0o644):
        data=source.read_bytes()
        if hashlib.sha256(data).hexdigest()!=sha:raise ValueError('Hash mismatch: '+str(source))
        if data[:4]!=b'\x7fELF' or struct.unpack_from('<H',data,18)[0]!=183:raise ValueError('Not ARM64 ELF')
        add(name,data,label,mode)
    for name,record in mesa['libraries'].items():
        target='lib64/'+name
        if name.startswith(('libEGL','libGLES')):target='lib64/egl/'+name
        if name=='libvulkan_panfrost.so':target='lib64/hw/vulkan.panfrost.so'
        binary(a.mesa/name,target,record['sha256'])
    for record in donor['files']:
        source=a.donor/record['path'];name=source.name
        target='lib64/'+name;label='same_process_hal_file';mode=0o644
        if name in ['gralloc.default.so','mapper.minigbm.so']:target='lib64/hw/'+name
        elif name=='android.hardware.graphics.allocator-service.minigbm':
            target='bin/hw/'+name;label='hal_graphics_allocator_default_exec';mode=0o755
        elif name=='android.hardware.composer.hwc3-service.drm':
            target='bin/hw/'+name;label='hal_graphics_composer_default_exec';mode=0o755
        binary(source,target,record['sha256'],label,mode)
    # Read the original validated recovery using the checked LP table, not a hardcoded offset.
    import importlib.util
    spec=importlib.util.spec_from_file_location('audit',ROOT/'tools/audit-userspace.py')
    audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
    _,parts=audit.partitions(a.recovery);ext=parts['vendor_a']
    if len(ext)!=1:raise ValueError('Expected contiguous vendor')
    def original(path):return subprocess.check_output([str(a.dump_erofs),'--offset='+str(ext[0]['offset']),'--path=/'+path,'--cat',str(a.recovery)])
    rc=original('etc/init/hwc3-drm.rc')
    if b'/vendor/bin/hw/android.hardware.composer.hwc3-service.drm' not in rc:raise ValueError('Unexpected compositor service')
    add('etc/init/hwc3-drm.rc',rc,'vendor_configs_file')
    add('etc/init/vendor.qti.hardware.display.allocator-service.rc',b'''service vendor.graphics.allocator /vendor/bin/hw/android.hardware.graphics.allocator-service.minigbm
    class hal animation
    user system
    group graphics drmrpc
    capabilities SYS_NICE
    onrestart restart surfaceflinger
    task_profiles ServiceCapacityLow
''','vendor_configs_file')
    for name,xml in {
      'vendor.qti.hardware.display.allocator-service.xml':'<manifest version="9.0" type="device"><hal format="aidl"><name>android.hardware.graphics.allocator</name><version>3</version><fqname>IAllocator/default</fqname></hal></manifest>',
      'mapper.qti.xml':'<manifest version="9.0" type="device"><hal format="native"><name>mapper</name><fqname>@5.0/minigbm</fqname></hal></manifest>'}.items():
        ET.fromstring(xml);add('etc/vintf/manifest/'+name,(xml+'\n').encode(),'vendor_configs_file')
    props={'ro.hardware.egl':'mesa','ro.hardware.vulkan':'panfrost','debug.hwui.renderer':'skiagl',
           'debug.renderengine.backend':'skiaglthreaded','ro.vendor.hwcomposer.mode':'client',
           'ro.vendor.hwc.drop_drm_master':'0'}
    lines=[l for l in original('build.prop').decode().splitlines() if l.split('=',1)[0] not in props]
    add('build.prop',('\n'.join(lines+[k+'='+v for k,v in props.items()])+'\n').encode(),'vendor_file',0o600)
    a.output.mkdir(parents=True);manifest=[]
    for name,(data,label,mode) in entries.items():
        target=a.output/'vendor'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data);target.chmod(mode)
        manifest.append({'path':name,'sha256':hashlib.sha256(data).hexdigest(),'mode':oct(mode),'selinux_type_required':label})
    report={'status':'STAGED_CANDIDATE_ONLY; not imported into vendor image; enforcing policy and linker namespace checks pending',
            'files':manifest,'native_gpu_device_tree_path':'/gpu@fb000000',
            'pending':['Check merged VINTF declarations and remove any conflicting original allocator/mapper declarations.',
                       'Resolve all direct/transitive dependencies in Android vendor linker namespaces.',
                       'Preserve EROFS ownership/xattrs and validate SELinux labels and GPU/DMA buffer access.',
                       'Validate allocator/compositor buffer exchange on actual hardware.']}
    (a.output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Staged and hashed '+str(len(entries))+' native graphics files; vendor image unchanged')
if __name__=='__main__':main()
