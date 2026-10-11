#!/usr/bin/env python3
"""Stage AOSP software security services for fresh test data; no device provisioning."""
import argparse,hashlib,json,re,struct,subprocess,zipfile,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('donor',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    if a.output.exists():raise ValueError('Output must be new')
    manifest=json.loads((a.donor/'manifest.json').read_text());pins=json.loads((ROOT/'sources.json').read_text())
    if manifest['zip_sha256']!=pins['cuttlefish']['sha256']:raise ValueError('Unrecognized donor')
    for name in ['security/rust_nonsecure_payload.img','security/com.android.hardware.gatekeeper.nonsecure.apex']:
        if hashlib.sha256((a.donor/name).read_bytes()).hexdigest()!=manifest['files'][name]:raise ValueError('Donor hash mismatch')
    a.output.mkdir(parents=True)
    gate=a.output/'gatekeeper-payload.img'
    with zipfile.ZipFile(a.donor/'security/com.android.hardware.gatekeeper.nonsecure.apex') as z:
        gate.write_bytes(z.read('apex_payload.img'))
    key=a.donor/'security/rust_nonsecure_payload.img';items=[]
    def add(name,data,label,mode=0o644):
        path=a.output/'vendor'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data);path.chmod(mode)
        r={'path':name,'sha256':hashlib.sha256(data).hexdigest(),'selinux_type_required':label,'mode':oct(mode)}
        if data[:4]==b'\x7fELF':
            if struct.unpack_from('<H',data,18)[0]!=183:raise ValueError('Not ARM64')
            text=subprocess.check_output(['readelf','-d',str(path)],text=True)
            r['needed']=re.findall(r'\(NEEDED\).*\[(.*?)\]',text)
        elif name.endswith('.xml'):ET.fromstring(data)
        items.append(r)
    def read(image,path):
        r=subprocess.run(['debugfs','-R','cat '+path,str(image)],capture_output=True,check=True)
        if not r.stdout or b'File not found' in r.stderr:raise ValueError('Missing payload entry: '+path)
        return r.stdout
    add('bin/hw/android.hardware.security.keymint-service',read(key,'/bin/hw/android.hardware.security.keymint-service.nonsecure'),'hal_keymint_default_exec',0o755)
    add('lib64/native_keymint/libcrypto.so',read(key,'/lib64/libcrypto.so'),'vendor_file')
    add('bin/hw/android.hardware.gatekeeper-service.nonsecure',read(gate,'/bin/hw/android.hardware.gatekeeper-service.nonsecure'),'hal_gatekeeper_default_exec',0o755)
    for n in ['keymint','secureclock','sharedsecret']:
        name='android.hardware.security.'+n+'-service.xml'
        add('etc/vintf/manifest/native-'+name,read(key,'/etc/vintf/'+name),'vendor_configs_file')
    for name in ['android.hardware.gatekeeper-service.nonsecure.xml','android.hardware.security.sharedsecret-gatekeeper.xml']:
        add('etc/vintf/manifest/native-'+name,read(gate,'/etc/vintf/'+name),'vendor_configs_file')
    add('etc/init/native-software-keymint.rc',b'''# Software-only test service; not hardware-backed.
service vendor.keymint-default /vendor/bin/hw/android.hardware.security.keymint-service
    class early_hal
    user nobody
    setenv LD_LIBRARY_PATH /vendor/lib64/native_keymint:/vendor/lib64
''','vendor_configs_file')
    add('etc/init/android.hardware.gatekeeper-service.trusty.rc',b'''# Replacement for unavailable Trusty; software-only test service.
service vendor.gatekeeper_default /vendor/bin/hw/android.hardware.gatekeeper-service.nonsecure
    class early_hal
    user system
    group system
''','vendor_configs_file')
    report={'status':'STAGED_SOFTWARE_ONLY; not installed; no hardware-backed keys, Widevine L1 or certification',
            'files':items,'gatekeeper_payload_sha256':hashlib.sha256(gate.read_bytes()).hexdigest(),
            'pending':['Resolve all dependencies in vendor linker namespaces and validate enforcing SELinux transitions.',
                       'Remove conflicting Trusty/StrongBox HAL instances and original service/APEX selections.',
                       'Verify SharedSecret negotiation, Keystore and vold on fresh isolated encrypted test data.',
                       'Do not reuse existing Android userdata or device provisioning material.']}
    (a.output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');print('Staged '+str(len(items))+' software security files; not installed')
if __name__=='__main__':main()
