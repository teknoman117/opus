/* SPDX-License-Identifier: BSD-3-Clause */
/* libopus's build configuration for the x86 work (HAVE_CONFIG_H): a fixed-point decoder for
   OpenWatcom's 32-bit DOS target, and for the host (gcc) build that the DOS builds are checked
   against. The branch's CPU-specific code is switched on here. */
#ifndef OPUS_X86_CONFIG_H
#define OPUS_X86_CONFIG_H

#define OPUS_BUILD 1
/* A fixed-point build, unless X86_FLOAT (CMake) asks for libopus's float one, for an FPU. */
#ifndef OPUS_X86_FLOAT
#define FIXED_POINT 1
#define DISABLE_FLOAT_API 1
#endif

/* With the float build's x87 routines: opus_decode() decodes packets that continue the previous
   one's mode, SILK-only or (stereo, at 48 kHz) CELT-only, straight to 16 bits, as the
   fixed-point decoder does (saturating, with no soft clip), rather than to float and then
   converting. It changes internal structs, so it's here, where every file sees it. */
#if defined(OPUS_X86_FLOAT) && defined(OPUS_X87_ASM)
#define OPUS_INT16_DIRECT 1
#endif

/* Scratch memory from one global block rather than alloca or variable-length arrays. The
   decoder uses about 8 KB of it at most (OPUSDOS reports it). */
#define NONTHREADSAFE_PSEUDOSTACK 1
#define GLOBAL_STACK_SIZE 32768

#define PACKAGE_VERSION "1.6.1-x86"

#ifdef __WATCOMC__
/* Watcom has <stdint.h>, but libopus only looks for it with C99 or HAVE_STDINT_H. */
#define HAVE_STDINT_H 1
/* dos386's code: the 386 IMUL/SHRD multiplies, the 16-bit FIR in silk_LPC_analysis_filter(),
   and (in only with -DOPUS_386_ENTDEC, as it measured 1% slower on an 8-bit bus) the range
   decoder's multiplier order. -DOPUS_NO_386_ASM leaves all of it out, -DOPUS_NO_386_FIR the
   FIR. On a branch without that code these do nothing. */
#ifndef OPUS_NO_386_ASM
#define OPUS_X86_386_ASM 1
#endif
#if !defined(OPUS_386_ENTDEC) && !defined(OPUS_NO_386_ENTDEC)
#define OPUS_NO_386_ENTDEC 1
#endif
#endif

#endif
