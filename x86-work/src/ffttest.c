/* SPDX-License-Identifier: BSD-3-Clause */
/*
 * FFTTEST - checks libopus's FFT (opus_fft(), with whatever butterflies the build has) for each
 * of CELT's sizes at 48 kHz against a DFT in double precision, on random input, and prints the
 * error relative to the output's RMS. A float build should be about 1e-7.
 */
#include <math.h>
#include <stdio.h>
#include <stdlib.h>

#include "config.h"
#include "kiss_fft.h"
#include "modes.h"

#define MAXN 480

static kiss_fft_cpx in[MAXN], out[MAXN];

int
main(void)
{
    const CELTMode *mode = opus_custom_mode_create(48000, 960, NULL);
    int             s, n, k, bad = 0;
    unsigned long   seed = 1;

    for (s = 0; s <= mode->mdct.maxshift; s++) {
        const kiss_fft_state *st = mode->mdct.kfft[s];
        double                err = 0, pow = 0;
        int                   N = st->nfft;
        for (n = 0; n < N; n++) {
            seed = seed * 1103515245ul + 12345ul;
            in[n].r = (float) (((seed >> 8) & 65535) - 32768) / 32768.f;
            seed = seed * 1103515245ul + 12345ul;
            in[n].i = (float) (((seed >> 8) & 65535) - 32768) / 32768.f;
        }
        opus_fft(st, in, out, 0);
        for (k = 0; k < N; k++) {
            double re = 0, im = 0;
            for (n = 0; n < N; n++) {
                double a = -2.0 * 3.14159265358979323846 * (double) n * k / N;
                re += in[n].r * cos(a) - in[n].i * sin(a);
                im += in[n].r * sin(a) + in[n].i * cos(a);
            }
            re /= N;
            im /= N;
            err += (out[k].r - re) * (out[k].r - re) + (out[k].i - im) * (out[k].i - im);
            pow += re * re + im * im;
        }
        err = sqrt(err / pow);
        printf("FFT %3d: relative RMS error %.2e%s\n", N, err, (err > 1e-5) ? "  BAD" : "");
        bad |= (err > 1e-5);
    }
    printf(bad ? "FFTTEST FAILED\n" : "FFTTEST OK\n");
    return bad;
}
