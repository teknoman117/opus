# SPDX-License-Identifier: BSD-3-Clause
# CMake toolchain for OPUS4DOS: OpenWatcom 2, 32-bit protected-mode DOS (flat model), linked with
# the DOS/32A extender bound in as the stub. OpenWatcom is $WATCOM, else ~/bin/watcom.
#
#   cmake -S . -B build/dos -G Ninja --toolchain cmake/openwatcom-dos32a.cmake
#   cmake --build build/dos
set(CMAKE_SYSTEM_NAME DOS)
set(CMAKE_SYSTEM_PROCESSOR x86) # 32-bit: wcl386 drives wcc386, wlink links for DOS

if(DEFINED ENV{WATCOM} AND NOT "$ENV{WATCOM}" STREQUAL "")
    set(WATCOM "$ENV{WATCOM}" CACHE PATH "OpenWatcom 2")
else()
    set(WATCOM "$ENV{HOME}/bin/watcom" CACHE PATH "OpenWatcom 2")
endif()
set(CMAKE_C_COMPILER "${WATCOM}/binl64/wcl386")

# OpenWatcom's tools find each other and their headers through the environment, at configure time
# here and at build time through the launchers (the build doesn't inherit this file's environment).
# binw holds dos32a.exe, the stub that `system dos32a` binds in.
set(_watcom_env WATCOM=${WATCOM} INCLUDE=${WATCOM}/h PATH=${WATCOM}/binl64:${WATCOM}/binl:${WATCOM}/binw:/usr/bin:/bin)
set(ENV{WATCOM} "${WATCOM}")
set(ENV{INCLUDE} "${WATCOM}/h")
set(ENV{PATH} "${WATCOM}/binl64:${WATCOM}/binl:${WATCOM}/binw:$ENV{PATH}")
set(CMAKE_C_COMPILER_LAUNCHER env ${_watcom_env})
set(CMAKE_C_LINKER_LAUNCHER env ${_watcom_env})
set(WATCOM_ENV env ${_watcom_env})
