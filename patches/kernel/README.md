# Android encryption port for Linux 6.18.54

0001 derives dm-default-key and skip-default-key BIO/fscrypt handling from:
https://github.com/dvab-sarma/android_kernel_rk_opi/tree/dc84a44bc09b7ca6fd938dfce96ff62c41055e9b
(Android 16 / 6.18 branch). Original Google copyright and GPL license are retained.

Only the default-key changes are ported. In particular the source branch's older
BIO bounce allocation and fscrypt device-list implementations are NOT copied
back over 6.18.54. The skip flag is propagated in the current
blk_crypto_alloc_enc_bio() path, reset in bio_init(), cloned through
bio_crypt_clone(), and checked when fscrypt decides whether I/O can be merged.
This prevents file ciphertext from being encrypted a second time by default-key.

The target advertises version 2.1.0, matching the live Android 12 target. This is
not by itself proof of old encrypted-volume compatibility. Live hardware must
also support the old KeyMint service and its existing Secure World keys.

0002 adds /firmware/optee using the linaro,optee-tz SMC binding observed in the
live Android 12 DTB. It does not replace or install Secure World firmware.

Both Android targets get built-in crypto and OP-TEE support. Android 16's fstab
remains unencrypted; adding kernel capability does not encrypt or migrate data.
Never remove old encryption flags, recreate metadata or allow a recovery test to
format existing userdata. Test mounting/unlocking on an offline clone first.

Validation on 2026-10-10: olddefconfig retained all required features. ARM64
cross-compilation passed for dm-default-key, BIO initialization, software crypto
fallback, fscrypt inline integration, dm-table, blk-crypto and the TEE directory.
The Plus DTB compiled and /firmware/optee reports linaro,optee-tz and smc.
These checks do not replace encrypted-volume read/write and unlock tests.

## 0003: Googlebook userdata block checkpoints (6.18.55)

Source: Android common android16-6.12, pinned commit
`f2c26311c21cf60ea5bf9ac15c3242139e210689`, drivers/md/dm-bow.c.
https://android.googlesource.com/kernel/common/+/f2c26311c21cf60ea5bf9ac15c3242139e210689/drivers/md/dm-bow.c

Preserves the original GPL notice and checkpoint implementation. Adapts
prepare_ioctl to the 6.18 callback signature, preserving the device-size
restriction used by the upstream linear target. File-local helpers and module
entry points are static. Adds Kconfig/Makefile integration and requires
CONFIG_DM_BOW=y in native validation. No userdata/metadata formatting or
encryption flag changes are included. The Googlebook ext4 checkpoint=block
requirement was observed failing in QEMU before the Keystore database panic.

ARM64 object compilation and configuration checks are recorded in the config
audit. Actual checkpoint create/commit/rollback and encrypted /data boot
remain runtime tests; compilation alone does not certify update safety.

## Android cgroup-v1 task migration

`0004-android-cgroup-cap-sys-nice.patch` matches the capability exception in Android common `android16-6.12`. The native mainline kernel rejects cross-UID task migration by UID 1000 even though system_server has CAP_SYS_NICE. Live logs show AddTidToCgroup returning Permission denied; the cgroup files are already system-owned and writable. This is a kernel source change, not a configuration option. Boot validation must confirm that these errors disappear.

Android17 memfd_class: 0006 backports upstream 094e94d13b606b820e3d1383e3a361f680ff023a. Only old_tsec/new_tsec names were adapted to old_crsec/new_crsec for 6.18.55. Policy capability index13 is preserved. No global SELinux relaxation. This is required for Googlebook vendor API202604 shared buffers; hardware AAC test remains pending.
