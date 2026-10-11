#!/usr/bin/env bash
set -euo pipefail
LAB="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export ROOT_DIR="$LAB/work/builder"
export LOCALVERSION=-opi5plus-googlebook-native
mkdir -p "$LAB/work" "$LAB/output"
readarray -t pins < <(python3 - "$LAB/sources.json" <<'PINS'
import json,sys
s=json.load(open(sys.argv[1]))
print(s['board_builder']['commit']); print(s['kernel']['vyos_ref']); print(s['kernel']['version'])
PINS
)
if [[ ! -d "$ROOT_DIR/.git" ]]; then
  git init "$ROOT_DIR"
  git -C "$ROOT_DIR" remote add origin https://github.com/frogro/vyos-arm64-board-builder.git
fi
git -C "$ROOT_DIR" fetch --depth 1 origin "${pins[0]}"
git -C "$ROOT_DIR" checkout --detach FETCH_HEAD
source "$ROOT_DIR/lib/ui.sh"
source "$ROOT_DIR/lib/board-hardware.sh"
source "$ROOT_DIR/sources/vyos.sh"
export VYOS_REF="${pins[1]}"
vyos_fetch
board_hardware_select orangepi5-plus
vyos_kernel_prepare "${pins[2]}" "$BOARD_BASE_PATCHES" "$BOARD_PERIPHERAL_PATCHES"
src="$ROOT_DIR/cache/linux-vyos/linux-${pins[2]}"
python3 "$ROOT_DIR/tools/patch-hdmi-audio-dependency.py" "$src"
python3 "$LAB/tools/patch-rockchip-dma-mask.py" "$src"
for patch_file in "$LAB"/patches/kernel/*.patch; do
  if ! patch --batch --fuzz=0 -R --dry-run -p1 -d "$src" < "$patch_file" >/dev/null 2>&1; then
    patch --batch --fuzz=0 -p1 -d "$src" < "$patch_file"
  fi
done
out="$LAB/work/kernel"
mkdir -p "$out"
ARCH=arm64 "$src/scripts/kconfig/merge_config.sh" -m -O "$out" "$LAB/config/board-reference.config" "$LAB/config/android.config" "$LAB/config/android-crypto.config" "$LAB/config/native.config"
make -C "$src" O="$out" ARCH=arm64 olddefconfig
python3 "$LAB/tools/check-kernel-config.py" "$out/.config" panthor 16
python3 "$LAB/tools/check-native-config.py" "$out/.config"
make -C "$src" O="$out" ARCH=arm64 -j"${JOBS:-2}" Image modules rockchip/rk3588-orangepi-5-plus.dtb
make -C "$src" O="$out" ARCH=arm64 INSTALL_MOD_PATH="$LAB/output/modules" INSTALL_MOD_STRIP=1 modules_install
find "$LAB/output/modules" -type l \( -name build -o -name source \) -delete
cp "$out/arch/arm64/boot/Image" "$out/arch/arm64/boot/dts/rockchip/rk3588-orangepi-5-plus.dtb" "$LAB/output/"
cp "$out/.config" "$LAB/output/kernel.config"
cp "$LAB/sources.json" "$LAB/output/"
cp "$src/.vyos-kernel-prepared" "$LAB/output/source-provenance.txt"
make -s -C "$src" O="$out" ARCH=arm64 kernelrelease > "$LAB/output/kernel.release"
tar -C "$LAB/output" -cJf "$LAB/output/modules.tar.xz" modules
(cd "$LAB/output" && sha256sum Image *.dtb modules.tar.xz kernel.config sources.json > SHA256SUMS)
printf 'KERNEL_BUNDLE_ONLY; native Android userspace not yet validated\n' > "$LAB/output/STATUS.txt"
