/* SPDX-License-Identifier: MIT */
/* silk_LPC_analysis_filter()'s FIR sums for the 386, with OpenWatcom.
   Written by gen_lpc_analysis_386.py.

   Each tap is a 16-bit IMUL of the input sample by the Q12 coefficient
   into DX:AX, added into a 32-bit sum kept in CX:BX with ADD/ADC: the
   wrapping 32-bit sum of the C. The coefficient is IMUL's operand, the
   386's optimizing multiplier, so its early-out multiply stops at the
   coefficient's few bits; the word operands are one bus cycle each on
   the 386SX's 16-bit bus.

   s points at the newest input sample and the taps go back from it:
   s[0] * c[0] + s[-1] * c[1] + ... */

#ifndef SILK_LPC_ANALYSIS_FILTER_386_H
#define SILK_LPC_ANALYSIS_FILTER_386_H

#ifdef __WATCOMC__


/* 10 taps. */
opus_int32 silk_fir10_386(const opus_int16 *s, const opus_int16 *c);
#pragma aux silk_fir10_386 = \
    "mov ax, [esi]" \
    "imul word ptr [edi]" \
    "mov bx, ax" \
    "mov cx, dx" \
    "mov ax, [esi-2]" \
    "imul word ptr [edi+2]" \
    "add bx, ax" \
    "adc cx, dx" \
    "mov ax, [esi-4]" \
    "imul word ptr [edi+4]" \
    "add bx, ax" \
    "adc cx, dx" \
    "mov ax, [esi-6]" \
    "imul word ptr [edi+6]" \
    "add bx, ax" \
    "adc cx, dx" \
    "mov ax, [esi-8]" \
    "imul word ptr [edi+8]" \
    "add bx, ax" \
    "adc cx, dx" \
    "mov ax, [esi-10]" \
    "imul word ptr [edi+10]" \
    "add bx, ax" \
    "adc cx, dx" \
    "mov ax, [esi-12]" \
    "imul word ptr [edi+12]" \
    "add bx, ax" \
    "adc cx, dx" \
    "mov ax, [esi-14]" \
    "imul word ptr [edi+14]" \
    "add bx, ax" \
    "adc cx, dx" \
    "mov ax, [esi-16]" \
    "imul word ptr [edi+16]" \
    "add bx, ax" \
    "adc cx, dx" \
    "mov ax, [esi-18]" \
    "imul word ptr [edi+18]" \
    "add bx, ax" \
    "adc cx, dx" \
    "shl ecx, 16" \
    "mov cx, bx" \
    parm [esi] [edi] value [ecx] modify exact [eax ebx ecx edx];

/* 16 taps. */
opus_int32 silk_fir16_386(const opus_int16 *s, const opus_int16 *c);
#pragma aux silk_fir16_386 = \
    "mov ax, [esi]" \
    "imul word ptr [edi]" \
    "mov bx, ax" \
    "mov cx, dx" \
    "mov ax, [esi-2]" \
    "imul word ptr [edi+2]" \
    "add bx, ax" \
    "adc cx, dx" \
    "mov ax, [esi-4]" \
    "imul word ptr [edi+4]" \
    "add bx, ax" \
    "adc cx, dx" \
    "mov ax, [esi-6]" \
    "imul word ptr [edi+6]" \
    "add bx, ax" \
    "adc cx, dx" \
    "mov ax, [esi-8]" \
    "imul word ptr [edi+8]" \
    "add bx, ax" \
    "adc cx, dx" \
    "mov ax, [esi-10]" \
    "imul word ptr [edi+10]" \
    "add bx, ax" \
    "adc cx, dx" \
    "mov ax, [esi-12]" \
    "imul word ptr [edi+12]" \
    "add bx, ax" \
    "adc cx, dx" \
    "mov ax, [esi-14]" \
    "imul word ptr [edi+14]" \
    "add bx, ax" \
    "adc cx, dx" \
    "mov ax, [esi-16]" \
    "imul word ptr [edi+16]" \
    "add bx, ax" \
    "adc cx, dx" \
    "mov ax, [esi-18]" \
    "imul word ptr [edi+18]" \
    "add bx, ax" \
    "adc cx, dx" \
    "mov ax, [esi-20]" \
    "imul word ptr [edi+20]" \
    "add bx, ax" \
    "adc cx, dx" \
    "mov ax, [esi-22]" \
    "imul word ptr [edi+22]" \
    "add bx, ax" \
    "adc cx, dx" \
    "mov ax, [esi-24]" \
    "imul word ptr [edi+24]" \
    "add bx, ax" \
    "adc cx, dx" \
    "mov ax, [esi-26]" \
    "imul word ptr [edi+26]" \
    "add bx, ax" \
    "adc cx, dx" \
    "mov ax, [esi-28]" \
    "imul word ptr [edi+28]" \
    "add bx, ax" \
    "adc cx, dx" \
    "mov ax, [esi-30]" \
    "imul word ptr [edi+30]" \
    "add bx, ax" \
    "adc cx, dx" \
    "shl ecx, 16" \
    "mov cx, bx" \
    parm [esi] [edi] value [ecx] modify exact [eax ebx ecx edx];

#endif /* __WATCOMC__ */

#endif /* SILK_LPC_ANALYSIS_FILTER_386_H */
