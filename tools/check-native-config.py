#!/usr/bin/env python3
import sys
from pathlib import Path
c=dict(line.split('=',1) for line in Path(sys.argv[1]).read_text().splitlines() if line.startswith('CONFIG_') and '=' in line)
required='DEBUG_INFO_BTF DEBUG_INFO_BTF_MODULES MEMFD_CREATE MEMFD_ASHMEM_SHIM VIRTUALIZATION KVM VSOCKETS VSOCKETS_DIAG VSOCKETS_LOOPBACK VIRTIO_VSOCKETS_COMMON VHOST VHOST_IOTLB VHOST_VSOCK TUN EVENTFD UNIX EROFS_FS EROFS_FS_ZIP F2FS_FS FS_ENCRYPTION FS_VERITY DRM_PANTHOR DRM_ROCKCHIP ANDROID_BINDER_IPC BLK_DEV_DM DM_VERITY DM_VERITY_FEC BLK_DEV_LOOP DM_DEFAULT_KEY DM_BOW UNICODE EXT4_FS QUOTA QFMT_V2 ARM64_4K_PAGES CGROUPS BLK_CGROUP CGROUP_SCHED FAIR_GROUP_SCHED CFS_BANDWIDTH CPUSETS CPUSETS_V1 MEMCG'.split()
required += ['SWAP', 'ZRAM_BACKEND_ZSTD', 'ZRAM_BACKEND_LZO', 'ZRAM_DEF_COMP_LZORLE', 'ZRAM_WRITEBACK', 'ZRAM_MULTI_COMP', 'MEMCG_V1', 'BLK_CGROUP_IOCOST', 'BLK_CGROUP_IOPRIO', 'IO_URING', 'CRYPTO_HCTR2', 'NETFILTER_XT_TARGET_NOTRACK', 'NETFILTER_XT_TARGET_TRACE', 'BT_RFCOMM_TTY']
missing=[k for k in required if c.get('CONFIG_'+k)!='y']
missing += [k for k in ['BT_RFCOMM', 'BT_HIDP'] if c.get('CONFIG_'+k) not in ('y', 'm')]
if missing: sys.exit('Missing built-in native requirements: '+', '.join(missing))
print('Native filesystem, graphics and Android kernel configuration checks passed')
