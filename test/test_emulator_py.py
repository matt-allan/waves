"""Python emulator integration tests — mirrors test/test_basic.c."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from emulator import Button, Emulator  # noqa: E402

ROM_PATH = os.environ.get("WAVES_ROM", "build/waves.gb")
LIB_PATH = os.environ.get("SAMEBOY_LIB", None)


class TestEmulator(unittest.TestCase):
    """Smoke tests matching the C test suite."""

    def test_init_and_close(self):
        with Emulator(ROM_PATH, lib_path=LIB_PATH) as emu:
            self.assertIsNotNone(emu)

    def test_run_frames(self):
        with Emulator(ROM_PATH, lib_path=LIB_PATH) as emu:
            emu.run_frames(60)

    def test_audio_output(self):
        with Emulator(ROM_PATH, lib_path=LIB_PATH) as emu:
            emu.run_frames(10)
            self.assertGreater(emu.audio_available(), 1000)
            samples = emu.drain_audio()
            self.assertGreater(len(samples), 1000)

    def test_screenshot(self):
        with Emulator(ROM_PATH, lib_path=LIB_PATH) as emu:
            emu.run_frames(5)
            data = emu.screenshot()
            self.assertEqual(len(data), 160 * 144 * 4)

    def test_screenshot_raw(self):
        with Emulator(ROM_PATH, lib_path=LIB_PATH) as emu:
            emu.run_frames(5)
            data = emu.screenshot_raw()
            self.assertEqual(len(data), 160 * 144 * 4)

    def test_save_screenshot_ppm(self):
        with Emulator(ROM_PATH, lib_path=LIB_PATH) as emu:
            emu.run_frames(5)
            with tempfile.NamedTemporaryFile(suffix=".ppm", delete=False) as f:
                path = f.name
            try:
                emu._save_ppm(path)
                self.assertGreater(os.path.getsize(path), 0)
            finally:
                os.unlink(path)

    def test_serial_note_on(self):
        """Send a NOTE_ON via serial and verify non-silent audio output."""
        with Emulator(ROM_PATH, lib_path=LIB_PATH) as emu:
            emu.run_frames(2)
            # proto_hdr(INSTR_PU1, MCU_NOTE_ON) = (0 << 5) | 0 = 0x00
            # Payload: period 1046 -> hi=0x04, lo=0x16
            emu.serial_send(bytes([0x00, 0x04, 0x16]))
            emu.run_frames(30)
            samples = emu.drain_audio()
            non_silent = any(l != 0 or r != 0 for l, r in samples)
            self.assertTrue(non_silent, "expected non-silent audio after NOTE_ON")

    def test_joypad(self):
        with Emulator(ROM_PATH, lib_path=LIB_PATH) as emu:
            emu.run_frames(2)
            emu.tap(Button.A)
            # Just verify no crash.

    def test_drain_audio_bytes(self):
        with Emulator(ROM_PATH, lib_path=LIB_PATH) as emu:
            emu.run_frames(10)
            data = emu.drain_audio_bytes()
            # Each sample = 4 bytes (2 channels * 2 bytes each).
            self.assertEqual(len(data) % 4, 0)
            self.assertGreater(len(data), 0)

    def test_save_audio_wav(self):
        with Emulator(ROM_PATH, lib_path=LIB_PATH) as emu:
            emu.run_frames(30)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                path = f.name
            try:
                emu.save_audio(path)
                self.assertGreater(os.path.getsize(path), 0)
            finally:
                os.unlink(path)


if __name__ == "__main__":
    unittest.main()
