; SPDX-License-Identifier: BSD-3-Clause
; The kiss FFT's radix-3, -4 and -5 butterflies (celt/kiss_fft.c) for the 486's x87, float
; build, with OpenWatcom's register calling convention (declared in float_x87.h):
;
;   void kf_bfly<p>_x87(kiss_fft_cpx *Fout [eax], const kiss_twiddle_cpx *tw [edx],
;                       int fstride [ebx], int m [ecx], int N [esi], int mm [edi])
;
; as kf_bfly<p>(Fout, fstride, st, m, N, mm), with st->twiddles for tw. EBP is kept; the
; other registers and the FPU stack are the caller's to lose.
;
; The 486's FPU runs one instruction at a time, and an operand from memory costs no more than
; one from the stack (FADD m32 14 clocks, as FADD st(i); FMUL m32 11, FMUL st(i) 16; FLD m32
; 3, FLD st(i) 4), but storing does (FST m32 7). So the twiddled inputs, each used twice, are
; stored once to the frame and then used from there, and everything else stays on the stack
; until it's an output. The C, as OpenWatcom compiles it, stores and reloads every
; intermediate.

bits 32

segment _TEXT public align=16 use32 class=CODE

; S = a * w (complex), into [esp+%3] (r) and [esp+%3+4] (i).
%macro CMUL 3
        fld     dword [%1]
        fmul    dword [%2]
        fld     dword [%1+4]
        fmul    dword [%2+4]
        fsubp   st1, st0                ; ar*wr - ai*wi
        fld     dword [%1]
        fmul    dword [%2+4]
        fld     dword [%1+4]
        fmul    dword [%2]
        faddp   st1, st0                ; ar*wi + ai*wr
        fstp    dword [esp+%3+4]
        fstp    dword [esp+%3]
%endmacro

; The frame's loop state, common to the three.
%define FSB     24                      ; fstride * 8: one twiddle step, in bytes
%define MMB     28                      ; mm * 8: from one butterfly group to the next
%define NCNT    32                      ; groups left
%define BEG     36                      ; this group's Fout
%define MCNT    40                      ; m
%define UCNT    44                      ; butterflies left in this group

; ---------------------------------------------------------------------------------------
; Radix 4.
%define B4FRAME 48
global kf_bfly4_x87_
kf_bfly4_x87_:
        push    ebp
        test    esi, esi
        jle     .ret
        cmp     ecx, 1
        je      near .m1
        test    ecx, ecx
        jle     .ret
        sub     esp, B4FRAME
        shl     ebx, 3
        mov     [esp+FSB], ebx
        shl     edi, 3
        mov     [esp+MMB], edi
        mov     [esp+NCNT], esi
        mov     [esp+BEG], eax
        mov     [esp+MCNT], ecx
        shl     ecx, 3                  ; ecx: m * 8, from one quarter to the next
        mov     ebx, edx                ; ebx: the twiddles
.group:
        mov     eax, [esp+BEG]          ; eax: Fout[j]
        lea     edx, [eax+ecx*2]        ; edx: Fout[j + 2m]
        xor     esi, esi                ; esi: j * fstride * 8
        mov     ebp, [esp+MCNT]
        mov     [esp+UCNT], ebp
.bfly:
        lea     edi, [ebx+esi*2]        ; [edi+esi]: the third twiddle
        CMUL    eax+ecx, ebx+esi, 0     ; S0 = F1 * tw1
        CMUL    edx, ebx+esi*2, 8       ; S1 = F2 * tw2
        CMUL    edx+ecx, edi+esi, 16    ; S2 = F3 * tw3
        ; real parts: s5r = F0r - S1r, s4i = S0i - S2i; F1r = s5r + s4i, F3r = s5r - s4i
        fld     dword [eax]
        fsub    dword [esp+8]           ; s5r
        fld     dword [esp+4]
        fsub    dword [esp+20]          ; s4i s5r
        fld     st1
        fadd    st0, st1
        fstp    dword [eax+ecx]         ; F1r
        fsubp   st1, st0
        fstp    dword [edx+ecx]         ; F3r
        ; A = F0r + S1r, s3r = S0r + S2r; F2r = A - s3r, F0r = A + s3r
        fld     dword [eax]
        fadd    dword [esp+8]           ; A
        fld     dword [esp]
        fadd    dword [esp+16]          ; s3r A
        fld     st1
        fsub    st0, st1
        fstp    dword [edx]             ; F2r
        faddp   st1, st0
        fstp    dword [eax]             ; F0r
        ; imaginary: s5i = F0i - S1i, s4r = S0r - S2r; F1i = s5i - s4r, F3i = s5i + s4r
        fld     dword [eax+4]
        fsub    dword [esp+12]          ; s5i
        fld     dword [esp]
        fsub    dword [esp+16]          ; s4r s5i
        fld     st1
        fsub    st0, st1
        fstp    dword [eax+ecx+4]       ; F1i
        faddp   st1, st0
        fstp    dword [edx+ecx+4]       ; F3i
        fld     dword [eax+4]
        fadd    dword [esp+12]          ; Ai
        fld     dword [esp+4]
        fadd    dword [esp+20]          ; s3i Ai
        fld     st1
        fsub    st0, st1
        fstp    dword [edx+4]           ; F2i
        faddp   st1, st0
        fstp    dword [eax+4]           ; F0i
        add     eax, 8
        add     edx, 8
        add     esi, [esp+FSB]
        dec     dword [esp+UCNT]
        jnz     .bfly
        mov     eax, [esp+MMB]
        add     [esp+BEG], eax
        dec     dword [esp+NCNT]
        jnz     .group
        add     esp, B4FRAME
.ret:
        pop     ebp
        ret

; m == 1: the twiddles are all 1, and the four inputs are adjacent. Every input is loaded
; before the output that overwrites it is stored.
.m1:
        fld     dword [eax+8]
        fsub    dword [eax+24]          ; t1 = F1r - F3r
        fld     dword [eax+12]
        fsub    dword [eax+28]          ; t2 = F1i - F3i
        fld     dword [eax]
        fsub    dword [eax+16]          ; u1 = F0r - F2r
        fld     dword [eax+4]
        fsub    dword [eax+20]          ; u2 = F0i - F2i            u2 u1 t2 t1
        fld     dword [eax]
        fadd    dword [eax+16]          ; F0r + F2r
        fld     dword [eax+8]
        fadd    dword [eax+24]          ; F1r + F3r
        fld     st1
        fadd    st0, st1
        fstp    dword [eax]             ; F0r = (F0r + F2r) + (F1r + F3r)
        fsubp   st1, st0
        fstp    dword [eax+16]          ; F2r = (F0r + F2r) - (F1r + F3r)
        fld     dword [eax+4]
        fadd    dword [eax+20]
        fld     dword [eax+12]
        fadd    dword [eax+28]
        fld     st1
        fadd    st0, st1
        fstp    dword [eax+4]           ; F0i
        fsubp   st1, st0
        fstp    dword [eax+20]          ; F2i                       u2 u1 t2 t1
        fld     st1
        fadd    st0, st3
        fstp    dword [eax+8]           ; F1r = u1 + t2
        fxch    st1                     ; u1 u2 t2 t1
        fsubrp  st2, st0                ; u2 (u1 - t2) t1
        fxch    st1
        fstp    dword [eax+24]          ; F3r = u1 - t2             u2 t1
        fld     st0
        fsub    st0, st2
        fstp    dword [eax+12]          ; F1i = u2 - t1
        faddp   st1, st0
        fstp    dword [eax+28]          ; F3i = u2 + t1
        add     eax, 32
        dec     esi
        jnz     .m1
        pop     ebp
        ret

; ---------------------------------------------------------------------------------------
; Radix 3. epi3 = tw[fstride * m]; only its imaginary part is used.
%define B3E     16
%define B3HALF  20
%define B3FRAME 48
global kf_bfly3_x87_
kf_bfly3_x87_:
        push    ebp
        test    esi, esi
        jle     .ret
        test    ecx, ecx
        jle     .ret
        sub     esp, B3FRAME
        shl     ebx, 3
        mov     [esp+FSB], ebx
        shl     edi, 3
        mov     [esp+MMB], edi
        mov     [esp+NCNT], esi
        mov     [esp+BEG], eax
        mov     [esp+MCNT], ecx
        mov     ebp, ebx
        imul    ebp, ecx                ; fstride * m * 8
        mov     ebp, [edx+ebp+4]
        mov     [esp+B3E], ebp          ; epi3.i
        mov     dword [esp+B3HALF], 0x3F000000 ; 0.5
        shl     ecx, 3                  ; ecx: m * 8
        mov     ebx, edx
.group:
        mov     eax, [esp+BEG]
        xor     esi, esi
        mov     ebp, [esp+MCNT]
        mov     [esp+UCNT], ebp
.bfly:
        CMUL    eax+ecx, ebx+esi, 0     ; S1 = F1 * tw1
        CMUL    eax+ecx*2, ebx+esi*2, 8 ; S2 = F2 * tw2
        ; real parts: d = (S1i - S2i) * epi3.i, s3r = S1r + S2r, Fm = F0r - s3r / 2;
        ; F0r += s3r, F2r = Fm + d, F1r = Fm - d
        fld     dword [esp+4]
        fsub    dword [esp+12]
        fmul    dword [esp+B3E]         ; d
        fld     dword [esp]
        fadd    dword [esp+8]           ; s3r d
        fld     st0
        fmul    dword [esp+B3HALF]
        fsubr   dword [eax]             ; Fm s3r d
        fxch    st1
        fadd    dword [eax]
        fstp    dword [eax]             ; F0r                       Fm d
        fld     st0
        fadd    st0, st2
        fstp    dword [eax+ecx*2]       ; F2r = Fm + d
        fsubrp  st1, st0
        fstp    dword [eax+ecx]         ; F1r = Fm - d
        ; imaginary: d = (S1r - S2r) * epi3.i, s3i = S1i + S2i, Fm = F0i - s3i / 2;
        ; F0i += s3i, F2i = Fm - d, F1i = Fm + d
        fld     dword [esp]
        fsub    dword [esp+8]
        fmul    dword [esp+B3E]
        fld     dword [esp+4]
        fadd    dword [esp+12]
        fld     st0
        fmul    dword [esp+B3HALF]
        fsubr   dword [eax+4]           ; Fm s3i d
        fxch    st1
        fadd    dword [eax+4]
        fstp    dword [eax+4]           ; F0i                       Fm d
        fld     st0
        fsub    st0, st2
        fstp    dword [eax+ecx*2+4]     ; F2i = Fm - d
        faddp   st1, st0
        fstp    dword [eax+ecx+4]       ; F1i = Fm + d
        add     eax, 8
        add     esi, [esp+FSB]
        dec     dword [esp+UCNT]
        jnz     .bfly
        mov     eax, [esp+MMB]
        add     [esp+BEG], eax
        dec     dword [esp+NCNT]
        jnz     .group
        add     esp, B3FRAME
.ret:
        pop     ebp
        ret

; ---------------------------------------------------------------------------------------
; Radix 5. ya = tw[fstride * m], yb = tw[2 * fstride * m].
%define S1      0
%define S2      8
%define S3      48
%define S4      56
%define YAR     64
%define YAI     68
%define YBR     72
%define YBI     76
%define B5FRAME 80
global kf_bfly5_x87_
kf_bfly5_x87_:
        push    ebp
        test    esi, esi
        jle     .ret
        test    ecx, ecx
        jle     .ret
        sub     esp, B5FRAME
        shl     ebx, 3
        mov     [esp+FSB], ebx
        shl     edi, 3
        mov     [esp+MMB], edi
        mov     [esp+NCNT], esi
        mov     [esp+BEG], eax
        mov     [esp+MCNT], ecx
        mov     ebp, ebx
        imul    ebp, ecx                ; fstride * m * 8
        mov     esi, [edx+ebp]
        mov     [esp+YAR], esi
        mov     esi, [edx+ebp+4]
        mov     [esp+YAI], esi
        mov     esi, [edx+ebp*2]
        mov     [esp+YBR], esi
        mov     esi, [edx+ebp*2+4]
        mov     [esp+YBI], esi
        shl     ecx, 3                  ; ecx: m * 8
        mov     ebx, edx
.group:
        mov     eax, [esp+BEG]          ; eax: Fout0
        lea     edx, [eax+ecx*2]        ; edx: Fout2; Fout3 is [edx+ecx], Fout4 [eax+ecx*4]
        xor     esi, esi                ; esi: u * fstride * 8
        mov     ebp, [esp+MCNT]
        mov     [esp+UCNT], ebp
.bfly:
        lea     edi, [ebx+esi*2]        ; [edi+esi]: tw[3 u fstride]
        CMUL    eax+ecx, ebx+esi, S1
        CMUL    edx, ebx+esi*2, S2
        CMUL    edx+ecx, edi+esi, S3
        CMUL    eax+ecx*4, ebx+esi*4, S4
        ; s7 = S1 + S4, s10 = S1 - S4, s8 = S2 + S3, s9 = S2 - S3.
        ; Real parts: s6r = s10i ya.i + s9i yb.i, s12r = s9i ya.i - s10i yb.i,
        ; s5r = F0r + s7r ya.r + s8r yb.r, s11r = F0r + s7r yb.r + s8r ya.r;
        ; F1r = s5r - s6r, F4r = s5r + s6r, F2r = s11r + s12r, F3r = s11r - s12r,
        ; F0r += s7r + s8r.
        fld     dword [esp+S1]
        fadd    dword [esp+S4]          ; s7r
        fld     dword [esp+S2]
        fadd    dword [esp+S3]          ; s8r s7r
        fld     dword [esp+S2+4]
        fsub    dword [esp+S3+4]        ; s9i s8r s7r
        fld     dword [esp+S1+4]
        fsub    dword [esp+S4+4]        ; s10i s9i s8r s7r
        fld     st0
        fmul    dword [esp+YAI]
        fld     st2
        fmul    dword [esp+YBI]
        faddp   st1, st0                ; s6r s10i s9i s8r s7r
        fxch    st2                     ; s9i s10i s6r s8r s7r
        fmul    dword [esp+YAI]
        fxch    st1
        fmul    dword [esp+YBI]
        fsubp   st1, st0                ; s12r s6r s8r s7r
        fld     st3
        fmul    dword [esp+YAR]
        fld     st3
        fmul    dword [esp+YBR]
        faddp   st1, st0
        fadd    dword [eax]             ; s5r s12r s6r s8r s7r
        fld     st0
        fsub    st0, st3
        fstp    dword [eax+ecx]         ; F1r = s5r - s6r
        faddp   st2, st0                ; s12r (s5r + s6r) s8r s7r
        fxch    st1
        fstp    dword [eax+ecx*4]       ; F4r = s5r + s6r           s12r s8r s7r
        fld     st2
        fmul    dword [esp+YBR]
        fld     st2
        fmul    dword [esp+YAR]
        faddp   st1, st0
        fadd    dword [eax]             ; s11r s12r s8r s7r
        fld     st0
        fadd    st0, st2
        fstp    dword [edx]             ; F2r = s11r + s12r
        fsubrp  st1, st0
        fstp    dword [edx+ecx]         ; F3r = s11r - s12r         s8r s7r
        faddp   st1, st0
        fadd    dword [eax]
        fstp    dword [eax]             ; F0r += s7r + s8r
        ; Imaginary parts: P = s10r ya.i + s9r yb.i (s6i = -P), s12i = s10r yb.i - s9r ya.i,
        ; s5i = F0i + s7i ya.r + s8i yb.r, s11i = F0i + s7i yb.r + s8i ya.r;
        ; F1i = s5i + P, F4i = s5i - P, F2i = s11i + s12i, F3i = s11i - s12i,
        ; F0i += s7i + s8i.
        fld     dword [esp+S1+4]
        fadd    dword [esp+S4+4]        ; s7i
        fld     dword [esp+S2+4]
        fadd    dword [esp+S3+4]        ; s8i s7i
        fld     dword [esp+S2]
        fsub    dword [esp+S3]          ; s9r s8i s7i
        fld     dword [esp+S1]
        fsub    dword [esp+S4]          ; s10r s9r s8i s7i
        fld     st0
        fmul    dword [esp+YAI]
        fld     st2
        fmul    dword [esp+YBI]
        faddp   st1, st0                ; P s10r s9r s8i s7i
        fxch    st1
        fmul    dword [esp+YBI]         ; s10r yb.i, P, s9r ...
        fxch    st2
        fmul    dword [esp+YAI]         ; s9r ya.i, P, s10r yb.i ...
        fsubp   st2, st0                ; P s12i s8i s7i
        fld     st3
        fmul    dword [esp+YAR]
        fld     st3
        fmul    dword [esp+YBR]
        faddp   st1, st0
        fadd    dword [eax+4]           ; s5i P s12i s8i s7i
        fld     st0
        fadd    st0, st2
        fstp    dword [eax+ecx+4]       ; F1i = s5i + P
        fsubrp  st1, st0
        fstp    dword [eax+ecx*4+4]     ; F4i = s5i - P             s12i s8i s7i
        fld     st2
        fmul    dword [esp+YBR]
        fld     st2
        fmul    dword [esp+YAR]
        faddp   st1, st0
        fadd    dword [eax+4]           ; s11i s12i s8i s7i
        fld     st0
        fadd    st0, st2
        fstp    dword [edx+4]           ; F2i = s11i + s12i
        fsubrp  st1, st0
        fstp    dword [edx+ecx+4]       ; F3i = s11i - s12i         s8i s7i
        faddp   st1, st0
        fadd    dword [eax+4]
        fstp    dword [eax+4]           ; F0i += s7i + s8i
        add     eax, 8
        add     edx, 8
        add     esi, [esp+FSB]
        dec     dword [esp+UCNT]
        jnz     .bfly
        mov     eax, [esp+MMB]
        add     [esp+BEG], eax
        dec     dword [esp+NCNT]
        jnz     .group
        add     esp, B5FRAME
.ret:
        pop     ebp
        ret
