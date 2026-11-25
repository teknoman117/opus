#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Use the 386 FIR sums (silk/x86/LPC_analysis_filter_386.h) in
silk_LPC_analysis_filter() for orders 10 and 16 under OPUS_X86_386_ASM
(idempotent).

Usage: patch_lpc_analysis.py <opus dir>
"""
import sys

p = f"{sys.argv[1]}/silk/LPC_analysis_filter.c"
s = open(p).read()
if "LPC_analysis_filter_386.h" in s:
    print("silk/LPC_analysis_filter.c already patched")
    sys.exit(0)


def rep(old, new):
    global s
    assert s.count(old) == 1, old[:70]
    s = s.replace(old, new)


rep('''#include "SigProc_FIX.h"
''', '''#include "SigProc_FIX.h"
#if defined(OPUS_X86_386_ASM) && !defined(OPUS_NO_386_FIR)
#include "x86/LPC_analysis_filter_386.h"
#endif
''')

rep('''        in_ptr = &in[ ix - 1 ];

        out32_Q12 = silk_SMULBB( in_ptr[  0 ], B[ 0 ] );
''', '''        in_ptr = &in[ ix - 1 ];

#if defined(OPUS_X86_386_ASM) && !defined(OPUS_NO_386_FIR)
        if( d == 16 ) {
            out32_Q12 = silk_fir16_386( in_ptr, B );
        } else if( d == 10 ) {
            out32_Q12 = silk_fir10_386( in_ptr, B );
        } else
#endif
        {
        out32_Q12 = silk_SMULBB( in_ptr[  0 ], B[ 0 ] );
''')

rep('''            out32_Q12 = silk_SMLABB_ovflw( out32_Q12, in_ptr[ -j - 1 ], B[ j + 1 ] );
        }
''', '''            out32_Q12 = silk_SMLABB_ovflw( out32_Q12, in_ptr[ -j - 1 ], B[ j + 1 ] );
        }
        }
''')

open(p, "w").write(s)
print("patched silk/LPC_analysis_filter.c")
