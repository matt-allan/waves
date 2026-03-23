"""Tests for pcmsnap."""

from __future__ import annotations

import json
import tempfile
import wave

import numpy as np
import pytest

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


def test_panning_from_states():
    states = ["C", "C", "C", "L", "L", "-"]
    pan = Panning.from_states(5.0, states)
    assert pan.n_windows == 6
    assert len(pan.runs) == 3
    assert pan.runs[0] == PanningRun(state="C", count=3)
    assert pan.runs[1] == PanningRun(state="L", count=2)
    assert pan.runs[2] == PanningRun(state="-", count=1)
    assert pan.states_str == "Cx3 Lx2 -"


def test_panning_expand():
    pan = Panning(
        window_ms=5.0,
        n_windows=4,
        runs=[PanningRun("C", 2), PanningRun("L", 2)],
    )
    assert pan.expand() == ["C", "C", "L", "L"]


def test_panning_parse_states_str():
    runs = Panning.parse_states_str("Cx50 -x20 L")
    assert len(runs) == 3
    assert runs[0].state == "C"
    assert runs[0].count == 50
    assert runs[2].count == 1


def test_spectral_peak():
    pk = SpectralPeak(freq_hz=440.0, mag_db=-12.3)
    assert pk.freq_hz == 440.0
    assert pk.mag_db == -12.3


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
    assert snap.meta.version == 2
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
    states = snap.panning.expand()
    assert all(s == "L" for s in states)


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

    parsed = json.loads(text)
    assert parsed["meta"]["version"] == 2

    snap2 = snapshot_from_json(text)
    assert isinstance(snap2, Snapshot)
    assert snap2.meta.version == snap.meta.version
    assert snap2.meta.sample_rate == snap.meta.sample_rate
    assert snap2.meta.n_samples == snap.meta.n_samples
    assert snap2.summary.left.peak == snap.summary.left.peak
    assert isinstance(snap2.timbre, PulseTimbre)
    assert snap2.timbre.duty_cycle == snap.timbre.duty_cycle
    assert snap2.envelope.left == snap.envelope.left
    assert snap2.panning.states_str == snap.panning.states_str


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
# Format loading tests
# ---------------------------------------------------------------------------


def test_load_wav():
    n = 1000
    left = np.sin(np.linspace(0, 2 * np.pi, n)) * 0.5
    right = np.cos(np.linspace(0, 2 * np.pi, n)) * 0.5

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        path = f.name
    _make_wav(path, left, right)

    audio = load_wav(path)
    assert audio.sample_rate == SR
    assert len(audio.left) == n
    assert len(audio.right) == n
    np.testing.assert_allclose(audio.left, left, atol=1e-4)


def test_load_audio_auto():
    n = 500
    signal = np.zeros(n)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        path = f.name
    _make_wav(path, signal, signal)

    audio = load_audio(path)
    assert audio.sample_rate == SR
    assert len(audio.left) == n


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


def test_render_dmg_palette():
    n = int(0.3 * SR)
    signal = np.zeros(n)
    audio = StereoAudio(left=signal, right=signal, sample_rate=SR)
    snap = analyze(audio, SnapshotConfig(channel="NOI"))

    svg = render_svg(snap, RenderConfig(palette="dmg"))
    assert "#9bbc0f" in svg  # DMG green background
