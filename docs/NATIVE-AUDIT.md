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

## Direct dependency and declaration audit

The 18 staged ELF files were compared with recovery vendor/system/system_ext library directories and the actual `com.android.runtime.apex` Bionic payload. All direct DT_NEEDED library names have candidate providers. This is only a filename inventory, not a transitive symbol or linker-namespace compatibility pass. The local result is `work/native-dependencies-v2.json`.

A duplicate Gatekeeper registration was identified before vendor import: the stock Trusty XML already declares `IGatekeeper/default`. The security staging tool now replaces that exact XML pathname instead of adding a second declaration. Regenerated candidate: `work/native-security-v2`. Existing Trusty/StrongBox APEX selections and policy remain separate integration work.

## SELinux pathname correction

The software Gatekeeper executable now uses `/vendor/bin/hw/android.hardware.gatekeeper-service`, which is already mapped to `hal_gatekeeper_default_exec`; candidate regenerated at `work/native-security-v3`. A libselinux pathname lookup against the combined platform/system_ext/product/vendor contexts found four added graphics libraries inheriting `vendor_file`. Exact entries in `config/native-graphics-file-contexts` assign their required existing `same_process_hal_file` type. With these entries, all 30 staged paths resolve to the requested labels. This verifies path labeling only; domain permissions, GPU sysfs/DMA-buffer access, policy compilation and device runtime remain unproven. No permissive mode or broad allow rules were added.

## Framework version subset check

The staged AIDL interface versions for allocator, KeyMint, remotely provisioned component, SecureClock, SharedSecret and Gatekeeper fall within the original framework matrix 202604 version ranges (`native-hal-version-audit.json`). The matrix allows composer3 versions 4–5, matching the inspected V5 compositor. This is a subset/version comparison, not a complete `checkvintf` pass or successful service registration. The kernel matrix names 6.18.0 without embedded option requirements; matching the 6.18 series therefore does not prove all Android kernel requirements.

## Remaining assembly gates

The local disk still contains the original Qualcomm vendor and module partitions. Prepared overlays have deliberately not been treated as installed. Remaining work includes reconciling all original service/APEX selections, synchronizing both fstab stages, replacing module partitions with this kernel's modules, validating Android linker namespaces and enforcing domain permissions, building the modified EROFS/LP/AVB layout, and then wiring the kernel/DTB/ramdisk into the ESP. Native Wi-Fi/Ethernet/audio hardware services and board firmware selection also need validation. Existing GPIO/display/kernel support alone is insufficient. No device boot or encrypted-data test has taken place.

## Resumed native integration: vendor filesystem candidate

The user resumed Googlebook work after the earlier timed window. Background work is enabled again alongside the serial Android builds, without physical-device or SD writes.

`tools/assemble-vendor-candidate.py` now merges the audited graphics and software-security stages into a separate EROFS file. It preserves existing ancestor inode metadata, restores the original compact root inode xattr body after incremental import, recomputes the EROFS checksum, runs fsck and reads back every staged file. The read-only metadata helper is from the already pinned MIT-licensed gbos-vm source.

First successful output: `../work/native-vendor-v1/vendor.erofs` (398123008 bytes), SHA-256 `0c7a8af1b49b26e3377281c7089d77ff1761e799b05cd1961c3d3375ca69ceda`. All 30 files passed content, ownership, mode and SELinux xattr checks; 10 existing directory metadata records were preserved. Original desktop init and precompiled policy bytes remain unchanged. Source recovery and assembled base disk were not modified.

This is an offline filesystem candidate, not a bootable image. Remaining gates: conflicting Qualcomm/Trusty/APEX HAL selection, second-stage fstab, matching module partitions/load lists, linker namespaces and enforcing policy permissions, then LP relocation and EFI kernel/initrd/DTB integration. Existing directory-label checks do not establish that service-domain permissions are sufficient. Do not install this candidate on an SD card yet.

## Native mount tables and kernel module filesystems

`prepare-native-fstab.py` now produces matching first- and second-stage mount tables from the inspected inputs. Qualcomm modem/DSP/Bluetooth firmware mounts are removed; userdata encryption/checkpoint flags are byte-for-byte unchanged. Only the modified vendor mount drops the original AVB descriptor, whose digest cannot validate a changed filesystem; other mount AVB flags remain. This exception is explicit and limited to the experimental candidate. Output `../work/native-fstab-v1` includes the matching initramfs and vendor overlay. `native-vendor-v2` includes 31 verified files and passes filesystem/readback checks; SHA256 `35da5651b0dddd7af1096db3da5a3d874e9f208bd4990ed37be87b297d86dd65`.

`prepare-native-modules.py` builds separate vendor_dlkm and empty system_dlkm candidates from kernel run 38099283383. All 1719 modules are decompressed without modifying their ELF/signature bytes, checked for matching release and signature trailer, indexed with depmod, and read back from the resulting EROFS with identical hashes. Three module ownership/SELinux samples passed. Output `../work/native-modules-v1`; approximately 48 MiB vendor_dlkm. Signature trailer presence is not a cryptographic verification or runtime acceptance test. Kernel enforces signatures, so these must remain paired with that exact kernel artifact.

The original module loader expects Android text indexes at `/vendor/lib/modules`, so the new filesystem puts the kernel-relative paths immediately below `/lib/modules`, not below an additional release directory. Autoload aliases are retained; the common/architecture/bluey loader configs still need replacement to stop requesting absent ChromeOS/Qualcomm modules. Before integrating these two modified partitions, extend the reviewed mount/AVB treatment explicitly to those partitions in both stages; the current fstab candidate exempts vendor only. No partition replacement or SD/device writes have occurred.

## Integrated native disk and EFI boot payload

`../output/googlebook-native-integrated-v1.img` is now a separate local candidate assembled from the verified base. `integrate-native-partitions.py` validates geometry, all six LP metadata copies, group size limits, free-space bounds and input file types before replacing vendor_a/vendor_dlkm_a/system_dlkm_a. Replacements are relocated into unused super space and read back with SHA256. Other logical extent maps and GPT locations stay unchanged; sgdisk reports no problems (the inherited original KERN partition alignment warning remains). The tool can update only a previously recorded candidate in place after validating its prior replacement hashes; the base and physical devices are never modified.

Current vendor: `native-vendor-v4`, 36 files verified. Common/ARM/bluey explicit module request lists no longer request absent ChromeOS/Qualcomm modules; native built-ins and module aliases are used. The Qualcomm post-fs-data wait for coprocessor modules is gated behind an unset Qualcomm-only boot property. StrongBox APEX is explicitly unselected because there is no provisioned native implementation. Four exact graphics path labels are included in vendor_file_contexts using existing policy types. All 36 pathname checks pass. Other hardware HAL adaptation, Trusty/desktop security dependencies and actual fresh-data setup remain untested.

Both mount stages now agree and exempt only the three explicitly modified filesystems from their original AVB descriptors. Unchanged partitions retain their descriptors. This experimental native boot is not the original verified boot chain and does not claim hardware-backed security. Data encryption flags remain unchanged.

`stage-native-boot.py` installed Image, board DTB, synchronized initramfs and `/boot/grub/native.cfg` into the existing ESP. All files and the written ESP were read back and hashed. GRUB syntax passes; loader already includes the FDT module. The menu selects the SD controller, slot A, generic Android Desktop hardware init, SELinux enforcing and native DT. None of the Qualcomm pKVM/Rust Binder boot arguments were copied. This is a constructed boot attempt, not a confirmed device boot.

`audit-native-symbols.py` resolved the transitive dependency closures of all 18 added ELF files and found no missing libraries or strong symbol names. The parser accounts for ARM64 IFUNC entries. Symbol version compatibility, actual namespace visibility, resolution order and runtime still require validation. Output: `../work/native-symbols-v2/report.json`. Existing system ueventd rules already grant access to DRM, DMA heap and input nodes; no broader device permission rules were added.

Integration report with offsets, hashes, history and boot-file hashes: `../output/googlebook-native-integrated-v1.integration.json`. Do not confuse the constructed test image with a tested functional Googlebook desktop. No SD card or running device has been written. Next work: full HAL/APEX/namespace review, then explicit hardware boot test when a test medium is provided/authorized.

## Mali firmware correction

A final boot-path review found that the Qualcomm vendor firmware inventory did not provide native Mali CSF firmware. `prepare-native-firmware.py` stages the unmodified firmware from installed `linux-firmware-misc` version `20260319.git217ca6e4-0ubuntu2.2`. The distro's arch10.8 symlink resolves to its arch10.10 payload. Decompressed SHA256: `a27847ea11f8efb3136340c3ba8aab413ae25145eeb4a7f64ff5edd829a2405b`. The package's complete Mali redistribution licence stanza is included with the vendor copy; no firmware binary is committed to this repository.

The vendor copy is `/vendor/firmware/arm/mali/arch10.8/mali_csffw.bin`, with existing `vendor_firmware_file` labels. Because Panthor is built into this kernel, the same bytes are also embedded at `/lib/firmware/arm/mali/arch10.8/mali_csffw.bin` in the early initramfs. The kernel Image contains the expected `arm/mali/arch%d.%d/%s` firmware request template. Availability and path are checked; successful GPU initialization still requires the hardware test.

Latest vendor filesystem: `../work/native-vendor-v6/vendor.erofs`, 38 files checked, SHA256 `e9885362748a13649c9ae5bd7d006c673cf4d58798bf1f643782a9ef3707d757`. It replaces the earlier vendor within the integrated candidate; the latest firmware-aware initramfs is from `../work/native-firmware-v2`. Boot staging supports a repeat only after verifying the existing ESP hash, then reads the updated files/ESP back. Intermediate `native-vendor-v5` was an incomplete attempt after zstd refused the symlink input; v6 uses the resolved regular firmware file and passed.

Final integrated-candidate SHA256 (19802357760 bytes): `0579590309fcc52c053585dc9249b2d69e2584b1d61ceb395377c358f61bfb46`. Sidecar `googlebook-native-integrated-v1.img.sha256`; the complete read finished after the firmware-aware ESP update and checked that image size/mtime stayed unchanged. Latest native boot and partition readbacks passed.

Vendor init inventory contains 180 service names; the new graphics/KeyMint/Gatekeeper services are unique in the inspected vendor directories. A pre-existing duplicated `vendor.msm_irqbalance` declaration remains in the two Qualcomm init files. APEX/system imports and the original Trusty Secretkeeper service remain part of the next runtime/compatibility audit. This inventory is not a full Android init semantic validation. Local Android tablet build continues independently (53% of Ninja steps at the end of this integration pass).

## Authorized SD flash — 2026-10-11

The user explicitly authorized overwriting the previously backed-up Android SD. The 62542315520-byte removable Generic SD/MMC device was identified by persistent USB ID, original GPT UUID/partition layout and a header comparison against the verified full backup. No partitions were mounted. The 19802357760-byte integrated candidate was verified before writing and then fully read back from the SD after flushing: SHA256 `0579590309fcc52c053585dc9249b2d69e2584b1d61ceb395377c358f61bfb46` matched. Backup GPT was relocated to the physical card end; partition extents were preserved and sgdisk validation passed. The header adjustment means the post-relocation whole-card bytes are intentionally not identical to the smaller source image.

Flash evidence and partition snapshot: `../work/sd-flash-20261011/status.json` (`VERIFIED`), `gpt-verify.log`, `written-partition-table.json`. Original Android backup remains `/mnt/android-build/orangepi-android12-kernel-test/backup/full-sd-20261011-014241/android12-full-sd.img`. Device boot remains untested; the card has only been written and verified on the host.

## First device attempt: logo retained, setup key did not respond

User reports the Orange Pi logo remains visible and Esc did not produce a setup menu. This does not locate the failure: firmware, input handling, boot selection and kernel display takeover remain possible. The card is currently absent from the host, so no device changes were made.

Prepared `config/native-debug.cfg`: explicit GRUB-stage messages, visible 15-second menu, verbose kernel/early framebuffer console, no panic reboot, and `acpi=off` to make the intended native DT path explicit. The latter is a diagnostic compatibility change, not a confirmed root cause. `stage-native-boot.py --config` can install it after validating the prior ESP hash, without rebuilding kernel or Android. GRUB syntax and Python compilation checks pass. This configuration cannot help if the firmware never reaches GRUB; serial output or a firmware-only test may then be needed. Do not claim a fix yet.

## Diagnostic ESP applied — 2026-10-11

After the user reinserted the reader, the persistent SD ID, capacity and complete GPT layout matched the verified flash. Automatically mounted SD partitions were unmounted. The prior ESP was backed up and its hash matched the original. Only the 512 MiB ESP was updated with the prepared diagnostic configuration; full readback matched SHA256 `28ceec31c465f61cc8bee1aa805b50c4c03e2691ed362f1d1806b08152c1e441`, and the partition table remained unchanged. Evidence: `../work/sd-debug-20261011/applied.json`; backup: `esp-before.img`. Kernel, DTB and initramfs bytes are unchanged. The reader was safely powered off. Awaiting device boot observations; no boot fix or success is claimed.

## Direct EFI probe — 2026-10-11

The user reports only the Orange Pi logo after the diagnostic GRUB update. Card returned: GPT and FAT checks passed; complete diagnostic ESP SHA remained identical. Firmware bytes differ from the donor only in 16 blocks at 0x380000–0x38ffff, beginning with `DVKR`; origin remains unconfirmed, so these bytes were preserved.

A minimal freestanding ARM64 PE/COFF EFI application now temporarily replaces only EFI/BOOT/BOOTAA64.EFI on the SD. It clears the text console, prints `GBNATIVE EFI TEST 20261011`, and waits indefinitely without starting GRUB or Android or writing storage. ARM64 machine, EFI subsystem, relocations and byte-for-byte SD readback checked. Original loader, source, probe and hashes: ../work/efi-probe-20261011. Restore BOOTAA64-original.EFI before normal boot testing. Device result pending. Reader left powered on; all SD partitions unmounted.

## EFI probe result and loader restoration — 2026-10-12

User reports only the Orange Pi logo again. Returned SD identity, complete GPT
partition geometry and EFI probe file match the recorded state; FAT check passes.
The exact probe successfully prints its banner under QEMU/AAVMF (log in
../work/efi-return-20261012/qemu-probe.log). This validates the generic EFI
application, not board firmware operation. The hardware failure is not yet
localized: boot source/selection, firmware initialization or console remain
candidates; no evidence establishes that GRUB or Linux ran.

Restored the original GRUB loader after verifying its recorded SHA256, flushed
and read back byte-for-byte. No kernel, Android partitions or firmware were
changed. All SD partitions are unmounted. Per user instruction, never power off
or eject the reader controller: unmount and flush only, leaving USB enumerated.

Next hardware diagnostic: attempt Esc/F1 with a wired USB keyboard from power-on
and observe the firmware progress bar and activity LED. If unavailable, obtain
UART output before further kernel changes. Check for competing SPI/eMMC boot
firmware without deleting or reflashing it blindly. The local EDK2 README warns
that another U-Boot can take precedence. No boot fix is claimed.

## Android12 early boot comparison and FIT repair — 2026-10-12

User again reports logo only, no F1 response and no Ethernet LED. Treat the next
boot stage as unconfirmed; an unlit Ethernet LED alone does not locate failure.
The working Android12 backup has DDR V1.08 (20220617), SPL 2017.09
gc060f28d70 (2022-04-18), and the U-Boot FIT partition at 8 MiB. The UEFI
donor has SPL 2017.09 g5f53abfa1e (2022-12-26) and its FIT at 1 MiB.
Both contain ATF/OP-TEE, but their FIT loadables and NV-data handling differ.
Do not transplant the Android SPL or relocate UEFI FIT without handling these
dependencies. A competing SPI/eMMC bootloader remains a hypothesis.

The returned SD has a 64 KiB DVKR vendor-storage block at 0x380000, where the
verified donor and original constructed image contain FF padding. This falls
INSIDE the UEFI payload hashed by the FIT. With Rockchip's 512-byte external
data alignment, payload begins at 0x100a00 and spans 0x500000 bytes. Donor
SHA256 matches FIT c212e5a7a7230979cdbde339c113f7fe2227da57e9c282d369adc20151f45bcf;
returned SD instead hashes b301c7dc3554fe5e7183f72a03cf644faeee09b41238cd2d790fea81c1983a58.
Host dumpimage assumes different alignment for this FIT: its initial extracted
hash was misleading and must not be used (corrected fit-checksums.json).

After verifying physical identity, full GPT layout and donor hash, saved the
first 32 MiB on Intenso and restored ONLY those 64 KiB from the pinned donor.
Flush/readback verifies the entire donor region from 0x8000 through donor EOF,
and the UEFI payload now matches the FIT checksum. No GPT, Android, EFI loader,
SPI or eMMC changes. All SD partitions unmounted, controller kept powered.
Evidence: ../work/bootchain-20261012/{fit-checksums.json,repair.json,sd-first32m.bin}.
The creation time/source of the vendor block is not established. It may recur
on boot; next test must check display progress and then re-read this region if
still stuck. This is a proven byte-integrity repair, not confirmed boot success.

## Repeated overwrite and missing SPL GPT entry — 2026-10-12

After the repaired card was tested, the exact 64 KiB region at 0x380000 again
contains DVKR vendor data. User confirms no eMMC or NVMe installed; SPI status
remains unknown. Returned first32MiB and hash are saved in bootchain-20261012.
Repeated repair alone is ineffective; writer/stage remains unproven.

The donor GPT has a partition named uboot, sectors 2048..18431. Our assembler
retained its FIT bytes but omitted this entry. The Rockchip next-dev SPL source
(common/spl/spl_mmc.c, locally captured) supports name-based raw-partition load
before raw-sector fallback; exact binary behavior remains hardware-unverified.
Added preservation of this donor entry to assemble-native-base.py, with geometry
and reserved-area bounds validation. Python compilation passes.

On a sparse local disk, loaded the backed-up current GPT, added partition40
uboot at 2048..18431 and verified GPT before applying the same entry to the SD.
All original 39 entries remain byte-equivalent in sfdisk output (geometry, IDs,
attributes); no OS partition moved. Restored the 64KiB FIT area again and verified
the expected payload hash. GPT verification reports no problems aside from the
pre-existing one-sector KERN-A alignment advisory. Reader remains powered.

Evidence: before-uboot.gpt, gpt-test.img, with-uboot-partition.json. This is a
new layout hypothesis test, not proof of boot success. The large integrated
image has not been rebuilt; assembler fix applies to future assembly. Previous
39-entry identity snapshots must not be used unmodified for subsequent SD writes.
Next device observation should distinguish firmware menu/GRUB output from the
same logo-only failure; on return, check for recurrent vendor overwrite first.

## First Linux boot: missing dm-verity FEC — 2026-10-12

Photo confirms Linux 6.18.54-opi5plus-googlebook-native running on Orange Pi 5
Plus, SD detected, metadata EXT4 mounted and logical system_a created. It then
reports verity: Invalid number of feature args, followed by PID1 termination
and Attempted to kill init. do_group_exit is the consequence, not the origin.

Stock vbmeta_a decoded by avbtool: system has FEC roots=2, offset 1069469696,
size 8462336. Original kernel config enables DM_VERITY_FEC; our built artifact
disables it. Linux dm-verity bounds its feature arguments by conditional FEC
support, consistent with this exact failure. Also loop-control times out: our
BLK_DEV_LOOP=m, original=y. These are independent early-init configuration gaps.

config/native.config now enables DM_VERITY_FEC=y and BLK_DEV_LOOP=y (min16).
check-native-config.py now requires both built-in. No AVB checks disabled and no
partition data modified. A replacement kernel and its matching signed modules
must be built and integrated before hardware validation. Existing kernel bundle
remains the old broken configuration. A lightweight dependency check uses an
isolated output directory with the available 6.18.55 source; it is not a full
6.18.54 build or device proof.

Validation: new guard rejects the original artifact for precisely FEC and loop; passes with both corrected. Isolated Kconfig resolves both plus Reed-Solomon built-in. Full native guard on the different CIX source cannot pass because that tree lacks Android DM_DEFAULT_KEY; no claim of a full native build check.
