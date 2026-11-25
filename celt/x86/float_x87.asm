; SPDX-License-Identifier: BSD-3-Clause
; The float decoder's output path for the 486's x87, with OpenWatcom's register calling
; convention (declared in float_x87.h). NASM, OMF (-f obj).
;
; On a 486 FIST/FISTP costs about 31 clocks and a float compare (FCOM, FNSTSW, SAHF) about 10,
; so these avoid both: a float is converted by adding 384.0, whose ulp is 2^-15, and taking
; the low bits of the stored sum, and range checks are integer compares of float bit patterns.

bits 32

segment _TEXT public align=16 use32 class=CODE

; void celt_float2int16_x87(const float *in [eax], short *out [edx], int cnt [ebx])
;
; out[i] = round-to-nearest-even(in[i] * 32768), saturated to 16 bits: the same as
; FLOAT2INT16() with lrint(). For |in[i]| < 128, in[i] + 384 lies in [256, 512), where a
; float's ulp is 2^-15, so the stored sum's mantissa holds the rounded result, offset by
; 384 * 32768: its bit pattern less that of 384.0 (43C00000h) is the integer. Sums outside
; [256, 512) give patterns outside 43800000h-43FFFFFFh, which saturate; a negative sum
; (in[i] < -384) has the sign bit set and saturates low.
global celt_float2int16_x87_
celt_float2int16_x87_:
        test    ebx, ebx
        jle     .ret
        push    ecx
        push    dword 0x43C00000        ; [esp+4]: 384.0
        push    eax                     ; [esp]: where the sum is stored
.loop:
        fld     dword [eax]
        fadd    dword [esp+4]
        fstp    dword [esp]
        mov     ecx, [esp]
        add     eax, 4
        test    ecx, ecx
        js      .low
        sub     ecx, 0x43C00000
        cmp     ecx, 32767
        jg      .high
        cmp     ecx, -32768
        jl      .low
.store:
        mov     [edx], cx
        add     edx, 2
        dec     ebx
        jnz     .loop
        add     esp, 8
        pop     ecx
.ret:
        ret
.high:
        mov     ecx, 32767
        jmp     .store
.low:
        mov     ecx, -32768
        jmp     .store

; int opus_limit2_checkwithin1_x87(float *samples [eax], int cnt [edx]) -> eax
;
; Clamps the samples to [-2, 2], as opus_limit2_checkwithin1_c() does, and returns 1 if they
; were all within [-1, 1] (so the soft clip can skip its per-sample checks), else 0. Integer
; only: |x| > 1 when its pattern, less the sign, is above 3F800000h, and > 2 above 40000000h
; (NaNs included, which clamp to 2 with their sign).
global opus_limit2_checkwithin1_x87_
opus_limit2_checkwithin1_x87_:
        push    ebx
        push    ecx
        push    esi
        mov     ebx, 1
        test    edx, edx
        jle     .done
.loop:
        mov     ecx, [eax]
        mov     esi, ecx
        and     esi, 0x7FFFFFFF
        cmp     esi, 0x3F800000
        ja      .over1
.next:
        add     eax, 4
        dec     edx
        jnz     .loop
.done:
        mov     eax, ebx
        pop     esi
        pop     ecx
        pop     ebx
        ret
.over1:
        xor     ebx, ebx
        cmp     esi, 0x40000000
        jbe     .next
        and     ecx, 0x80000000
        or      ecx, 0x40000000
        mov     [eax], ecx
        jmp     .next

; void deemphasis_stereo_x87(const float *x0 [eax], const float *x1 [edx], float *pcm [ebx],
;                            int N [ecx], float *mem [esi], const float *coef0 [edi])
;
; deemphasis_stereo_simple() of celt_decoder.c, float build: for each channel,
; tmp = x[j] + VERY_SMALL + m, m = coef0 * tmp, pcm[2j + c] = tmp / 32768. The two filter
; states stay on the stack (at full precision) for the whole frame.
global deemphasis_stereo_x87_
deemphasis_stereo_x87_:
        push    dword [edi]             ; [esp+8]: coef0
        push    dword 0x38000000        ; [esp+4]: 1/32768
        push    dword 0x0DA24260        ; [esp]: VERY_SMALL, 1e-30
        fld     dword [esi+4]
        fld     dword [esi]             ; m0 m1
        test    ecx, ecx
        jle     .done
.loop:
        fld     dword [eax]
        fadd    dword [esp]
        faddp   st1, st0                ; tmp0 m1
        fld     st0
        fmul    dword [esp+4]
        fstp    dword [ebx]
        fmul    dword [esp+8]           ; m0 m1
        fxch    st1
        fld     dword [edx]
        fadd    dword [esp]
        faddp   st1, st0                ; tmp1 m0
        fld     st0
        fmul    dword [esp+4]
        fstp    dword [ebx+4]
        fmul    dword [esp+8]           ; m1 m0
        fxch    st1
        add     eax, 4
        add     edx, 4
        add     ebx, 8
        dec     ecx
        jnz     .loop
.done:
        fstp    dword [esi]
        fstp    dword [esi+4]
        add     esp, 12
        ret

; void deemphasis16_stereo_x87(const float *x0 [eax], const float *x1 [edx], short *pcm [ebx],
;                              int N [ecx], float *mem [esi], const float *coef0 [edi])
;
; deemphasis_stereo_x87() straight to 16 bits, as libopus's fixed-point decoder does it:
; pcm[2j + c] = tmp saturated (CELT's float signal is already at 16-bit scale), with no soft
; clip. tmp + 1.5 * 2^23 lies in [2^23, 2^24), where a float's ulp is 1, for |tmp| < 2^22, so
; the stored sum's pattern less 4B400000h is tmp rounded to nearest even; outside that range
; the pattern saturates as in celt_float2int16_x87. VERY_SMALL isn't added: the states stay
; on the stack at full precision, where it changes nothing, and denormals can only appear
; after over a second of digital silence, and then briefly.
global deemphasis16_stereo_x87_
deemphasis16_stereo_x87_:
        push    ebp
        push    dword [edi]             ; [esp+8]: coef0
        push    dword 0x4B400000        ; [esp+4]: 1.5 * 2^23
        push    eax                     ; [esp]: where the sum is stored
        fld     dword [esi+4]
        fld     dword [esi]             ; m0 m1
        test    ecx, ecx
        jle     .done
.loop:
        fld     dword [eax]
        faddp   st1, st0                ; tmp0 m1
        fld     st0
        fadd    dword [esp+4]
        fstp    dword [esp]
        fmul    dword [esp+8]           ; m0 m1
        mov     ebp, [esp]
        test    ebp, ebp
        js      .lo0
        sub     ebp, 0x4B400000
        cmp     ebp, 32767
        jg      .hi0
        cmp     ebp, -32768
        jl      .lo0
.st0:   mov     [ebx], bp
        fxch    st1
        fld     dword [edx]
        faddp   st1, st0                ; tmp1 m0
        fld     st0
        fadd    dword [esp+4]
        fstp    dword [esp]
        fmul    dword [esp+8]           ; m1 m0
        fxch    st1
        mov     ebp, [esp]
        test    ebp, ebp
        js      .lo1
        sub     ebp, 0x4B400000
        cmp     ebp, 32767
        jg      .hi1
        cmp     ebp, -32768
        jl      .lo1
.st1:   mov     [ebx+2], bp
        add     eax, 4
        add     edx, 4
        add     ebx, 4
        dec     ecx
        jnz     .loop
.done:
        fstp    dword [esi]
        fstp    dword [esi+4]
        add     esp, 12
        pop     ebp
        ret
.hi0:   mov     ebp, 32767
        jmp     .st0
.lo0:   mov     ebp, -32768
        jmp     .st0
.hi1:   mov     ebp, 32767
        jmp     .st1
.lo1:   mov     ebp, -32768
        jmp     .st1
