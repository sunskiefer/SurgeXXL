# SurgeXXL: the plugin library (and, on a desktop host, its offline tests).
# build.sh drives this: it generates build/gen (params.h, vst2_wrap.c) first, then configures with the armv7 toolchain
# (tools/armv7-zig.cmake) for the Force, or natively for the x86 tests (test/run_tests.sh).
cmake_minimum_required(VERSION 3.21)
project(SurgeXXL VERSION 0.1.0 LANGUAGES C CXX ASM)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

set(SXXL_GEN "${CMAKE_SOURCE_DIR}/build/gen" CACHE PATH "params.h and vst2_wrap.c from build.sh")
set(MPC_VST "${CMAKE_SOURCE_DIR}/third_party/mpc-vst-plugins" CACHE PATH "mpc-vst-plugins checkout")
option(SXXL_TESTS "Build the offline tests (desktop host only)" OFF)

# Surge XT's engine, headless (as Surge's VCV Rack modules build it); see src/VENDORED.md
set(SURGE_SKIP_JUCE_FOR_RACK ON CACHE BOOL "" FORCE)
set(SURGE_SKIP_ODDSOUND_MTS ON CACHE BOOL "" FORCE)
set(SURGE_BUILD_32BIT_LINUX ON CACHE BOOL "" FORCE)
set(SURGE_BUILD_TESTRUNNER OFF CACHE BOOL "" FORCE)
set(SURGE_SKIP_WERROR ON CACHE BOOL "" FORCE)
set(SURGE_BUILD_XT OFF CACHE BOOL "" FORCE)
set(SURGE_BUILD_FX OFF CACHE BOOL "" FORCE)
set(LUAJIT_DISABLE_JIT ON CACHE BOOL "" FORCE)   # Lua (formula modulators) interpreted: no JIT code pages on MPC OS
add_subdirectory(third_party/surge EXCLUDE_FROM_ALL)

add_library(surgexxl SHARED src/engine.cpp ${SXXL_GEN}/vst2_wrap.c)
target_include_directories(surgexxl PRIVATE src ${SXXL_GEN} ${MPC_VST}/wrapper)
target_link_libraries(surgexxl PRIVATE surge-common pthread dl m)
set_target_properties(surgexxl PROPERTIES PREFIX "" OUTPUT_NAME surgexxl
                      C_VISIBILITY_PRESET hidden CXX_VISIBILITY_PRESET hidden VISIBILITY_INLINES_HIDDEN ON)
set_source_files_properties(${SXXL_GEN}/vst2_wrap.c PROPERTIES COMPILE_OPTIONS "-std=gnu11")
if(CMAKE_CROSSCOMPILING)
  file(WRITE ${CMAKE_BINARY_DIR}/exports.map "{\n  global: VSTPluginMain;\n  local: *;\n};\n")
  target_link_options(surgexxl PRIVATE -Wl,--no-undefined -Wl,--version-script=${CMAKE_BINARY_DIR}/exports.map
                      -Wl,--gc-sections)
  # debug sections dropped, the symbol table kept: the crash log (src/diag.h) names functions by offset
  add_custom_command(TARGET surgexxl POST_BUILD COMMAND ${CMAKE_SOURCE_DIR}/tools/zig/zstrip $<TARGET_FILE:surgexxl>)
  target_compile_options(surgexxl PRIVATE -ffunction-sections -fdata-sections)
endif()

if(SXXL_TESTS)
  # the engine on its own (no VST wrapper), for the offline tests
  add_library(surgexxl_engine STATIC src/engine.cpp)
  target_include_directories(surgexxl_engine PUBLIC src ${SXXL_GEN} ${MPC_VST}/wrapper)
  target_link_libraries(surgexxl_engine PUBLIC surge-common pthread dl m)
  add_executable(engine_test test/engine_test.cpp)
  target_link_libraries(engine_test PRIVATE surgexxl_engine)
  # the framework's VST-level host test (tools/host_test.c) on the whole plugin: wrapper + engine
  add_executable(host_test ${MPC_VST}/tools/host_test.c ${SXXL_GEN}/vst2_wrap.c)
  set_source_files_properties(${MPC_VST}/tools/host_test.c PROPERTIES COMPILE_OPTIONS "-std=gnu11")
  target_include_directories(host_test PRIVATE ${SXXL_GEN} ${MPC_VST}/wrapper)
  target_link_libraries(host_test PRIVATE surgexxl_engine)
  add_executable(dump_facts test/dump_facts.cpp)
  target_link_libraries(dump_facts PRIVATE surge-common)
endif()
