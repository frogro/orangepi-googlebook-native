#!/usr/bin/env python3
"""Reject a successful compile whose config cannot provide basic Android boot/ADB."""
import sys
from pathlib import Path
config = {}
for line in Path(sys.argv[1]).read_text().splitlines():
    if line.startswith('CONFIG_') and '=' in line:
        key, value = line.split('=', 1)
        config[key] = value
required = '''ANDROID_BINDER_IPC ANDROID_BINDERFS SECURITY_SELINUX
SECURITY_SELINUX_BOOTPARAM MODULE_SIG_FORCE USB_CONFIGFS USB_CONFIGFS_F_FS
EXT4_FS DRM_ROCKCHIP HID HID_GENERIC HID_MULTITOUCH USB_HID
R8169 DM_DEFAULT_KEY BLK_INLINE_ENCRYPTION BLK_INLINE_ENCRYPTION_FALLBACK
FS_ENCRYPTION_INLINE_CRYPT CRYPTO_AES CRYPTO_XTS CRYPTO_CTS TEE OPTEE'''.split()
required += ['IP_NF_IPTABLES_LEGACY', 'IP6_NF_IPTABLES_LEGACY', 'QUOTA', 'QFMT_V2', 'NETFILTER_XTABLES', 'NETFILTER_XTABLES_LEGACY', 'NF_CONNTRACK', 'NF_NAT', 'IP_NF_IPTABLES', 'IP_NF_FILTER', 'IP_NF_NAT', 'IP_NF_MANGLE', 'IP_NF_RAW', 'IP_NF_TARGET_REJECT', 'IP6_NF_IPTABLES', 'IP6_NF_FILTER', 'IP6_NF_NAT', 'IP6_NF_MANGLE', 'IP6_NF_RAW', 'IP6_NF_TARGET_REJECT', 'NETFILTER_XT_MARK', 'NETFILTER_XT_CONNMARK', 'NETFILTER_XT_MATCH_BPF', 'NETFILTER_XT_MATCH_OWNER', 'NETFILTER_XT_MATCH_POLICY', 'NETFILTER_XT_MATCH_MARK', 'NETFILTER_XT_MATCH_CONNTRACK', 'NETFILTER_XT_MATCH_STATE', 'NETFILTER_XT_MATCH_LIMIT', 'NETFILTER_XT_MATCH_QUOTA', 'NETFILTER_XT_MATCH_PKTTYPE', 'NETFILTER_XT_MATCH_SOCKET', 'NETFILTER_XT_TARGET_NFLOG', 'NETFILTER_XT_TARGET_TCPMSS', 'NETFILTER_XT_TARGET_TPROXY', 'NETFILTER_XT_TARGET_MASQUERADE', 'NETFILTER_XT_TARGET_REDIRECT', 'FUSE_FS', 'ZRAM', 'ZRAM_BACKEND_LZ4']
android_version = sys.argv[3] if len(sys.argv) > 3 else '16'
if android_version not in ('12', '16'):
    sys.exit('Unknown Android version')
if android_version == '12':
    required += '''F2FS_FS F2FS_FS_XATTR F2FS_FS_SECURITY FS_ENCRYPTION
BLK_INLINE_ENCRYPTION BLK_INLINE_ENCRYPTION_FALLBACK FS_ENCRYPTION_INLINE_CRYPT
QUOTA QFMT_V2 ZRAM ZRAM_BACKEND_LZO ZRAM_BACKEND_LZ4 ZRAM_WRITEBACK
USB_DWC3_GENERIC_PLAT USB_DWC3_OF_SIMPLE PSTORE_PMSG'''.split()
gpu_driver = sys.argv[2] if len(sys.argv) > 2 else 'panthor'
if gpu_driver not in ('panthor', 'kbase'):
    sys.exit('Unknown GPU driver')
if gpu_driver == 'panthor':
    required.append('DRM_PANTHOR')
errors = [f'CONFIG_{key}: expected y, got {config.get("CONFIG_" + key, "n")}'
          for key in required if config.get('CONFIG_' + key) != 'y']
if gpu_driver == 'kbase' and config.get('CONFIG_DRM_PANTHOR', 'n') != 'n':
    errors.append('Kbase variant must disable Panthor')
for key in ('USB_AUDIO', 'USB_G_SERIAL', 'USB_ETH'):
    if config.get('CONFIG_' + key, 'n') != 'n':
        errors.append(f'CONFIG_{key}: legacy gadget must be disabled')
if errors:
    sys.exit('\n'.join(errors))
print('Android boot/ADB kernel configuration checks passed')
