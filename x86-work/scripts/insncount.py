#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Count the instructions OPUSDOS executes decoding each file, and time it, on an emulated 486.

Usage: insncount.py <86Box> <OPUSDOS.EXE> <cpu> <out.json> <file.opu>... [--rate 48000] [--seconds 10] [--args "<OPUSDOS options>"] [--profile <ms>] [--watch]

<cpu> is dx33, dx2-66 or dx4-100. The machine is an ABIT AB-PB4 (ALi M1489, PCI, Award BIOS) with that
CPU, 16 MB, a Cirrus GD5446, booting FreeDOS 1.4 from floppy, the files on an IDE disk (whose MBR
boots the floppy: vm/floppymbr.bin). 86Box runs its interpreter (no dynarec), so every
instruction is counted, by opcode, by the `insns` automation command (an 86Box built with
AUTOMATION=ON and the instruction counter). The count covers OPUSDOS's decode only: it's reset
when OPUSDOS says it's decoding and read when it says it has decoded. OPUSDOS's own timing (by
the machine's clock) comes with it. Results, per file, go to out.json.

--profile <ms> also samples the CPU's linear EIP every <ms> of emulated time through the
decode (into "eip", by address), for prof_map.py to put to functions; the decode's address,
which OPUSDOS prints, goes in "anchor". The sampling doesn't change the counts or the timing.
"""
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

BOOT = os.path.expanduser("~/Downloads/FD14-FloppyEdition/144m/x86BOOT.img")
CPUS = {
    "dx33": ("i486dx", 33333333, 1),
    "dx2-66": ("i486dx2", 66666666, 2),
    "dx4-100": ("idx4", 100000000, 3),
    "5x86-133": ("am5x86", 133333333, 4),
}
CONFIG = """[Machine]
machine = abpb4
cpu_family = {family}
cpu_speed = {speed}
cpu_multi = {multi}
cpu_use_dynarec = 0
mem_size = 16384

[Video]
gfxcard = cl_gd5446_pci

[Floppy and CD-ROM drives]
fdd_01_type = 35_2hd
fdd_01_fn = {boot}
fdd_02_type = none

[Hard disks]
hdd_01_parameters = 63, 16, 130, 0, ide
hdd_01_fn = {data}
hdd_01_ide_channel = 0:0
"""
CYLS, HEADS, SECTORS = 130, 16, 63

args = sys.argv[1:]
rate, seconds = 48000, 10
watch = "--watch" in args
if watch:
    args.remove("--watch")
profile = 0
if "--profile" in args:
    i = args.index("--profile")
    profile = int(args[i + 1])
    del args[i:i + 2]
extra = ""
if "--args" in args:
    i = args.index("--args")
    extra = " " + args[i + 1]
    del args[i:i + 2]
for opt in ("--rate", "--seconds"):
    if opt in args:
        i = args.index(opt)
        if opt == "--rate":
            rate = int(args[i + 1])
        else:
            seconds = int(args[i + 1])
        del args[i:i + 2]
emu, exe, cpu, out_json = args[0], args[1], args[2], Path(args[3])
files = args[4:]
family, speed, multi = CPUS[cpu]


def mtools(*a):
    subprocess.run(list(a), check=True)


results = []
with tempfile.TemporaryDirectory(prefix="insncount_") as tmp:
    root = Path(tmp)
    boot, data = root / "boot.img", root / "hdd.img"
    shutil.copy(BOOT, boot)
    mtools("mdel", "-i", str(boot), "::SETUP.BAT")
    (root / "FDCONFIG.SYS").write_text("FILES=40\r\nBUFFERS=20\r\nLASTDRIVE=Z\r\n"
                                       "SHELL=\\FREEDOS\\BIN\\COMMAND.COM \\FREEDOS\\BIN /E:2048 /P=\\FDAUTO.BAT\r\n")
    lines = ["@ECHO OFF", "SET PATH=\\FREEDOS\\BIN", "C:"]
    for n, f in enumerate(files):
        lines += ["CLS", f"ECHO ==RUN {n}==", f"OPUSDOS {os.path.basename(f).upper()} {rate} -s {seconds}{extra}"]
    lines += ["CLS", "ECHO ==ALL DONE=="]
    (root / "FDAUTO.BAT").write_text("\r\n".join(lines) + "\r\n")
    for name in ("FDCONFIG.SYS", "FDAUTO.BAT"):
        mtools("mcopy", "-o", "-i", str(boot), str(root / name), "::" + name)
    with open(data, "wb") as d:
        d.truncate(CYLS * HEADS * SECTORS * 512)
    subprocess.run(["sfdisk", "--no-reread", "-q", str(data)], input=b"start=63, type=6, bootable\n",
                   check=True, stdout=subprocess.DEVNULL)
    mbr = (Path(__file__).resolve().parent / "vm" / "floppymbr.bin").read_bytes()
    with open(data, "r+b") as d:
        d.write(mbr[:0x1be])
    part = f"{data}@@{63 * 512}"
    mtools("mformat", "-i", part, "-T", str(CYLS * HEADS * SECTORS - 63), "-h", str(HEADS), "-s", str(SECTORS),
           "-H", "63", "-v", "OPUSX86", "::")
    mtools("mcopy", "-i", part, exe, "::OPUSDOS.EXE")
    for f in files:
        mtools("mcopy", "-i", part, f, "::" + os.path.basename(f).upper())

    (root / "86box.cfg").write_text(CONFIG.format(family=family, speed=speed, multi=multi, boot=boot, data=data))
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
        else:
            raise SystemExit("86Box didn't open its automation socket")
        fh = s.makefile("rwb", buffering=0)

        def req(line):
            fh.write((line + "\n").encode())
            r = json.loads(fh.readline())
            if not r.get("ok"):
                raise RuntimeError(f"{line!r}: {r}")
            return r

        def screen():
            t = req("text")
            return "\n".join(bytes.fromhex(row).decode("cp437", "replace").rstrip() for row in t.get("chars", []))

        def wait_for(text, limit_s=3600):
            t0 = time.time()
            while time.time() - t0 < limit_s:
                if req(f"wait text 10000 {text}").get("matched"):
                    return True
                scr = screen()
                if watch:
                    tail = [l for l in scr.splitlines() if l.strip()][-2:]
                    print(f"  [{time.time() - t0:5.0f} s, waiting for {text!r}] " + " | ".join(tail), flush=True)
                if ("F2" in scr) and ("efault" in scr):  # AMI: load the defaults and go on
                    req("key down 0x3c")
                    req("key up 0x3c")
                elif "Press F1 to continue" in scr:  # Award
                    req("key down 0x3b")
                    req("key up 0x3b")
            raise SystemExit(f"no {text!r} after {limit_s} s; the screen:\n{screen()}")

        for n, f in enumerate(files):
            wait_for(f"==RUN {n}==")
            wait_for("decoding (")
            req("insns reset")
            samples = {}
            if profile:
                n_s = 0
                while True:
                    req(f"step {profile}")
                    g = req("regs")
                    a = g.get("cs_base", 0) + g["eip"]
                    samples[a] = samples.get(a, 0) + 1
                    n_s += 1
                    if n_s % 200 == 0 and " decoded " in screen():
                        break
            wait_for(" decoded ")
            counts = req("insns")
            # The rest of OPUSDOS's line comes after the counts are taken: let it be printed.
            wait_for("CRC-32", 600)
            req("step 50")
            # OPUSDOS's lines are longer than the screen is wide: match across the wraps.
            scr = screen().replace("\n", "")
            m = re.search(r"decoded ([\d.]+) s of audio at (\d+) Hz in ([\d.]+) s: ([\d.]+)% of real time, CRC-32 ([0-9A-F]+)",
                          scr)
            anchor = re.search(r"decoding \((\w+) at ([0-9A-Fa-f]+)\)", scr)
            mix = re.search(r"SILK (\d+), hybrid (\d+), CELT (\d+)", scr)
            r = {"file": os.path.basename(f), "cpu": cpu, "rate": rate, "seconds": seconds, "args": extra.strip(),
                 "instructions": counts["total"], "counts": counts["counts"]}
            if m:
                r.update(audio_s=float(m.group(1)), decode_s=float(m.group(3)), pct=float(m.group(4)), crc=m.group(5))
            if profile:
                r.update(eip={f"{a:#x}": c for a, c in samples.items()}, every_ms=profile)
                if anchor:
                    r.update(anchor_sym=anchor.group(1), anchor=int(anchor.group(2), 16))
            if mix:
                r.update(silk=int(mix.group(1)), hybrid=int(mix.group(2)), celt=int(mix.group(3)))
            results.append(r)
            print(f"{cpu:8s} {r['file']:13s} {r['instructions'] / 1e6:9.1f} M instructions"
                  f" ({r['instructions'] / max(r.get('audio_s', seconds), 1e-9) / 1e6:6.1f} M per s of audio),"
                  f" {r.get('pct', float('nan')):6.1f}% of real time", flush=True)
        wait_for("==ALL DONE==", 600)
        fh.write(b"quit\n")
        p.wait(timeout=30)
    finally:
        if p.poll() is None:
            p.kill()
out_json.write_text(json.dumps(results, indent=1))
