#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
checkout() {
  local url="$1" commit="$2" dest="$3"
  if [[ ! -d "$dest/.git" ]]; then
    git init "$dest"
    git -C "$dest" remote add origin "$url"
    git -C "$dest" fetch --depth=1 origin "$commit"
    git -C "$dest" checkout --detach FETCH_HEAD
  fi
  test "$(git -C "$dest" rev-parse HEAD)" = "$commit"
}
checkout https://github.com/KhronosGroup/SPIRV-Tools.git \
  4d2f0b40bfe290dea6c6904dafdf7fd8328ba346 work/mesa/spirv-tools
checkout https://github.com/KhronosGroup/SPIRV-Headers.git \
  3f17b2af6784bfa2c5aa5dbb8e0e74a607dd8b3b work/mesa/spirv-tools/external/spirv-headers
cmake -S work/mesa/spirv-tools -B work/mesa/spirv-build -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_POSITION_INDEPENDENT_CODE=ON \
  -DCMAKE_INSTALL_PREFIX="$ROOT/work/mesa/host-prefix" -DCMAKE_INSTALL_LIBDIR=lib \
  -DSPIRV_SKIP_TESTS=ON -DSPIRV_SKIP_EXECUTABLES=ON
cmake --build work/mesa/spirv-build --parallel 2
cmake --install work/mesa/spirv-build
