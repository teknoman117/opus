/* SPDX-License-Identifier: MIT */
/*
 * The CELT decoder's entry points for a SILK-only OPUSDOS: linked ahead of
 * libopus, they keep its CELT code and tables (some 70 KB) out of the
 * executable, which a 512 KB board without extended memory needs.
 *
 * opus_decode() only reaches CELT's decoding for CELT and hybrid packets,
 * and for the redundancy and transition frames around them; for SILK-only
 * packets it just sets CELT up and makes ctl calls, which these accept, so
 * a SILK stream decodes bit-exact. A CELT or hybrid packet gets
 * OPUS_UNIMPLEMENTED rather than wrong audio.
 */
#include <stdarg.h>
#include <string.h>
#include "config.h"
#include "celt.h"
#include "modes.h"

/* Only its window is read, for the fades around redundancy frames, which
   SILK-only streams don't have. */
static const CELTMode stub_mode;

int
celt_decoder_get_size(int channels)
{
    (void) channels;
    return 16;
}

int
celt_decoder_init(CELTDecoder *st, opus_int32 sampling_rate, int channels)
{
    (void) st;
    (void) sampling_rate;
    (void) channels;
    return OPUS_OK;
}

int
celt_decode_with_ec_dred(CELTDecoder *OPUS_RESTRICT st, const unsigned char *data, int len,
                         opus_res *OPUS_RESTRICT pcm, int frame_size, ec_dec *dec, int accum
#ifdef ENABLE_DEEP_PLC
                         , LPCNetPLCState *lpcnet
#endif
                         ARG_QEXT(const unsigned char *qext_payload) ARG_QEXT(int qext_payload_len))
{
    (void) st;
    (void) data;
    (void) len;
    (void) pcm;
    (void) frame_size;
    (void) dec;
    (void) accum;
    return OPUS_UNIMPLEMENTED;
}

int
celt_decode_with_ec(OpusCustomDecoder *OPUS_RESTRICT st, const unsigned char *data, int len,
                    opus_res *OPUS_RESTRICT pcm, int frame_size, ec_dec *dec, int accum)
{
    (void) st;
    (void) data;
    (void) len;
    (void) pcm;
    (void) frame_size;
    (void) dec;
    (void) accum;
    return OPUS_UNIMPLEMENTED;
}

int
opus_custom_decoder_ctl(OpusCustomDecoder *OPUS_RESTRICT st, int request, ...)
{
    va_list ap;

    (void) st;
    va_start(ap, request);
    switch (request) {
        case CELT_GET_MODE_REQUEST:
            *va_arg(ap, const CELTMode **) = &stub_mode;
            break;
        case OPUS_GET_FINAL_RANGE_REQUEST:
            *va_arg(ap, opus_uint32 *) = 0;
            break;
        case OPUS_GET_PITCH_REQUEST:
        case OPUS_GET_PHASE_INVERSION_DISABLED_REQUEST:
            *va_arg(ap, opus_int32 *) = 0;
            break;
        default:
            /* The SET requests and OPUS_RESET_STATE. */
            break;
    }
    va_end(ap);
    return OPUS_OK;
}
