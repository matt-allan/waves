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

typedef struct harness harness_t;

/*
 * harness_new — allocate and initialise a harness.
 *
 * rom_path      Path to waves.gb (must exist).
 * boot_rom_path Path to a DMG boot ROM image, or NULL to skip boot ROM
 *               (the emulator will start directly in the ROM entry point;
 *               some hardware-init code may behave differently).
 *
 * Returns NULL on failure (error printed to stderr).
 */
harness_t *harness_new(const char *rom_path, const char *boot_rom_path);

/*
 * harness_free — destroy a harness and release all resources.
 * Safe to call with NULL.
 */
void harness_free(harness_t *h);

/* ---------------------------------------------------------------------- */
/* Emulation control                                                        */
/* ---------------------------------------------------------------------- */

/*
 * harness_run_frames — advance the emulator by exactly n vblank frames.
 * Each frame is roughly 16.7 ms of Game Boy time (~59.7 fps).
 */
void harness_run_frames(harness_t *h, int n);

/* ---------------------------------------------------------------------- */
/* Link port (serial) — MCU side                                            */
/* ---------------------------------------------------------------------- */

/*
 * harness_serial_enqueue — add one byte to the outgoing (MCU→GB) queue.
 * The byte will be clocked into the GB one bit at a time as the GB's
 * serial hardware initiates transfers.
 *
 * The queue holds up to HARNESS_SERIAL_QUEUE_LEN bytes; enqueueing
 * beyond that is silently dropped (test code should not overflow it).
 */
#define HARNESS_SERIAL_QUEUE_LEN 256
void harness_serial_enqueue(harness_t *h, uint8_t byte);

/*
 * harness_serial_dequeue — pop one byte received from the GB.
 * Returns true and writes *out on success; returns false if the queue
 * is empty.
 */
bool harness_serial_dequeue(harness_t *h, uint8_t *out);

/*
 * Convenience wrappers that build and enqueue complete protocol messages.
 * See test/protocol.h for field semantics.
 */
void harness_send_note_on(harness_t *h, uint8_t channel, uint16_t period);
void harness_send_note_off(harness_t *h, uint8_t channel);
void harness_send_cc_update(harness_t *h, uint8_t channel,
                            uint8_t param, uint8_t value);

/* ---------------------------------------------------------------------- */
/* Screen capture                                                           */
/* ---------------------------------------------------------------------- */

/* Native GB screen dimensions */
#define HARNESS_SCREEN_W 160
#define HARNESS_SCREEN_H 144

/*
 * harness_get_framebuffer — pointer to the latest completed frame.
 * Layout: HARNESS_SCREEN_W * HARNESS_SCREEN_H uint32_t pixels, row-major,
 * top-left first.  Each pixel is 0xFFRRGGBB (alpha always 0xFF).
 * Valid until the next call to harness_run_frames().
 */
const uint32_t *harness_get_framebuffer(const harness_t *h);

/*
 * harness_save_ppm — write the current framebuffer to a plain-text PPM
 * file (P3 format).  Useful for manual inspection during test development.
 * Returns 0 on success, -1 on I/O error.
 */
int harness_save_ppm(const harness_t *h, const char *path);

/* ---------------------------------------------------------------------- */
/* Audio capture                                                            */
/* ---------------------------------------------------------------------- */

/*
 * harness_drain_audio — copy up to max_samples audio samples from the
 * internal ring buffer into buf.
 *
 * Returns the number of samples actually copied.  Drained samples are
 * removed from the buffer.
 *
 * Sample rate is fixed at HARNESS_SAMPLE_RATE.  Each GB_sample_t holds
 * one stereo pair of signed 16-bit PCM values.
 */
#define HARNESS_SAMPLE_RATE 44100
#define HARNESS_AUDIO_BUF_LEN 8192   /* ring buffer capacity in samples */

size_t harness_drain_audio(harness_t *h, GB_sample_t *buf, size_t max_samples);

/*
 * harness_audio_available — number of samples currently in the buffer.
 */
size_t harness_audio_available(const harness_t *h);

#endif /* WAVES_HARNESS_H */
