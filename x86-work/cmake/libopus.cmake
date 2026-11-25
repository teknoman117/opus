# SPDX-License-Identifier: MIT
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
opus_mk_sources(silk_fixed_src silk_sources.mk SILK_SOURCES_FIXED)
opus_mk_sources(opus_src opus_sources.mk OPUS_SOURCES)

add_library(opus STATIC ${celt_src} ${silk_src} ${silk_fixed_src} ${opus_src})
target_compile_definitions(opus PRIVATE HAVE_CONFIG_H)
target_include_directories(opus
    PRIVATE "${PROJECT_SOURCE_DIR}/src/include/config" "${OPUS_DIR}" "${OPUS_DIR}/celt" "${OPUS_DIR}/silk"
            "${OPUS_DIR}/silk/fixed"
    PUBLIC "${OPUS_DIR}/include")
if(CMAKE_C_COMPILER_ID STREQUAL "OpenWatcom")
    # libopus is written for compilers with fewer warnings than Watcom's; they aren't ours to fix.
    target_compile_options(opus PRIVATE -w0)
endif()
