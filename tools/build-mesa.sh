#!/usr/bin/env bash
# Build native Mali userspace; no VirGL, Venus, Metal or software CPU emulation.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
mkdir -p work/mesa output/mesa
NDK="${ANDROID_NDK_HOME:-${ANDROID_NDK_ROOT:-}}"
test -n "$NDK"
BIN="$NDK/toolchains/llvm/prebuilt/linux-x86_64/bin"
test -x "$BIN/aarch64-linux-android35-clang"
archive=work/mesa/mesa-26.2.4.tar.xz
if [[ ! -f "$archive" ]]; then
  curl -fL --retry 3 -o "$archive.part" https://archive.mesa3d.org/mesa-26.2.4.tar.xz
  mv "$archive.part" "$archive"
fi
printf '%s  %s\n' bce5f7fbebb934373b86c999a064d52fb5065878dc57f287f95346648ec832e9 "$archive" | sha256sum -c -
if [[ ! -d work/mesa/mesa-26.2.4 ]]; then tar -xf "$archive" -C work/mesa; fi
# Shader generators run on the x86_64 builder, never on the Android target.
# Ubuntu 24.04's SPIRV-Tools predates Mesa's minimum; build a pinned host copy.
bash tools/build-spirv-host.sh
export PKG_CONFIG_PATH="$ROOT/work/mesa/host-prefix/lib/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}"
export PATH="/usr/lib/llvm-18/bin:$PATH"
if [[ ! -f work/mesa/host/build.ninja ]]; then
  meson setup work/mesa/host work/mesa/mesa-26.2.4 --buildtype=release \
    --force-fallback-for=libdrm,expat \
    -Dplatforms= -Dgallium-drivers=panfrost -Dvulkan-drivers= \
    -Dllvm=enabled -Dmesa-clc=enabled -Dprecomp-compiler=enabled \
    -Dglx=disabled -Degl=disabled -Dgbm=enabled -Dgallium-va=disabled \
    -Dgles1=disabled -Dgles2=disabled -Dopengl=false -Dvideo-codecs=
fi
ninja -j2 -C work/mesa/host src/compiler/clc/mesa_clc \
  src/compiler/spirv/vtn_bindgen2 src/panfrost/clc/panfrost_compile
export PATH="$ROOT/work/mesa/host/src/compiler/clc:$ROOT/work/mesa/host/src/compiler/spirv:$ROOT/work/mesa/host/src/panfrost/clc:$PATH"
cat > work/mesa/android.cross <<EOF
[binaries]
c = '$BIN/aarch64-linux-android35-clang'
cpp = ['$BIN/aarch64-linux-android35-clang++', '-static-libstdc++']
ar = '$BIN/llvm-ar'
strip = '$BIN/llvm-strip'
pkg-config = 'pkg-config'
[host_machine]
system = 'android'
cpu_family = 'aarch64'
cpu = 'armv8'
endian = 'little'
[properties]
needs_exe_wrapper = true
pkg_config_libdir = '$ROOT/work/mesa/pkgconfig'
EOF
mkdir -p work/mesa/pkgconfig
if [[ ! -f work/mesa/build/build.ninja ]]; then
  meson setup work/mesa/build work/mesa/mesa-26.2.4 --cross-file work/mesa/android.cross \
    --buildtype=release --force-fallback-for=libdrm,expat \
    -Dplatforms=android -Dplatform-sdk-version=35 -Dandroid-stub=true \
    -Dgallium-drivers=panfrost -Dvulkan-drivers=panfrost \
    -Dmesa-clc=system -Dprecomp-compiler=system \
    -Dllvm=disabled -Dglx=disabled -Dgbm=enabled -Dgallium-va=disabled \
    -Dvideo-codecs= -Dzstd=disabled -Dandroid-libbacktrace=disabled \
    -Degl=enabled -Dgles1=enabled -Dgles2=enabled -Dopengl=true \
    -Degl-lib-suffix=_mesa -Dgles-lib-suffix=_mesa
fi
ninja -j2 -C work/mesa/build
DESTDIR="$ROOT/output/mesa/root" meson install -C work/mesa/build --no-rebuild
find output/mesa/root -type f -name '*.so*' -print > output/mesa/library-list.txt
while IFS= read -r lib; do
  "$BIN/llvm-readelf" -h "$lib" | grep -q 'AArch64'
  "$BIN/llvm-readelf" -d "$lib"
done < output/mesa/library-list.txt > output/mesa/dynamic-dependencies.txt
cp "$NDK/source.properties" output/mesa/ndk-source.properties
cp sources.json output/mesa/
printf 'NATIVE_GRAPHICS_LIBRARIES_ONLY; allocator/composer integration and device runtime untested\n' > output/mesa/STATUS.txt
(cd output/mesa && find root -type f -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS)
