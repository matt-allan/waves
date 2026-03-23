"""Tests for pcmsnap."""

from __future__ import annotations

import json

import numpy as np
import pytest

from pcmsnap import (
    ChannelSummary,
    Envelope,
    Meta,
    NoiseTimbre,
    Panning,
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


# ---------------------------------------------------------------------------
# Analysis tests
# ---------------------------------------------------------------------------


def test_pulse_50pct():
    n = int(0.5 * SR)
    osc = _gb_pulse(261.6, n, duty=0.5)
    env = _adsr(n, 10, 50, 0.7, 150)
    signal = osc * env * 0.8
    audio = StereoAudio(left=signal, right=signal, sample_rate=SR)
    cfg = SnapshotConfig(channel="PU1")
    snap = analyze(audio, cfg)

    assert isinstance(snap, Snapshot)
    assert isinstance(snap.meta, Meta)
    assert snap.meta.sample_rate == SR
    assert isinstance(snap.summary, Summary)
    assert isinstance(snap.summary.left, ChannelSummary)
    assert snap.summary.left.peak > 0
    assert isinstance(snap.timbre, PulseTimbre)
    assert snap.timbre.channel == "PU1"
    assert snap.timbre.duty_cycle == "50%"
    assert snap.timbre.fundamental_hz is not None
    assert abs(snap.timbre.fundamental_hz - 261.6) < 5
    assert snap.waveform is not None


def test_pulse_25pct():
    n = int(0.5 * SR)
    osc = _gb_pulse(440.0, n, duty=0.25)
    env = _adsr(n, 5, 40, 0.7, 100)
    signal = osc * env * 0.75
    audio = StereoAudio(left=signal, right=signal, sample_rate=SR)
    cfg = SnapshotConfig(channel="PU2")
    snap = analyze(audio, cfg)

    assert isinstance(snap.timbre, PulseTimbre)
    assert snap.timbre.channel == "PU2"
    assert snap.timbre.duty_cycle == "25%"


def test_noise_channel():
    n = int(0.3 * SR)
    rng = np.random.RandomState(42)
    signal = rng.randn(n) * 0.3
    signal = np.round(signal * 7.5) / 7.5
    audio = StereoAudio(left=signal, right=signal, sample_rate=SR)
    cfg = SnapshotConfig(channel="NOI")
    snap = analyze(audio, cfg)

    assert isinstance(snap.timbre, NoiseTimbre)
    assert snap.timbre.channel == "NOI"
    assert snap.waveform is None


def test_panning_detection():
    n = int(0.2 * SR)
    signal = _gb_pulse(440.0, n, duty=0.5) * 0.5
    audio = StereoAudio(left=signal, right=np.zeros(n), sample_rate=SR)
    cfg = SnapshotConfig(channel="PU1")
    snap = analyze(audio, cfg)
    assert all(s == "L" for s in snap.panning.states)


def test_silent_audio():
    n = int(0.1 * SR)
    audio = StereoAudio(left=np.zeros(n), right=np.zeros(n), sample_rate=SR)
    snap = analyze(audio)
    assert snap.summary.left.peak == 0.0
    assert snap.summary.left.rms == 0.0


# ---------------------------------------------------------------------------
# Serialization round-trip tests
# ---------------------------------------------------------------------------


@pytest.fixture
def pulse_snapshot():
    n = int(0.5 * SR)
    osc = _gb_pulse(261.6, n, duty=0.5)
    env = _adsr(n, 10, 50, 0.7, 150)
    signal = osc * env * 0.8
    audio = StereoAudio(left=signal, right=signal, sample_rate=SR)
    return analyze(audio, SnapshotConfig(channel="PU1"))


def test_json_roundtrip(pulse_snapshot):
    snap = pulse_snapshot
    text = snapshot_to_json(snap)

    snap2 = snapshot_from_json(text)
    assert isinstance(snap2, Snapshot)
    assert snap2.meta.sample_rate == snap.meta.sample_rate
    assert snap2.meta.n_samples == snap.meta.n_samples
    assert snap2.summary.left.peak == snap.summary.left.peak
    assert isinstance(snap2.timbre, PulseTimbre)
    assert snap2.timbre.duty_cycle == snap.timbre.duty_cycle
    assert snap2.envelope.left == snap.envelope.left
    assert snap2.panning.states == snap.panning.states


def test_json_is_compact(pulse_snapshot):
    text = snapshot_to_json(pulse_snapshot)
    lines = text.strip().split("\n")
    assert all(len(line) < 500 for line in lines)


def test_wav_channel_spectrum_roundtrip():
    n = int(0.5 * SR)
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
    assert isinstance(snap.timbre, WavTimbre)

    text = snapshot_to_json(snap)
    snap2 = snapshot_from_json(text)
    assert isinstance(snap2.timbre, WavTimbre)
    assert len(snap2.timbre.spectrum) == len(snap.timbre.spectrum)


# ---------------------------------------------------------------------------
# Render tests
# ---------------------------------------------------------------------------


def test_render_produces_svg():
    n = int(0.5 * SR)
    osc = _gb_pulse(261.6, n, duty=0.5)
    env = _adsr(n, 10, 50, 0.7, 150)
    signal = osc * env * 0.8
    audio = StereoAudio(left=signal, right=signal, sample_rate=SR)
    snap = analyze(audio, SnapshotConfig(channel="PU1"))

    svg = render_svg(snap)
    assert svg.startswith("<svg")
    assert svg.strip().endswith("</svg>")
    assert "WAVEFORM" in svg
    assert "ENVELOPE" in svg
    assert "TIMBRE" in svg
    assert "PAN" in svg
