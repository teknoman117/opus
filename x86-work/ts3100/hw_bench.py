#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""A/B timing of the OPUSDOS variants on the real TS-3100.

Usage: hw_bench.py [--dir C:\\OPUS] [--variants OALL,OGEN,...] [--quick] [--no-celt]

The console is COM2 (/dev/ttyUSB1, 9600 8N1); files go over COM1
(/dev/ttyUSB0) at 38400 to the board's DSZ (A:\\UTIL\\DSZ.EXE) by ZMODEM,
from build/hw (made by build_variants.sh) and media/. Each variant is sent,
timed on each stream with -p (packet by packet, PIT timed), and deleted
again to spare the disk. Every decode's CRC is checked against the host
build's (build/host/opusdos, made by build_host.sh) for the same command.

  OGEN  libopus's generic C        OFIR  + the 16-bit FIR
  OMUL  + the 386 multiplies       OENT  + the range decoder's multiplier order
  OALL  all of it, which runs twice (for the board's run-to-run spread)
  OCELT OALL with CELT, on SILK MB and the CELT streams
The first five are SILK-only, small enough for a 512 KB board without
extended memory; OCELT may not have the memory to load there, which is
recorded and the run goes on. The board's ver, mem and chkdsk come first.

--quick runs only OALL on SILK MB; --no-celt leaves out OCELT.
The log goes to build/hw_results/<time>.log and a summary to <time>.json.
"""
import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

import serial

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, os.path.expanduser("~/Projects/386ex-dma-dos/hw"))
from hwcon import Console  # noqa: E402

# (file, rate, seconds): SILK, then CELT.
SILK = [("SMB12.OPU", 12000, 10), ("SWB16.OPU", 16000, 10)]
CELT = [("CWB24.OPU", 12000, 5), ("CSWB40.OPU", 24000, 5)]
VARIANTS = ["OALL", "OGEN", "OMUL", "OFIR", "OENT", "OCELT"]

args = sys.argv[1:]
board_dir = "C:\\OPUS"
quick = "--quick" in args
celt = "--no-celt" not in args
if "--dir" in args:
    board_dir = args[args.index("--dir") + 1].upper()
if "--variants" in args:
    VARIANTS = args[args.index("--variants") + 1].upper().split(",")
if not celt:
    VARIANTS = [v for v in VARIANTS if v != "OCELT"]
if quick:
    VARIANTS, SILK, celt = ["OALL"], SILK[:1], False

stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
outdir = ROOT / "build" / "hw_results"
outdir.mkdir(parents=True, exist_ok=True)
logf = open(outdir / f"{stamp}.log", "w")


def log(text):
    sys.stdout.write(text)
    sys.stdout.flush()
    logf.write(text)
    logf.flush()


def host_crc(name, rate, secs):
    p = subprocess.run([str(ROOT / "build/host/opusdos"), str(ROOT / "media" / name), str(rate), "-s", str(secs), "-p"],
                       capture_output=True, text=True, check=True)
    return re.search(r"CRC-32 ([0-9A-F]{8})", p.stdout).group(1)


def parse(out):
    r = {}
    m = re.search(r"decoded ([\d.]+) s of audio at (\d+) Hz in ([\d.]+) s: ([\d.]+)% of real time, CRC-32 ([0-9A-F]{8})", out)
    if m:
        r.update(audio_s=float(m.group(1)), decode_s=float(m.group(3)), pct=float(m.group(4)), crc=m.group(5))
    m = re.search(r"mean ([\d.]+) ms, slowest ([\d.]+) ms \(packet (\d+)\), worst ([\d.]+)% of its duration", out)
    if m:
        r.update(mean_ms=float(m.group(1)), slowest_ms=float(m.group(2)), worst_pct=float(m.group(4)))
    m = re.search(r"reading the file: ([\d.]+) s, ([\d.]+)%", out)
    if m:
        r.update(read_s=float(m.group(1)), read_pct=float(m.group(2)))
    m = re.search(r"memory left: DOS (\d+) KB, DPMI (\d+) KB", out)
    if m:
        r.update(dos_kb_left=int(m.group(1)), dpmi_kb_left=int(m.group(2)))
    m = re.search(r"scratch: (\d+) of", out)
    if m:
        r.update(scratch=int(m.group(1)))
    return r


con = Console()
com1 = serial.Serial("/dev/ttyUSB0", 38400, timeout=0, xonxoff=False, rtscts=False, dsrdtr=False)
prompt = re.compile(re.escape(f"[{board_dir}]").encode())
results = []


def run(cmd, timeout=30, done=None):
    out = con.run(cmd, timeout=timeout, done=done or prompt).decode(errors="replace").replace("\r", "")
    log(out + "\n")
    return out


def send(paths):
    """Sends files into the current directory with the board's DSZ, at 38400
    and, if that fails (DSZ runs without handshaking, so a slow disk write
    can overrun its UART), again at 19200 and 9600."""
    for speed in (38400, 19200, 9600):
        com1.baudrate = speed
        com1.reset_input_buffer()
        con.s.reset_input_buffer()
        con.type(f"a:\\util\\dsz port 1 speed {speed} d ha off rz -y\r")
        time.sleep(3)
        os.set_blocking(com1.fileno(), True)  # pyserial leaves it non-blocking, which sz takes for an error
        total = sum(os.path.getsize(p) for p in paths)
        try:
            p = subprocess.run(["sz", "-b"] + [str(x) for x in paths], stdin=com1.fileno(), stdout=com1.fileno(),
                               stderr=subprocess.PIPE, timeout=60 + total * 20 // speed)
            rc = p.returncode
        except subprocess.TimeoutExpired:
            rc = -1
        os.set_blocking(com1.fileno(), False)
        log(f"[sz {' '.join(Path(x).name for x in paths)} at {speed}: exit {rc}]\n")
        out = con.wait_for(b"DSZ FINISHED", 30) + con.read_for(2)
        out = out.decode(errors="replace").replace("\r", "")
        log(out + "\n")
        if (rc == 0) and ("exit code = 0" in out):
            return
        con.type("\x18" * 10 + "\r")  # cancel a DSZ still waiting
        con.read_for(3)
    raise SystemExit("ZMODEM transfer failed at every speed")


try:
    con.run("", timeout=3)
    log(f"== board ({stamp})\n")
    con.run("c:", timeout=10, done=re.compile(rb"\[C:\\[^\]]*\]"))
    con.run(f"md {board_dir}", timeout=10, done=re.compile(rb"\[C:\\[^\]]*\]"))
    run(f"cd {board_dir}")
    for c in ("ver", "mem", "chkdsk c:", "dir"):
        run(c, timeout=60)

    streams = SILK + (CELT if celt else [])
    expect = {s: host_crc(*s) for s in streams}
    send([ROOT / "media" / s[0] for s in SILK])

    for v in VARIANTS:
        log(f"== {v}\n")
        send([ROOT / "build" / "hw" / f"{v}.EXE"])
        if v == "OCELT":
            send([ROOT / "media" / s[0] for s in CELT])
            trials = SILK[:1] + CELT
        else:
            trials = list(SILK) * (2 if v == "OALL" else 1)
        for name, rate, secs in trials:
            out = run(f"{v} {name} {rate} -s {secs} -p", timeout=60 + secs * 20)
            r = parse(out)
            r.update(variant=v, stream=name, rate=rate, seconds=secs, expect_crc=expect[(name, rate, secs)])
            r["crc_ok"] = r.get("crc") == r["expect_crc"]
            m = re.search(r"(DOS/32A fatal[^\n]*|out of memory[^\n]*|can't set up[^\n]*)", out)
            if m:
                r["error"] = m.group(1).strip()
            if "pct" not in r:
                log(f"!! {v} {name}: no result\n")
            elif not r["crc_ok"]:
                log(f"!! {v} {name}: CRC {r.get('crc')}, want {r['expect_crc']}\n")
            results.append(r)
        if v == "OCELT":
            for s in CELT:  # DOS's del takes one file
                run(f"del {s[0]}")
        run(f"del {v}.EXE")
finally:
    json.dump(results, open(outdir / f"{stamp}.json", "w"), indent=1)
    com1.close()
    con.close()

log("\n== summary (% of real time; worst = slowest packet against its duration)\n")
for r in results:
    if "pct" in r:
        log(f"  {r['variant']:5s} {r['stream']:10s} {r['rate']:5d} Hz  {r['pct']:6.1f}%  worst {r.get('worst_pct', 0):6.1f}%"
            f"  read {r.get('read_pct', 0):4.1f}%  CRC {'ok' if r['crc_ok'] else 'MISMATCH'}\n")
    else:
        log(f"  {r['variant']:5s} {r['stream']:10s} no result{': ' + r['error'] if 'error' in r else ''}\n")
log(f"results in {outdir / stamp}.json\n")
