#!/usr/bin/env python3
"""How much host time the emulated TS-3100 takes per emulated second, in
one big step and in 5 ms steps (as the ZMODEM bridge takes them), with
fast forward off and on.

Usage: ts_steptime.py <86Box>
"""
import os
import sys
import time

sys.path.insert(0, os.path.expanduser("~/Projects/386ex-dma-dos"))
import tsvm  # noqa: E402

vm = tsvm.TsVm(sys.argv[1])
try:
    vm.boot()
    for ff in ("off", "on"):
        vm.req(f"ff {ff}")
        t = time.monotonic()
        vm.step(1000)
        big = time.monotonic() - t
        t = time.monotonic()
        for _ in range(200):
            vm.step(5)
        small = time.monotonic() - t
        print(f"ff {ff}: 1 s emulated as one step {big:.2f} s host, as 200 x 5 ms steps {small:.2f} s host", flush=True)
finally:
    vm.close()
