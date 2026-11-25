#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Make the range decoder's multiplies take their small operand as the 386's
optimizing multiplier under OPUS_X86_386_ASM (idempotent).

Every IMUL32() in celt/entdec.c multiplies the range by a symbol's
frequency or icdf entry (at most 16 bits). The 386's early-out multiply
takes as many clocks as the r/m operand has bits, and the compiler is free
to put the 32-bit range there, so this pins the order.

Usage: patch_entdec.py <opus dir>
"""
import sys

p = f"{sys.argv[1]}/celt/entdec.c"
s = open(p).read()
if "ec_imul_386" in s:
    print("celt/entdec.c already patched")
    sys.exit(0)

old = '''#include "mfrngcod.h"
'''
assert s.count(old) == 1
s = s.replace(old, '''#include "mfrngcod.h"

#if defined(OPUS_X86_386_ASM) && !defined(OPUS_NO_386_ENTDEC) && defined(__WATCOMC__)
/* a * b with b as IMUL's r/m operand, the 386's optimizing multiplier. */
opus_uint32 ec_imul_386(opus_uint32 a, opus_uint32 b);
#pragma aux ec_imul_386 = \\
    "imul eax, edx" \\
    parm [eax] [edx] value [eax] modify exact [eax];
#undef IMUL32
#define IMUL32(a, b) ec_imul_386((a), (b))
#endif
''')
open(p, "w").write(s)
print("patched celt/entdec.c")
