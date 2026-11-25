/* SPDX-License-Identifier: MIT */
/* Fixed-point multiplies for the 386, with OpenWatcom.

   A 386 has no fast 64-bit type, so fixed_generic.h splits these multiplies
   into two to four 16x16 ones. One 32x32 IMUL gives the whole 64-bit product
   in EDX:EAX, and SHRD takes the bits wanted out of it, which on a 386 costs
   less than the split, most of all for the 32x32 forms.

   The 386's IMUL stops early, taking about 9 clocks plus the bit length of
   its multiplier, the operand it names (EDX here), so the 16x32 forms pass
   the 16-bit value in EDX: at most about 25 clocks rather than 41. */

#ifndef FIXED_386_H
#define FIXED_386_H

#ifdef __WATCOMC__

opus_val32 celt_mul_shr15_386(opus_val32 a, opus_val32 b);
#pragma aux celt_mul_shr15_386 = \
    "imul edx"                   \
    "shrd eax, edx, 15"          \
    parm [edx] [eax] value [eax] modify exact [eax edx] nomemory;

opus_val32 celt_mul_shr16_386(opus_val32 a, opus_val32 b);
#pragma aux celt_mul_shr16_386 = \
    "imul edx"                   \
    "shrd eax, edx, 16"          \
    parm [edx] [eax] value [eax] modify exact [eax edx] nomemory;

opus_val32 celt_mul_rshr16_386(opus_val32 a, opus_val32 b);
#pragma aux celt_mul_rshr16_386 = \
    "imul edx"                    \
    "add eax, 32768"              \
    "adc edx, 0"                  \
    "shrd eax, edx, 16"           \
    parm [edx] [eax] value [eax] modify exact [eax edx] nomemory;

opus_val32 celt_mul_shr31_386(opus_val32 a, opus_val32 b);
#pragma aux celt_mul_shr31_386 = \
    "imul edx"                   \
    "shrd eax, edx, 31"          \
    parm [eax] [edx] value [eax] modify exact [eax edx] nomemory;

opus_val32 celt_mul_rshr31_386(opus_val32 a, opus_val32 b);
#pragma aux celt_mul_rshr31_386 = \
    "imul edx"                    \
    "add eax, 40000000h"          \
    "adc edx, 0"                  \
    "shrd eax, edx, 31"           \
    parm [eax] [edx] value [eax] modify exact [eax edx] nomemory;

opus_val32 celt_mul_shr32_386(opus_val32 a, opus_val32 b);
#pragma aux celt_mul_shr32_386 = \
    "imul edx"                   \
    parm [eax] [edx] value [edx] modify exact [eax edx] nomemory;

#undef MULT16_32_Q16
#define MULT16_32_Q16(a,b) celt_mul_shr16_386((opus_val16)(a), (b))
#undef MULT16_32_P16
#define MULT16_32_P16(a,b) celt_mul_rshr16_386((opus_val16)(a), (b))
#undef MULT16_32_Q15
#define MULT16_32_Q15(a,b) celt_mul_shr15_386((opus_val16)(a), (b))
#undef MAC16_32_Q15
#define MAC16_32_Q15(c,a,b) ADD32((c), MULT16_32_Q15((a), (b)))
#undef MAC16_32_Q16
#define MAC16_32_Q16(c,a,b) ADD32((c), MULT16_32_Q16((a), (b)))
#undef MULT32_32_Q16
#define MULT32_32_Q16(a,b) celt_mul_shr16_386((a), (b))
#undef MULT32_32_Q31
#define MULT32_32_Q31(a,b) celt_mul_shr31_386((a), (b))
#undef MULT32_32_P31
#define MULT32_32_P31(a,b) celt_mul_rshr31_386((a), (b))
#undef MULT32_32_Q32
#define MULT32_32_Q32(a,b) celt_mul_shr32_386((a), (b))

#endif /* __WATCOMC__ */

#endif /* FIXED_386_H */
