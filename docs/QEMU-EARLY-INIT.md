# Googlebook early-init QEMU check

`tools/qemu-android-init-smoke.py` runs a real kernel bundle and the adapted
Googlebook initramfs against a QCOW2 overlay of the native system image. It
refuses block-device inputs. Base-image size/mtime must stay unchanged.

Requirements: qemu-system-aarch64, qemu-img, aarch64-linux-gnu-gcc with static
libc, modprobe, sfdisk, Python 3; zstd if modules are compressed with zstd.
All outputs belong on Intenso. Use a fresh output directory on every run.

Example from the project directory:

```sh
nice -n 15 python3 tools/qemu-android-init-smoke.py \
  --bundle ../work/artifacts/kernel-38099283383/orangepi5-plus-googlebook-native-kernel-38099283383 \
  --initramfs ../work/native-firmware-v2/initramfs-native-candidate.cpio.gz \
  --disk ../output/googlebook-native-integrated-v1.img \
  --output ../work/qemu-new-run --timeout 180
```

The small static PID1 wrapper loads the bundle's own signed VirtIO MMIO/SCSI
modules and executes the unchanged Android `/init`. Android discovers the
virtual disk using the existing `super` partition UUID. The wrapper is only
for QEMU; never install it on the physical SD. Kernel FEC and loop settings are
not repaired by the wrapper, so their failures remain observable.

QEMU uses its generated virt-machine DT, not the incompatible RK3588 DTB.
SELinux remains enforcing and AVB handling remains that of the candidate
initramfs. No graphics device or network is provided. Two virtual CPUs and
2 GiB RAM limit the test footprint; this is not an Android desktop benchmark.

Outputs: console.log, report.json, exact command, test initramfs and disk overlay.
Exit 1 means kernel panic, guest reboot or detected bootstrap/cgroup failure; exit 2 means inconclusive/second stage not observed;
exit 0 means Android second-stage init was observed without a detected fatal failure
in the time window. None of these establish desktop or physical board success.

Scope: kernel execution, module loading, partition discovery, logical partitions,
verity and early filesystem/init transitions. It does NOT validate Rockchip ROM,
SPL, UEFI, GRUB, GPIO, physical SD, board DT, HDMI, Panthor/Mali, audio or Ethernet.
Those require the separate EFI/GRUB tests and real board validation.

## Baseline verified on 2026-10-12

Old kernel bundle 38099283383 with native-firmware-v2 initramfs and integrated-v1
system reproduces the board failure: loop-control timeout, mounted metadata,
created system_a, `verity: Invalid number of feature args`, then PID1 panic.
Evidence: ../work/qemu-android-init-old-v4/{console.log,report.json}.
The VM was stopped after the completed panic trace. The test correctly exits 1.
Earlier harness iterations failed at virtual storage discovery; those are not
FEC reproductions. New kernel bundles still need their comparison runs.

## Explicit diagnostic override

`--diagnostic-skip-avb` removes only AVB-related fstab flags in the temporary
QEMU initramfs. Every removed flag is recorded in diagnostic-overrides.json;
report.json labels this mode. The original initramfs, disk and physical SD are
unchanged. Use only to look for subsequent boot errors while awaiting a fixed
kernel. This mode cannot validate AVB or count as the normal regression pass.
SELinux and userdata encryption flags remain unchanged. Default runs preserve
AVB. Never install the diagnostic initramfs on the device.

## Diagnostic result on 2026-10-12

With the old 6.18.54 bundle and `--diagnostic-skip-avb`, Android reaches second
stage init at 89.6 guest seconds. The next observed blocker is cgroup setup:
`Unknown subsys name 'blkio'`, missing `/sys/fs/cgroup/system/uid_0`, then
`createProcessGroup` fails for `apexd-bootstrap`. Android reboots with
`bootloader,bootstrap-apexd-failed` at 127.6 guest seconds. The bundle has
`CONFIG_BLK_CGROUP` disabled. This is a concrete configuration gap; it does not
by itself prove the cause of every cgroup or ueventd failure. SELinux property
permission denials also occur and need separate assessment. No desktop boot
was achieved. Evidence: ../work/qemu-android-init-diagnostic-noavb-v1/console.log.
The report classifier now treats this guest reboot as failure even though QEMU
itself exits zero. The saved report was reclassified from the existing log.

## Consolidated cgroup kernel correction

Read-only extraction from the integrated system confirms that cgroups.json
requires v1 blkio, cpu and cpuset, plus cgroup v2 with optional memory. The old
kernel lacks BLK_CGROUP and CPUSETS_V1. Both are now explicitly enabled and
required by check-native-config.py, together with the existing scheduler and
memory controller requirements. The original Googlebook kernel also enables
both missing options. MEMCG_V1 is not added: this system config uses v2 memory.
Evidence files are in ../work/cgroup-audit/. This corrects proven configuration
gaps, but a new QEMU run with AVB enabled must establish whether apexd proceeds.
SELinux property denials remain a separate userspace audit item; enforcement
and security policy are unchanged.
