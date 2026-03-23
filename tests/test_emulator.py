import os
import tempfile
from collections.abc import Generator

import pytest

from emulator import Button, Emulator  # noqa: E402

ROM_PATH = os.environ.get("WAVES_ROM", "build/waves.gb")
LIB_PATH = os.environ.get("SAMEBOY_LIB", None)


@pytest.fixture
def emu() -> Generator[Emulator, None, None]:
    with Emulator(ROM_PATH, lib_path=LIB_PATH) as e:
        yield e


def test_init_and_close():
    with Emulator(ROM_PATH, lib_path=LIB_PATH) as e:
        assert e is not None


def test_run_frames(emu: Emulator):
    emu.run_frames(60)


def test_audio_output(emu: Emulator):
    emu.run_frames(10)
    assert emu.audio_available() > 1000
    samples = emu.drain_audio()
    assert len(samples) > 1000


def test_screenshot(emu: Emulator):
    emu.run_frames(5)
    data = emu.screenshot()
    assert len(data) == 160 * 144 * 4


def test_screenshot_raw(emu: Emulator):
    emu.run_frames(5)
    data = emu.screenshot_raw()
    assert len(data) == 160 * 144 * 4


def test_save_screenshot_ppm(emu: Emulator):
    emu.run_frames(5)
    with tempfile.NamedTemporaryFile(suffix=".ppm", delete=False) as f:
        path = f.name
    try:
        emu._save_ppm(path)
        assert os.path.getsize(path) > 0
    finally:
        os.unlink(path)


def test_serial_note_on(emu: Emulator):
    """Send a NOTE_ON via serial and verify non-silent audio output."""
    emu.run_frames(2)
    # proto_hdr(INSTR_PU1, MCU_NOTE_ON) = (0 << 5) | 0 = 0x00
    # Payload: period 1046 -> hi=0x04, lo=0x16
    emu.serial_send(bytes([0x00, 0x04, 0x16]))
    emu.run_frames(30)
    samples = emu.drain_audio()
    assert any(l != 0 or r != 0 for l, r in samples), (
        "expected non-silent audio after NOTE_ON"
    )


def test_joypad(emu: Emulator):
    emu.run_frames(2)
    emu.tap(Button.A)
    # Just verify no crash.


def test_drain_audio_bytes(emu: Emulator):
    emu.run_frames(10)
    data = emu.drain_audio_bytes()
    # Each sample = 4 bytes (2 channels * 2 bytes each).
    assert len(data) % 4 == 0
    assert len(data) > 0


def test_save_audio_wav(emu: Emulator):
    emu.run_frames(30)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        path = f.name
    try:
        emu.save_audio(path)
        assert os.path.getsize(path) > 0
    finally:
        os.unlink(path)
