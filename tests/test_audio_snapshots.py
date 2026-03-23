"""Audio snapshot tests — verify emulator audio output against stored snapshots."""

import os
from collections.abc import Generator

import pytest

from emulator import Button, Emulator
from pcmsnap import SnapshotConfig, analyze, audio_from_bytes, snapshot_to_dict

ROM_PATH = os.environ.get("WAVES_ROM", "build/waves.gb")
LIB_PATH = os.environ.get("SAMEBOY_LIB", None)


@pytest.fixture
def emu() -> Generator[Emulator, None, None]:
    with Emulator(ROM_PATH, lib_path=LIB_PATH) as e:
        # Run past startup and discard any boot audio.
        e.run_frames(60)
        e.drain_audio()
        yield e


def test_button_a_pulse(emu: Emulator, snapshot) -> None:
    """Holding A should produce a PU1 pulse wave with the default patch."""
    emu.press(Button.A)
    emu.run_frames(30)

    audio_bytes = emu.drain_audio_bytes()
    audio = audio_from_bytes(audio_bytes)
    snap = analyze(audio, SnapshotConfig(channel="PU1"))

    snapshot.assert_match(snapshot_to_dict(snap), "button_a_pulse.json", snap=snap)
