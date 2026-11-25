/* SPDX-License-Identifier: BSD-3-Clause */
/*
 * RSBENCH - times OPUS4DOS's 48 to 44.1 kHz resampler (its src/resample.c) on stereo 16-bit
 * audio, a 20 ms packet (960 frames) at a time as the player feeds it, in memory.
 *
 * Usage: RSBENCH [file] [rate] [-s seconds]   (default 10 s, to 44100 Hz)
 *
 * It takes OPUSDOS's command line, and ignores the file: it resamples a synthetic signal.
 *
 * It prints what OPUSDOS prints ("decoding (", then " decoded ... % of real time, CRC-32 ..."),
 * so insncount.py counts and times it as it does a decode.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#include "resample.h"

#define PACKET 960 /* frames: 20 ms at 48 kHz */

static short in[PACKET * 2];
static short out[(PACKET + 4) * 2];

int
main(int argc, char **argv)
{
    double        secs = 10.0;
    long          rate = 44100;
    long          packets, p, frames = 0;
    unsigned long crc = 0, seed = 12345;
    resampler     rs;
    clock_t       t0, t1;
    int           i;

    for (i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "-s") && (i + 1 < argc))
            secs = atof(argv[++i]);
        else if (atol(argv[i]) > 0)
            rate = atol(argv[i]);
    }
    packets = (long) (secs * 48000.0 / PACKET);
    /* Something like music: a 440 Hz-ish triangle plus noise, different in each channel. */
    for (i = 0; i < PACKET * 2; i++) {
        seed = seed * 1103515245ul + 12345ul;
        in[i] = (short) (((i * 37) % 8192) - 4096 + ((seed >> 16) & 1023));
    }
    resample_init(&rs, 48000, rate, 2);
    printf("RSBENCH: 48000 Hz stereo to %ld Hz, %ld packets of %d frames\n", rate, packets, PACKET);
    printf("  decoding (resample at %p)\n", (void *) resample);
    fflush(stdout);
    t0 = clock();
    for (p = 0; p < packets; p++) {
        long n = resample(&rs, in, PACKET, out);
        frames += n;
        crc += (unsigned short) out[n];
    }
    t1 = clock();
    {
        double audio_s = (double) packets * PACKET / 48000.0;
        double s = (double) (t1 - t0) / CLOCKS_PER_SEC;
        printf("  decoded %.2f s of audio at %ld Hz in %.2f s: %.1f%% of real time, CRC-32 %08lX\n", audio_s, rate, s,
               100.0 * s / audio_s, crc);
    }
    printf("  %ld frames out\n", frames);
    return 0;
}
