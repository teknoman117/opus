#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Estimate 486 run times from insncount.py's instruction counts, and set them against 86Box's.

Usage: insnmodel.py <insncount.json>... [--top N]

Each opcode gets a typical 486 cost in clocks, from Intel's tables with the operands in the
cache: the opcode byte alone can't tell register from memory operands, nor (for F6h/F7h) MUL
from NOT, so it's a first-order model. From that: the clocks a second of audio takes, what share
of a 486DX-33, DX2-66 and DX4-100 that is, and the clocks per instruction it implies, beside the
real-time share 86Box measured on the CPU each count came from.
"""
import json
import sys

MHZ = {"dx33": 33.33, "dx2-66": 66.67, "dx4-100": 100.0}


def cost(op):
    """Typical 486 clocks for an opcode key: "8b", or "0f af"."""
    if op.startswith("0f "):
        b = int(op[3:], 16)
        if 0x80 <= b <= 0x8f:
            return 2.0   # Jcc near: 3 taken, 1 not
        if 0x90 <= b <= 0x9f:
            return 3.5   # SETcc
        if b == 0xaf:
            return 18.0  # IMUL r32, r/m32: 13-42 by the multiplier
        if b in (0xb6, 0xb7, 0xbe, 0xbf):
            return 3.0   # MOVZX/MOVSX
        if b in (0xa4, 0xa5, 0xac, 0xad):
            return 3.0   # SHLD/SHRD
        if b in (0xa3, 0xab, 0xb3, 0xbb, 0xba, 0xbc, 0xbd):
            return 4.0   # bit tests and scans (BSF/BSR more)
        return 3.0
    b = int(op, 16)
    if b < 0x40 and (b & 7) < 6:
        return 1.5       # ALU r/m: 1 with registers, 2-3 with memory
    if 0x40 <= b <= 0x4f:
        return 1.0       # INC/DEC r32
    if 0x50 <= b <= 0x5f:
        return 1.0       # PUSH/POP r32
    if b in (0x60, 0x61):
        return 10.0      # PUSHA/POPA
    if b in (0x68, 0x6a):
        return 1.0
    if b in (0x69, 0x6b):
        return 16.0      # IMUL r, r/m, imm
    if 0x70 <= b <= 0x7f:
        return 2.0       # Jcc short
    if 0x80 <= b <= 0x83:
        return 2.0       # ALU r/m, imm
    if b in (0x84, 0x85, 0xa8, 0xa9):
        return 1.0       # TEST
    if b in (0x86, 0x87):
        return 3.0       # XCHG
    if 0x88 <= b <= 0x8c or b == 0x8e:
        return 1.0       # MOV
    if b == 0x8d:
        return 1.0       # LEA
    if b == 0x8f:
        return 6.0
    if b == 0x90:
        return 1.0
    if b in (0x98, 0x99):
        return 3.0       # CBW/CWD
    if b in (0x9c, 0x9d):
        return 6.0
    if 0xa0 <= b <= 0xa3:
        return 1.0
    if b in (0xa4, 0xa5):
        return 7.0       # MOVS (REP is counted apart)
    if b in (0xaa, 0xab):
        return 5.0
    if b in (0xac, 0xad):
        return 5.0
    if 0xb0 <= b <= 0xbf:
        return 1.0       # MOV r, imm
    if b in (0xc0, 0xc1, 0xd0, 0xd1, 0xd2, 0xd3):
        return 3.0       # shifts and rotates
    if b in (0xc2, 0xc3):
        return 5.0       # RET
    if b in (0xc6, 0xc7):
        return 1.0
    if b == 0xc9:
        return 5.0       # LEAVE
    if b == 0xe8:
        return 3.0       # CALL
    if b in (0xe9, 0xeb):
        return 3.0       # JMP
    if b in (0xf6, 0xf7):
        return 20.0      # MUL/IMUL/DIV mostly, in this code (NEG/NOT/TEST are 1-3)
    if b == 0xff:
        return 3.0       # INC/DEC/CALL/JMP/PUSH r/m
    if b in (0x26, 0x2e, 0x36, 0x3e, 0x64, 0x65, 0x66, 0x67, 0xf0, 0xf2, 0xf3):
        return 1.0       # prefixes
    if 0xd8 <= b <= 0xdf:
        return 10.0      # x87 (there shouldn't be any: a fixed-point build)
    return 3.0


args = sys.argv[1:]
top = 12
if "--top" in args:
    i = args.index("--top")
    top = int(args[i + 1])
    del args[i:i + 2]
rows = []
for path in args:
    rows += json.load(open(path))

print(f"{'file':13s} {'measured on':10s} {'Minstr/s':>9s} {'model clk/s':>11s} {'CPI':>5s}"
      f" {'model DX-33':>11s} {'DX2-66':>7s} {'DX4-100':>8s} {'86Box':>8s} {'86Box CPI':>9s}")
for r in rows:
    secs = r.get("audio_s") or r["seconds"]
    ips = r["instructions"] / secs
    clocks = sum(n * cost(op) for op, n in r["counts"].items()) / secs
    cpi = clocks / ips
    model = [100.0 * clocks / (MHZ[c] * 1e6) for c in ("dx33", "dx2-66", "dx4-100")]
    measured = r.get("pct")
    real_cpi = (measured / 100.0 * MHZ[r["cpu"]] * 1e6 / ips) if measured else float("nan")
    print(f"{r['file']:13s} {r['cpu']:10s} {ips / 1e6:9.2f} {clocks / 1e6:10.1f}M {cpi:5.2f}"
          f" {model[0]:10.0f}% {model[1]:6.0f}% {model[2]:7.0f}% {measured or float('nan'):7.1f}% {real_cpi:9.2f}")

if rows:
    r = rows[0]
    tot = r["instructions"]
    print(f"\nthe commonest opcodes in {r['file']} (share of instructions, share of modelled clocks):")
    clk = {op: n * cost(op) for op, n in r["counts"].items()}
    allclk = sum(clk.values())
    for op, n in sorted(r["counts"].items(), key=lambda kv: -kv[1])[:top]:
        print(f"  {op:6s} {100.0 * n / tot:5.1f}%  {100.0 * clk[op] / allclk:5.1f}%")
