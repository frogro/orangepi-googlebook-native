# Googlebook 6.12.81 versus native 6.18.55 configuration audit

The complete symbol/value comparison includes y, m, n, absent symbols and
non-boolean values; it is not a claim of semantic equivalence across releases.
Reference: recovered Googlebook build 16471258, Linux 6.12.81.
Tested native: GitHub run 38247430845, Linux 6.18.55.
6,539 reference symbols, 8,863 native symbols, 5,444 differing entries.
Reference y -> native m: 264; reference m -> native y: 14.
Enabled reference -> native disabled: 247; enabled -> absent: 340.
An absent symbol may have been removed, renamed, selected differently, or be
an Android-only patch. It does not automatically mean absent functionality.

## Reviewed boot and userspace differences

- DM_BOW=y is required by the actual ext4 userdata checkpoint=block entry.
  The missing target causes /data mount failure and the captured Keystore
  SQLite panic. Port it and require built-in support.
- QUOTA/QFMT_V2, FUSE and Android netd legacy tables are already included in
  the later 5ee4216 build inputs. That build was not the kernel in the failing
  Keystore test; do not conflate requested inputs with tested artifacts.
- Core loop, verity/FEC, binder, cgroups, fscrypt/default-key, ext4 and erofs
  have built-in assertions in the project validation scripts.
- BLK_DEV_SD and virtual storage transports are modules in the native kernel;
  the QEMU wrapper loads their matching modules before Android init. Their
  y->m difference must not be interpreted as missing functionality. Other
  module differences still require runtime module-loading coverage.
- DM_USER remains absent: inspect virtual A/B / snapuserd update requirements
  before claiming update completeness. dm-bow alone does not validate OTA.
- ASHMEM and ANDROID_WRAPFD remain Android-specific compatibility questions.
  The tablet memfd library has not been copied into Googlebook.
- NETFILTER_XT_MATCH_QUOTA2, FUSE_BPF and Android vendor hooks are not silently
  replaced by similarly named upstream features. Evaluate actual userspace
  calls when their relevant services start.
- Qualcomm, UFS, pKVM/Trusty, compiler/GKI/KABI and other architecture-specific
  flags cannot be wholesale enabled on the Rockchip target.

This is a complete mechanical diff with prioritized review, NOT validation of
all 5,444 differences or proof that every =m driver is loaded correctly.
The candidate's resolved config must be compared again after olddefconfig;
GitHub's final kernel.config remains the authoritative shipped configuration.

`resolved-candidate-diff.tsv` compares all values after olddefconfig using
the pending branch inputs plus dm-bow/default-key patches on a private
6.18.55 test source. Native and Android configuration assertions both pass.
The final GitHub artifact still needs comparison because its complete board
source preparation and native compiler differ from this cross-compile check.

Validation: ARM64 GCC 15 cross-compilation of dm-bow.o and dm-default-key.o
passes on Linux 6.18.55. Final dm-bow compilation has no compiler warnings.
Both project config checkers pass; a negative check with DM_BOW disabled
is rejected. Patch reverse dry-run passes with zero fuzz. No runtime
checkpoint or filesystem recovery success is inferred from these checks.
