/*
 * test_basic.c — smoke tests for the waves.gb test harness
 *
 * Environment variables:
 *   WAVES_ROM       path to waves.gb  (default: ../waves.gb)
 *   SAMEBOY_BOOT_ROM  path to DMG boot ROM image (optional)
 *
 * Each test function prints "PASS" or "FAIL" and the overall exit code
 * is non-zero if any test failed.
 */
#include "harness.h"
#include "protocol.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ---------------------------------------------------------------------- */
/* Minimal test framework                                                   */
/* ---------------------------------------------------------------------- */

static int g_failures = 0;

#define EXPECT(cond, fmt, ...)                                          \
	do {                                                            \
		if (!(cond)) {                                          \
			fprintf(stderr, "  FAIL %s:%d: " fmt "\n",     \
			        __FILE__, __LINE__, ##__VA_ARGS__);     \
			g_failures++;                                   \
		}                                                       \
	} while (0)

static void print_result(const char *name, int failures_before)
{
	int passed = (g_failures == failures_before);
	printf("  %s %s\n", passed ? "PASS" : "FAIL", name);
}

/* ---------------------------------------------------------------------- */
/* Tests                                                                    */
/* ---------------------------------------------------------------------- */

/*
 * test_init — verify the harness initialises and tears down cleanly.
 */
static void test_init(const char *rom, const char *boot_rom)
{
	int before = g_failures;
	harness_t *h = harness_new(rom, boot_rom);
	EXPECT(h != NULL, "harness_new returned NULL");
	harness_free(h);
	print_result("test_init", before);
}

/*
 * test_run_frames — run 60 frames (~1 s GB time) without crashing.
 */
static void test_run_frames(const char *rom, const char *boot_rom)
{
	int before = g_failures;
	harness_t *h = harness_new(rom, boot_rom);
	if (!h) { g_failures++; print_result("test_run_frames", before); return; }

	harness_run_frames(h, 60);
	/* If we get here without crashing the emulator loop works */
	EXPECT(true, "should not reach here on crash");

	harness_free(h);
	print_result("test_run_frames", before);
}

/*
 * test_audio_output — confirm the APU produces samples after a few frames.
 * The test does not validate specific waveforms; just that samples flow.
 */
static void test_audio_output(const char *rom, const char *boot_rom)
{
	int before = g_failures;
	harness_t *h = harness_new(rom, boot_rom);
	if (!h) { g_failures++; print_result("test_audio_output", before); return; }

	harness_run_frames(h, 10);

	size_t available = harness_audio_available(h);
	EXPECT(available > 0, "expected audio samples after 10 frames, got 0");

	GB_sample_t buf[HARNESS_AUDIO_BUF_LEN];
	size_t drained = harness_drain_audio(h, buf, HARNESS_AUDIO_BUF_LEN);
	EXPECT(drained == available,
	       "drain returned %zu, expected %zu", drained, available);
	EXPECT(harness_audio_available(h) == 0,
	       "buffer should be empty after drain");

	/*
	 * Rough sanity: at 44100 Hz, 10 frames at 59.7 fps ~= 7390 samples.
	 * Allow a wide margin since the emulator may not run at exact speed.
	 */
	EXPECT(drained > 1000,
	       "unexpectedly few samples: %zu (expected > 1000)", drained);

	harness_free(h);
	print_result("test_audio_output", before);
}

/*
 * test_screen_capture — verify we can save a PPM without errors.
 * The PPM is written to /tmp/waves_test_frame.ppm for manual inspection.
 */
static void test_screen_capture(const char *rom, const char *boot_rom)
{
	int before = g_failures;
	harness_t *h = harness_new(rom, boot_rom);
	if (!h) { g_failures++; print_result("test_screen_capture", before); return; }

	harness_run_frames(h, 5);

	const uint32_t *fb = harness_get_framebuffer(h);
	EXPECT(fb != NULL, "framebuffer pointer is NULL");

	int rc = harness_save_ppm(h, "/tmp/waves_test_frame.ppm");
	EXPECT(rc == 0, "harness_save_ppm failed (rc=%d)", rc);

	if (rc == 0)
		printf("    (screenshot saved to /tmp/waves_test_frame.ppm)\n");

	harness_free(h);
	print_result("test_screen_capture", before);
}

/*
 * test_serial_enqueue — enqueue a note-on and note-off, run frames so the
 * serial hardware has time to clock the bytes in, then check the TX queue
 * drains.  (The GB serial ISR is not yet implemented, so bytes may not be
 * consumed; this test just verifies the harness side doesn't crash or
 * assert.)
 */
static void test_serial_enqueue(const char *rom, const char *boot_rom)
{
	int before = g_failures;
	harness_t *h = harness_new(rom, boot_rom);
	if (!h) { g_failures++; print_result("test_serial_enqueue", before); return; }

	/*
	 * Middle C on PU1: period 1046 (from DESIGN.md).
	 * This matches the MIDDLE_C_PERIOD constant that will be added to
	 * waves.h once the serial ISR is implemented.
	 */
	harness_send_note_on(h, WAVES_CH_PU1, 1046);

	/* Run enough frames to clock 4 bytes through at ~8192 baud */
	harness_run_frames(h, 30);

	harness_send_note_off(h, WAVES_CH_PU1);
	harness_run_frames(h, 10);

	/* No crash = pass for now; extend assertions as protocol is implemented */
	EXPECT(true, "should not reach here on crash");

	harness_free(h);
	print_result("test_serial_enqueue", before);
}

/*
 * test_audio_after_note_on — queue a note-on and verify audio continues
 * flowing.  Once the GB serial ISR is wired up this test can be tightened
 * to assert non-silent output.
 */
static void test_audio_after_note_on(const char *rom, const char *boot_rom)
{
	int before = g_failures;
	harness_t *h = harness_new(rom, boot_rom);
	if (!h) { g_failures++; print_result("test_audio_after_note_on", before); return; }

	/* Let the ROM settle */
	harness_run_frames(h, 10);
	harness_drain_audio(h, NULL, 0); /* discard baseline */

	harness_send_note_on(h, WAVES_CH_PU1, 1046);
	harness_run_frames(h, 20);

	size_t samples = harness_audio_available(h);
	EXPECT(samples > 0,
	       "expected audio samples after note-on, got 0");

	harness_free(h);
	print_result("test_audio_after_note_on", before);
}

/* ---------------------------------------------------------------------- */
/* main                                                                     */
/* ---------------------------------------------------------------------- */

int main(void)
{
	const char *rom      = getenv("WAVES_ROM");
	const char *boot_rom = getenv("SAMEBOY_BOOT_ROM");

	if (!rom)
		rom = "../waves.gb";

	printf("waves test harness — basic smoke tests\n");
	printf("  ROM:      %s\n", rom);
	printf("  boot ROM: %s\n", boot_rom ? boot_rom : "(none)");
	printf("\n");

	test_init(rom, boot_rom);
	test_run_frames(rom, boot_rom);
	test_audio_output(rom, boot_rom);
	test_screen_capture(rom, boot_rom);
	test_serial_enqueue(rom, boot_rom);
	test_audio_after_note_on(rom, boot_rom);

	printf("\n%s (%d failure%s)\n",
	       g_failures == 0 ? "ALL PASS" : "FAILURES DETECTED",
	       g_failures, g_failures == 1 ? "" : "s");

	return g_failures > 0 ? 1 : 0;
}
