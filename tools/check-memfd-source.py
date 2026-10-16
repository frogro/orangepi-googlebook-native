#!/usr/bin/env python3
"""Reject incomplete Android17 memfd_class kernel backports before compiling."""
from pathlib import Path
import sys
p=Path(sys.argv[1])
cap=(p/'security/selinux/include/policycap.h').read_text()
enum=cap.split('enum {',1)[1].split('};',1)[0]
names=[x.strip() for x in enum.split(',') if x.strip()]
assert names.index('POLICYDB_CAP_MEMFD_CLASS')==13, 'Android policycap ABI mismatch'
checks={
 'mm/memfd.c':['security_inode_init_security_anon(inode,','&QSTR(MEMFD_ANON_NAME), NULL)'],
 'security/selinux/hooks.c':['if (!selinux_policycap_memfd_class())','isec->sclass = SECCLASS_MEMFD_FILE;','avc_has_perm(old_crsec->sid, isec->sid, isec->sclass,','avc_has_perm(new_crsec->sid, isec->sid, isec->sclass,'],
 'security/selinux/include/classmap.h':['"memfd_file"'],
 'security/selinux/include/policycap_names.h':['"memfd_class"'],
 'security/selinux/include/security.h':['selinux_policycap_memfd_class(void)'],
}
for file,needles in checks.items():
 text=(p/file).read_text()
 for needle in needles:assert needle in text,(file,needle)
print('memfd_class ABI13, labeling hook, execution checks and policy gate verified')

# Reject incomplete ashmem compatibility backports.
shim = (p / "mm/memfd-ashmem-shim.c").read_text()
shmem = (p / "mm/shmem.c").read_text()
assert "ASHMEM_GET_SIZE" in shim and "i_size_read" in shim
assert "memfd_ashmem_shim_ioctl" in shmem
assert "memfd_ashmem_shim_compat_ioctl" in shmem
print("Ashmem/memfd ioctl shim: present and wired")
