# SPDX-License-Identifier: BSD-3-Clause
# OPUSDOS, the decoder test bench for the x86 work: libopus from this clone (the branch checked
# out), and OPUSDOS, which decodes an Ogg Opus file and times it.
#
# DOS (OpenWatcom 2, 32-bit, DOS/32A):
#   cmake -S x86-work -B build/dos -G Ninja --toolchain x86-work/cmake/openwatcom-dos32a.cmake
#   cmake --build build/dos                      -> build/dos/OPUSDOS.EXE
# Host (the reference the DOS builds are checked against):
#   cmake -S x86-work -B build/host -G Ninja && cmake --build build/host   -> build/host/opusdos
#
# For A/B builds: -DX86_DEFINES="OPUS_NO_386_FIR;OPUS_386_ENTDEC" (see src/include/config/config.h), and
# -DX86_SILK_ONLY=ON to leave CELT out (src/celt_stub.c), as a 512 KB board needs, and
# -DX86_FLOAT=ON for libopus's floating-point decoder on an x87.
cmake_minimum_required(VERSION 3.21)
project(opus-x86 C)

set(X86_DEFINES "" CACHE STRING "Macros for src/include/config/config.h's switches, for A/B builds")
option(X86_SILK_ONLY "Leave CELT out: SILK packets only" OFF)
option(X86_FLOAT "libopus's floating-point build, with x87 instructions (a 486DX or later)" OFF)
option(X86_X87_ASM "In the float build, libopus's x87 routines in NASM (celt/x86/*_x87.asm)" ON)
add_compile_definitions(${X86_DEFINES})

if(CMAKE_C_COMPILER_ID STREQUAL "OpenWatcom")
    # The flat model, 386 register calling, floating point by library calls (no FPU needed), no
    # stack checks, optimized for speed, structures packed to 4 bytes; DOS/32A bound in.
    set(CMAKE_C_FLAGS "-bt=dos")
    foreach(type DEBUG RELEASE RELWITHDEBINFO MINSIZEREL)
        set(CMAKE_C_FLAGS_${type} "")
        set(CMAKE_EXE_LINKER_FLAGS_${type} "")
    endforeach()
    set(CMAKE_EXE_LINKER_FLAGS "system dos32a")
    # -fpc: floating point by library calls, so no FPU is needed; a float build has x87
    # instructions inline (-fpi87), 387 ones (-fp3).
    if(X86_FLOAT)
        set(X86_FP -fpi87 -fp3)
    else()
        set(X86_FP -fpc)
    endif()
    add_compile_options("$<$<COMPILE_LANGUAGE:C>:-mf;-3r;${X86_FP};-s;-otexan;-zp4>")
    # Watcom ends an option's file name at a '-', and libopus's objects are named after their
    # full paths (they're outside this directory), which have one (opus-x86): quote them.
    set(CMAKE_C_COMPILE_OBJECT
        "<CMAKE_C_COMPILER> -zq -d+ <DEFINES> <INCLUDES> <FLAGS> \"-fo=\\\"<OBJECT>\\\"\" -c -cc <SOURCE>")
    # CMake tracks no header dependencies for OpenWatcom: wcc386's -ad files, read by Ninja.
    set(CMAKE_DEPFILE_FLAGS_C
        "\"-ad=\\\"<DEP_FILE>\\\"\" \"-adt=\\\"<OBJECT>\\\"\" \"-add=\\\"<SOURCE>\\\"\" -adfs")
    set(CMAKE_C_DEPFILE_FORMAT gcc)
    set(CMAKE_C_DEPENDS_USE_COMPILER TRUE)
elseif(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release)
endif()

include(cmake/libopus.cmake)

add_executable(opusdos src/opusdos.c)
if(X86_SILK_ONLY)
    target_sources(opusdos PRIVATE src/celt_stub.c)
    target_include_directories(opusdos PRIVATE "${OPUS_DIR}/celt")
endif()
target_include_directories(opusdos PRIVATE src/include/config)
target_link_libraries(opusdos PRIVATE opus)
if(CMAKE_C_COMPILER_ID STREQUAL "OpenWatcom")
    set_target_properties(opusdos PROPERTIES OUTPUT_NAME OPUSDOS SUFFIX .EXE LINK_FLAGS "option stack=64k option map option statics")
else()
    target_link_libraries(opusdos PRIVATE m)
endif()

# RSBENCH: OPUS4DOS's resampler (src/resample.c of an OPUS4DOS checkout), on its own.
set(OPUS4DOS_DIR "$ENV{HOME}/Projects/opus4dos" CACHE PATH "An OPUS4DOS checkout, for RSBENCH")
if(EXISTS "${OPUS4DOS_DIR}/src/resample.c")
    add_executable(rsbench src/rsbench.c "${OPUS4DOS_DIR}/src/resample.c")
    target_include_directories(rsbench PRIVATE "${OPUS4DOS_DIR}/src")
    if(CMAKE_C_COMPILER_ID STREQUAL "OpenWatcom")
        set_target_properties(rsbench PROPERTIES OUTPUT_NAME RSBENCH SUFFIX .EXE LINK_FLAGS "option stack=16k")
    endif()
endif()


# FFTTEST: libopus's FFT against a DFT, for checking butterflies (the float build's x87 ones).
if(X86_FLOAT)
    add_executable(ffttest src/ffttest.c)
    target_include_directories(ffttest PRIVATE src/include/config "${OPUS_DIR}/celt" "${OPUS_DIR}/include")
    target_compile_definitions(ffttest PRIVATE HAVE_CONFIG_H)
    target_link_libraries(ffttest PRIVATE opus)
    if(CMAKE_C_COMPILER_ID STREQUAL "OpenWatcom")
        set_target_properties(ffttest PROPERTIES OUTPUT_NAME FFTTEST SUFFIX .EXE LINK_FLAGS "option stack=64k")
    endif()
endif()
