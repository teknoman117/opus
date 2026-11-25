#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Map saved EIP samples (from prof386.py) to functions in a Watcom map.

Usage: prof_map.py <samples.json> <map> [--base <hex>] [--top <n>]
Without --base, the code base is 100000h, where DOS/32A loads OPUSDOS's code
(checked against the hot loop in ec_dec_icdf). The base prof386.py works out
from the address OPUSDOS prints for opus_decode is off by 0BB0h, for reasons
not looked into, so it isn't used.
"""
import bisect
import collections
import json
import os
import re
import sys

args = sys.argv[1:]
data = json.load(open(args[0]))
mapfile = args[1]
base = 0x100000
top = 30
i = 2
while i < len(args):
    if args[i] == "--base":
        base = int(args[i + 1], 16)
    elif args[i] == "--top":
        top = int(args[i + 1])
    i += 2

syms = []
module = "?"
for line in open(mapfile, errors="replace"):
    m = re.match(r"Module: (.*)", line)
    if m:
        module = os.path.basename(m.group(1).strip())
        continue
    m = re.match(r"0001:([0-9a-f]{8})[ *+s]\s*(\S+)", line)
    if m:
        syms.append((int(m.group(1), 16), m.group(2), module))
syms.sort()
offsets = [s[0] for s in syms]

by_fn = collections.Counter()
by_mod = collections.Counter()
for a, c in data["samples"].items():
    off = int(a, 16) - base
    k = bisect.bisect_right(offsets, off) - 1
    if (k < 0) or (off > offsets[-1] + 0x4000):
        by_fn["(outside the program)"] += c
        by_mod["(outside the program)"] += c
    else:
        by_fn[syms[k][1]] += c
        by_mod[syms[k][2]] += c

total = sum(by_fn.values())
print(f"{data['cmd']}: {total} samples, code base {base:#x}")
print("functions:")
for name, c in by_fn.most_common(top):
    print(f"  {100.0 * c / total:5.1f}%  {name}")
print("modules:")
for name, c in by_mod.most_common(15):
    print(f"  {100.0 * c / total:5.1f}%  {name}")
