"""Tests for the midilink MIDI-to-gamelink translator."""

import ctypes
import os
from pathlib import Path

import pytest

LIB_PATH = os.environ.get(
    "MIDILINK_LIB", str(Path(__file__).resolve().parent.parent / "build" / "lib" / "libmidilink.so")
)


# -- ctypes bindings ---------------------------------------------------------

class Midilink(ctypes.Structure):
    """Opaque wrapper — sized to hold the C struct midilink."""
    _fields_ = [("_opaque", ctypes.c_uint8 * 64)]


@pytest.fixture(scope="session")
def lib():
    return ctypes.CDLL(LIB_PATH)


@pytest.fixture
def ml(lib):
    ctx = Midilink()
    lib.midilink_init(ctypes.byref(ctx))
    return ctx


def feed(lib, ml, byte):
    """Feed one MIDI byte, return list of protocol bytes produced."""
    out = (ctypes.c_uint8 * 4)()
    n = lib.midilink_feed(ctypes.byref(ml), ctypes.c_uint8(byte), out, ctypes.c_uint8(4))
    return list(out[:n])


def feed_bytes(lib, ml, data):
    """Feed a sequence of MIDI bytes, return all protocol bytes produced."""
    result = []
    for b in data:
        result.extend(feed(lib, ml, b))
    return result


# -- Helpers ------------------------------------------------------------------

def proto_hdr(instr, cmd):
    return (instr << 5) | (cmd & 0x1F)


INSTR_PU1 = 0
INSTR_PU2 = 1
INSTR_WAV = 2
INSTR_NOISE = 3

MCU_NOTE_ON = 0
MCU_NOTE_OFF = 1

# Period table (C3=note48 .. B8=note119), must match midilink.c
PERIOD_TABLE = [
    44, 156, 262, 363, 457, 547, 631, 710, 786, 854, 923, 986,
    1046, 1102, 1155, 1205, 1253, 1297, 1339, 1379, 1417, 1452, 1486, 1517,
    1546, 1575, 1602, 1627, 1650, 1673, 1694, 1714, 1732, 1750, 1767, 1783,
    1798, 1812, 1825, 1837, 1849, 1860, 1871, 1881, 1890, 1899, 1907, 1915,
    1923, 1930, 1936, 1943, 1949, 1954, 1959, 1964, 1969, 1974, 1978, 1982,
    1985, 1988, 1992, 1995, 1998, 2001, 2004, 2006, 2009, 2011, 2013, 2015,
]

MIDI_NOTE_MIN = 48


def expected_note_on(instr, midi_note):
    """Expected protocol bytes for a NOTE_ON."""
    period = PERIOD_TABLE[midi_note - MIDI_NOTE_MIN]
    return [
        proto_hdr(instr, MCU_NOTE_ON),
        (period >> 8) & 0xFF,
        period & 0xFF,
    ]


def expected_note_off(instr):
    """Expected protocol bytes for a NOTE_OFF."""
    return [proto_hdr(instr, MCU_NOTE_OFF)]


# -- Tests --------------------------------------------------------------------


class TestNoteOn:
    def test_pu1_note_on(self, lib, ml):
        """NOTE_ON on ch1 → PU1 NOTE_ON with correct period."""
        note = 60  # Middle C (C5)
        out = feed_bytes(lib, ml, [0x90, note, 100])
        assert out == expected_note_on(INSTR_PU1, note)

    def test_pu2_note_on(self, lib, ml):
        """NOTE_ON on ch2 → PU2."""
        note = 72
        out = feed_bytes(lib, ml, [0x91, note, 80])
        assert out == expected_note_on(INSTR_PU2, note)

    def test_wav_note_on(self, lib, ml):
        """NOTE_ON on ch3 → WAV."""
        note = 60
        out = feed_bytes(lib, ml, [0x92, note, 64])
        assert out == expected_note_on(INSTR_WAV, note)

    def test_noise_note_on(self, lib, ml):
        """NOTE_ON on ch10 → NOISE."""
        note = 60
        out = feed_bytes(lib, ml, [0x99, note, 127])
        assert out == expected_note_on(INSTR_NOISE, note)

    def test_lowest_note(self, lib, ml):
        """C3 (note 48) is the lowest supported note."""
        out = feed_bytes(lib, ml, [0x90, 48, 100])
        assert out == expected_note_on(INSTR_PU1, 48)

    def test_highest_note(self, lib, ml):
        """B8 (note 119) is the highest supported note."""
        out = feed_bytes(lib, ml, [0x90, 119, 100])
        assert out == expected_note_on(INSTR_PU1, 119)


class TestNoteOff:
    def test_note_off_message(self, lib, ml):
        """MIDI NOTE_OFF (0x80) → protocol NOTE_OFF."""
        out = feed_bytes(lib, ml, [0x80, 60, 0])
        assert out == expected_note_off(INSTR_PU1)

    def test_note_on_velocity_zero(self, lib, ml):
        """NOTE_ON with velocity 0 is treated as NOTE_OFF."""
        out = feed_bytes(lib, ml, [0x90, 60, 0])
        assert out == expected_note_off(INSTR_PU1)

    def test_note_off_pu2(self, lib, ml):
        out = feed_bytes(lib, ml, [0x81, 72, 64])
        assert out == expected_note_off(INSTR_PU2)


class TestEdgeCases:
    def test_out_of_range_low(self, lib, ml):
        """Notes below C3 are dropped."""
        out = feed_bytes(lib, ml, [0x90, 47, 100])
        assert out == []

    def test_out_of_range_high(self, lib, ml):
        """Notes above B8 are dropped."""
        out = feed_bytes(lib, ml, [0x90, 120, 100])
        assert out == []

    def test_unmapped_channel(self, lib, ml):
        """Messages on unmapped MIDI channels produce no output."""
        # Channel 5 (0x94) is not mapped to any instrument
        out = feed_bytes(lib, ml, [0x94, 60, 100])
        assert out == []

    def test_non_note_messages_ignored(self, lib, ml):
        """CC, program change, etc. produce no output."""
        # CC on ch1
        out = feed_bytes(lib, ml, [0xB0, 7, 100])
        assert out == []

    def test_system_messages_ignored(self, lib, ml):
        """Real-time / system messages produce no output."""
        # Timing clock
        out = feed_bytes(lib, ml, [0xF8])
        assert out == []


class TestRunningStatus:
    def test_running_status_note_on(self, lib, ml):
        """MIDI running status: second note without repeated status byte."""
        note1 = 60
        note2 = 64
        out = feed_bytes(lib, ml, [0x90, note1, 100, note2, 100])
        expected = expected_note_on(INSTR_PU1, note1) + expected_note_on(INSTR_PU1, note2)
        assert out == expected

    def test_running_status_note_off_via_vel_zero(self, lib, ml):
        """Running status: note-on then note-off (vel=0) without re-sending status."""
        note = 60
        out = feed_bytes(lib, ml, [0x90, note, 100, note, 0])
        expected = expected_note_on(INSTR_PU1, note) + expected_note_off(INSTR_PU1)
        assert out == expected


class TestSequence:
    def test_note_on_then_off(self, lib, ml):
        """Full note cycle: on then off."""
        note = 60
        out = feed_bytes(lib, ml, [0x90, note, 100, 0x80, note, 0])
        expected = expected_note_on(INSTR_PU1, note) + expected_note_off(INSTR_PU1)
        assert out == expected

    def test_multiple_instruments(self, lib, ml):
        """Notes to different instruments in sequence."""
        out = feed_bytes(lib, ml, [
            0x90, 60, 100,  # PU1
            0x91, 64, 80,   # PU2
            0x92, 67, 64,   # WAV
        ])
        expected = (
            expected_note_on(INSTR_PU1, 60)
            + expected_note_on(INSTR_PU2, 64)
            + expected_note_on(INSTR_WAV, 67)
        )
        assert out == expected

    def test_interleaved_realtime(self, lib, ml):
        """Real-time messages interleaved with note data don't break parsing."""
        out = feed_bytes(lib, ml, [0x90, 0xF8, 60, 0xF8, 100])
        assert out == expected_note_on(INSTR_PU1, 60)
