/*
 * harness.c — SameBoy-backed test harness for waves.gb
 */
#include "harness.h"

#include <sameboy/gb.h>

#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ---------------------------------------------------------------------- */
/* Internal state                                                           */
/* ---------------------------------------------------------------------- */

struct harness {
	GB_gameboy_t *gb;

	/* Video */
	uint32_t pixels[HARNESS_SCREEN_W * HARNESS_SCREEN_H];
	bool     frame_ready;

	/* Audio ring buffer */
	GB_sample_t audio_buf[HARNESS_AUDIO_BUF_LEN];
	size_t      audio_head;   /* next write position */
	size_t      audio_tail;   /* next read position  */

	/*
	 * Serial bit engine
	 *
	 * TX path (MCU → GB): bytes in tx_queue are clocked out MSB-first,
	 * one byte per 8-bit transfer, starting only at the MSB edge so that
	 * a late enqueue never splits a byte across two transfers.
	 *
	 * RX path (GB → MCU): bits arriving in bit_start are accumulated
	 * MSB-first; completed bytes are pushed to rx_queue.
	 */
	uint8_t tx_queue[HARNESS_SERIAL_QUEUE_LEN];
	int     tx_head;          /* next byte to read  */
	int     tx_tail;          /* next slot to write */
	uint8_t tx_byte;          /* byte currently being clocked out */
	int     tx_bit;           /* bit index 7..0; -1 = idle */
	int     tx_xfer;          /* transfer position 7..0; 7 = MSB/start  */

	uint8_t rx_queue[HARNESS_SERIAL_QUEUE_LEN];
	int     rx_head;
	int     rx_tail;
	uint8_t rx_byte;          /* byte being assembled from incoming bits */
	int     rx_bit;           /* how many bits received so far (0..7) */
};

/* ---------------------------------------------------------------------- */
/* Helpers: circular queue arithmetic                                       */
/* ---------------------------------------------------------------------- */

static inline int queue_used(int head, int tail, int cap)
{
	return (tail - head + cap) % cap;
}

static inline int queue_free(int head, int tail, int cap)
{
	return cap - 1 - queue_used(head, tail, cap);
}

/*
 * Minimal DMG boot ROM stub — all NOPs except for the last four bytes
 * which write 1 to 0xFF50 (disabling the boot ROM mapping) and let the
 * CPU fall through to address 0x0100 (game entry point).
 *
 *   0x00FC: LD A, 1       (3E 01)
 *   0x00FE: LDH (0x50), A (E0 50)
 */
static const uint8_t boot_rom_stub[256] = {
	[0xFC] = 0x3E, [0xFD] = 0x01, /* LD A, 1          */
	[0xFE] = 0xE0, [0xFF] = 0x50, /* LDH (0x50), A    */
};

/* ---------------------------------------------------------------------- */
/* SameBoy callbacks                                                        */
/* ---------------------------------------------------------------------- */

static uint32_t cb_rgb_encode(GB_gameboy_t *gb, uint8_t r, uint8_t g, uint8_t b)
{
	(void)gb;
	return 0xFF000000u | ((uint32_t)r << 16) | ((uint32_t)g << 8) | b;
}

static void cb_vblank(GB_gameboy_t *gb, GB_vblank_type_t type)
{
	(void)type;
	struct harness *h = GB_get_user_data(gb);
	h->frame_ready = true;
}

static void cb_log(GB_gameboy_t *gb, const char *str, GB_log_attributes_t attrs)
{
	(void)gb;
	(void)attrs;
	fputs(str, stderr);
}

static void cb_audio_sample(GB_gameboy_t *gb, GB_sample_t *sample)
{
	struct harness *h = GB_get_user_data(gb);

	size_t next = (h->audio_head + 1) % HARNESS_AUDIO_BUF_LEN;
	if (next == h->audio_tail) {
		/* Buffer full — drop oldest sample to make room */
		h->audio_tail = (h->audio_tail + 1) % HARNESS_AUDIO_BUF_LEN;
	}
	h->audio_buf[h->audio_head] = *sample;
	h->audio_head = next;
}

/*
 * bit_start_callback — called when the GB begins clocking out a bit.
 * bit_to_send is the bit the GB is driving onto the link cable.
 * We accumulate it into rx_byte (MSB first).
 */
static void cb_serial_bit_start(GB_gameboy_t *gb, bool bit_to_send)
{
	struct harness *h = GB_get_user_data(gb);

	/* Accumulate bit from GB (MSB first: bit 7 arrives first) */
	h->rx_byte = (uint8_t)((h->rx_byte << 1) | (bit_to_send ? 1 : 0));
	h->rx_bit++;

	if (h->rx_bit == 8) {
		/* Full byte received — push to rx_queue if space available */
		int next = (h->rx_tail + 1) % HARNESS_SERIAL_QUEUE_LEN;
		if (next != h->rx_head) {
			h->rx_queue[h->rx_tail] = h->rx_byte;
			h->rx_tail = next;
		}
		h->rx_byte = 0;
		h->rx_bit  = 0;
	}
}

/*
 * bit_end_callback — called when the GB expects to latch the incoming bit.
 * Return the next bit from our TX queue (MSB first), or 1 (idle) if none.
 *
 * Bytes are loaded from the queue only at the start of a new 8-bit
 * transfer (tx_xfer == 7 == MSB position).  This prevents a byte that
 * is enqueued mid-transfer from being split across two transfers and
 * corrupting the receiver's state machine.
 */
static bool cb_serial_bit_end(GB_gameboy_t *gb)
{
	struct harness *h = GB_get_user_data(gb);

	/* Only load at the MSB edge of a new transfer so a byte enqueued
	 * mid-transfer is never split across two consecutive transfers. */
	if (h->tx_xfer == 7 && h->tx_bit < 0) {
		if (h->tx_head != h->tx_tail) {
			h->tx_byte = h->tx_queue[h->tx_head];
			h->tx_head = (h->tx_head + 1) % HARNESS_SERIAL_QUEUE_LEN;
			h->tx_bit  = 7; /* will return bit 7 this call */
		}
	}

	bool bit;
	if (h->tx_bit >= 0) {
		bit = (h->tx_byte >> h->tx_bit) & 1;
		h->tx_bit--;
	} else {
		bit = true; /* idle line high */
	}

	/* Advance the transfer position counter (wraps 0 → 7). */
	h->tx_xfer = (h->tx_xfer == 0) ? 7 : (h->tx_xfer - 1);

	return bit;
}

/* ---------------------------------------------------------------------- */
/* Lifecycle                                                                */
/* ---------------------------------------------------------------------- */

struct harness *harness_new(const char *rom_path, const char *boot_rom_path)
{
	struct harness *h = calloc(1, sizeof(*h));
	if (!h) {
		fprintf(stderr, "harness: out of memory\n");
		return NULL;
	}

	h->tx_bit  = -1; /* no byte in flight */
	h->tx_xfer = 7;  /* next bit_end call is the MSB of a new transfer */

	h->gb = GB_init(GB_alloc(), GB_MODEL_DMG_B);
	if (!h->gb) {
		fprintf(stderr, "harness: GB_init failed\n");
		free(h);
		return NULL;
	}

	GB_set_user_data(h->gb, h);
	GB_set_log_callback(h->gb, cb_log);

	/* Video */
	GB_set_pixels_output(h->gb, h->pixels);
	GB_set_rgb_encode_callback(h->gb, cb_rgb_encode);
	GB_set_vblank_callback(h->gb, cb_vblank);

	/* Audio */
	GB_set_sample_rate(h->gb, HARNESS_SAMPLE_RATE);
	GB_apu_set_sample_callback(h->gb, cb_audio_sample);

	/* Serial */
	GB_set_serial_transfer_bit_start_callback(h->gb, cb_serial_bit_start);
	GB_set_serial_transfer_bit_end_callback(h->gb, cb_serial_bit_end);

	/* Boot ROM: use provided image or the built-in stub (see boot_rom_stub). */
	if (boot_rom_path) {
		if (GB_load_boot_rom(h->gb, boot_rom_path) != 0) {
			fprintf(stderr, "harness: failed to load boot ROM: %s\n",
			        boot_rom_path);
			GB_dealloc(h->gb);
			free(h);
			return NULL;
		}
	} else {
		GB_load_boot_rom_from_buffer(h->gb, boot_rom_stub,
		                             sizeof(boot_rom_stub));
	}

	/* Game ROM */
	if (GB_load_rom(h->gb, rom_path) != 0) {
		fprintf(stderr, "harness: failed to load ROM: %s\n", rom_path);
		GB_dealloc(h->gb);
		free(h);
		return NULL;
	}

	return h;
}

void harness_free(struct harness *h)
{
	if (!h)
		return;
	GB_dealloc(h->gb);
	free(h);
}

/* ---------------------------------------------------------------------- */
/* Emulation control                                                        */
/* ---------------------------------------------------------------------- */

void harness_run_frames(struct harness *h, int n)
{
	for (int i = 0; i < n; i++) {
		h->frame_ready = false;
		while (!h->frame_ready)
			GB_run_frame(h->gb);
	}
}

/* ---------------------------------------------------------------------- */
/* Link port                                                                */
/* ---------------------------------------------------------------------- */

void harness_serial_enqueue(struct harness *h, uint8_t byte)
{
	int next = (h->tx_tail + 1) % HARNESS_SERIAL_QUEUE_LEN;
	if (next == h->tx_head) {
		fprintf(stderr, "harness: TX queue full, byte 0x%02x dropped\n", byte);
		return;
	}
	h->tx_queue[h->tx_tail] = byte;
	h->tx_tail = next;
}

bool harness_serial_dequeue(struct harness *h, uint8_t *out)
{
	if (h->rx_head == h->rx_tail)
		return false;
	*out = h->rx_queue[h->rx_head];
	h->rx_head = (h->rx_head + 1) % HARNESS_SERIAL_QUEUE_LEN;
	return true;
}


/* ---------------------------------------------------------------------- */
/* Screen capture                                                           */
/* ---------------------------------------------------------------------- */

const uint32_t *harness_get_framebuffer(const struct harness *h)
{
	return h->pixels;
}

int harness_save_ppm(const struct harness *h, const char *path)
{
	FILE *f = fopen(path, "w");
	if (!f) {
		perror(path);
		return -1;
	}

	fprintf(f, "P3\n%d %d\n255\n", HARNESS_SCREEN_W, HARNESS_SCREEN_H);

	for (int y = 0; y < HARNESS_SCREEN_H; y++) {
		for (int x = 0; x < HARNESS_SCREEN_W; x++) {
			uint32_t px = h->pixels[y * HARNESS_SCREEN_W + x];
			uint8_t r = (px >> 16) & 0xFF;
			uint8_t g = (px >>  8) & 0xFF;
			uint8_t b = (px      ) & 0xFF;
			fprintf(f, "%d %d %d\n", r, g, b);
		}
	}

	fclose(f);
	return 0;
}

/* ---------------------------------------------------------------------- */
/* Audio capture                                                            */
/* ---------------------------------------------------------------------- */

size_t harness_drain_audio(struct harness *h, GB_sample_t *buf, size_t max_samples)
{
	size_t count = 0;
	while (count < max_samples && h->audio_tail != h->audio_head) {
		buf[count++] = h->audio_buf[h->audio_tail];
		h->audio_tail = (h->audio_tail + 1) % HARNESS_AUDIO_BUF_LEN;
	}
	return count;
}

size_t harness_audio_available(const struct harness *h)
{
	return (h->audio_head - h->audio_tail + HARNESS_AUDIO_BUF_LEN)
	       % HARNESS_AUDIO_BUF_LEN;
}
