/*
 * harness.h — SameBoy-backed test harness for waves.gb
 *
 * The harness loads waves.gb into a SameBoy emulator instance and
 * exposes the three test-observable surfaces:
 *
 *   1. Link port  — queue bytes to send as the MCU; receive bytes the
 *                   GB sends back.
 *   2. Audio      — drain buffered PCM samples (stereo int16).
 *   3. Screen     — read the 160×144 RGBA framebuffer or save a PPM.
 *
 * One harness = one GB instance running waves.gb.  Not thread-safe.
 */
#ifndef WAVES_HARNESS_H
#define WAVES_HARNESS_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* GB_sample_t is { int16_t left, right; } from <sameboy/gb.h> */
#include <sameboy/gb.h>

/* ---------------------------------------------------------------------- */
/* Harness object                                                           */
/* ---------------------------------------------------------------------- */

struct harness;

/**
 * Allocate and initialise a harness.
 *
 * rom_path is the path to waves.gb (must exist).  boot_rom_path is the
 * path to a DMG boot ROM image, or NULL to use a minimal built-in stub
 * that finishes the boot ROM sequence so interrupt vectors are correctly
 * mapped to the ROM.
 *
 * Returns NULL on failure (error printed to stderr).
 */
struct harness *harness_new(const char *rom_path, const char *boot_rom_path);

/**
 * Destroy a harness and release all resources.
 * Safe to call with NULL.
 */
void harness_free(struct harness *h);

/* ---------------------------------------------------------------------- */
/* Emulation control                                                        */
/* ---------------------------------------------------------------------- */

/**
 * Advance the emulator by exactly n vblank frames.
 * Each frame is roughly 16.7 ms of Game Boy time (~59.7 fps).
 */
void harness_run_frames(struct harness *h, int n);

/* ---------------------------------------------------------------------- */
/* Link port (serial) — MCU side                                            */
/* ---------------------------------------------------------------------- */

enum { HARNESS_SERIAL_QUEUE_LEN = 256 };

/**
 * Add one byte to the outgoing (MCU→GB) queue.
 *
 * The byte will be clocked into the GB one bit at a time as the GB's
 * serial hardware initiates transfers.  The queue holds up to
 * HARNESS_SERIAL_QUEUE_LEN bytes; enqueueing beyond that is silently
 * dropped (test code should not overflow it).
 */
void harness_serial_enqueue(struct harness *h, uint8_t byte);

/**
 * Pop one byte received from the GB.
 * Returns true and writes *out on success; returns false if the queue
 * is empty.
 */
bool harness_serial_dequeue(struct harness *h, uint8_t *out);

/* ---------------------------------------------------------------------- */
/* Screen capture                                                           */
/* ---------------------------------------------------------------------- */

/* Native GB screen dimensions */
enum { HARNESS_SCREEN_W = 160, HARNESS_SCREEN_H = 144 };

/**
 * Pointer to the latest completed frame.
 *
 * Layout: HARNESS_SCREEN_W * HARNESS_SCREEN_H uint32_t pixels, row-major,
 * top-left first.  Each pixel is 0xFFRRGGBB (alpha always 0xFF).
 * Valid until the next call to harness_run_frames().
 */
const uint32_t *harness_get_framebuffer(const struct harness *h);

/**
 * Write the current framebuffer to a plain-text PPM file (P3 format).
 * Useful for manual inspection during test development.
 * Returns 0 on success, -1 on I/O error.
 */
int harness_save_ppm(const struct harness *h, const char *path);

/* ---------------------------------------------------------------------- */
/* Audio capture                                                            */
/* ---------------------------------------------------------------------- */

static const int HARNESS_SAMPLE_RATE = 44100;
enum { HARNESS_AUDIO_BUF_LEN = 8192 }; /* ring buffer capacity in samples */

/**
 * Copy up to max_samples audio samples from the internal ring buffer
 * into buf.
 *
 * Returns the number of samples actually copied.  Drained samples are
 * removed from the buffer.  Sample rate is fixed at HARNESS_SAMPLE_RATE;
 * each GB_sample_t holds one stereo pair of signed 16-bit PCM values.
 */
size_t harness_drain_audio(struct harness *h, GB_sample_t *buf,
			   size_t max_samples);

/**
 * Number of samples currently in the buffer.
 */
size_t harness_audio_available(const struct harness *h);

#endif /* WAVES_HARNESS_H */
