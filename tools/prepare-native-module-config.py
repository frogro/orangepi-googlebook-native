#!/usr/bin/env python3
"""Replace platform-specific explicit module requests with native alias loading."""
import argparse,hashlib,json,subprocess
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for n in ['vendor','dump_erofs','kernel_config','output']:p.add_argument(n,type=Path)
a=p.parse_args();cfg=a.kernel_config.read_text()
for key in ['DRM_ROCKCHIP','DRM_PANTHOR','MMC_DW_ROCKCHIP','MMC_SDHCI_OF_DWCMSHC','DMABUF_HEAPS_SYSTEM']:
 assert 'CONFIG_'+key+'=y\n' in cfg,key
files=[];a.output.mkdir(parents=True,exist_ok=False)
for name in ['init.insmod.common.cfg','init.insmod.cfg','init.insmod.bluey.init.cfg']:
 path='etc/'+name
 original=subprocess.check_output([str(a.dump_erofs),'--cat','--path=/'+path,str(a.vendor)])
 assert b'modprobe|' in original,path
 data=b'# Native RK3588: display, storage and system heap are built into this kernel.\n# Remaining drivers load through ueventd and vendor_dlkm/modules.alias.\n# Do not request the original Qualcomm or ChromeOS platform modules.\n'
 dst=a.output/'vendor'/path;dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(data)
 files.append({'path':path,'sha256':hashlib.sha256(data).hexdigest(),'source_sha256':hashlib.sha256(original).hexdigest(),'mode':'0o644','selinux_type_required':'vendor_configs_file'})
(a.output/'manifest.json').write_text(json.dumps({'status':'NATIVE_MODULE_CONFIG; hardware HAL and firmware selection still pending','files':files},indent=2)+'\n')
