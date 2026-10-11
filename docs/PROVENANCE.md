# Sources and boundaries

Exact upstream commits and recovery checksums are recorded in `sources.json`.
The recovery is downloaded from Google and is not redistributed by this repository.
The read-only boot extractor and cpio helper are from skylartaylor/gbos-vm, pinned in sources.json, with its MIT license in third_party/gbos-vm/LICENSE.
The board configuration, Android crypto patches and kernel checks derive from frogro/orangepi-android16-mainline at the recorded commit. Kernel patches retain their upstream notices.

This project targets native RK3588 boot. Apple's hypervisor, Metal, QEMU and virtual Cuttlefish graphics are not the target hardware.
Kernel, DTB and modules must come from one build. Neither Android 12 vendor modules nor the Googlebook Qualcomm modules can be loaded into our replacement kernel.
The kernel bundle is not a bootable SD image. Do not flash it as one.

Native image gates:
1. Verify the recovery and inspect bootconfig, fstab, VINTF and vendor API requirements.
2. Build a Panthor kernel with built-in EROFS and F2FS and matching signed modules.
3. Supply matching RK3588 Android hardware services, graphics mapper/composer, audio and security services; check framework/vendor compatibility and SELinux policy.
4. Assemble an independent bootable test image and verify partition bounds, checksums, bootloader, DTB and ramdisk.
5. Test on a separate card, retaining the working Android card and its backup.

A compiled kernel does not establish Android 17 compatibility, hardware-backed key provisioning, Google certification or working desktop graphics. No existing userdata is reused or formatted by these tools.

## Build and inspection

Run `bash tools/build-kernel.sh` on an ARM64 Linux builder. The manual GitHub workflow uses a separate ARM64 runner. Run `bash tools/local-inspect.sh` on Linux with Python 3, curl and lz4 to download, verify and inspect the recovery. All outputs stay next to this checkout. Inspection never writes block devices.
