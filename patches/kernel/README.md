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

Diagnostic branch only: `0005-hdmirx-audio-diagnostics.patch` records the measured
HDMI audio rate before fallback and periodic receiver state. See
`docs/HDMI-AUDIO-DIAGNOSTIC-20261014.md`; this is instrumentation, not a fix.
