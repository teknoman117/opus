#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Run programs on the emulated TS-3100 (86Box, 512 KB, flash disk A:).

Usage: ts_run.py <86Box> [--machine ts3100|ts3200] [--file <path>]... [--free <A: path>]...
                  [--timeout <emulated s>] [--speed <DSZ baud, default 115200>] <command>...

Boots the board (the TS-3100 by default: 512 KB and a 300 KB flash disk;
the TS-3200 has 8 MB and a 1 MB flash disk), deletes the --free files from its flash disk for room
(the emulated flash is a temporary copy), sends the --file files into A:\\
with DSZ over COM1, then runs each command and prints the console.
"""
import os
import sys

sys.path.insert(0, os.path.expanduser("~/Projects/386ex-dma-dos"))
import tsvm  # noqa: E402

args = sys.argv[1:]
emu = args.pop(0)
files, frees, cmds, timeout_ms, machine, speed = [], [], [], 120000, "ts3100", 115200
while args:
    a = args.pop(0)
    if a == "--file":
        files.append(os.path.abspath(args.pop(0)))
    elif a == "--free":
        frees.append(args.pop(0))
    elif a == "--speed":
        speed = int(args.pop(0))
    elif a == "--machine":
        machine = args.pop(0)
    elif a == "--timeout":
        timeout_ms = int(args.pop(0)) * 1000
    else:
        cmds.append(a)

PROMPT = b"[A:\\]"


def zmodem_send(vm, files, timeout_ms):
    """Sends files to a DSZ already receiving on COM1, bridging the host's sz
    to it, with flow control the automation backend doesn't do itself: sz's
    output is held here and given to COM1 a little at a time, only while the
    guest has RTS up and the backend's input queue is nearly empty. Without
    that, the board overruns its UART while it writes a buffer to the flash
    disk (DSZ: "Serial Input Error: Line Status Register 01"), and DSZ gives
    up. Ends when DSZ says it's finished."""
    import select
    import subprocess
    import time
    sz = subprocess.Popen(["sz", "-b", "-q"] + files, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL)
    os.set_blocking(sz.stdout.fileno(), False)
    pos, sent, held = 0, 0, b""
    mark = len(vm.con)
    start = time.monotonic()
    next_report = vm.now + 5000
    try:
        for _ in range(timeout_ms // 5):
            data, r = vm.com1_read(pos)
            pos += len(data)
            if data and sz.poll() is None:
                try:
                    sz.stdin.write(data)
                    sz.stdin.flush()
                except BrokenPipeError:
                    pass
            if select.select([sz.stdout], [], [], 0.001)[0]:
                held += sz.stdout.read() or b""
            if held and r.get("rts", 1) and (r.get("pending", 0) < 64):
                chunk, held = held[:256], held[256:]
                vm.com1_write(chunk)
                sent += len(chunk)
            if b"DSZ FINISHED" in vm.con[mark:]:
                return 0 if b"exit code = 0" in vm.con[mark:] else 1
            if (sz.poll() is not None) and not held and (r.get("pending", 0) == 0):
                vm.step(200)
                return sz.returncode
            if vm.now >= next_report:
                tail = vm.con[-60:].decode(errors="replace").replace("\r", " ").replace("\n", " ")
                print(f"[zmodem: {sent} bytes to the board, {vm.now / 1000:.0f} s emulated, "
                      f"{time.monotonic() - start:.0f} s host; console ...{tail!r}]", flush=True)
                next_report = vm.now + 5000
            if time.monotonic() - start > 900:
                print("[zmodem: no end after 15 minutes of host time, giving up]", flush=True)
                return None
            vm.step(5)
        return None
    finally:
        if sz.poll() is None:
            sz.kill()


if machine != "ts3100":
    tsvm.CONFIG = tsvm.CONFIG.replace("machine = ts3100", f"machine = {machine}").replace("mem_size = 512", "mem_size = 8192")
vm = tsvm.TsVm(emu)
try:
    # Unthrottled: each step otherwise runs at real time, which makes a big
    # ZMODEM transfer take many times as long. Emulated time is unchanged.
    vm.req("ff on")
    vm.boot()
    for f in frees:
        vm.run(f"del {f}", PROMPT, 20000)
    if files:
        mark = len(vm.con)
        vm.type(f"dsz port 1 speed {speed} pB16384 d rz -y\r")
        vm.step(1500)
        rc = zmodem_send(vm, files, 600000)
        vm.wait_console(PROMPT, 20000, since=mark)
        print(f"[sz exit {rc}]", flush=True)
        if rc != 0:
            print(vm.con[mark:].decode(errors="replace").replace("\r", "")[-1500:], flush=True)
            raise SystemExit("the ZMODEM transfer failed")
    for c in cmds:
        print(vm.run(c, PROMPT, timeout_ms).decode(errors="replace").replace("\r", ""), flush=True)
finally:
    vm.close()
