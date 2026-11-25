/* SPDX-License-Identifier: MIT */
/* SILK's 32x16 and 32x32 multiplies for the 386, with OpenWatcom.

   macros.h splits these into two 16x16 multiplies when there is no fast
   64-bit type; one 32x32 IMUL into EDX:EAX and a SHRD do the same, exactly,
   for less on a 386. */

#ifndef SILK_MACROS_386_H
#define SILK_MACROS_386_H

#ifdef __WATCOMC__

opus_int32 silk_mul_shr16_386(opus_int32 a, opus_int32 b);
#pragma aux silk_mul_shr16_386 = \
    "imul edx"                   \
    "shrd eax, edx, 16"          \
    parm [eax] [edx] value [eax] modify exact [eax edx] nomemory;

opus_int32 silk_mul_shr32_386(opus_int32 a, opus_int32 b);
#pragma aux silk_mul_shr32_386 = \
    "imul edx"                   \
    parm [eax] [edx] value [edx] modify exact [eax edx] nomemory;

/* (a32 * (opus_int16)b32) >> 16 */
#undef silk_SMULWB
#define silk_SMULWB(a32, b32) silk_mul_shr16_386((a32), (opus_int32)(opus_int16)(b32))

/* a32 + ((b32 * (opus_int16)c32) >> 16) */
#undef silk_SMLAWB
#define silk_SMLAWB(a32, b32, c32) ((a32) + silk_mul_shr16_386((b32), (opus_int32)(opus_int16)(c32)))

/* (a32 * b32) >> 16 */
#undef silk_SMULWW
#define silk_SMULWW(a32, b32) silk_mul_shr16_386((a32), (b32))

/* a32 + ((b32 * c32) >> 16) */
#undef silk_SMLAWW
#define silk_SMLAWW(a32, b32, c32) ((a32) + silk_mul_shr16_386((b32), (c32)))

/* (a32 * b32) >> 32 */
#undef silk_SMMUL
#define silk_SMMUL(a32, b32) silk_mul_shr32_386((a32), (b32))

#endif /* __WATCOMC__ */

#endif /* SILK_MACROS_386_H */
