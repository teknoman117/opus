/* SPDX-License-Identifier: BSD-3-Clause */
/* SILK's top-word multiply for the 386, with OpenWatcom: one IMUL, whose
   high half in EDX is the result, instead of a 64-bit multiply call. */

#ifndef SILK_SIGPROC_FIX_386_H
#define SILK_SIGPROC_FIX_386_H

#ifdef __WATCOMC__

opus_int32 silk_mul_shr32_386(opus_int32 a, opus_int32 b);
#pragma aux silk_mul_shr32_386 = \
    "imul edx"                   \
    parm [eax] [edx] value [edx] modify exact [eax edx] nomemory;

/* (a32 * b32) >> 32 */
#undef silk_SMMUL
#define silk_SMMUL(a32, b32) silk_mul_shr32_386((a32), (b32))

#endif /* __WATCOMC__ */

#endif /* SILK_SIGPROC_FIX_386_H */
