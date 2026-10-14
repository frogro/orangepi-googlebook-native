# Original Googlebook kernel comparison and swap correction

The original mica 6.12.81 config was compared with the config read from the running 6.18.55 RK3588 kernel. The full 9,712-symbol comparison retains y/m/n distinctions; 569 original enabled options are disabled or absent in the running kernel. This count includes board-specific drivers, renamed/removed options and Android downstream extensions, not 569 proven boot blockers.

## Confirmed defect and changes

`CONFIG_ZRAM=y` did not imply `CONFIG_SWAP=y`. The live kernel had no `/proc/swaps`; mmd_setup aborted with ENOENT. Enable SWAP and require it in the build check. Also enable original zRAM LZO/LZO-RLE and ZSTD backends, default LZO-RLE, writeback and multiple compression support. This makes features available; it does not automatically configure writeback to the SD card.

Additional generic parity: MEMCG_V1, BLK_CGROUP_IOCOST, BLK_CGROUP_IOPRIO, IO_URING, CRYPTO_HCTR2, netfilter NOTRACK/TRACE, modular RFCOMM and HIDP with RFCOMM TTY. Bluetooth HAL compatibility remains a separate userspace task.

The base is commit 2a8b43388c31bfb81df3c063a5f548e983d00185, successful run 38562540372. Preserve its Panthor/RK3588 drivers, netfilter, DM_BOW, quota and built-in Unicode/casefold fixes.

## Differences deliberately not copied

Qualcomm hardware, vendor hooks/KABI and architecture-specific or renamed crypto symbols are not transplanted. BPF_LSM, SafeSetID/Landlock and scheduler policy changes need their own userspace requirement review; simply enabling their config symbols does not establish parity. Android downstream DM_USER, FUSE_BPF, zRAM Android ioctl and Android USB accessory/uevent extensions are absent from this source and require separate porting if runtime evidence requires them. The current filesystem and ADB fixes do not establish these interfaces.

## Validation and limits

Merged the same four fragments as CI and ran ARM64 olddefconfig against the local patched 6.18.55 source. Both existing configuration checkers pass. A negative check confirms removing SWAP is rejected. No local kernel compilation was performed. CI repeats configuration checks against the pinned build source and produces Image, DTB and matching signed modules. Native boot and mmd validation are pending the resulting artifacts. This kernel change does not fix ADB trade-in mode, service manifests or device suspend policy.
