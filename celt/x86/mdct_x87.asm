; SPDX-License-Identifier: BSD-3-Clause
; clt_mdct_backward_c()'s three loops (celt/mdct.c), float build, for the 486's x87, with
; OpenWatcom's register calling convention: each takes a pointer to its parameters (struct
; mdct_x87_args in float_x87.h) in EAX. Each product is formed from memory operands (FMUL m32,
; 11 clocks, against 16 for FMUL st(i)) and stored once, as an output; OpenWatcom copies every
; float through an integer register into a stack temporary first.

bits 32

segment _TEXT public align=16 use32 class=CODE

; struct mdct_x87_args: the field offsets.
%define A_IN1   0       ; pre: xp1 / post: yp0 / mirror: xp1
%define A_IN2   4       ; pre: xp2 / post: yp1 / mirror: yp1
%define A_OUT   8       ; pre: yp
%define A_T     12      ; trig / mirror: window
%define A_REV   16      ; pre: bitrev
%define A_N     20      ; pre: N4, post: N4, mirror: overlap
%define A_STEP  24      ; pre: 2 * stride * 4, bytes

; Pre-rotation: for i < N4, rev = bitrev[i]:
;   yp[2 rev + 1] = x2 t[i] + x1 t[N4 + i], yp[2 rev] = x1 t[i] - x2 t[N4 + i],
; x1 = *xp1, x2 = *xp2, xp1 += 2 stride, xp2 -= 2 stride.
global mdct_prerot_x87_
mdct_prerot_x87_:
        push    ebx
        push    ecx
        push    edx
        push    esi
        push    edi
        push    ebp
        mov     ecx, [eax+A_N]
        test    ecx, ecx
        jle     .ret
        push    ecx                     ; [esp]: iterations left
        mov     edi, [eax+A_T]          ; t + i
        mov     ebp, ecx
        shl     ebp, 2                  ; N4 * 4: [edi+ebp] is t[N4 + i]
        mov     esi, [eax+A_REV]
        mov     ebx, [eax+A_OUT]
        mov     edx, [eax+A_IN2]
        mov     ecx, [eax+A_STEP]
        mov     eax, [eax+A_IN1]
.loop:
        fld     dword [edx]
        fmul    dword [edi]
        fld     dword [eax]
        fmul    dword [edi+ebp]
        faddp   st1, st0                ; yr
        fld     dword [eax]
        fmul    dword [edi]
        fld     dword [edx]
        fmul    dword [edi+ebp]
        fsubp   st1, st0                ; yi yr
        push    eax
        movsx   eax, word [esi]
        fstp    dword [ebx+eax*8]
        fstp    dword [ebx+eax*8+4]
        pop     eax
        add     esi, 2
        add     edi, 4
        add     eax, ecx
        sub     edx, ecx
        dec     dword [esp]
        jnz     .loop
        pop     ecx
.ret:
        pop     ebp
        pop     edi
        pop     esi
        pop     edx
        pop     ecx
        pop     ebx
        ret

; Post-rotation, from both ends at once: for i < (N4 + 1) / 2, with t0 = t[i], t1 = t[N4 + i],
; t2 = t[N4 - 1 - i], t3 = t[N2 - 1 - i] = t[N4 + (N4 - 1 - i)]:
;   yp0[0] = yp0[1] t0 + yp0[0] t1,  yp1[1] = yp0[1] t1 - yp0[0] t0,
;   yp1[0] = yp1[1] t2 + yp1[0] t3,  yp0[1] = yp1[1] t3 - yp1[0] t2,
; all four loaded before any is stored; yp0 += 2, yp1 -= 2.
global mdct_postrot_x87_
mdct_postrot_x87_:
        push    ebx
        push    ecx
        push    edx
        push    esi
        push    edi
        push    ebp
        mov     ecx, [eax+A_N]
        mov     ebp, ecx
        shl     ebp, 2                  ; N4 * 4
        mov     edi, [eax+A_T]
        lea     esi, [edi+ebp-4]        ; t + N4 - 1 - i
        inc     ecx
        sar     ecx, 1
        test    ecx, ecx
        jle     .ret
        mov     edx, [eax+A_IN2]        ; yp1
        mov     eax, [eax+A_IN1]        ; yp0
.loop:
        fld     dword [eax+4]
        fmul    dword [edi]
        fld     dword [eax]
        fmul    dword [edi+ebp]
        faddp   st1, st0                ; yr
        fld     dword [eax+4]
        fmul    dword [edi+ebp]
        fld     dword [eax]
        fmul    dword [edi]
        fsubp   st1, st0                ; yi yr
        fld     dword [edx+4]
        fmul    dword [esi]
        fld     dword [edx]
        fmul    dword [esi+ebp]
        faddp   st1, st0                ; yr2 yi yr
        fld     dword [edx+4]
        fmul    dword [esi+ebp]
        fld     dword [edx]
        fmul    dword [esi]
        fsubp   st1, st0                ; yi2 yr2 yi yr
        fstp    dword [eax+4]
        fstp    dword [edx]
        fstp    dword [edx+4]
        fstp    dword [eax]
        add     eax, 8
        sub     edx, 8
        add     edi, 4
        sub     esi, 4
        dec     ecx
        jnz     .loop
.ret:
        pop     ebp
        pop     edi
        pop     esi
        pop     edx
        pop     ecx
        pop     ebx
        ret

; The TDAC mirror: for i < overlap / 2, x1 = *xp1, x2 = *yp1:
;   *yp1++ = x2 wp2 - x1 wp1, *xp1-- = x2 wp1 + x1 wp2, wp1 = window + i,
;   wp2 = window + overlap - 1 - i.
global mdct_mirror_x87_
mdct_mirror_x87_:
        push    ebx
        push    ecx
        push    edx
        push    esi
        mov     ecx, [eax+A_N]
        mov     ebx, [eax+A_T]          ; wp1
        lea     esi, [ebx+ecx*4-4]      ; wp2
        sar     ecx, 1
        test    ecx, ecx
        jle     .ret
        mov     edx, [eax+A_IN2]        ; yp1
        mov     eax, [eax+A_IN1]        ; xp1
.loop:
        fld     dword [edx]
        fmul    dword [esi]
        fld     dword [eax]
        fmul    dword [ebx]
        fsubp   st1, st0                ; x2 wp2 - x1 wp1
        fld     dword [edx]
        fmul    dword [ebx]
        fld     dword [eax]
        fmul    dword [esi]
        faddp   st1, st0                ; x2 wp1 + x1 wp2
        fstp    dword [eax]
        fstp    dword [edx]
        add     edx, 4
        sub     eax, 4
        add     ebx, 4
        sub     esi, 4
        dec     ecx
        jnz     .loop
.ret:
        pop     esi
        pop     edx
        pop     ecx
        pop     ebx
        ret
