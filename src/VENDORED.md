# Vendored source

## Surge XT (`third_party/surge`)

- Upstream: https://github.com/surge-synthesizer/surge, tag `release_xt_1.3.4`, commit
  `f7b97c682ade0b87da85ca5968b63d5c7c98e68d` (2024-08-11), with the submodules at the commits that tag pins.
- Licence: GPL-3.0-or-later (`third_party/surge/LICENSE`). The libraries keep their own licences in their folders.
- What is here: Surge's top-level CMake files, `cmake/`, `src/CMakeLists.txt`, `src/cmake/`, `src/common/` (the engine),
  `src/lua/`, `src/platform/`, `resources/CMakeLists.txt`, `resources/surge-shared/`, `resources/data/` (every factory and
  third-party patch, wavetable, FX and modulator preset and tuning; not Surge's GUI skins), and the libraries the
  engine needs: `LuaJitLib` (with LuaJIT), `PEGTL`, `eurorack`, `fmt`, `libsamplerate`, `oddsound-mts` (headers; MTS-ESP
  is off), `pffft`, `simde`, `sqlite-3.23.3`, `sst/*`, `tuning-library`, and from JUCE 7.0.12 only `juce_core`,
  `juce_audio_basics`, `juce_audio_formats` and `juce_dsp` (Surge's headless build compiles them for Neuron), with
  JUCE's `LICENSE.md`. Test, doc and example folders of the libraries are left out.
- Added: `VERSION_GIT_INFO` (Surge's version files without git: version, branch, commit).

### Local changes (each marked "SurgeXXL" in the file)

1. `src/CMakeLists.txt`: clap-juce-extensions is not added when `SURGE_SKIP_JUCE_FOR_RACK` is on (the headless build
   has no JUCE plugin targets; upstream adds it anyway, which needs the submodule).
2. Spring Reverb is not built: `src/common/CMakeLists.txt` drops its sources and `src/common/dsp/Effect.cpp` makes
   no effect for that type (Surge's top-level CMake names it as the part that fails on 32-bit Linux). A slot of that
   type is off; the engine sets it to Off when a patch loads. Its folders are not vendored.
3. `src/common/SurgeStorage.cpp` / `.h`: `surgeXXLUserDataPath()`, a folder the plugin sets before it makes a synth;
   on Linux it replaces `~/Documents/Surge XT` as Surge's user folder (Patches, Wavetables, ...).
4. `libs/LuaJitLib/CMakeLists.txt`: with `LUAJIT_DISABLE_JIT` the define also reaches LuaJIT's architecture tests
   (so DynASM gets no `-D JIT`) and the cross-built `buildvm`; upstream's CMake mixes a JIT VM with a no-JIT build.

### Build settings (CMakeLists.txt, tools/armv7-zig.cmake)

Surge's own options: `SURGE_SKIP_JUCE_FOR_RACK` (the headless engine, as Surge's VCV Rack modules),
`SURGE_SKIP_ODDSOUND_MTS`, `SURGE_BUILD_32BIT_LINUX` (Surge's own escape hatch for 32-bit Linux; with the Spring Reverb
gone and NEON on, the rest, Airwindows included, builds and passes the offline tests), `SURGE_SKIP_WERROR`; and `LUAJIT_DISABLE_JIT` (formula
modulators run in LuaJIT's interpreter: no JIT code pages inside MPC). The device build targets the Force's Cortex-A17
with NEON and 64-bit file offsets.

To re-vendor a newer Surge: copy the same folders from the new tag, re-apply the four changes (search "SurgeXXL"),
run `test/dump_facts` to refresh `tools/surge_facts.json`, then `test/run_tests.sh`.
