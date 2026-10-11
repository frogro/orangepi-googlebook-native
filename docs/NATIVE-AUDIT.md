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

## Donor inspection result

Official Cuttlefish build 16373615 was downloaded and SHA256-verified; 36 reference files were extracted locally without mounts. None were installed or committed. The allocator is an Android37 ARM64 ELF and exports `backend_rockchip`. The generic DRM compositor links against `android.hardware.graphics.composer3-V5-ndk.so`, matching the Googlebook declaration. File hashes and direct ELF dependencies are recorded in donor-graphics-audit.json. This establishes concrete integration candidates, not buffer-sharing, linker-namespace, SELinux or runtime compatibility.

The stock boot command line includes `binder.impl=rust` and Qualcomm pKVM protected modules; these must not be carried into the native boot config. The original userdata uses ext4 with file and metadata encryption. Retaining EROFS/F2FS support does not by itself implement the original Trusty/KeyMint security stack.

## Disk layout validation

The pinned Orange Pi 5 Plus EDK2 v1.1 donor contains Rockchip `RKNS` loader data at LBA64 and a boot firmware payload starting at 1 MiB. Its payload overlaps the stock Googlebook recovery partition at 2 MiB. Writing that donor over the recovery disk would corrupt data.

`tools/plan-native-disk.py` now validates the firmware checksum and original GPT/LP metadata, checks all 38 source partition intervals, and plans a 32 MiB shift of every Android partition plus a separate 512 MiB ESP. Logical extents remain relative to `super`; their on-disk LP values must not change. New primary and backup GPTs are required. The tool emits a plan only and never writes a block device or disk image. Kernel, ramdisk and HAL integration remain prerequisites to assembling a bootable image.

## Mesa cross-build correction

Mesa's Panfrost shader generators require a native host build of `mesa_clc`, `vtn_bindgen2` and `panfrost_compile`. LLVM18 and matching SPIRV translator are host build dependencies only. SPIRV-Tools v2024.4 and its matching headers are pinned because the runner's packaged version is older than Mesa's minimum. The Android target uses these host tools with target LLVM disabled. A successful compiler build alone does not establish runtime graphics compatibility.

`tools/assemble-native-base.py` implements file-only assembly of that layout. It verifies the complete original recovery hash, preserves source partition GUIDs/types/attributes, creates both GPT copies and a FAT32 ESP, and verifies every copied partition hash plus relocated Android LP bounds. Exclusive output creation prevents overwriting an existing file or block device. Its output is explicitly a disk base: the ESP initially has no boot application, and original Qualcomm services still require adaptation. Local assembly completed successfully under `orangepi-googlebook-base.service`; all source partition copy hashes and the relocated LP metadata match. An independent `sgdisk -v` check reports no problems with the primary/backup GPT. It warns that the preserved 512-byte KERN-A placeholder is not 16-sector aligned; that is inherited from the recovery, not a new encrypted data partition. Logs are in the parent `logs/native-base.log`, and the image plus per-partition hash report are in `output/googlebook-native-base.img{,.json}` outside this checkout. Do not flash this base as a finished OS.

Mesa follow-up: host shader generators now compile. The cross configuration needed Mesa's explicit `-Dallow-fallback-for=libdrm` in addition to Meson's force-fallback switch; without it Mesa refuses its own pinned libdrm subproject. Commit 829bae5 enables that source fallback while retaining Android-only target dependency discovery.

## Completed userspace and EFI builds

Mesa run 38102125837 and EFI run 38102173479 succeeded. Downloaded artifacts match their SHA256 manifests, and the shared libraries have ARM64 ELF machine headers. `native-mesa-audit.json` records the selected runtime libraries and direct dependencies. Android linker namespace resolution, native gralloc buffers and runtime graphics remain untested.

The EFI loader was copied into the local base image using `tools/stage-efi.py`, read back from FAT and compared byte-for-byte, then the complete written ESP hash was checked. The image sidecar now records the new ESP and loader hashes. A repeated GPT check passes. The loader deliberately reports a missing OS payload until `/boot/grub/native.cfg` and matching kernel/DTB/initramfs are supplied. There is still no native Googlebook boot success.

## Kernel and first-stage candidate

Kernel run 38099283383 completed successfully. SHA256 checks, the ARM64 Image header and native configuration gates pass. All 1,719 supplied modules have matching `6.18.54-opi5plus-googlebook-native` vermagic and a nonempty build-key signer field; this checks module metadata, not a device-side cryptographic signature acceptance. Details are in native-kernel-audit.json.

`prepare-native-initramfs.py` combines the original generic init ramdisk and platform ramdisk while preserving newc ownership, modes, device numbers and hardlink grouping. It removes 114 original module entries and the Qualcomm modem/DSP/Bluetooth firmware mounts. Storage/device-mapper/filesystem support is checked as built-in first. The output has 61 records and passes serialization round-trip checks. File/metadata encryption settings remain intact. This is only a first-stage candidate: second-stage fstab/module loading, native HAL/SELinux configuration, software security services and boot-device selection remain mandatory before a bootable Android image can be claimed. The candidate stays outside the image pending those integration gates.

## Native graphics staging

`prepare-native-graphics.py` produced 20 staged vendor files under the parent `work/native-graphics-v1`. Every binary is checked against the previously audited SHA256 and ARM64 ELF header. The staged files combine native Mesa GLES/PanVK, minigbm mapper/allocator and the generic composer3 V5 implementation. The original `hwc3-drm.rc` already uses the generic compositor executable path and is retained. Allocator/mapper declarations and graphics properties are prepared separately. No vendor filesystem has been modified yet; final linker namespace, merged VINTF, EROFS xattr and enforcing SELinux checks are still required. The compiled DTB confirms the native GPU node is `/gpu@fb000000`, not a QEMU PCI device.

## Software security candidate

`prepare-software-security.py` verifies the previously downloaded donor payload hashes and stages ten files: software KeyMint, software Gatekeeper, private KeyMint libcrypto, init entries and VINTF declarations. ELF architecture, direct dependencies and XML syntax are checked. The KeyMint donor declares version 5 and the matching SecureClock/SharedSecret services. Gatekeeper also has a SharedSecret declaration. These files are local candidates only, under `work/native-security-v1`; original Trusty/StrongBox registrations and APEX selections still need reconciliation, and vendor linker/SELinux checks must pass before import. Fresh-data encryption and SharedSecret negotiation have not been exercised. No device keys were read, copied or provisioned and no hardware-backed security or DRM certification is implied.
