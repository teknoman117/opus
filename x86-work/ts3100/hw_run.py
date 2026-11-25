#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Send files to the real TS-3100's C:\\OPUS and run commands there.

Usage: hw_run.py [--file <path>]... [--timeout <s>] <command>...

The console is COM2 (/dev/ttyUSB1, 9600 8N1); files go over COM1
(/dev/ttyUSB0) by ZMODEM to the board's DSZ, at 38400, or 19200 or 9600 if
that fails. Each command's console output is printed.
"""
import os
from pathlib import Path
import re
import subprocess
import sys
import time

import serial

sys.path.insert(0, os.path.expanduser("~/Projects/386ex-dma-dos/hw"))
from hwcon import Console  # noqa: E402

args = sys.argv[1:]
files, cmds, timeout = [], [], 120
while args:
    a = args.pop(0)
    if a == "--file":
        files.append(Path(args.pop(0)).resolve())
    elif a == "--timeout":
        timeout = int(args.pop(0))
    else:
        cmds.append(a)

con = Console()
com1 = serial.Serial("/dev/ttyUSB0", 38400, timeout=0, xonxoff=False, rtscts=False, dsrdtr=False)
prompt = re.compile(rb"\[C:\\OPUS\]")
anyp = re.compile(rb"\[[A-Z]:\\[^\]\r\n]*\]")


def send(paths):
    for speed in (38400, 19200, 9600):
        com1.baudrate = speed
        com1.reset_input_buffer()
        con.s.reset_input_buffer()
        con.type(f"a:\\util\\dsz port 1 speed {speed} d ha off rz -y\r")
        time.sleep(3)
        os.set_blocking(com1.fileno(), True)
        total = sum(os.path.getsize(p) for p in paths)
        try:
            rc = subprocess.run(["sz", "-b"] + [str(p) for p in paths], stdin=com1.fileno(), stdout=com1.fileno(),
                                stderr=subprocess.PIPE, timeout=60 + total * 20 // speed).returncode
        except subprocess.TimeoutExpired:
            rc = -1
        os.set_blocking(com1.fileno(), False)
        out = (con.wait_for(b"DSZ FINISHED", 30) + con.read_for(2)).decode(errors="replace")
        print(f"[sz {' '.join(p.name for p in paths)} at {speed}: exit {rc}, "
              f"{'ok' if 'exit code = 0' in out else 'DSZ failed'}]", flush=True)
        if (rc == 0) and ("exit code = 0" in out):
            return
        con.type("\x18" * 10 + "\r")
        con.read_for(3)
    raise SystemExit("ZMODEM transfer failed at every speed")


try:
    con.run("", timeout=3, done=anyp)
    con.run("c:", timeout=10, done=anyp)
    con.run("md c:\\opus", timeout=10, done=anyp)
    con.run("cd c:\\opus", timeout=10, done=anyp)
    if files:
        send(files)
    for c in cmds:
        print(con.run(c, timeout=timeout, done=prompt).decode(errors="replace").replace("\r", ""), flush=True)
finally:
    com1.close()
    con.close()
