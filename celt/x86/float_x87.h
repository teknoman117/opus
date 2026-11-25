/* SPDX-License-Identifier: BSD-3-Clause */
/* The float decoder's x87 routines (float_x87.asm, kiss_fft_x87.asm), for OpenWatcom's register
   calling convention: arguments in EAX, EDX, EBX, ECX, ESI, EDI, in that order. OPUS_X87_ASM
   (x86-work's X86_FLOAT build) turns them on. */
#ifndef FLOAT_X87_H
#define FLOAT_X87_H

#if defined(OPUS_X87_ASM) && defined(__WATCOMC__) && !defined(FIXED_POINT)

void celt_float2int16_x87(const float *in, short *out, int cnt);
#pragma aux celt_float2int16_x87 "*_" parm [eax] [edx] [ebx] modify exact [eax ebx edx 8087];
#define OVERRIDE_FLOAT2INT16
#define celt_float2int16(in, out, cnt, arch) ((void) (arch), celt_float2int16_x87(in, out, cnt))

int opus_limit2_checkwithin1_x87(float *samples, int cnt);
#pragma aux opus_limit2_checkwithin1_x87 "*_" parm [eax] [edx] value [eax] modify exact [eax edx];
#define OVERRIDE_LIMIT2_CHECKWITHIN1
#define opus_limit2_checkwithin1(samples, cnt, arch) ((void) (arch), opus_limit2_checkwithin1_x87(samples, cnt))

/* The kiss FFT's butterflies (kiss_fft_x87.asm): as kf_bfly<p>(), with st->twiddles for st. */
#define KF_BFLY_X87(p) \
    void kf_bfly##p##_x87(void *Fout, const void *tw, int fstride, int m, int N, int mm);
KF_BFLY_X87(3)
KF_BFLY_X87(4)
KF_BFLY_X87(5)
#pragma aux kf_bfly3_x87 "*_" parm [eax] [edx] [ebx] [ecx] [esi] [edi] modify exact [eax ebx ecx edx esi edi 8087];
#pragma aux kf_bfly4_x87 "*_" parm [eax] [edx] [ebx] [ecx] [esi] [edi] modify exact [eax ebx ecx edx esi edi 8087];
#pragma aux kf_bfly5_x87 "*_" parm [eax] [edx] [ebx] [ecx] [esi] [edi] modify exact [eax ebx ecx edx esi edi 8087];
#define OPUS_X87_KF_BFLY

/* deemphasis_stereo_simple() of celt_decoder.c (float_x87.asm). */
void deemphasis_stereo_x87(const float *x0, const float *x1, float *pcm, int N, float *mem, const float *coef0);
#pragma aux deemphasis_stereo_x87 "*_" parm [eax] [edx] [ebx] [ecx] [esi] [edi] modify exact [eax ebx ecx edx 8087];
#define OPUS_X87_DEEMPHASIS

/* The same, straight to saturated 16-bit samples (float_x87.asm), for OPUS_INT16_DIRECT. */
void deemphasis16_stereo_x87(const float *x0, const float *x1, short *pcm, int N, float *mem, const float *coef0);
#pragma aux deemphasis16_stereo_x87 "*_" parm [eax] [edx] [ebx] [ecx] [esi] [edi] modify exact [eax ebx ecx edx 8087];
void deemphasis16acc_stereo_x87(const float *x0, const float *x1, short *pcm, int N, float *mem, const float *coef0);
#pragma aux deemphasis16acc_stereo_x87 "*_" parm [eax] [edx] [ebx] [ecx] [esi] [edi] modify exact [eax ebx ecx edx edi 8087];
#define OPUS_X87_DEEMPHASIS16

/* clt_mdct_backward_c()'s loops (mdct_x87.asm), each given its parameters in one block. */
struct mdct_x87_args {
    const float *in1, *in2; /* pre: xp1, xp2; post: yp0, yp1; mirror: xp1, yp1 */
    float       *out;       /* pre: yp */
    const float *t;         /* trig, or the window */
    const short *bitrev;    /* pre */
    int          n;         /* N4, or the overlap */
    int          step;      /* pre: 2 * stride * sizeof (float) */
};
void mdct_prerot_x87(const struct mdct_x87_args *a);
void mdct_postrot_x87(const struct mdct_x87_args *a);
void mdct_mirror_x87(const struct mdct_x87_args *a);
#pragma aux mdct_prerot_x87 "*_" parm [eax] modify exact [eax 8087];
#pragma aux mdct_postrot_x87 "*_" parm [eax] modify exact [eax 8087];
#pragma aux mdct_mirror_x87 "*_" parm [eax] modify exact [eax 8087];
#define OPUS_X87_MDCT

#endif
#endif
