/* SPDX-License-Identifier: BSD-3-Clause */
/*
 * OPUSDOS - decode an Ogg Opus file with libopus's fixed-point decoder, and
 * time it.
 *
 * Usage: OPUSDOS file.opus [rate] [-o out.wav] [-s seconds] [-p]
 *   rate     the output rate: 8000, 12000, 16000, 24000 or 48000 (default 48000)
 *   -o       also write the decoded audio to a WAV file (after the timing)
 *   -s       decode only the first so many seconds
 *   -p       decode packet by packet into one frame's buffer, timing each
 *            packet with the PIT, and report the slowest packet too (DOS)
 *
 * The stream is taken to arrive in memory already, as from a DMA-capable
 * source: the whole file is read and split into its Opus packets before the
 * clock starts, and only opus_decode() is timed, into one output buffer.
 * A CRC-32 of the decoded samples, taken after the clock stops, lets a build
 * on another machine be checked against this one.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include "opus.h"
#include "config.h" /* GLOBAL_STACK_SIZE */

#define MAX_FRAME 5760 /* 120 ms at 48 kHz */

/*
   libopus's scratch memory (NONTHREADSAFE_PSEUDOSTACK): it allocates
   GLOBAL_STACK_SIZE bytes on first use unless global_stack is set, so this
   sets it to a block filled with a pattern, to see afterwards how much the
   decoder used.
 */
extern char *global_stack;
static char *scratch;

static void
scratch_init(void)
{
    scratch = (char *) malloc(GLOBAL_STACK_SIZE);
    if (scratch == NULL) {
        fprintf(stderr, "out of memory for libopus's %ld bytes of scratch\n", (long) GLOBAL_STACK_SIZE);
        exit(1);
    }
    memset(scratch, 0xa5, GLOBAL_STACK_SIZE);
    global_stack = scratch;
}

static void
scratch_report(void)
{
    long used = GLOBAL_STACK_SIZE;

    while ((used > 0) && ((unsigned char) scratch[used - 1] == 0xa5))
        used--;
    printf("  scratch: %ld of %ld bytes used\n", used, (long) GLOBAL_STACK_SIZE);
}

typedef struct {
    unsigned long off;
    unsigned int  len;
} packet_t;

static unsigned char *file_data;
static unsigned long  file_len;
static unsigned char *pkt_data; /* the packets, end to end */
static unsigned long  pkt_bytes;
static packet_t      *pkts;
static unsigned long  npkts;
static unsigned long  max_pkts;

static unsigned long
le32(const unsigned char *p)
{
    return p[0] | ((unsigned long) p[1] << 8) | ((unsigned long) p[2] << 16) | ((unsigned long) p[3] << 24);
}

static void
add_packet(unsigned long off, unsigned int len)
{
    if (npkts == max_pkts) {
        max_pkts = max_pkts ? max_pkts * 2 : 1024;
        pkts     = (packet_t *) realloc(pkts, max_pkts * sizeof(packet_t));
        if (pkts == NULL) {
            fprintf(stderr, "out of memory\n");
            exit(1);
        }
    }
    pkts[npkts].off = off;
    pkts[npkts].len = len;
    npkts++;
}

/* Splits the Ogg pages' segments back into packets, which may span pages. */
static int
demux(void)
{
    unsigned long pos = 0;
    unsigned long cur = 0; /* the start of the packet being gathered, in pkt_data */
    unsigned long have = 0;

    pkt_data = (unsigned char *) malloc(file_len);
    if (pkt_data == NULL)
        return -1;

    while (pos + 27 <= file_len) {
        unsigned int  nseg;
        unsigned long body;
        unsigned int  i;

        if (memcmp(file_data + pos, "OggS", 4) != 0)
            return -1;
        nseg = file_data[pos + 26];
        if (pos + 27 + nseg > file_len)
            return -1;
        body = pos + 27 + nseg;
        for (i = 0; i < nseg; i++) {
            unsigned int lace = file_data[pos + 27 + i];

            if (body + lace > file_len)
                return -1;
            memcpy(pkt_data + cur + have, file_data + body, lace);
            have += lace;
            body += lace;
            if (lace < 255) { /* the packet ends here */
                add_packet(cur, (unsigned int) have);
                cur += have;
                have = 0;
            }
        }
        pos = body;
    }
    pkt_bytes = cur;
    return 0;
}

static unsigned long crc_table[256];

static void
crc_init(void)
{
    unsigned long c;
    int           n, k;

    for (n = 0; n < 256; n++) {
        c = (unsigned long) n;
        for (k = 0; k < 8; k++)
            c = (c & 1) ? (0xedb88320UL ^ (c >> 1)) : (c >> 1);
        crc_table[n] = c;
    }
}

static unsigned long
crc32(unsigned long crc, const unsigned char *p, unsigned long n)
{
    crc = ~crc & 0xffffffffUL;
    while (n--)
        crc = crc_table[(crc ^ *p++) & 0xff] ^ (crc >> 8);
    return ~crc & 0xffffffffUL;
}

/*
   A timer finer than clock()'s 55 ms tick: the BIOS tick count with the
   8254's channel 0 count below it, at 1193182 Hz. Channel 0 is switched to
   mode 2 with the same divisor (65536), so it still interrupts 18.2 times a
   second but counts down by one, once per period, which mode 3 doesn't.
 */
#if defined(__WATCOMC__) && defined(__386__)
#include <conio.h>
#include <i86.h>
#define PIT_HZ 1193182.0

static volatile unsigned long *const bios_ticks = (volatile unsigned long *) 0x46c;

static void
pit_mode2(void)
{
    _disable();
    outp(0x43, 0x34); /* channel 0, low then high byte, mode 2, binary */
    outp(0x40, 0);
    outp(0x40, 0);
    _enable();
}

static void
pit_mode3(void)
{
    _disable();
    outp(0x43, 0x36); /* back to the BIOS's mode 3 */
    outp(0x40, 0);
    outp(0x40, 0);
    _enable();
}

/* Now, in PIT counts. */
static double
pit_now(void)
{
    unsigned long ticks;
    unsigned int  count, irr;
    unsigned long elapsed;

    _disable();
    ticks = *bios_ticks;
    outp(0x43, 0x00); /* latch channel 0 */
    count = inp(0x40);
    count |= inp(0x40) << 8;
    outp(0x20, 0x0a); /* the PIC's IRR: is the tick that wrapped the count still pending? */
    irr = inp(0x20);
    _enable();
    elapsed = 65536UL - (count ? count : 65536UL);
    if ((irr & 1) && (elapsed < 32768UL))
        ticks++;
    return (double) ticks * 65536.0 + (double) elapsed;
}

/* What's left once everything is allocated, as the DPMI host (PMODE/W or
   DOS/32A) sees it: the largest DOS block and the largest DPMI block. */
static void
mem_report(void)
{
    union REGS          r;
    struct SREGS        sr;
    static unsigned long info[12];

    memset(&r, 0, sizeof(r));
    r.w.ax = 0x0100; /* allocate DOS memory: too much, for the largest block */
    r.w.bx = 0xffff;
    int386(0x31, &r, &r);
    printf("  memory left: DOS %lu KB", ((unsigned long) r.w.bx * 16) / 1024);
    memset(&r, 0, sizeof(r));
    segread(&sr);
    r.w.ax  = 0x0500; /* get free memory information */
    r.x.edi = (unsigned int) info;
    int386x(0x31, &r, &r, &sr);
    printf(", DPMI %lu KB\n", info[0] / 1024);
}
#else
/* Elsewhere (the host build), clock() stands in for the PIT. */
static void mem_report(void) {}
#define PIT_HZ ((double) CLOCKS_PER_SEC)
static void pit_mode2(void) {}
static void pit_mode3(void) {}
static double pit_now(void) { return (double) clock(); }
#endif
#define HAVE_PIT_TIMER 1

static void
put_le16(FILE *f, unsigned int v)
{
    fputc(v & 0xff, f);
    fputc((v >> 8) & 0xff, f);
}

static void
put_le32(FILE *f, unsigned long v)
{
    put_le16(f, (unsigned int) (v & 0xffff));
    put_le16(f, (unsigned int) (v >> 16));
}

static void
wav_header(FILE *f, unsigned long rate, int channels, unsigned long data_bytes)
{
    fwrite("RIFF", 1, 4, f);
    put_le32(f, 36 + data_bytes);
    fwrite("WAVEfmt ", 1, 8, f);
    put_le32(f, 16);
    put_le16(f, 1);
    put_le16(f, channels);
    put_le32(f, rate);
    put_le32(f, rate * channels * 2);
    put_le16(f, channels * 2);
    put_le16(f, 16);
    fwrite("data", 1, 4, f);
    put_le32(f, data_bytes);
}

/*
   Decodes packets [first, end) into out, end to end, as a player's output
   buffer would take them; returns the samples per channel, or -1. Nothing
   else happens in the loop, which is what is timed.
 */
static long
decode_all(OpusDecoder *dec, unsigned long first, unsigned long end, int channels, opus_int16 *out, long cap)
{
    unsigned long i;
    long          pos = 0;

    for (i = first; i < end; i++) {
        int n;

        if (pos + MAX_FRAME > cap) {
            fprintf(stderr, "output buffer too small\n");
            return -1;
        }
        n = opus_decode(dec, pkt_data + pkts[i].off, (opus_int32) pkts[i].len, out + pos * channels, MAX_FRAME, 0);
        if (n < 0) {
            fprintf(stderr, "packet %lu: %s\n", i, opus_strerror(n));
            return -1;
        }
        pos += n;
    }
    return pos;
}

#ifdef HAVE_PIT_TIMER
/*
   The -p mode, for small boards: the file is read a page at a time, as a
   stream would come in, rather than all at once, and each packet goes to
   opus_decode() into one 120 ms buffer at the output rate, as a player
   feeding a DMA output buffer would.

   Only the opus_decode() calls are timed, each with the PIT; reading a page
   is timed apart, and the CRC of the samples after the pre-skip (the same
   CRC as the whole-file mode's) goes between the timings.
 */
typedef struct {
    FILE          *f;
    unsigned char  hdr[27 + 255];
    unsigned char *body;    /* the page's body */
    unsigned long  body_cap;
    unsigned int   nseg, seg;
    unsigned long  body_pos;
    unsigned char *pkt;     /* the packet being gathered, which may span pages */
    unsigned long  pkt_len, pkt_cap;
    double         read_t;  /* PIT counts spent reading pages */
} stream_t;

/* Reads the next page; returns 0, or -1 at the end or on an error. */
static int
stream_page(stream_t *s)
{
    unsigned long len = 0;
    unsigned int  i;
    double        t0  = pit_now();
    int           ret = -1;

    if ((fread(s->hdr, 1, 27, s->f) == 27) && !memcmp(s->hdr, "OggS", 4)) {
        s->nseg = s->hdr[26];
        if (fread(s->hdr + 27, 1, s->nseg, s->f) == s->nseg) {
            for (i = 0; i < s->nseg; i++)
                len += s->hdr[27 + i];
            if (len > s->body_cap) {
                s->body     = (unsigned char *) realloc(s->body, len);
                s->body_cap = len;
            }
            if ((s->body != NULL) && (fread(s->body, 1, len, s->f) == len)) {
                s->seg      = 0;
                s->body_pos = 0;
                ret         = 0;
            }
        }
    }
    s->read_t += pit_now() - t0;
    return ret;
}

/* The next packet in s->pkt / s->pkt_len; returns 0, or -1 at the end. */
static int
stream_packet(stream_t *s)
{
    s->pkt_len = 0;
    for (;;) {
        unsigned int lace;

        if (s->seg == s->nseg) {
            if (stream_page(s) < 0)
                return -1;
            continue;
        }
        lace = s->hdr[27 + s->seg++];
        if (s->pkt_len + lace > s->pkt_cap) {
            s->pkt_cap = s->pkt_len + lace + 1024;
            s->pkt     = (unsigned char *) realloc(s->pkt, s->pkt_cap);
            if (s->pkt == NULL)
                return -1;
        }
        memcpy(s->pkt + s->pkt_len, s->body + s->body_pos, lace);
        s->pkt_len += lace;
        s->body_pos += lace;
        if (lace < 255)
            return 0;
    }
}

static int
decode_stream(const char *in_name, long rate, double limit_s)
{
    stream_t      s;
    OpusDecoder  *dec;
    opus_int16   *frame;
    int           channels, err, max_frame;
    long          skip, samples = 0;
    double        decoded_s = 0.0; /* summed as the whole-file mode's -s does, to stop at the same packet */
    unsigned long npk = 0, worst_pkt = 0, crc = 0;
    unsigned long modes[3] = { 0, 0, 0 };
    double        total = 0.0, worst = 0.0, worst_ratio = 0.0, worst_ratio_t = 0.0;
    double        audio_s;

    memset(&s, 0, sizeof(s));
    s.f = fopen(in_name, "rb");
    if (s.f == NULL) {
        fprintf(stderr, "can't open %s\n", in_name);
        return 1;
    }
    pit_mode2();
    if ((stream_packet(&s) < 0) || (s.pkt_len < 19) || memcmp(s.pkt, "OpusHead", 8)) {
        pit_mode3();
        fprintf(stderr, "%s isn't an Ogg Opus file\n", in_name);
        return 1;
    }
    channels = s.pkt[9];
    skip     = (long) (s.pkt[10] | (s.pkt[11] << 8)) * rate / 48000;
    stream_packet(&s); /* OpusTags */

    max_frame = (int) (rate * 120 / 1000); /* 120 ms, Opus's longest packet */
    frame     = (opus_int16 *) malloc((size_t) max_frame * channels * sizeof(opus_int16));
    scratch_init();
    dec = opus_decoder_create((opus_int32) rate, channels, &err);
    if ((frame == NULL) || (err != OPUS_OK)) {
        pit_mode3();
        fprintf(stderr, "can't set up the decoder: %s\n", (frame == NULL) ? "out of memory" : opus_strerror(err));
        return 1;
    }
    printf("%s: %d channel(s), streamed packet by packet, timed with the PIT\n", in_name, channels);
    mem_report();
    fflush(stdout);
    crc_init();
    s.read_t = 0.0;

    /* -s counts whole packets' durations, pre-skip and all, as the whole-file mode does. */
    while (((limit_s <= 0.0) || (decoded_s < limit_s)) && (stream_packet(&s) == 0)) {
        double       t0, t, ratio;
        unsigned int cfg = s.pkt[0] >> 3;
        int          n;

        modes[(cfg < 12) ? 0 : (cfg < 16) ? 1 : 2]++;
        t0 = pit_now();
        n  = opus_decode(dec, s.pkt, (opus_int32) s.pkt_len, frame, max_frame, 0);
        t  = pit_now() - t0;
        if (n < 0) {
            pit_mode3();
            printf("  packet %lu: %s\n", npk, opus_strerror(n));
            return 1;
        }
        total += t;
        if (t > worst) {
            worst     = t;
            worst_pkt = npk;
        }
        /* Against the packet's own duration, which is the deadline a player has. */
        ratio = (t / PIT_HZ) / ((double) n / (double) rate);
        if (ratio > worst_ratio) {
            worst_ratio   = ratio;
            worst_ratio_t = t;
        }
        decoded_s += (double) n / (double) rate;
        if (skip >= n) {
            skip -= n;
        } else {
            crc = crc32(crc, (const unsigned char *) (frame + skip * channels), (unsigned long) (n - skip) * channels * 2);
            samples += n - skip;
            skip = 0;
        }
        npk++;
    }
    pit_mode3();
    fclose(s.f);

    audio_s = (double) samples / (double) rate;
    printf("  SILK %lu, hybrid %lu, CELT %lu packets\n", modes[0], modes[1], modes[2]);
    printf("  decoded %.2f s of audio at %ld Hz in %.2f s: %.1f%% of real time, CRC-32 %08lX\n",
           audio_s, rate, total / PIT_HZ, (audio_s > 0.0) ? 100.0 * (total / PIT_HZ) / audio_s : 0.0, crc);
    printf("  per packet: mean %.2f ms, slowest %.2f ms (packet %lu), worst %.1f%% of its duration (%.2f ms)\n",
           1000.0 * total / PIT_HZ / (double) (npk ? npk : 1), 1000.0 * worst / PIT_HZ, worst_pkt,
           100.0 * worst_ratio, 1000.0 * worst_ratio_t / PIT_HZ);
    printf("  reading the file: %.2f s, %.1f%% of real time\n", s.read_t / PIT_HZ,
           (audio_s > 0.0) ? 100.0 * (s.read_t / PIT_HZ) / audio_s : 0.0);
    scratch_report();
    opus_decoder_destroy(dec);
    return 0;
}
#endif

int
main(int argc, char **argv)
{
    const char   *in_name  = NULL;
    const char   *out_name = NULL;
    long          rate     = 48000;
    double        limit_s  = 0.0;
    FILE         *f;
    int           channels, err, i;
    unsigned int  preskip;
    unsigned long first, end, n;
    unsigned long modes[3] = { 0, 0, 0 };
    unsigned long bws[5]   = { 0, 0, 0, 0, 0 };
    OpusDecoder  *dec;
    clock_t       t0, t1;
    long          samples, cap, skip;
    opus_int16   *out;
    unsigned long crc = 0;
    double        secs, audio_s;
    int           per_packet = 0;

    for (i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "-p"))
            per_packet = 1;
        else if (!strcmp(argv[i], "-o") && (i + 1 < argc))
            out_name = argv[++i];
        else if (!strcmp(argv[i], "-s") && (i + 1 < argc))
            limit_s = atof(argv[++i]);
        else if (in_name == NULL)
            in_name = argv[i];
        else
            rate = atol(argv[i]);
    }
    if (in_name == NULL) {
        fprintf(stderr, "Usage: OPUSDOS file.opus [rate] [-o out.wav] [-s seconds] [-p]\n");
        return 1;
    }

    if (per_packet) {
#ifdef HAVE_PIT_TIMER
        if (out_name != NULL)
            fprintf(stderr, "-o is ignored with -p\n");
        return decode_stream(in_name, rate, limit_s);
#else
        fprintf(stderr, "-p needs the PIT timer of the DOS build\n");
        return 1;
#endif
    }

    f = fopen(in_name, "rb");
    if (f == NULL) {
        fprintf(stderr, "can't open %s\n", in_name);
        return 1;
    }
    fseek(f, 0, SEEK_END);
    file_len = (unsigned long) ftell(f);
    fseek(f, 0, SEEK_SET);
    file_data = (unsigned char *) malloc(file_len);
    if ((file_data == NULL) || (fread(file_data, 1, file_len, f) != file_len)) {
        fprintf(stderr, "can't read %s\n", in_name);
        return 1;
    }
    fclose(f);

    if ((demux() < 0) || (npkts < 3) || (pkts[0].len < 19) || memcmp(pkt_data + pkts[0].off, "OpusHead", 8)) {
        fprintf(stderr, "%s isn't an Ogg Opus file\n", in_name);
        return 1;
    }
    channels = pkt_data[pkts[0].off + 9];
    preskip  = pkt_data[pkts[0].off + 10] | (pkt_data[pkts[0].off + 11] << 8);
    first    = 2; /* after OpusHead and OpusTags */
    end      = npkts;

    /* What the packets are: their TOC bytes give the mode and bandwidth. */
    for (n = first; n < end; n++) {
        unsigned int cfg = pkt_data[pkts[n].off] >> 3;

        if (cfg < 12) {
            modes[0]++;
            bws[cfg / 4]++;
        } else if (cfg < 16) {
            modes[1]++;
            bws[(cfg < 14) ? 3 : 4]++;
        } else {
            modes[2]++;
            bws[(cfg < 20) ? 0 : (cfg < 24) ? 2 : (cfg < 28) ? 3 : 4]++;
        }
    }
    if (limit_s > 0.0) {
        /* Count packets by their duration until the limit. */
        double t = 0.0;

        for (n = first; (n < end) && (t < limit_s); n++)
            t += (double) opus_packet_get_nb_samples(pkt_data + pkts[n].off, (opus_int32) pkts[n].len, 48000) / 48000.0;
        end = n;
    }

    printf("%s: %d channel(s), %lu packets, pre-skip %u\n", in_name, channels, end - first, preskip);
    printf("  SILK %lu, hybrid %lu, CELT %lu; NB %lu MB %lu WB %lu SWB %lu FB %lu\n",
           modes[0], modes[1], modes[2], bws[0], bws[1], bws[2], bws[3], bws[4]);

    scratch_init();
    dec = opus_decoder_create((opus_int32) rate, channels, &err);
    if (err != OPUS_OK) {
        fprintf(stderr, "opus_decoder_create: %s\n", opus_strerror(err));
        return 1;
    }


    /* Room for every packet's samples at the output rate. */
    cap = MAX_FRAME;
    for (n = first; n < end; n++)
        cap += opus_packet_get_nb_samples(pkt_data + pkts[n].off, (opus_int32) pkts[n].len, (opus_int32) rate);
    out = (opus_int16 *) malloc((size_t) cap * channels * sizeof(opus_int16));
    if (out == NULL) {
        fprintf(stderr, "out of memory for %ld samples\n", cap);
        return 1;
    }

    /* For a sampling profiler: where the code is, against the link map's address of opus_decode. */
    printf("  decoding (opus_decode at %08lX)\n", (unsigned long) opus_decode);
    fflush(stdout);

    t0      = clock();
    samples = decode_all(dec, first, end, channels, out, cap);
    t1      = clock();
    if (samples < 0)
        return 1;

    /* The pre-skip, at the output rate, isn't audio. */
    skip = (long) preskip * rate / 48000;
    if (skip > samples)
        skip = samples;
    samples -= skip;
    crc_init();
    crc = crc32(0, (const unsigned char *) (out + skip * channels), (unsigned long) samples * channels * 2);

    secs    = (double) (t1 - t0) / CLOCKS_PER_SEC;
    audio_s = (double) samples / (double) rate;
    printf("  decoded %.2f s of audio at %ld Hz in %.2f s: %.1f%% of real time, CRC-32 %08lX\n",
           audio_s, rate, secs, (audio_s > 0.0) ? 100.0 * secs / audio_s : 0.0, crc);
    scratch_report();

    if (out_name != NULL) {
        FILE *w = fopen(out_name, "wb");

        if (w == NULL) {
            fprintf(stderr, "can't write %s\n", out_name);
            return 1;
        }
        wav_header(w, (unsigned long) rate, channels, (unsigned long) samples * channels * 2);
        fwrite(out + skip * channels, sizeof(opus_int16), (size_t) samples * channels, w);
        fclose(w);
        printf("  wrote %s\n", out_name);
    }

    opus_decoder_destroy(dec);
    return 0;
}
