# SPDX-License-Identifier: BSD-3-Clause
# libopus, as a static library built from this clone (x86-work/..), whatever branch is checked out:
# its sources come from libopus's own source lists (celt_sources.mk, silk_sources.mk,
# opus_sources.mk), its configuration from x86-work/src/include/config/config.h (HAVE_CONFIG_H).
#
# A fixed-point build: CELT, SILK with its fixed-point sources and the Opus layer. The library has
# the encoder in it too, but a program that only decodes links in only the decoder.
get_filename_component(OPUS_DIR "${PROJECT_SOURCE_DIR}/.." ABSOLUTE)
if(NOT EXISTS "${OPUS_DIR}/opus_sources.mk")
    message(FATAL_ERROR "${OPUS_DIR} isn't a libopus tree")
endif()

# The value of `NAME = a.c b.c \ ...` in a .mk file, as a list of absolute paths.
function(opus_mk_sources out mkfile name)
    file(READ "${OPUS_DIR}/${mkfile}" text)
    string(REGEX REPLACE "\\\\\n" " " text "${text}")
    string(REGEX MATCH "(^|\n)${name} *=([^\n]*)" line "${text}")
    if(NOT line)
        message(FATAL_ERROR "${mkfile}: no ${name}")
    endif()
    string(REGEX REPLACE "(^|\n)${name} *=" "" line "${line}")
    string(REGEX REPLACE "[ \t]+" ";" files "${line}")
    set(paths "")
    foreach(f IN LISTS files)
        if(f)
            list(APPEND paths "${OPUS_DIR}/${f}")
        endif()
    endforeach()
    set(${out} "${paths}" PARENT_SCOPE)
endfunction()

opus_mk_sources(celt_src celt_sources.mk CELT_SOURCES)
opus_mk_sources(silk_src silk_sources.mk SILK_SOURCES)
opus_mk_sources(opus_src opus_sources.mk OPUS_SOURCES)
if(X86_FLOAT)
    # The float build: SILK's float sources (its encoder's; the decoder is fixed point either
    # way) and the Opus layer's float ones.
    opus_mk_sources(silk_x_src silk_sources.mk SILK_SOURCES_FLOAT)
    opus_mk_sources(opus_x_src opus_sources.mk OPUS_SOURCES_FLOAT)
    set(silk_x_dir "${OPUS_DIR}/silk/float")
else()
    opus_mk_sources(silk_x_src silk_sources.mk SILK_SOURCES_FIXED)
    set(opus_x_src "")
    set(silk_x_dir "${OPUS_DIR}/silk/fixed")
endif()

add_library(opus STATIC ${celt_src} ${silk_src} ${silk_x_src} ${opus_src} ${opus_x_src})
target_compile_definitions(opus PRIVATE HAVE_CONFIG_H)
if(X86_FLOAT)
    target_compile_definitions(opus PUBLIC OPUS_X86_FLOAT)
    if(X86_X87_ASM)
        # x87 routines in NASM (celt/x86/*_x87.asm), for OpenWatcom's register convention.
        set(CMAKE_ASM_NASM_OBJECT_FORMAT obj)
        enable_language(ASM_NASM)
        set(x87_asm "${OPUS_DIR}/celt/x86/float_x87.asm" "${OPUS_DIR}/celt/x86/kiss_fft_x87.asm" "${OPUS_DIR}/celt/x86/mdct_x87.asm")
        target_sources(opus PRIVATE ${x87_asm})
        target_compile_definitions(opus PRIVATE OPUS_X87_ASM)
    endif()
    if(CMAKE_C_COMPILER_ID STREQUAL "OpenWatcom")
        # float2int() takes lrint() (Watcom has no lrintf()) only in C99 mode; otherwise it's
        # floor(x + 0.5), a library call for every sample out.
        target_compile_definitions(opus PRIVATE HAVE_LRINT)
        target_compile_options(opus PRIVATE $<$<COMPILE_LANGUAGE:C>:-za99>)
    endif()
endif()
target_include_directories(opus
    PRIVATE "${PROJECT_SOURCE_DIR}/src/include/config" "${OPUS_DIR}" "${OPUS_DIR}/celt" "${OPUS_DIR}/silk"
            "${silk_x_dir}"
    PUBLIC "${OPUS_DIR}/include")
if(CMAKE_C_COMPILER_ID STREQUAL "OpenWatcom")
    # libopus is written for compilers with fewer warnings than Watcom's; they aren't ours to fix.
    target_compile_options(opus PRIVATE $<$<COMPILE_LANGUAGE:C>:-w0>)
endif()
