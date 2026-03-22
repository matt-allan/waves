/*
 * test_basic.c — smoke tests for the waves.gb test emulator
 *
 * Environment variables:
 *   WAVES_ROM         path to waves.gb  (default: ../waves.gb)
 *   SAMEBOY_BOOT_ROM  path to DMG boot ROM image (optional)
 */
#include "emulator.h"
#include "protocol.h"

#include <assert.h>
#include <stdio.h>
#include <stdlib.h>

/* ---------------------------------------------------------------------- */
/* Tests                                                                    */
/* ---------------------------------------------------------------------- */

/* Verify the emulator initialises and tears down cleanly. */
static void test_init(const char *rom, const char *boot_rom)
{
	struct emulator *h = emulator_new(rom, boot_rom);
	assert(h != NULL);
	emulator_free(h);
}

/* Run 60 frames (~1 s GB time) without crashing. */
static void test_run_frames(const char *rom, const char *boot_rom)
{
	struct emulator *h = emulator_new(rom, boot_rom);
	assert(h != NULL);
	emulator_run_frames(h, 60);
	emulator_free(h);
}

/*
 * Confirm the APU produces samples after a few frames.
 * Does not validate specific waveforms; just that samples flow.
 */
static void test_audio_output(const char *rom, const char *boot_rom)
{
	struct emulator *h = emulator_new(rom, boot_rom);
	assert(h != NULL);

	emulator_run_frames(h, 10);

	size_t available = emulator_audio_available(h);
	assert(available > 0);

	GB_sample_t buf[EMULATOR_AUDIO_BUF_LEN];
	size_t drained = emulator_drain_audio(h, buf, EMULATOR_AUDIO_BUF_LEN);
	assert(drained == available);
	assert(emulator_audio_available(h) == 0);

	/*
	 * Rough sanity: at 44100 Hz, 10 frames at 59.7 fps ~= 7390 samples.
	 * Allow a wide margin since the emulator may not run at exact speed.
	 */
	assert(drained > 1000);

	emulator_free(h);
}

/* Verify we can save a PPM without errors. */
static void test_screen_capture(const char *rom, const char *boot_rom)
{
	struct emulator *h = emulator_new(rom, boot_rom);
	assert(h != NULL);

	emulator_run_frames(h, 5);

	assert(emulator_get_framebuffer(h) != NULL);

	assert(emulator_save_ppm(h, "/tmp/waves_test_frame.ppm") == 0);
	printf("    (screenshot saved to /tmp/waves_test_frame.ppm)\n");

	emulator_free(h);
}

/*
 * Send a NOTE_ON via the serial link and verify the APU produces non-silent
 * audio.  PU1 at period 1046 (~C5).
 */
static void test_note_on(const char *rom, const char *boot_rom)
{
	struct emulator *h = emulator_new(rom, boot_rom);
	assert(h != NULL);

	emulator_run_frames(h, 2);

	/* NOTE_ON: PU1, period = 1046 */
	emulator_serial_enqueue(h, proto_hdr(INSTR_PU1, MCU_NOTE_ON));
	emulator_serial_enqueue(h, 1046 >> 8);
	emulator_serial_enqueue(h, 1046 & 0xFF);

	emulator_run_frames(h, 30);

	GB_sample_t buf[EMULATOR_AUDIO_BUF_LEN];
	size_t n = emulator_drain_audio(h, buf, EMULATOR_AUDIO_BUF_LEN);
	assert(n > 0);

	bool non_silent = false;
	for (size_t i = 0; i < n; i++) {
		if (buf[i].left != 0 || buf[i].right != 0) {
			non_silent = true;
			break;
		}
	}
	assert(non_silent);

	emulator_free(h);
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

	printf("waves test emulator — basic smoke tests\n");
	printf("  ROM:      %s\n", rom);
	printf("  boot ROM: %s\n", boot_rom ? boot_rom : "(none)");
	printf("\n");

	test_init(rom, boot_rom);
	test_run_frames(rom, boot_rom);
	test_audio_output(rom, boot_rom);
	test_screen_capture(rom, boot_rom);
	test_note_on(rom, boot_rom);

	printf("ALL PASS\n");
	return 0;
}
