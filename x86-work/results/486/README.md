# OPUSDOS on emulated 486s (86Box)

Measured with `scripts/insncount.py`: 10 s of each clip decoded at 48 kHz stereo on an ABIT AB-PB4
(ALi M1489) in 86Box's interpreter, with OPUSDOS's own timing of `opus_decode()`. Percent of real
time: under 100 keeps up. `--profile 1` runs sample EIP (`scripts/insnprof.py` maps them).

## DX2-66, the target

| Clip (48 kHz stereo)  | stock fixed | float, C | dos486 |
|-----------------------|------------:|---------:|-------:|
| GHOSTS, CELT 128k     | 345.0       | 327.5    | 185.9  |
| BADAPPLE, CELT 64k    | 297.8       | 301.1    | 158.5  |
| FEARHYB, hybrid 20k   | 360.9       | 402.6    | 231.5  |
| FEARSILK, SILK 12k    | 95.4        | 224.9    | 76.8   |

dos486, step by step (GHOSTS / BADAPPLE / FEARHYB / FEARSILK):

| Build                                             | DX2-66 |
|---------------------------------------------------|--------|
| float, OPUSDOS -f (inline FISTP conversion)       | 213 / 186 / 290 / 112 |
| x87 output path (conversion, limit check)         | 209 / 183 / 283 / 105 |
| + x87 FFT butterflies (radix 3, 4, 5)             | 200 / 174 / 274 / 105 |
| + x87 MDCT loops, de-emphasis                     | 195 / 171 / 272 / 106 |
| + 16-bit output for CELT-only and SILK-only       | 186 / 159 / 272 / 95  |
| + dos386's multiplies (SILK)                      | 186 / 159 / 247 / 77  |
| + 16-bit output for hybrid                        | 186 / 159 / 232 / 77  |

-4r scheduling and -oh -ol+ change nothing measurable.

GHOSTS re-encoded from the source (same minute), dos486: 128k 186, 96k 176, 64k 167, 48k 170;
12 kHz cutoff (super-wideband) 96k 159, 64k 150. Bitrate and bandwidth cut the band decoding;
the synthesis (two 1920-sample IMDCTs per 20 ms, post-filter, de-emphasis) costs the same at
any bitrate, around 90-100% of a DX2-66 by itself.

OPUS4DOS's 48 to 44.1 kHz resampler on top: 18.7% of a DX2-66, 8.2% with the exact-step rewrite
(opus4dos branch fast-resampler).

## Where GHOSTS's time goes now (DX2-66)

FFT 29% (radix 5 9.8, radix 4 9.5, radix 3 6.9, radix 2 2.8), band decoding 33% (exp_rotation1
7.9, cwrsi 4.0, stereo_merge 3.8, denormalise_bands 3.2, normalise_residual 2.8, ...), MDCT
rotations 10.3%, post-filter 6.0%, de-emphasis to 16 bits 5.6%, range decoding 3%.

## Reading these against real hardware

86Box charges the 486 FPU the middle of Intel's ranges: FADD/FSUB 14 clocks (Intel: 8-20,
typically 10), FMUL m32 11, FMUL st(i) 16, FLD m32 3, FST m32 7, FXCH 4, FIST 31. The float
decoder is mostly FADDs and FMULs, so a real DX2 may well run it faster than 86Box says; but
86Box runs a clock-doubled DX2 at exactly twice a DX-33, with nothing for cache misses on the
33 MHz bus, which a real one pays. IMUL is a flat 30 clocks in 86Box (13-42, by the multiplier,
on a 486).
