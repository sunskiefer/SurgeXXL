#!/usr/bin/env bash
# Build SurgeXXL for MPC OS Gen1 (the Force: armv7-a hard-float, glibc <= 2.31 so it also loads on MPC OS 2.x).
#   ./build.sh                 the plugin folder in build/package/
#   ./build.sh --skin-only     just the skin (build/skin/), to look at with test/preview.sh
# Needs: python3 + Pillow + cairosvg, cmake + ninja, a host gcc (for shadow_art), and Zig (pip install ziglang).
# No Docker. Output: build/package/ANDREALPHEUS - VST - SurgeXXL/ (skin, surgexxl.so and Surge's data folder).
# Set SXXL_WT_PICTURES=0 to build without the 761 wavetable pictures (a lighter skin, if MPC finds it too heavy).
set -euo pipefail
cd "$(dirname "$0")"
MPC_VST="${MPC_VST:-$PWD/third_party/mpc-vst-plugins}"
NAME="ANDREALPHEUS - VST - SurgeXXL"
JOBS="${JOBS:-$(nproc 2>/dev/null || echo 2)}"

python3 tools/gen_params.py
python3 tools/panel.py --check   # layout.conf matches tools/panel.py and qlinks.json

# ---- the skin
mkdir -p build/host build/gen
[ -x build/host/shadow_art ] || gcc -O2 -w -I"$MPC_VST/tools/vendor/force-shadow/tools" -x c -o build/host/shadow_art "$MPC_VST/tools/shadow_art.c" -lm
rm -rf build/skin
SHADOW_TITLE_FONT="$PWD/art/fonts/TitilliumWeb-SemiBold.ttf" SHADOW_ART="$PWD/build/host/shadow_art" \
  python3 "$MPC_VST/tools/gen_vst.py" vst.json 2>&1 | grep -v -e "TOUCH" -e "EDGE" || true   # panel_art places every control
[ -f build/params.h ] && [ -d "build/skin/$NAME/Plugin Skins" ]
python3 tools/panel_art.py "build/skin/$NAME/Plugin Skins"
python3 "$MPC_VST/tools/skin_check.py" "build/skin/$NAME" || true
[ "${1:-}" = --skin-only ] && exit 0

# ---- the library: Surge's engine and the plugin layer, with the framework's wrapper (state chunk enlarged)
cp build/params.h build/gen/params.h
python3 tools/wrap_chunk.py "$MPC_VST" build/gen/vst2_wrap.c
cmake -S . -B build/arm -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_TOOLCHAIN_FILE="$PWD/tools/armv7-zig.cmake" \
  -DMPC_VST="$MPC_VST" > build/arm-configure.log
ninja -C build/arm -j"$JOBS" surgexxl

# ---- the plugin folder
PKG="build/package/$NAME"
rm -rf build/package && mkdir -p "$PKG"
cp -r "build/skin/$NAME/." "$PKG/"
cp build/arm/surgexxl.so "$PKG/"
tools/stage_data.sh "$PKG"
echo "-> $PKG"
