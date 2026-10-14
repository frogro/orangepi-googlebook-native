# Googlebook fresh-data QEMU regression, 2026-10-14

Tested kernel: 4416798ad71ff88a23e1180ec992a171329395c5, GitHub run 38280747179, Linux 6.18.55.

A fresh qcow2 overlay used the v12 diagnostic system, matching signed modules and the previously verified Cuttlefish boot-control service. SELinux remained enforcing; userdata encryption and block checkpoints remained enabled. The raw source image was not changed.

APEX activation and boot-control startup succeeded. The earlier unknown dm-bow target error did not recur. Software KeyMint and Gatekeeper started and shared-secret negotiation succeeded.

Fresh userdata formatting then failed to mount:

```
EXT4-fs (dm-10): Filesystem with casefold feature cannot be mounted without CONFIG_UNICODE
```

Keystore subsequently failed with SQLite error 14 because /data was unavailable, and the guest rebooted. This is not a successful system boot.

The original 6.12.81 configuration enables UNICODE=y. The tested kernel already enables ext4, filesystem encryption, verity, dm-default-key, dm-bow, quota, QFMT_V2 and AES/XTS/CTS built-in. Enable UNICODE=y and enforce it in the native configuration check. No checkpoint or encryption bypass is introduced.

Next: rebuild kernel, DTB and matching signed modules; repeat the identical fresh-overlay QEMU test and require a mounted /data, initialized persistent Keystore database, successful earlyBootEnded and no recurring security-service crashes. QEMU does not validate Orange Pi graphics or hardware.
