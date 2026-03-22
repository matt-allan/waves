/*
 * emulator.h — SameBoy-backed emulator for waves.gb
 *
 * The emulator loads waves.gb into a SameBoy instance and
 * exposes the three observable surfaces:
 *
 *   1. Link port  — queue bytes to send as the MCU; receive bytes the
 *                   GB sends back.
 *   2. Audio      — drain buffered PCM samples (stereo int16).
 *   3. Screen     — read the 160×144 RGBA framebuffer or save a PPM.
 *
 * One emulator = one GB instance running waves.gb.  Not thread-safe.
 */
#ifndef WAVES_EMULATOR_H
#define WAVES_EMULATOR_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* GB_sample_t is { int16_t left, right; } from <sameboy/gb.h> */
#include <sameboy/gb.h>

/* ---------------------------------------------------------------------- */
/* Emulator object                                                           */
/* ---------------------------------------------------------------------- */

struct emulator;

/**
 * Allocate and initialise a emulator.
 *
 * rom_path is the path to waves.gb (must exist).  boot_rom_path is the
 * path to a DMG boot ROM image, or NULL to use a minimal built-in stub
 * that finishes the boot ROM sequence so interrupt vectors are correctly
 * mapped to the ROM.
 *
 * Returns NULL on failure (error printed to stderr).
 */
struct emulator *emulator_new(const char *rom_path, const char *boot_rom_path);

/**
 * Destroy a emulator and release all resources.
 * Safe to call with NULL.
 */
void emulator_free(struct emulator *h);

/* ---------------------------------------------------------------------- */
/* Emulation control                                                        */
/* ---------------------------------------------------------------------- */

/**
 * Advance the emulator by exactly n vblank frames.
 * Each frame is roughly 16.7 ms of Game Boy time (~59.7 fps).
 */
void emulator_run_frames(struct emulator *h, int n);

/* ---------------------------------------------------------------------- */
/* Link port (serial) — MCU side                                            */
/* ---------------------------------------------------------------------- */

enum { EMULATOR_SERIAL_QUEUE_LEN = 256 };

/**
 * Add one byte to the outgoing (MCU→GB) queue.
 *
 * The byte will be clocked into the GB one bit at a time as the GB's
 * serial hardware initiates transfers.  The queue holds up to
 * EMULATOR_SERIAL_QUEUE_LEN bytes; enqueueing beyond that is silently
 * dropped (test code should not overflow it).
 */
void emulator_serial_enqueue(struct emulator *h, uint8_t byte);

/**
 * Pop one byte received from the GB.
 * Returns true and writes *out on success; returns false if the queue
 * is empty.
 */
bool emulator_serial_dequeue(struct emulator *h, uint8_t *out);

/* ---------------------------------------------------------------------- */
/* Screen capture                                                           */
/* ---------------------------------------------------------------------- */

/* Native GB screen dimensions */
enum { EMULATOR_SCREEN_W = 160, EMULATOR_SCREEN_H = 144 };

/**
 * Pointer to the latest completed frame.
 *
 * Layout: EMULATOR_SCREEN_W * EMULATOR_SCREEN_H uint32_t pixels, row-major,
 * top-left first.  Each pixel is 0xFFRRGGBB (alpha always 0xFF).
 * Valid until the next call to emulator_run_frames().
 */
const uint32_t *emulator_get_framebuffer(const struct emulator *h);

/**
 * Write the current framebuffer to a plain-text PPM file (P3 format).
 * Useful for manual inspection during test development.
 * Returns 0 on success, -1 on I/O error.
 */
int emulator_save_ppm(const struct emulator *h, const char *path);

/* ---------------------------------------------------------------------- */
/* Audio capture                                                            */
/* ---------------------------------------------------------------------- */

static const int EMULATOR_SAMPLE_RATE = 44100;
enum { EMULATOR_AUDIO_BUF_LEN = 8192 }; /* ring buffer capacity in samples */

/**
 * Copy up to max_samples audio samples from the internal ring buffer
 * into buf.
 *
 * Returns the number of samples actually copied.  Drained samples are
 * removed from the buffer.  Sample rate is fixed at EMULATOR_SAMPLE_RATE;
 * each GB_sample_t holds one stereo pair of signed 16-bit PCM values.
 */
size_t emulator_drain_audio(struct emulator *h, GB_sample_t *buf,
			   size_t max_samples);

/**
 * Number of samples currently in the buffer.
 */
size_t emulator_audio_available(const struct emulator *h);

#endif /* WAVES_EMULATOR_H */
