#!/usr/bin/env python3
import sys
from pathlib import Path
c=dict(line.split('=',1) for line in Path(sys.argv[1]).read_text().splitlines() if line.startswith('CONFIG_') and '=' in line)
required='EROFS_FS EROFS_FS_ZIP F2FS_FS FS_ENCRYPTION FS_VERITY DRM_PANTHOR DRM_ROCKCHIP ANDROID_BINDER_IPC BLK_DEV_DM DM_VERITY DM_VERITY_FEC BLK_DEV_LOOP DM_DEFAULT_KEY ARM64_4K_PAGES'.split()
missing=[k for k in required if c.get('CONFIG_'+k)!='y']
if missing: sys.exit('Missing built-in native requirements: '+', '.join(missing))
print('Native filesystem, graphics and Android kernel configuration checks passed')
