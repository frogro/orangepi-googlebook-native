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
