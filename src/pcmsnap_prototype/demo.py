#!/usr/bin/env python3
"""Demo: generate Game Boy APU-style test signals and produce snapshots + SVGs.

Simulates (in software) the output of each GB channel type:
  1. PU1 — 50% duty pulse at C4, custom ADSR, panned center
  2. PU2 — 25% duty pulse at A4, with a panning change mid-note
  3. WAV — custom wavetable at E3, slow attack
  4. NOI — 15-bit white noise with fast decay (hi-hat style)
"""

import sys
import os
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from synth_snapshot import analyze, snapshot_to_json, render_svg, GBSnapshotConfig


SR = 44100  # SameBoy default output rate


def _adsr(n, sr, a_ms, d_ms, sus, r_ms):
    """Generate an ADSR envelope."""
    a = int(a_ms * sr / 1000)
    d = int(d_ms * sr / 1000)
    r = int(r_ms * sr / 1000)
    s_len = max(0, n - a - d - r)
    env = np.zeros(n)
    pos = 0
    env[pos:pos+a] = np.linspace(0, 1, a); pos += a
    env[pos:pos+d] = np.linspace(1, sus, d); pos += d
    env[pos:pos+s_len] = sus; pos += s_len
    actual_r = min(r, n - pos)
    if actual_r > 0:
        env[pos:pos+actual_r] = np.linspace(sus, 0, actual_r)
    return env


def _gb_pulse(freq, n, sr, duty=0.5):
    """Band-limited pulse wave approximating GB output.

    The real GB DAC is 4-bit, so we quantize to 16 levels.
    """
    t = np.arange(n) / sr
    max_harmonic = min(int(sr / (2 * freq)), 30)
    signal = np.zeros(n)

    # Additive synthesis for band-limited pulse
    for k in range(1, max_harmonic + 1):
        coeff = np.sin(k * np.pi * duty) / (k * np.pi) * 2
        signal += coeff * np.sin(2 * np.pi * k * freq * t)

    # Quantize to 4-bit (16 levels) to match GB DAC
    signal = np.round(signal * 7.5) / 7.5

    return signal


def _gb_wavetable(freq, n, sr, table):
    """Wavetable synthesis from a 32-sample 4-bit table.

    The GB WAV channel plays back a 32-sample waveform from RAM
    at a programmable rate.
    """
    t = np.arange(n) / sr
    phase = (t * freq) % 1.0
    indices = (phase * len(table)).astype(int) % len(table)
    # Table values 0-15 -> -1.0 to 1.0
    signal = np.array([table[i] for i in indices], dtype=np.float64)
    signal = (signal / 7.5) - 1.0
    return signal


def _gb_noise(n, sr, lfsr_7bit=False):
    """LFSR noise approximating GB noise channel.

    7-bit LFSR: 127-step cycle, very tonal
    15-bit LFSR: 32767-step cycle, white-ish noise
    """
    bits = 7 if lfsr_7bit else 15
    mask = (1 << bits) - 1
    lfsr = mask

    # Generate LFSR output at ~262kHz (GB clock / 4 roughly)
    # then downsample
    gb_rate = 262144
    n_gb = int(n * gb_rate / sr) + 1
    raw = np.zeros(n_gb)

    for i in range(n_gb):
        raw[i] = 1.0 if (lfsr & 1) else -1.0
        bit = ((lfsr >> 0) ^ (lfsr >> 1)) & 1
        lfsr = (lfsr >> 1) | (bit << (bits - 1))
        lfsr &= mask

    # Downsample to output rate (simple decimation with averaging)
    ratio = gb_rate / sr
    signal = np.zeros(n)
    for i in range(n):
        start = int(i * ratio)
        end = min(int((i + 1) * ratio), n_gb)
        signal[i] = np.mean(raw[start:end])

    # Quantize to 4-bit
    signal = np.round(signal * 7.5) / 7.5
    return signal


def test_pu1_square(out_dir):
    """PU1: 50% duty pulse at C4 (≈261.6Hz), custom ADSR, center pan."""
    dur_ms = 600
    n = int(dur_ms * SR / 1000)

    osc = _gb_pulse(261.6, n, SR, duty=0.5)
    env = _adsr(n, SR, a_ms=15, d_ms=80, sus=0.6, r_ms=200)
    signal = osc * env * 0.8

    # Center pan
    left = signal
    right = signal

    cfg = GBSnapshotConfig(channel="PU1")
    snap = analyze(left, right, SR, cfg)

    _write(snap, out_dir, "pu1_c4_50pct")


def test_pu2_panning(out_dir):
    """PU2: 25% duty at A4 (440Hz), panning changes L->C mid-note."""
    dur_ms = 500
    n = int(dur_ms * SR / 1000)

    osc = _gb_pulse(440.0, n, SR, duty=0.25)
    env = _adsr(n, SR, a_ms=5, d_ms=40, sus=0.7, r_ms=150)
    signal = osc * env * 0.75

    # First half: left only. Second half: center.
    mid = n // 2
    left = signal.copy()
    right = np.zeros(n)
    right[mid:] = signal[mid:]  # Right channel joins halfway

    cfg = GBSnapshotConfig(channel="PU2")
    snap = analyze(left, right, SR, cfg)

    _write(snap, out_dir, "pu2_a4_25pct_pan")


def test_wav_custom(out_dir):
    """WAV: Custom wavetable at E3 (≈164.8Hz), slow attack."""
    dur_ms = 800
    n = int(dur_ms * SR / 1000)

    # A sawtooth-ish wavetable (32 x 4-bit values)
    table = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15,
             15, 14, 13, 12, 10, 8, 6, 4, 3, 2, 1, 0, 0, 0, 0, 0]

    osc = _gb_wavetable(164.8, n, SR, table)
    env = _adsr(n, SR, a_ms=100, d_ms=50, sus=0.8, r_ms=300)
    signal = osc * env * 0.7

    left = signal
    right = signal

    cfg = GBSnapshotConfig(channel="WAV")
    snap = analyze(left, right, SR, cfg)

    _write(snap, out_dir, "wav_e3_custom")


def test_noi_hihat(out_dir):
    """NOI: 15-bit noise, fast decay (hi-hat style)."""
    dur_ms = 300
    n = int(dur_ms * SR / 1000)

    osc = _gb_noise(n, SR, lfsr_7bit=False)
    env = _adsr(n, SR, a_ms=1, d_ms=60, sus=0.0, r_ms=1)
    signal = osc * env * 0.6

    left = signal
    right = signal

    cfg = GBSnapshotConfig(channel="NOI")
    snap = analyze(left, right, SR, cfg)

    _write(snap, out_dir, "noi_hihat_15bit")


def _write(snap, out_dir, name):
    json_path = os.path.join(out_dir, f"{name}.snap.json")
    svg_path = os.path.join(out_dir, f"{name}.svg")
    with open(json_path, "w") as f:
        f.write(snapshot_to_json(snap))
    with open(svg_path, "w") as f:
        f.write(render_svg(snap))
    print(f"  {json_path}")
    print(f"  {svg_path}")


def main():
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_output")
    os.makedirs(out, exist_ok=True)

    print("Generating GB synth snapshot demos...\n")

    print("1. PU1 — 50% duty C4 with ADSR:")
    test_pu1_square(out)

    print("\n2. PU2 — 25% duty A4 with panning change:")
    test_pu2_panning(out)

    print("\n3. WAV — custom wavetable E3:")
    test_wav_custom(out)

    print("\n4. NOI — 15-bit hi-hat:")
    test_noi_hihat(out)

    print(f"\nAll outputs in: {out}")


if __name__ == "__main__":
    main()
