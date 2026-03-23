"""Tests for pcmsnap."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "pcmsnap"))

import numpy as np

from pcmsnap import (
    ChannelSummary,
    Envelope,
    Meta,
    NoiseTimbre,
    Panning,
    PanningRun,
    PulseTimbre,
    RenderConfig,
    Snapshot,
    SnapshotConfig,
    SpectralPeak,
    StereoAudio,
    Summary,
    WavTimbre,
    WaveformDigest,
    analyze,
    load_audio,
    load_wav,
    render_svg,
    snapshot_from_json,
    snapshot_to_json,
)


# ---------------------------------------------------------------------------
# Helpers — generate GB-style test signals
# ---------------------------------------------------------------------------

SR = 44100


def _gb_pulse(freq: float, n: int, duty: float = 0.5) -> np.ndarray:
    """Band-limited pulse wave, quantized to 4-bit like the GB DAC."""
    t = np.arange(n) / SR
    max_harmonic = min(int(SR / (2 * freq)), 30)
    signal = np.zeros(n)
    for k in range(1, max_harmonic + 1):
        coeff = np.sin(k * np.pi * duty) / (k * np.pi) * 2
        signal += coeff * np.sin(2 * np.pi * k * freq * t)
    return np.round(signal * 7.5) / 7.5


def _adsr(n: int, a_ms: float, d_ms: float, sus: float, r_ms: float) -> np.ndarray:
    a = int(a_ms * SR / 1000)
    d = int(d_ms * SR / 1000)
    r = int(r_ms * SR / 1000)
    s_len = max(0, n - a - d - r)
    env = np.zeros(n)
    pos = 0
    env[pos : pos + a] = np.linspace(0, 1, a)
    pos += a
    env[pos : pos + d] = np.linspace(1, sus, d)
    pos += d
    env[pos : pos + s_len] = sus
    pos += s_len
    actual_r = min(r, n - pos)
    if actual_r > 0:
        env[pos : pos + actual_r] = np.linspace(sus, 0, actual_r)
    return env


def _make_wav(path: str, left: np.ndarray, right: np.ndarray) -> None:
    """Write stereo float arrays to a 16-bit WAV file."""
    n = len(left)
    interleaved = np.empty(n * 2, dtype=np.int16)
    interleaved[0::2] = np.clip(left * 32767, -32768, 32767).astype(np.int16)
    interleaved[1::2] = np.clip(right * 32767, -32768, 32767).astype(np.int16)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(interleaved.tobytes())


# ---------------------------------------------------------------------------
# Type tests
# ---------------------------------------------------------------------------


class TestTypes(unittest.TestCase):
    def test_panning_from_states(self):
        states = ["C", "C", "C", "L", "L", "-"]
        pan = Panning.from_states(5.0, states)
        self.assertEqual(pan.n_windows, 6)
        self.assertEqual(len(pan.runs), 3)
        self.assertEqual(pan.runs[0], PanningRun(state="C", count=3))
        self.assertEqual(pan.runs[1], PanningRun(state="L", count=2))
        self.assertEqual(pan.runs[2], PanningRun(state="-", count=1))
        self.assertEqual(pan.states_str, "Cx3 Lx2 -")

    def test_panning_expand(self):
        pan = Panning(
            window_ms=5.0,
            n_windows=4,
            runs=[PanningRun("C", 2), PanningRun("L", 2)],
        )
        self.assertEqual(pan.expand(), ["C", "C", "L", "L"])

    def test_panning_parse_states_str(self):
        runs = Panning.parse_states_str("Cx50 -x20 L")
        self.assertEqual(len(runs), 3)
        self.assertEqual(runs[0].state, "C")
        self.assertEqual(runs[0].count, 50)
        self.assertEqual(runs[2].count, 1)

    def test_spectral_peak(self):
        pk = SpectralPeak(freq_hz=440.0, mag_db=-12.3)
        self.assertEqual(pk.freq_hz, 440.0)
        self.assertEqual(pk.mag_db, -12.3)


# ---------------------------------------------------------------------------
# Analysis tests
# ---------------------------------------------------------------------------


class TestAnalyze(unittest.TestCase):
    def test_pulse_50pct(self):
        n = int(0.5 * SR)
        osc = _gb_pulse(261.6, n, duty=0.5)
        env = _adsr(n, 10, 50, 0.7, 150)
        signal = osc * env * 0.8
        audio = StereoAudio(left=signal, right=signal, sample_rate=SR)
        cfg = SnapshotConfig(channel="PU1")
        snap = analyze(audio, cfg)

        self.assertIsInstance(snap, Snapshot)
        self.assertIsInstance(snap.meta, Meta)
        self.assertEqual(snap.meta.version, 2)
        self.assertEqual(snap.meta.sample_rate, SR)
        self.assertIsInstance(snap.summary, Summary)
        self.assertIsInstance(snap.summary.left, ChannelSummary)
        self.assertGreater(snap.summary.left.peak, 0)
        self.assertIsInstance(snap.timbre, PulseTimbre)
        self.assertEqual(snap.timbre.channel, "PU1")
        self.assertEqual(snap.timbre.duty_cycle, "50%")
        self.assertIsNotNone(snap.timbre.fundamental_hz)
        self.assertAlmostEqual(snap.timbre.fundamental_hz, 261.6, delta=5)
        self.assertIsNotNone(snap.waveform)

    def test_pulse_25pct(self):
        n = int(0.5 * SR)
        osc = _gb_pulse(440.0, n, duty=0.25)
        env = _adsr(n, 5, 40, 0.7, 100)
        signal = osc * env * 0.75
        audio = StereoAudio(left=signal, right=signal, sample_rate=SR)
        cfg = SnapshotConfig(channel="PU2")
        snap = analyze(audio, cfg)

        self.assertIsInstance(snap.timbre, PulseTimbre)
        self.assertEqual(snap.timbre.channel, "PU2")
        self.assertEqual(snap.timbre.duty_cycle, "25%")

    def test_noise_channel(self):
        n = int(0.3 * SR)
        rng = np.random.RandomState(42)
        signal = rng.randn(n) * 0.3
        signal = np.round(signal * 7.5) / 7.5
        audio = StereoAudio(left=signal, right=signal, sample_rate=SR)
        cfg = SnapshotConfig(channel="NOI")
        snap = analyze(audio, cfg)

        self.assertIsInstance(snap.timbre, NoiseTimbre)
        self.assertEqual(snap.timbre.channel, "NOI")
        self.assertIsNone(snap.waveform)

    def test_panning_detection(self):
        n = int(0.2 * SR)
        signal = _gb_pulse(440.0, n, duty=0.5) * 0.5
        # Left only
        audio = StereoAudio(
            left=signal, right=np.zeros(n), sample_rate=SR,
        )
        cfg = SnapshotConfig(channel="PU1")
        snap = analyze(audio, cfg)
        states = snap.panning.expand()
        self.assertTrue(all(s == "L" for s in states))

    def test_silent_audio(self):
        n = int(0.1 * SR)
        audio = StereoAudio(
            left=np.zeros(n), right=np.zeros(n), sample_rate=SR,
        )
        snap = analyze(audio)
        self.assertEqual(snap.summary.left.peak, 0.0)
        self.assertEqual(snap.summary.left.rms, 0.0)


# ---------------------------------------------------------------------------
# Serialization round-trip tests
# ---------------------------------------------------------------------------


class TestSerialization(unittest.TestCase):
    def _make_snapshot(self) -> Snapshot:
        n = int(0.5 * SR)
        osc = _gb_pulse(261.6, n, duty=0.5)
        env = _adsr(n, 10, 50, 0.7, 150)
        signal = osc * env * 0.8
        audio = StereoAudio(left=signal, right=signal, sample_rate=SR)
        return analyze(audio, SnapshotConfig(channel="PU1"))

    def test_json_roundtrip(self):
        snap = self._make_snapshot()
        text = snapshot_to_json(snap)

        # Valid JSON
        parsed = json.loads(text)
        self.assertEqual(parsed["meta"]["version"], 2)

        # Round-trip back to Snapshot
        snap2 = snapshot_from_json(text)
        self.assertIsInstance(snap2, Snapshot)
        self.assertEqual(snap2.meta.version, snap.meta.version)
        self.assertEqual(snap2.meta.sample_rate, snap.meta.sample_rate)
        self.assertEqual(snap2.meta.n_samples, snap.meta.n_samples)
        self.assertEqual(snap2.summary.left.peak, snap.summary.left.peak)
        self.assertIsInstance(snap2.timbre, PulseTimbre)
        self.assertEqual(snap2.timbre.duty_cycle, snap.timbre.duty_cycle)
        self.assertEqual(snap2.envelope.left, snap.envelope.left)
        self.assertEqual(snap2.panning.states_str, snap.panning.states_str)

    def test_json_is_compact(self):
        snap = self._make_snapshot()
        text = snapshot_to_json(snap)
        # Should not have excessive whitespace (not standard pretty-print)
        lines = text.strip().split("\n")
        # Compact encoder chunks arrays, so lines should be reasonable length
        self.assertTrue(all(len(line) < 500 for line in lines))

    def test_wav_channel_spectrum_roundtrip(self):
        n = int(0.5 * SR)
        # Simple sawtooth-ish wavetable
        table = list(range(16)) + list(range(15, -1, -1))
        t = np.arange(n) / SR
        phase = (t * 164.8) % 1.0
        indices = (phase * len(table)).astype(int) % len(table)
        signal = np.array([table[i] for i in indices], dtype=np.float64)
        signal = (signal / 7.5) - 1.0
        env = _adsr(n, 50, 30, 0.8, 200)
        signal = signal * env * 0.7

        audio = StereoAudio(left=signal, right=signal, sample_rate=SR)
        snap = analyze(audio, SnapshotConfig(channel="WAV"))
        self.assertIsInstance(snap.timbre, WavTimbre)

        text = snapshot_to_json(snap)
        snap2 = snapshot_from_json(text)
        self.assertIsInstance(snap2.timbre, WavTimbre)
        self.assertEqual(
            len(snap2.timbre.spectrum), len(snap.timbre.spectrum)
        )


# ---------------------------------------------------------------------------
# Format loading tests
# ---------------------------------------------------------------------------


class TestFormats(unittest.TestCase):
    def test_load_wav(self):
        n = 1000
        left = np.sin(np.linspace(0, 2 * np.pi, n)) * 0.5
        right = np.cos(np.linspace(0, 2 * np.pi, n)) * 0.5

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            path = f.name
        _make_wav(path, left, right)

        audio = load_wav(path)
        self.assertEqual(audio.sample_rate, SR)
        self.assertEqual(len(audio.left), n)
        self.assertEqual(len(audio.right), n)
        # Should be close (16-bit quantization introduces small error)
        np.testing.assert_allclose(audio.left, left, atol=1e-4)

    def test_load_audio_auto(self):
        n = 500
        signal = np.zeros(n)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            path = f.name
        _make_wav(path, signal, signal)

        audio = load_audio(path)
        self.assertEqual(audio.sample_rate, SR)
        self.assertEqual(len(audio.left), n)


# ---------------------------------------------------------------------------
# Render tests
# ---------------------------------------------------------------------------


class TestRender(unittest.TestCase):
    def test_render_produces_svg(self):
        n = int(0.5 * SR)
        osc = _gb_pulse(261.6, n, duty=0.5)
        env = _adsr(n, 10, 50, 0.7, 150)
        signal = osc * env * 0.8
        audio = StereoAudio(left=signal, right=signal, sample_rate=SR)
        snap = analyze(audio, SnapshotConfig(channel="PU1"))

        svg = render_svg(snap)
        self.assertTrue(svg.startswith("<svg"))
        self.assertTrue(svg.strip().endswith("</svg>"))
        self.assertIn("WAVEFORM", svg)
        self.assertIn("ENVELOPE", svg)
        self.assertIn("TIMBRE", svg)
        self.assertIn("PAN", svg)

    def test_render_dmg_palette(self):
        n = int(0.3 * SR)
        signal = np.zeros(n)
        audio = StereoAudio(left=signal, right=signal, sample_rate=SR)
        snap = analyze(audio, SnapshotConfig(channel="NOI"))

        svg = render_svg(snap, RenderConfig(palette="dmg"))
        self.assertIn("#9bbc0f", svg)  # DMG green background

if __name__ == "__main__":
    unittest.main()
