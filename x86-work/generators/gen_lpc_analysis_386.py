#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Write silk/x86/LPC_analysis_filter_386.h: silk_LPC_analysis_filter()'s
FIR sums for orders 10 and 16 as OpenWatcom inline 386 code.

Usage: gen_lpc_analysis_386.py <opus dir>
"""
import sys

out = [f"""/* silk_LPC_analysis_filter()'s FIR sums for the 386, with OpenWatcom.
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
"""]

for order in (10, 16):
    out.append(f"\n/* {order} taps. */\nopus_int32 silk_fir{order}_386(const opus_int16 *s, const opus_int16 *c);")
    out.append(f"#pragma aux silk_fir{order}_386 = \\")
    out.append('    "mov ax, [esi]" \\')
    out.append('    "imul word ptr [edi]" \\')
    out.append('    "mov bx, ax" \\')
    out.append('    "mov cx, dx" \\')
    for j in range(1, order):
        out.append(f'    "mov ax, [esi-{2 * j}]" \\')
        out.append(f'    "imul word ptr [edi+{2 * j}]" \\')
        out.append('    "add bx, ax" \\')
        out.append('    "adc cx, dx" \\')
    out.append('    "shl ecx, 16" \\')
    out.append('    "mov cx, bx" \\')
    out.append("    parm [esi] [edi] value [ecx] modify exact [eax ebx ecx edx];")

out.append("""
#endif /* __WATCOMC__ */

#endif /* SILK_LPC_ANALYSIS_FILTER_386_H */
""")
open(f"{sys.argv[1]}/silk/x86/LPC_analysis_filter_386.h", "w").write("\n".join(out))
print("wrote silk/x86/LPC_analysis_filter_386.h")
