#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Hook the 386 headers into libopus behind OPUS_X86_386_ASM (idempotent).

Usage: patch_386.py <opus dir>
"""
import sys

opus = sys.argv[1]


def patch(path, anchor, add):
    p = f"{opus}/{path}"
    s = open(p).read()
    if add.strip() in s:
        return
    assert s.count(anchor) == 1, (path, anchor)
    s = s.replace(anchor, anchor + add)
    open(p, "w").write(s)
    print("patched", path)


patch("celt/arch.h", '''#elif defined (TI_C6X_ASM)
#include "fixed_c6x.h"
''', '''#elif defined (OPUS_X86_386_ASM)
#include "x86/fixed_386.h"
''')

patch("silk/macros.h", '''#ifdef OPUS_XTENSA_LX7
#include "xtensa/macros_lx7.h"
#endif
''', '''
#ifdef OPUS_X86_386_ASM
#include "x86/macros_386.h"
#endif
''')

s = open(f"{opus}/silk/SigProc_FIX.h").read()
anchor = "#endif /* SILK_SIGPROC_FIX_H */"
add = '''#ifdef OPUS_X86_386_ASM
#include "x86/SigProc_FIX_386.h"
#endif

'''
if add.strip() not in s:
    assert s.count(anchor) == 1
    s = s.replace(anchor, add + anchor)
    open(f"{opus}/silk/SigProc_FIX.h", "w").write(s)
    print("patched silk/SigProc_FIX.h")
