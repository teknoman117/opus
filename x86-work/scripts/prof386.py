#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Profile OPUSDOS on the emulated 386SX-25 by sampling its EIP.

Usage: prof386.py <86Box> <OPUSDOS.EXE> <map> "<command>" [--file <path>]... [--every <ms>] [--top <n>]

Boots as run386.py does and runs the one command, with its output on the
screen. Once OPUSDOS prints where opus_decode is, every --every ms (default
1) of emulated time the CPU's EIP is read; the decode ends when OPUSDOS
prints its result. Each sample goes to the function it falls in, from the
Watcom map file, with the code's load address taken from opus_decode's.
"""
import bisect
import collections
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
BOOT = os.path.expanduser("~/Downloads/FD14-FloppyEdition/144m/x86BOOT.img")

args = sys.argv[1:]
emu, exe, mapfile, cmd = args[0], args[1], args[2], args[3]
files, every, top = [], 1, 30
i = 4
while i < len(args):
    if args[i] == "--file":
        files.append(args[i + 1])
    elif args[i] == "--every":
        every = int(args[i + 1])
    elif args[i] == "--top":
        top = int(args[i + 1])
    i += 2

# The map: code symbols (object 1) by offset, with their modules.
syms = []
module = "?"
for line in open(mapfile, errors="replace"):
    m = re.match(r"Module: (.*)", line)
    if m:
        module = os.path.basename(m.group(1).strip())
        continue
    m = re.match(r"0001:([0-9a-f]{8})[ *+]+(\S+)", line)
    if m:
        syms.append((int(m.group(1), 16), m.group(2), module))
syms.sort()
offsets = [s[0] for s in syms]
anchor = next(s[0] for s in syms if s[1] == "opus_decode_")

CONFIG = """[Machine]
machine = cmdsl386sx25
cpu_family = i386sx
cpu_speed = 25000000
cpu_multi = 1
cpu_use_dynarec = 0
mem_size = 4096

[Video]
gfxcard = internal

[Floppy and CD-ROM drives]
fdd_01_type = 35_2hd
fdd_01_fn = {floppy}
fdd_02_type = none
"""

with tempfile.TemporaryDirectory(prefix="prof386_") as tmp:
    root = Path(tmp)
    img = str(root / "test.img")
    shutil.copy(BOOT, img)
    subprocess.run(["mdel", "-i", img, "::SETUP.BAT"], check=True)
    (root / "FDCONFIG.SYS").write_text("FILES=40\r\nBUFFERS=20\r\nLASTDRIVE=Z\r\n"
                                       "SHELL=\\FREEDOS\\BIN\\COMMAND.COM \\FREEDOS\\BIN /E:2048 /P=\\FDAUTO.BAT\r\n")
    (root / "FDAUTO.BAT").write_text("@ECHO OFF\r\nSET PATH=\\FREEDOS\\BIN\r\nA:\r\nCD \\\r\n" + cmd + "\r\nECHO OPUSDONE\r\n")
    for name in ("FDCONFIG.SYS", "FDAUTO.BAT"):
        subprocess.run(["mcopy", "-o", "-i", img, str(root / name), "::" + name], check=True)
    subprocess.run(["mcopy", "-o", "-i", img, exe, "::OPUSDOS.EXE"], check=True)
    for f in files:
        subprocess.run(["mcopy", "-o", "-i", img, f, "::" + os.path.basename(f).upper()], check=True)
    (root / "86box.cfg").write_text(CONFIG.format(floppy=img))
    (root / "nvr").mkdir()
    shutil.copy(HERE / "vm386" / "nvr" / "cmdsl386sx25.nvr", root / "nvr")

    sock = root / "a.sock"
    env = dict(os.environ)
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    p = subprocess.Popen([emu, "-N", "-P", str(root), "-O", str(root / "g.cfg"), "-L", str(root / "log"),
                          "--automation", str(sock), "--automation-hold"],
                         env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(300):
            try:
                s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                s.connect(str(sock))
                break
            except OSError:
                s.close()
                time.sleep(0.1)
        f = s.makefile("rwb", buffering=0)

        def req(line):
            f.write((line + "\n").encode())
            r = json.loads(f.readline())
            if not r.get("ok"):
                raise RuntimeError(f"{line!r}: {r}")
            return r

        def screen():
            t = req("text")
            return "\n".join(bytes.fromhex(row).decode("cp437", "replace").rstrip() for row in t.get("chars", []))

        if not req("wait text 600000 opus_decode at").get("matched"):
            raise SystemExit("OPUSDOS never started decoding:\n" + screen())
        # The line can wrap at the screen's edge, so look in the rows joined end to end.
        raw = "".join(bytes.fromhex(row).decode("cp437", "replace") for row in req("text").get("chars", []))
        m = re.search(r"opus_decode at ([0-9A-Fa-f]+)", raw)
        base = int(m.group(1), 16) - anchor
        print(f"opus_decode at {m.group(1)}, map offset {anchor:#x}: code base {base:#x}")
        print("regs:", json.dumps(req("regs"))[:400])

        samples = collections.Counter()
        n = 0
        while True:
            req(f"step {every}")
            r = req("regs")
            samples[r.get("cs_base", 0) + r["eip"]] += 1
            n += 1
            if n % 250 == 0 and ("decoded " in screen() or "OPUSDONE" in screen()):
                break
        result = [l for l in screen().splitlines() if "decoded " in l]
        f.write(b"quit\n")
        p.wait(timeout=30)
    finally:
        if p.poll() is None:
            p.kill()

by_fn = collections.Counter()
by_mod = collections.Counter()
for addr, c in samples.items():
    off = addr - base
    k = bisect.bisect_right(offsets, off) - 1
    if (k < 0) or (off > offsets[-1] + 0x10000):
        by_fn["(outside the program)"] += c
        by_mod["(outside the program)"] += c
        continue
    by_fn[syms[k][1]] += c
    by_mod[syms[k][2]] += c

total = sum(samples.values())
dump = HERE.parent / "build" / ("prof_" + re.sub(r"[^A-Za-z0-9]+", "_", cmd) + ".json")
dump.write_text(json.dumps({"cmd": cmd, "base": base, "samples": {f"{a:#x}": c for a, c in samples.items()}}))
print(f"raw samples in {dump}")
print("most common raw addresses:", ", ".join(f"{a:#x}" for a, _ in samples.most_common(8)))
print(f"{cmd}: {total} samples, {every} ms apart")
for line in result:
    print(line.strip())
print("functions:")
for name, c in by_fn.most_common(top):
    print(f"  {100.0 * c / total:5.1f}%  {name}")
print("modules:")
for name, c in by_mod.most_common(15):
    print(f"  {100.0 * c / total:5.1f}%  {name}")
