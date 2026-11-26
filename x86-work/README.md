# libopus for x86 DOS machines: CPU-specific decoders

This is a libopus clone for decoders tuned to particular x86 generations, for OPUS4DOS
(`~/Projects/opus4dos`, which builds stock libopus 1.6.1 from its submodule). Each generation's
work is a branch on v1.6.1, so it stays a short, readable series of commits on libopus. Notes,
tools and measurements are in `x86-work/` (this folder).

| Branch | Target | State |
|---|---|---|
| `dos386` | 386SX/386EX, 16- and 8-bit buses: a SILK-only fixed-point decoder | started, below |
| (`dos486`) | 486: fixed point, and float on a 486DX's FPU | not started |
| (`dos586`) | Pentium and later: superscalar fixed point (U/V pairing), and integer work interleaved with FPU work, Quake style | not started |

## Building and timing a branch

`x86-work` is a CMake project of its own: libopus from this clone (whatever branch is checked
out), configured by `src/include/config/config.h`, and OPUSDOS (`src/opusdos.c`), which decodes
an Ogg Opus file and times it.

    cmake -S x86-work -B x86-work/build/dos -G Ninja --toolchain $PWD/x86-work/cmake/openwatcom-dos32a.cmake
    cmake --build x86-work/build/dos               # x86-work/build/dos/OPUSDOS.EXE
    cmake -S x86-work -B x86-work/build/host -G Ninja && cmake --build x86-work/build/host

The host build's CRCs are the reference: a DOS build must give the same ones. `-DX86_DEFINES=`
takes config.h's switches for A/B builds (`OPUS_NO_386_ASM`, `OPUS_NO_386_FIR`,
`OPUS_386_ENTDEC`); `-DX86_SILK_ONLY=ON` links `src/celt_stub.c` ahead of libopus, which stands
in for the CELT decoder's entry points, so SILK streams decode bit-exact, CELT and hybrid
packets fail with OPUS_UNIMPLEMENTED, and CELT's code and tables (about 70 KB) stay out.

    OPUSDOS file.opus [rate] [-s seconds] [-o out.wav] [-p]

decodes into memory and times opus_decode() alone (`-p`: streams the file and times each packet
with the PIT, with the slowest packet against its deadline). `scripts/`: `run_dosbox.sh` runs it
in DOSBox (correctness, not speed), `run386.py` on an emulated 386SX-25 (86Box, `scripts/vm386`),
`prof386.py` samples where it spends its time there and `prof_map.py` maps the samples to
functions, `compare.py` gives one WAV's SNR against another. Test streams go in
`x86-work/media`, which isn't in git (they're made from commercial recordings).

OPUS4DOS (`~/Projects/opus4dos`) can take a branch too. Its `external/opus` comes from the same
fork (github.com/teknoman117/opus), where this is `386-dos` (and the 486 work `486-dos`): check
one out there (`git fetch origin 386-dos && git checkout FETCH_HEAD`) and define
`OPUS_X86_386_ASM` in its config.h. Locally the branches are `~/Projects/opus-x86-386` and its
worktree `~/Projects/opus-x86-486`.

## dos386: what's there

Three commits on v1.6.1, each with an opt-out macro:

1. **386 IMUL/SHRD forms of the fixed-point multiplies** (`celt/x86/fixed_386.h`,
   `silk/x86/macros_386.h`, `silk/x86/SigProc_FIX_386.h`): a 32x16 multiply keeping bits 16-47
   is one `imul` and one `shrd`, with the 16-bit operand as IMUL's r/m operand (the 386's
   early-out multiplier), instead of Watcom's 64-bit multiply helper. `-dOPUS_NO_386_ASM`
   leaves all of the 386 code out.
2. **A 16-bit FIR for `silk_LPC_analysis_filter()`** (orders 10 and 16): `imul word` into DX:AX,
   summed with ADD/ADC. `-dOPUS_NO_386_FIR`.
3. **The range decoder's multiplies with their small operand as the multiplier** (`entdec.c`):
   measured slower on an 8-bit bus, so in only with `-dOPUS_386_ENTDEC`.

`generators/` has the scripts that wrote them (`patch_386.py` hooks the headers in,
`gen_lpc_analysis_386.py` writes the FIR); `ts3100/` the scripts that ran the A/B builds on a
real TS-3100 (`hw_bench.py`), and on the emulated TS-3100 and TS-3200 (`ts_run.py`);
`results/` the real board's A/B logs.

## Measurements

Percentages are decode time against the audio's length: under 100% is real time.

**Emulated 386SX-25** (86Box, Commodore SL386SX-25: 16-bit bus, two wait states, no cache), 10 s:

| Stream | libopus C | + 386 multiplies | + operand order |
|---|---|---|---|
| SILK MB 12 kHz | 271.5% | 168.9% | 160.2% |
| SILK WB 16 kHz | 463.5% | 267.7% | |
| CELT WB 24k, 12 kHz out | 940.9% | 645.3% | |
| CELT SWB 40k, 24 kHz out | 1057.7% | 742.4% | |

86Box charges IMUL its worst case. With the 386's early-out timing (86Box branch
`386-mul-early-out`, pushed to the nlewis fork), SILK MB goes only from 160.2% to 156.9%: the
code is bound by the bus (code fetch and data), not by multiplies.

**Real TS-3100** (386EX-25, bus narrowed to 8 bits, slow DRAM, SILK-only builds), 10 s, by the
PIT. These were taken assuming the PIT runs at 1193182 Hz; the TS-3x00's runs at 1 MHz, so
the times read 16% short: multiply them by 1.19 (335% is really about 400%).

| Build | SILK MB 12 kHz | SILK WB 16 kHz |
|---|---|---|
| libopus C | 583.3% | 1004.8% |
| + 386 multiplies | 336.6% | 526.9% |
| + 16-bit FIR | 335.1% | 521.3% |
| + range decoder order (no FIR) | 339.7% | 531.4% |
| all | 338.3% | 525.7% |

BUSBENCH on that board (now in the VQ8 workstream; it read 16% short too): about 6 clocks per
byte for code fetch and data alike, a taken jump refetches (a 15-byte loop costs 80 clocks a
pass, so nothing runs out of the prefetch queue), and SILK's 32x16 multiply-accumulate tap costs
101-108 clocks however it's written. SILK MB needs about 25 taps a sample, against 2083 clocks
a sample at 12 kHz, so bit-exact SILK can't run in real time on that board.

## Lessons so far

- On a 386SX/EX, count bytes moved (code and data), not instruction clocks. Smaller encodings
  and 16-bit data win; a dword coefficient costs more than a 16-bit one plus a MOVSX.
- Hand-written predictor loops with dword coefficients were *slower* than Watcom's C (167.8% vs
  160.2% emulated), for that reason.
- What's left in SILK beyond the taps (excitation, range decoding, per-sample saturation,
  loop overhead) is most of the time: decode_core's taps are about a third of its cost.
- An 8-bit DAC would allow 16-bit synthesis state (no SHRD per tap, half the state traffic);
  that's not bit-exact, so it needs an SNR check against libopus instead of CRCs.

## Memory, for a 512 KB board

The full decoder needs about 275 KB of conventional memory under DOS/32A; the SILK-only build
about 200 KB (130 KB executable, 113 KB static, 32 KB of libopus scratch of which 8 KB is used).
Without extended memory DOS/32A needs object loading scheme #1 (`d32cfg.py --load 1`, in
OPUS4DOS's scripts), and can't load SC-packed executables (their decompression buffers come
from extended memory only).

## Roadmap ideas

- **386, SILK only**: decode_core in assembly with 16-bit operand loads and minimal code per
  sample; the excitation and range decoder too; 16-bit synthesis state for an 8-bit DAC.
- **486**: an 8 KB unified cache makes loops cheap again (the opposite of the 386EX), IMUL is
  13-42 clocks, most ALU ops 1 clock; fixed point tuned for that, and a float build for 486DX
  (libopus's float decoder on the FPU).
- **586+**: U/V pipe pairing in the fixed-point kernels; for float, FPU multiplies and adds
  interleaved with integer work (the range decoder, bit unpacking) the way Quake overlapped its
  FDIV with integer code; CELT's IMDCT is the big target.

## License

What this work adds is BSD 3-clause licensed, as libopus is (`x86-work/LICENSE`): everything in
`x86-work/`, and the new x86 headers in libopus's tree (`celt/x86/fixed_386.h`,
`silk/x86/macros_386.h`, `silk/x86/SigProc_FIX_386.h`, `silk/x86/LPC_analysis_filter_386.h`),
each marked with an SPDX line. The changes to libopus's own files are under libopus's license
(`COPYING`). An OPUSDOS.EXE built here also contains libopus, the DOS/32 Advanced DOS Extender
and OpenWatcom's C library: see OPUS4DOS's `NOTICE` for their terms.
