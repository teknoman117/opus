#!/usr/bin/env python3
"""Boot the emulated TS-3100 (86Box, 512 KB) and run DOS commands on its console.

Usage: ts_probe.py <86Box> <command>...
"""
import os
import sys

sys.path.insert(0, os.path.expanduser("~/Projects/386ex-dma-dos"))
from tsvm import TsVm  # noqa: E402

vm = TsVm(sys.argv[1])
try:
    vm.boot()
    for c in sys.argv[2:]:
        print(vm.run(c, b"[A:\\]", 60000).decode(errors="replace").replace("\r", ""))
finally:
    vm.close()
