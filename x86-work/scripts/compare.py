#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""SNR of a 16-bit WAV against a reference WAV of the same rate and channels.

Usage: compare.py <test.wav> <reference.wav>
"""
import array
import math
import sys
import wave


def samples(path):
    with wave.open(path, "rb") as w:
        if w.getsampwidth() != 2:
            raise SystemExit(f"{path}: not 16-bit")
        data = array.array("h", w.readframes(w.getnframes()))
        return data, w.getframerate(), w.getnchannels()


a, ra, ca = samples(sys.argv[1])
b, rb, cb = samples(sys.argv[2])
if (ra, ca) != (rb, cb):
    raise SystemExit(f"format differs: {ra}/{ca} vs {rb}/{cb}")
n = min(len(a), len(b))
sig = sum(x * x for x in b[:n])
err = sum((x - y) * (x - y) for x, y in zip(a[:n], b[:n]))
peak = max(abs(x - y) for x, y in zip(a[:n], b[:n]))
snr = 10 * math.log10(sig / err) if err else float("inf")
print(f"{sys.argv[1]}: {n} samples ({len(a)} vs {len(b)}), SNR {snr:.1f} dB, peak difference {peak}")
