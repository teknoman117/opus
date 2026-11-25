#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Run OPUSDOS on an emulated 386SX-25 (86Box, Commodore SL386SX-25) and print its log.

Usage: run386.py <86Box> <OPUSDOS.EXE> <command>... [--file <path>]... [--timeout <emulated s>]

Each <command> is a DOS command line run in A:\\ with its output appended to
A:\\RESULT.TXT; the --file paths are copied to the floppy first. The floppy
is the FreeDOS 1.4 boot disk without its installer. The CPU runs on 86Box's
interpreter (no dynarec), so the 386SX's instruction timings apply.
"""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time

BOOT = os.path.expanduser("~/Downloads/FD14-FloppyEdition/144m/x86BOOT.img")

args = sys.argv[1:]
emu, exe = args[0], args[1]
cmds, files, timeout_s, watch = [], [], 900, False
i = 2
while i < len(args):
    if args[i] == "--watch":
        watch = True
        i += 1
    elif args[i] == "--file":
        files.append(args[i + 1])
        i += 2
    elif args[i] == "--timeout":
        timeout_s = int(args[i + 1])
        i += 2
    else:
        cmds.append(args[i])
        i += 1

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


def mtools(*a):
    subprocess.run(list(a), check=True)


with tempfile.TemporaryDirectory(prefix="run386_") as tmp:
    root = Path(tmp)
    floppy = root / "test.img"
    shutil.copy(BOOT, floppy)
    img = str(floppy)
    mtools("mdel", "-i", img, "::SETUP.BAT")
    (root / "FDCONFIG.SYS").write_text("FILES=40\r\nBUFFERS=20\r\nLASTDRIVE=Z\r\n"
                                       "SHELL=\\FREEDOS\\BIN\\COMMAND.COM \\FREEDOS\\BIN /E:2048 /P=\\FDAUTO.BAT\r\n")
    lines = ["@ECHO OFF", "SET PATH=\\FREEDOS\\BIN", "A:", "CD \\", "ECHO OPUSDOS on a 386SX-25 > RESULT.TXT"]
    for c in cmds:
        lines += [f"ECHO ^> {c} >> RESULT.TXT", f"{c} >> RESULT.TXT"]
    lines += ["ECHO OPUSDONE"]
    (root / "FDAUTO.BAT").write_text("\r\n".join(lines) + "\r\n")
    for name in ("FDCONFIG.SYS", "FDAUTO.BAT"):
        mtools("mcopy", "-o", "-i", img, str(root / name), "::" + name)
    mtools("mcopy", "-o", "-i", img, exe, "::OPUSDOS.EXE")
    for f in files:
        mtools("mcopy", "-o", "-i", img, f, "::" + os.path.basename(f).upper())

    (root / "86box.cfg").write_text(CONFIG.format(floppy=img))
    # The CMOS, set up once with vmkeys.py: drive A is a 1.44M 3.5" drive.
    (root / "nvr").mkdir()
    shutil.copy(Path(__file__).resolve().parent / "vm386" / "nvr" / "cmdsl386sx25.nvr", root / "nvr")
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
            try:
                t = req("text")
            except RuntimeError:
                return ""
            return "\n".join(bytes.fromhex(row).decode("cp437", "replace").rstrip() for row in t.get("chars", []))

        t0 = time.time()
        done = False
        for _ in range(timeout_s // 10):
            r = req("wait text 10000 OPUSDONE")
            if r.get("matched"):
                done = True
                break
            scr = screen()
            if watch:
                tail = [l for l in scr.splitlines() if l.strip()][-3:]
                print(f"[{time.time() - t0:5.0f} s host] " + " | ".join(tail), flush=True)
            if "F1" in scr or "CMOS" in scr.upper():
                req("key down 0x3b")
                req("key up 0x3b")
        print(f"[{'finished' if done else 'TIMED OUT'} after {time.time() - t0:.0f} s of host time]")
        if not done:
            print(screen())
        f.write(b"quit\n")
        p.wait(timeout=30)
    finally:
        if p.poll() is None:
            p.kill()

    out = subprocess.run(["mtype", "-i", img, "::RESULT.TXT"], capture_output=True, text=True)
    print(out.stdout.replace("\r", "") if out.returncode == 0 else f"(no RESULT.TXT: {out.stderr.strip()})")
