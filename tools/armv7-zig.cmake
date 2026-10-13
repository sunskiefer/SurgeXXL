# CMake toolchain: SurgeXXL for the Force (armv7-a hard-float, glibc 2.31) with zig (pip install ziglang)
get_filename_component(SXXL_ZIG "${CMAKE_CURRENT_LIST_DIR}/zig" ABSOLUTE)
set(CMAKE_SYSTEM_NAME Linux)
set(CMAKE_SYSTEM_PROCESSOR armv7l)
set(CMAKE_C_COMPILER ${SXXL_ZIG}/zcc)
set(CMAKE_CXX_COMPILER ${SXXL_ZIG}/zcxx)
set(CMAKE_ASM_COMPILER ${SXXL_ZIG}/zcc)
set(CMAKE_AR ${SXXL_ZIG}/zar)
set(CMAKE_RANLIB ${SXXL_ZIG}/zranlib)
set(LUAJIT_HOSTCC ${SXXL_ZIG}/hostcc32 CACHE FILEPATH "" FORCE)
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
# 64-bit file offsets and inode numbers: without them a 32-bit build's stat()/readdir() fail with EOVERFLOW
# ("Value too large for defined data type") on filesystems with large inode numbers, and Surge then finds no
# patches or wavetables (seen offline under qemu-arm on an ext4 build machine, 2026-10-13).
set(CMAKE_C_FLAGS_INIT "-D_FILE_OFFSET_BITS=64 -D_LARGEFILE_SOURCE -funwind-tables")
set(CMAKE_CXX_FLAGS_INIT "-D_FILE_OFFSET_BITS=64 -D_LARGEFILE_SOURCE -funwind-tables")
