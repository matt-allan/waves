"""High-level Game Boy emulator driver — *ChromeDriver for Game Boy*.

Usage::

    from emulator import Emulator, Button

    with Emulator("build/waves.gb") as emu:
        emu.run_frames(60)          # advance ~1 second
        emu.press(Button.START)
        emu.run_frames(2)
        emu.release(Button.START)

        emu.serial_send(b"\\x00\\x04\\x16")
        emu.run_frames(30)

        emu.save_screenshot("/tmp/frame.png")
        emu.save_audio("/tmp/clip.wav")
"""

import ctypes
import sys
from enum import IntEnum

from . import _bindings as bind
from ._audio import AudioBuffer, SAMPLE_RATE
from ._serial import SerialEngine

# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

SCREEN_W = 160
SCREEN_H = 144

_BOOT_ROM_STUB = bytearray(256)
_BOOT_ROM_STUB[0xFC] = 0x3E
_BOOT_ROM_STUB[0xFD] = 0x01
_BOOT_ROM_STUB[0xFE] = 0xE0
_BOOT_ROM_STUB[0xFF] = 0x50


class Button(IntEnum):
    """Game Boy joypad buttons."""

    RIGHT = bind.GB_KEY_RIGHT
    LEFT = bind.GB_KEY_LEFT
    UP = bind.GB_KEY_UP
    DOWN = bind.GB_KEY_DOWN
    A = bind.GB_KEY_A
    B = bind.GB_KEY_B
    SELECT = bind.GB_KEY_SELECT
    START = bind.GB_KEY_START


# ---------------------------------------------------------------------------
# Emulator
# ---------------------------------------------------------------------------


class Emulator:
    """High-level wrapper around a SameBoy Game Boy emulator instance.

    Parameters
    ----------
    rom_path:
        Path to a ``.gb`` ROM file.
    boot_rom_path:
        Optional path to a DMG boot ROM image.  When *None* a minimal
        built-in stub is used that disables the boot ROM mapping and
        jumps to the game entry point.
    lib_path:
        Path to the ``libsameboy`` shared library.  When *None* the
        default build output location (``build/lib/``) is searched.
    """

    def __init__(self, rom_path, *, boot_rom_path=None, lib_path=None):
        self._lib = bind.load(lib_path)
        self._serial = SerialEngine()
        self._audio = AudioBuffer()
        self._frame_ready = False
        self._gb = None

        # Pixel buffer — 160 * 144 uint32 values.
        self._pixels = (ctypes.c_uint32 * (SCREEN_W * SCREEN_H))()

        # Build C-callable callbacks.  We must keep references to prevent
        # the pointers from being garbage-collected.
        self._cb_rgb = bind.RGB_ENCODE_FUNC(self._on_rgb_encode)
        self._cb_vblank = bind.VBLANK_FUNC(self._on_vblank)
        self._cb_log = bind.LOG_FUNC(self._on_log)
        self._cb_audio = bind.AUDIO_SAMPLE_FUNC(self._on_audio_sample)
        self._cb_serial_start = bind.SERIAL_BIT_START_FUNC(self._on_serial_bit_start)
        self._cb_serial_end = bind.SERIAL_BIT_END_FUNC(self._on_serial_bit_end)

        # Initialise SameBoy.
        self._gb = self._lib.GB_init(self._lib.GB_alloc(), bind.GB_MODEL_DMG_B)
        if not self._gb:
            raise RuntimeError("GB_init failed")

        # Register callbacks.
        self._lib.GB_set_log_callback(self._gb, self._cb_log)
        self._lib.GB_set_pixels_output(self._gb, self._pixels)
        self._lib.GB_set_rgb_encode_callback(self._gb, self._cb_rgb)
        self._lib.GB_set_vblank_callback(self._gb, self._cb_vblank)
        self._lib.GB_set_sample_rate(self._gb, SAMPLE_RATE)
        self._lib.GB_apu_set_sample_callback(self._gb, self._cb_audio)
        self._lib.GB_set_serial_transfer_bit_start_callback(
            self._gb, self._cb_serial_start
        )
        self._lib.GB_set_serial_transfer_bit_end_callback(self._gb, self._cb_serial_end)

        # Boot ROM.
        if boot_rom_path:
            if self._lib.GB_load_boot_rom(self._gb, boot_rom_path.encode()) != 0:
                self._cleanup()
                raise FileNotFoundError(f"Failed to load boot ROM: {boot_rom_path}")
        else:
            stub = (ctypes.c_uint8 * 256)(*_BOOT_ROM_STUB)
            self._lib.GB_load_boot_rom_from_buffer(self._gb, stub, 256)

        # Game ROM.
        if self._lib.GB_load_rom(self._gb, rom_path.encode()) != 0:
            self._cleanup()
            raise FileNotFoundError(f"Failed to load ROM: {rom_path}")

    # -- Context manager --------------------------------------------------

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self):
        """Destroy the emulator and release all resources."""
        if self._gb:
            self._lib.GB_dealloc(self._gb)
            self._gb = None

    def _cleanup(self):
        if self._gb:
            self._lib.GB_dealloc(self._gb)
            self._gb = None

    # -- SameBoy callbacks (private) --------------------------------------

    def _on_rgb_encode(self, _gb, r, g, b):
        return 0xFF000000 | (r << 16) | (g << 8) | b

    def _on_vblank(self, _gb, _vblank_type):
        self._frame_ready = True

    def _on_log(self, _gb, msg, _attrs):
        if msg:
            print(msg.decode("utf-8", errors="replace"), end="", file=sys.stderr)

    def _on_audio_sample(self, _gb, sample_ptr):
        s = sample_ptr[0]
        self._audio.push(s.left, s.right)

    def _on_serial_bit_start(self, _gb, bit_to_send):
        self._serial.on_bit_start(bool(bit_to_send))

    def _on_serial_bit_end(self, _gb):
        return self._serial.on_bit_end()

    # -- Emulation control ------------------------------------------------

    def run_frames(self, n=1):
        """Advance the emulator by *n* vblank frames (~16.7 ms each)."""
        for _ in range(n):
            self._frame_ready = False
            while not self._frame_ready:
                self._lib.GB_run_frame(self._gb)

    # -- Joypad input -----------------------------------------------------

    def press(self, button: Button) -> None:
        """Press a joypad button (stays held until :meth:`release`)."""
        self._lib.GB_set_key_state(self._gb, int(button), True)

    def release(self, button: Button) -> None:
        """Release a joypad button."""
        self._lib.GB_set_key_state(self._gb, int(button), False)

    def tap(
        self, button: Button, hold_frames: int = 2, release_frames: int = 2
    ) -> None:
        """Press and release *button*, advancing frames in between."""
        self.press(button)
        self.run_frames(hold_frames)
        self.release(button)
        self.run_frames(release_frames)

    # -- Serial link ------------------------------------------------------

    def serial_send(self, data: bytes) -> None:
        """Enqueue *data* bytes to send to the GB via the serial link."""
        for b in data:
            self._serial.enqueue(b if isinstance(b, int) else ord(b))

    def serial_recv(self, max_bytes=256):
        """Dequeue up to *max_bytes* received from the GB serial link."""
        result = bytearray()
        for _ in range(max_bytes):
            b = self._serial.dequeue()
            if b is None:
                break
            result.append(b)
        return bytes(result)

    # -- Screen capture ---------------------------------------------------

    def screenshot(self):
        """Return raw RGBA pixel data as ``bytes`` (160 * 144 * 4)."""
        raw = ctypes.string_at(ctypes.addressof(self._pixels), SCREEN_W * SCREEN_H * 4)
        # The pixel format is 0xFFRRGGBB which, on little-endian, is
        # stored as BB GG RR FF in memory.  Convert to R G B A.
        out = bytearray(len(raw))
        for i in range(SCREEN_W * SCREEN_H):
            off = i * 4
            out[off] = raw[off + 2]  # R
            out[off + 1] = raw[off + 1]  # G
            out[off + 2] = raw[off]  # B
            out[off + 3] = raw[off + 3]  # A
        return bytes(out)

    def screenshot_raw(self):
        """Return the native pixel buffer as ``bytes`` (0xFFRRGGBB format)."""
        return bytes(
            ctypes.string_at(ctypes.addressof(self._pixels), SCREEN_W * SCREEN_H * 4)
        )

    def screenshot_pil(self):
        """Return a :class:`PIL.Image.Image`.  Requires *Pillow*."""
        from PIL import Image

        return Image.frombytes("RGBA", (SCREEN_W, SCREEN_H), self.screenshot())

    def save_screenshot(self, path):
        """Save a screenshot.  Uses Pillow for PNG if available, else PPM."""
        try:
            self.screenshot_pil().save(path)
        except ImportError:
            self._save_ppm(path)

    def _save_ppm(self, path: str) -> None:
        with open(path, "w") as f:
            f.write(f"P3\n{SCREEN_W} {SCREEN_H}\n255\n")
            for i in range(SCREEN_W * SCREEN_H):
                px = self._pixels[i]
                r = (px >> 16) & 0xFF
                g = (px >> 8) & 0xFF
                b = px & 0xFF
                f.write(f"{r} {g} {b}\n")

    # -- Audio capture ----------------------------------------------------

    def drain_audio(self):
        """Drain all buffered audio as a list of ``(left, right)`` pairs."""
        return self._audio.drain()

    def drain_audio_bytes(self):
        """Drain all buffered audio as packed int16 LE bytes."""
        return self._audio.drain_bytes()

    def save_audio(self, path: str) -> None:
        """Drain the audio buffer and write a WAV file to *path*."""
        data = self.drain_audio_bytes()
        AudioBuffer.save_wav(path, data)

    def audio_available(self):
        """Number of audio samples currently buffered."""
        return self._audio.available()
