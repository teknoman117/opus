#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Boot the 386SX-25 test VM (opus4dos/scripts/vm386) and send keys, dumping the screen.

Usage: vmkeys.py <86Box> <step>...
Each step is one of:
  wait:<ms>          run that much emulated time
  until:<text>       run until <text> is on the screen (up to 60 s)
  key:<name>[+...]   press and release keys together, e.g. key:ctrl+alt+esc
  show               print the screen
The VM keeps its CMOS in vm386/nvr when it quits.
"""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
VM = HERE / "vm386"
SC = {"esc": 0x01, "enter": 0x1c, "ctrl": 0x1d, "alt": 0x38, "y": 0x15, "n": 0x31, "f1": 0x3b, "f5": 0x3f, "f10": 0x44,
      "up": 0x148, "down": 0x150, "left": 0x14b, "right": 0x14d, "pgup": 0x149, "pgdn": 0x151, "tab": 0x0f,
      "space": 0x39, "del": 0x153, "plus": 0x4e, "minus": 0x4a}

emu = sys.argv[1]
VM.mkdir(exist_ok=True)
cfg = VM / "86box.cfg"
if not cfg.exists():
    cfg.write_text("""[Machine]
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
fdd_02_type = none
""")
sock = VM / "a.sock"
env = dict(os.environ)
env.setdefault("QT_QPA_PLATFORM", "offscreen")
p = subprocess.Popen([emu, "-N", "-P", str(VM), "-O", str(VM / "g.cfg"), "-L", str(VM / "log"),
                      "--automation", str(sock), "--automation-hold"], env=env,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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

    def show():
        t = req("text")
        rows = [bytes.fromhex(r).decode("cp437", "replace").rstrip() for r in t.get("chars", [])]
        while rows and not rows[-1]:
            rows.pop()
        print("\n".join(rows))
        print("-" * 40)

    for st in sys.argv[2:]:
        kind, _, arg = st.partition(":")
        if kind == "wait":
            req(f"step {int(arg)}")
        elif kind == "until":
            print(f"until {arg!r}: matched {req(f'wait text 60000 {arg}').get('matched')}")
        elif kind == "key":
            codes = [SC[k] for k in arg.split("+")]
            req("key down " + " ".join(f"{c:#x}" for c in codes))
            req("key up " + " ".join(f"{c:#x}" for c in reversed(codes)))
            req("step 150")
        elif kind == "show":
            show()
    f.write(b"quit\n")
    p.wait(timeout=30)
finally:
    if p.poll() is None:
        p.kill()
