#!/usr/bin/env bash
# Build a standalone ARM64 EFI loader; OS payload/configuration is separate.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/output/efi"
mkdir -p "$OUT/EFI/BOOT" "$ROOT/work/efi"
test -d /usr/lib/grub/arm64-efi
cat > "$ROOT/work/efi/grub.cfg" <<'CFG'
search --no-floppy --label GBNATIVE --set=root
if [ -f /boot/grub/native.cfg ]; then
    configfile /boot/grub/native.cfg
else
    echo "Googlebook native test base: OS boot payload has not been installed."
    echo "This is not a completed bootable Android image."
    sleep --interruptible 60
fi
CFG
grub-mkstandalone -O arm64-efi -d /usr/lib/grub/arm64-efi \
  --modules='part_gpt fat normal configfile search search_label linux fdt echo sleep test' \
  --locales='' --fonts='' -o "$OUT/EFI/BOOT/BOOTAA64.EFI" \
  "boot/grub/grub.cfg=$ROOT/work/efi/grub.cfg"
python3 - "$OUT/EFI/BOOT/BOOTAA64.EFI" <<'PY'
import struct, sys
from pathlib import Path
b=Path(sys.argv[1]).read_bytes()
assert b[:2]==b'MZ'
p=struct.unpack_from('<I',b,0x3c)[0]
assert b[p:p+4]==b'PE\0\0'
assert struct.unpack_from('<H',b,p+4)[0]==0xaa64, 'Not ARM64 EFI'
print('ARM64 PE/COFF loader verified')
PY
grub-mkstandalone --version > "$OUT/grub-version.txt"
dpkg-query -W grub-common grub-efi-arm64-bin > "$OUT/package-versions.txt"
cp "$ROOT/work/efi/grub.cfg" "$OUT/embedded-grub.cfg"
printf 'EFI_LOADER_ONLY; OS kernel/DTB/initramfs/native.cfg not included\n' > "$OUT/STATUS.txt"
(cd "$OUT" && sha256sum EFI/BOOT/BOOTAA64.EFI embedded-grub.cfg > SHA256SUMS)
