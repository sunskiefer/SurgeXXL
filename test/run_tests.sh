#!/usr/bin/env bash
# SurgeXXL's offline tests (no device): the engine test and mpc-vst-plugins' host test, on x86 and, under qemu-arm,
# as the Force build itself.
#   test/run_tests.sh [x86|arm|all] [--patches all|N]
# x86 needs cmake, ninja and a host compiler; arm needs build.sh's toolchain (zig) plus qemu-user and an armhf glibc
# (Debian/Ubuntu: apt install qemu-user libc6-armhf-cross). The stage (test/stage.sh) is a card with the plugin's data
# folder; the user folder (SurgeXXL/) is emptied before each run.
set -euo pipefail
cd "$(dirname "$0")/.."
WHICH="${1:-all}"; shift || true
PATCHES=(--patches 10)
[ "${1:-}" = --patches ] && PATCHES=(--patches "$2")
MPC_VST="${MPC_VST:-$PWD/third_party/mpc-vst-plugins}"
python3 tools/gen_params.py >/dev/null
python3 "$MPC_VST/tools/gen_vst.py" vst.json --params-h >/dev/null
mkdir -p build/gen && cp build/params.h build/gen/params.h
python3 tools/wrap_chunk.py "$MPC_VST" build/gen/vst2_wrap.c
STAGE=build/stage
mkdir -p "$STAGE/Synths/plugin"
[ -e "$STAGE/Synths/plugin/data/configuration.xml" ] || tools/stage_data.sh "$STAGE/Synths/plugin" --link

if [ "$WHICH" = x86 ] || [ "$WHICH" = all ]; then
  cmake -S . -B build/x86 -G Ninja -DCMAKE_BUILD_TYPE=Release -DSXXL_TESTS=ON >/dev/null
  ninja -C build/x86 engine_test host_test
  rm -rf "$STAGE/SurgeXXL"
  build/x86/engine_test "$STAGE" "${PATCHES[@]}" --fx
  cp build/x86/host_test "$STAGE/Synths/plugin/host_test"
  (cd "$STAGE/Synths/plugin" && ./host_test)
fi
if [ "$WHICH" = arm ] || [ "$WHICH" = all ]; then
  cmake -S . -B build/arm -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_TOOLCHAIN_FILE="$PWD/tools/armv7-zig.cmake" \
    -DSXXL_TESTS=ON >/dev/null
  ninja -C build/arm engine_test host_test
  rm -rf "$STAGE/SurgeXXL"
  QEMU="qemu-arm -cpu cortex-a15 -L /usr/arm-linux-gnueabihf"
  $QEMU build/arm/engine_test "$STAGE" "${PATCHES[@]}" --fx
  cp build/arm/host_test "$STAGE/Synths/plugin/host_test_arm"
  (cd "$STAGE/Synths/plugin" && $QEMU ./host_test_arm)
fi
