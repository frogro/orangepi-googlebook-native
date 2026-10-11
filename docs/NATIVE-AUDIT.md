# Native port audit — 2026-10-11

Recovery build 16471258 was downloaded from Google. Both ZIP and extracted image match the checksums in sources.json. Read-only GPT CRC and LP metadata checksums/bounds pass. Boot/kernel/ramdisk extraction completed in the isolated workspace.

## Observed interfaces

- System and vendor report Android 17, SDK 37, SDK full 37.1.
- Vendor platform is Qualcomm `hamoa`; vendor board API and SELinux version are `202604`.
- Framework matrices include levels 8, 202504 and 202604. Level 202604 names kernel 6.18.0. Our 6.18.54 candidate matches that kernel series; this is not a complete VINTF/config/runtime pass.
- SELinux mappings exist for 31.0, 32.0, 33.0, 34.0, 202404, 202504 and 202604. Presence is not proof that our Android16 vendor policy compiles with this system.
- The original kernel and our candidate use 4 KiB ARM64 pages.
- The original vendor advertises composer3 version 5 and native mapper 5.0/qti. Qualcomm allocator/mapper must be replaced with a compatible native DRM/Mali path.
- Native Mesa GLES/PanVK is built separately with NDK 28.2.13676358. Panthor is the kernel driver; Mesa's build driver name is panfrost. VirGL/Venus/Metal are not selected.

## Boot changes required

The original fstab mounts logical A/B EROFS partitions and encrypted ext4 userdata. It also waits for Qualcomm modem, DSP and Bluetooth firmware partitions. The ramdisk and second-stage vendor mount tables must agree after adaptation. Do not reuse existing Android12 userdata or its encryption metadata.

The stock command line requests Rust Binder and Qualcomm protected-KVM modules. It cannot be copied to our kernel unchanged: our Binder is built-in C, and neither those modules nor their hardware exists on RK3588. Native boot does not require a QEMU guest or host KVM. Software KeyMint/Gatekeeper are candidates for the isolated test installation, without hardware-backed security claims.

Old Googlebook system/vendor_dlkm modules are not compatible with the replacement kernel. Use only the new build's signed modules and DTB. The whole boot chain and partition layout still need assembly and validation; the CI output is currently a kernel bundle, not an SD image.

## Current next steps

1. Finish the native kernel build and verify its bundle and module signatures/vermagic.
2. Build native Mali userspace and inspect its Android dynamic-library dependencies.
3. Inspect official Cuttlefish build 16373615 generic userspace services for reuse. Its virtio modules and virtual-radio service are not suitable Orange Pi hardware drivers.
4. Assemble the native vendor changes with matching VINTF declarations and enforcing SELinux policy; establish native display allocator/composer compatibility.
5. Generate and verify an independent test disk with a board-appropriate bootloader. No physical storage writes are part of this preparation.

No boot, desktop, audio, DRM or hardware acceleration success has been established for this new image.
