#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Put the EIP samples of insncount.py --profile to functions, from OPUSDOS's Watcom map.

Usage: insnprof.py <insncount.json> <OPUSDOS.map> [--file NAME] [--top N] [--base HEX]

The code's base is the address OPUSDOS printed for its decode function, less that function's
offset in the map, unless --base gives it.
"""
import bisect
import collections
import json
import os
import re
import sys

args = sys.argv[1:]
only, top, base = None, 30, None
for opt in ("--file", "--top", "--base"):
    if opt in args:
        i = args.index(opt)
        v = args[i + 1]
        del args[i:i + 2]
        if opt == "--file":
            only = v
        elif opt == "--top":
            top = int(v)
        else:
            base = int(v, 16)
rows, mapfile = json.load(open(args[0])), args[1]

syms, module = [], "?"
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
by_name = {s[1]: s[0] for s in syms}

for r in rows:
    if (only and r["file"] != only) or "eip" not in r:
        continue
    b = base
    if b is None:
        sym = r.get("anchor_sym", "opus_decode") + "_"
        b = r["anchor"] - by_name[sym]
    by_fn, by_mod = collections.Counter(), collections.Counter()
    for a, c in r["eip"].items():
        off = int(a, 16) - b
        k = bisect.bisect_right(offsets, off) - 1
        if k < 0 or off > offsets[-1] + 0x10000:
            name, mod = "(outside the program)", "(outside)"
        else:
            name, mod = syms[k][1], syms[k][2]
        by_fn[name] += c
        by_mod[mod] += c
    total = sum(by_fn.values())
    print(f"{r['file']} on {r['cpu']} {r.get('args', '')}: {total} samples {r['every_ms']} ms apart,"
          f" {r.get('pct', float('nan')):.1f}% of real time; code base {b:#x}")
    for name, c in by_fn.most_common(top):
        print(f"  {100.0 * c / total:5.1f}%  {name}")
    print("  by module:", ", ".join(f"{m} {100.0 * c / total:.1f}%" for m, c in by_mod.most_common(10)))
