"""Core audio analysis for Game Boy synth snapshot generation.

Tailored for the Game Boy APU's 4 channels:
  - PU1/PU2: Pulse waves with 4 duty cycles (12.5%, 25%, 50%, 75%)
  - WAV: 4-bit wavetable (32 samples)
  - NOI: Noise (7-bit or 15-bit LFSR)

Captures:
  - Summary statistics (peak, RMS, DC offset)
  - Amplitude envelope at fine resolution (the main event for custom ADSR)
  - Channel-type-aware timbre detection (duty cycle, noise mode, fundamental)
  - Binary panning state per window (L / R / C / silent)
  - Waveform digest (pulse/WAV only)
"""

import json
from dataclasses import dataclass
from typing import Optional, Literal
import numpy as np


ChannelType = Literal["PU1", "PU2", "WAV", "NOI", "auto"]

# GB DAC is 4-bit (16 levels).  Three decimal places already gives us
# plenty of headroom without recording emulator interpolation noise.
_AMP_PREC  = 3
_DB_PREC   = 1
_FREQ_PREC = 1
_TIME_PREC = 1


@dataclass
class GBSnapshotConfig:
    """Configuration for GB snapshot analysis."""

    channel: ChannelType = "auto"

    # Envelope — finer window than a general synth because GB volume
    # changes are fast and the custom ADSR is the main thing under test.
    envelope_window_ms: float = 5.0

    # Timbre detection
    fft_size: int = 2048
    noise_floor_db: float = -48.0

    # Spectrum — only emitted for WAV channel (arbitrary wavetable)
    spectrum_max_peaks: int = 16

    # Waveform digest
    waveform_points_per_cycle: int = 64
    waveform_num_cycles: int = 2

    # Panning
    panning_window_ms: float = 5.0
    silence_threshold: float = 0.005


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(x ** 2))) if len(x) else 0.0

def _peak(x: np.ndarray) -> float:
    return float(np.max(np.abs(x))) if len(x) else 0.0

def _dc_offset(x: np.ndarray) -> float:
    return float(np.mean(x)) if len(x) else 0.0


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def compute_summary(left: np.ndarray, right: np.ndarray) -> dict:
    def _ch(ch):
        return {
            "peak": round(_peak(ch), _AMP_PREC),
            "rms": round(_rms(ch), _AMP_PREC),
            "dc_offset": round(_dc_offset(ch), _AMP_PREC),
        }
    return {"left": _ch(left), "right": _ch(right)}


# ---------------------------------------------------------------------------
# Envelope  (the star of the show for custom ADSR testing)
# ---------------------------------------------------------------------------

def compute_envelope(left: np.ndarray, right: np.ndarray,
                     sample_rate: int, cfg: GBSnapshotConfig) -> dict:
    win = max(1, int(cfg.envelope_window_ms * sample_rate / 1000))
    n_windows = len(left) // win

    env_l, env_r = [], []
    for i in range(n_windows):
        s, e = i * win, (i + 1) * win
        env_l.append(round(_rms(left[s:e]), _AMP_PREC))
        env_r.append(round(_rms(right[s:e]), _AMP_PREC))

    return {
        "window_ms": cfg.envelope_window_ms,
        "n_windows": n_windows,
        "left": env_l,
        "right": env_r,
    }


# ---------------------------------------------------------------------------
# Panning  (binary: L / R / C / silent)
# ---------------------------------------------------------------------------

def compute_panning(left: np.ndarray, right: np.ndarray,
                    sample_rate: int, cfg: GBSnapshotConfig) -> dict:
    """Detect per-window panning state.

    GB panning is binary per channel via NR51.  We detect from signal:
      'C' = center (both channels active)
      'L' = left only
      'R' = right only
      '-' = silent
    """
    win = max(1, int(cfg.panning_window_ms * sample_rate / 1000))
    n_windows = len(left) // win
    thr = cfg.silence_threshold

    states = []
    for i in range(n_windows):
        s, e = i * win, (i + 1) * win
        l_on = _rms(left[s:e]) > thr
        r_on = _rms(right[s:e]) > thr

        if l_on and r_on:
            states.append("C")
        elif l_on:
            states.append("L")
        elif r_on:
            states.append("R")
        else:
            states.append("-")

    # Run-length encode for compact, readable diffs.
    # e.g. "Cx50 -x20" instead of 70 individual characters.
    runs = []
    if states:
        cur, count = states[0], 1
        for st in states[1:]:
            if st == cur:
                count += 1
            else:
                runs.append(f"{cur}x{count}" if count > 1 else cur)
                cur, count = st, 1
        runs.append(f"{cur}x{count}" if count > 1 else cur)

    return {
        "window_ms": cfg.panning_window_ms,
        "n_windows": n_windows,
        "states": " ".join(runs),
    }


# ---------------------------------------------------------------------------
# Timbre detection  (channel-type aware)
# ---------------------------------------------------------------------------

def _detect_fundamental(signal: np.ndarray, sample_rate: int,
                        min_freq: float = 20.0,
                        max_freq: float = 8000.0) -> Optional[float]:
    min_lag = int(sample_rate / max_freq)
    max_lag = min(int(sample_rate / min_freq), len(signal) - 1)
    if min_lag >= max_lag:
        return None

    sig = signal - np.mean(signal)
    if np.max(np.abs(sig)) < 1e-6:
        return None

    corr = np.correlate(sig, sig, mode="full")
    corr = corr[len(corr) // 2:]
    if corr[0] > 0:
        corr = corr / corr[0]

    search = corr[min_lag:max_lag]
    if len(search) < 3:
        return None

    peaks = []
    for i in range(1, len(search) - 1):
        if search[i] > search[i-1] and search[i] > search[i+1] and search[i] > 0.3:
            peaks.append((i + min_lag, search[i]))

    if not peaks:
        return None

    best_lag = max(peaks, key=lambda x: x[1])[0]
    return sample_rate / best_lag


def _detect_duty_cycle(signal: np.ndarray, sample_rate: int,
                       fundamental: float) -> Optional[str]:
    """Detect pulse duty cycle from harmonic ratios.

    GB duty cycles and their spectral signatures:
      12.5% — all harmonics, every 8th suppressed
      25%   — every 4th harmonic suppressed
      50%   — only odd harmonics (square wave)
      75%   — same spectrum as 25% (inverted waveform)
    """
    n = len(signal)
    fft = np.fft.rfft(signal * np.hanning(n))
    mag = np.abs(fft)

    harmonic_mag = []
    for k in range(1, 9):
        target = fundamental * k
        idx = int(round(target * n / sample_rate))
        if 0 < idx < len(mag):
            lo, hi = max(0, idx - 2), min(len(mag), idx + 3)
            harmonic_mag.append(float(np.max(mag[lo:hi])))
        else:
            harmonic_mag.append(0.0)

    if harmonic_mag[0] < 1e-6:
        return None

    h = [m / harmonic_mag[0] for m in harmonic_mag]

    # 50% duty: even harmonics near zero
    even_energy = (h[1] + h[3] + h[5] + h[7]) / 4
    if even_energy < 0.15:
        return "50%"

    # 25%/75%: every 4th harmonic suppressed
    fourth_energy = (h[3] + h[7]) / 2
    if fourth_energy < 0.15:
        return "25%"

    # 12.5%: every 8th suppressed
    if h[7] < 0.15:
        return "12.5%"

    return None


def _detect_noise_mode(signal: np.ndarray, sample_rate: int) -> Optional[str]:
    """Detect 7-bit (tonal) vs 15-bit (white) LFSR mode.

    7-bit produces a short repeating pattern with strong spectral peaks.
    15-bit is much flatter spectrally.
    """
    n = min(len(signal), 8192)
    chunk = signal[:n]
    if _rms(chunk) < 0.005:
        return None

    fft = np.fft.rfft(chunk * np.hanning(n))
    mag = np.abs(fft)
    if np.max(mag) < 1e-6:
        return None

    log_mag = np.log(mag[1:] + 1e-10)
    geo_mean = np.exp(np.mean(log_mag))
    arith_mean = np.mean(mag[1:])
    flatness = geo_mean / arith_mean if arith_mean > 0 else 0

    return "15-bit" if flatness > 0.3 else "7-bit"


def compute_timbre(left: np.ndarray, right: np.ndarray,
                   sample_rate: int, cfg: GBSnapshotConfig) -> dict:
    """Channel-type-aware timbre detection."""
    mono = left if _rms(left) >= _rms(right) else right

    # Use loudest 50ms window for analysis
    win = max(1, int(50 * sample_rate / 1000))
    n_wins = len(mono) // win
    if n_wins == 0:
        return {"channel": cfg.channel, "note": "signal too short"}

    rms_per_win = [_rms(mono[i*win:(i+1)*win]) for i in range(n_wins)]
    best_win = int(np.argmax(rms_per_win))
    chunk = mono[best_win * win:(best_win + 1) * win]

    channel = cfg.channel

    if channel == "auto":
        fund = _detect_fundamental(chunk, sample_rate)
        channel = "NOI" if fund is None else "PU1"

    result = {"channel": channel}

    if channel in ("PU1", "PU2"):
        fund = _detect_fundamental(chunk, sample_rate)
        if fund is not None:
            result["fundamental_hz"] = round(fund, _FREQ_PREC)
            duty = _detect_duty_cycle(chunk, sample_rate, fund)
            if duty is not None:
                result["duty_cycle"] = duty

    elif channel == "WAV":
        fund = _detect_fundamental(chunk, sample_rate)
        if fund is not None:
            result["fundamental_hz"] = round(fund, _FREQ_PREC)

        # Lightweight spectrum — WAV wavetable can be arbitrary
        n = len(chunk)
        fft = np.fft.rfft(chunk * np.hanning(n))
        freqs = np.fft.rfftfreq(n, 1.0 / sample_rate)
        mag_db = 20 * np.log10(np.abs(fft) / (n / 2) + 1e-10)

        peaks = []
        for i in range(1, len(mag_db) - 1):
            if (mag_db[i] > cfg.noise_floor_db and
                    mag_db[i] >= mag_db[i-1] and
                    mag_db[i] >= mag_db[i+1]):
                peaks.append([round(float(freqs[i]), _FREQ_PREC),
                              round(float(mag_db[i]), _DB_PREC)])
        peaks.sort(key=lambda x: x[1], reverse=True)
        peaks = peaks[:cfg.spectrum_max_peaks]
        peaks.sort(key=lambda x: x[0])
        result["spectrum"] = peaks

    elif channel == "NOI":
        mode = _detect_noise_mode(chunk, sample_rate)
        if mode is not None:
            result["lfsr_mode"] = mode

    return result


# ---------------------------------------------------------------------------
# Waveform digest  (pulse/WAV only — meaningless for noise)
# ---------------------------------------------------------------------------

def compute_waveform_digest(left: np.ndarray, right: np.ndarray,
                            sample_rate: int,
                            cfg: GBSnapshotConfig) -> Optional[dict]:
    if cfg.channel == "NOI":
        return None

    mono = left if _rms(left) >= _rms(right) else right

    win = max(1, int(50 * sample_rate / 1000))
    n_wins = len(mono) // win
    if n_wins < 2:
        return None

    rms_per_win = [_rms(mono[i*win:(i+1)*win]) for i in range(n_wins)]
    best_win = int(np.argmax(rms_per_win))
    region_start = best_win * win
    region_end = min(region_start + win * 3, len(mono))
    chunk = mono[region_start:region_end]

    freq = _detect_fundamental(chunk, sample_rate)
    if freq is None or freq < 20:
        return None

    period = sample_rate / freq
    total = int(period * cfg.waveform_num_cycles)
    if total > len(chunk):
        return None

    start = 0
    for i in range(1, min(int(period), len(chunk))):
        if chunk[i-1] <= 0 < chunk[i]:
            start = i
            break

    end = start + total
    if end > len(chunk):
        end = len(chunk)
        start = max(0, end - total)

    n_points = cfg.waveform_points_per_cycle * cfg.waveform_num_cycles
    seg = chunk[start:end]
    if len(seg) < 4:
        return None

    x_orig = np.linspace(0, 1, len(seg))
    x_resamp = np.linspace(0, 1, n_points)
    resampled = np.interp(x_resamp, x_orig, seg)

    return {
        "fundamental_hz": round(freq, _FREQ_PREC),
        "num_cycles": cfg.waveform_num_cycles,
        "points_per_cycle": cfg.waveform_points_per_cycle,
        "offset_ms": round(region_start / sample_rate * 1000, _TIME_PREC),
        "values": [round(float(v), _AMP_PREC) for v in resampled],
    }


# ---------------------------------------------------------------------------
# Top-level
# ---------------------------------------------------------------------------

def analyze(left: np.ndarray, right: np.ndarray, sample_rate: int,
            config: Optional[GBSnapshotConfig] = None) -> dict:
    if config is None:
        config = GBSnapshotConfig()

    duration_ms = round(len(left) / sample_rate * 1000, _TIME_PREC)

    snapshot = {
        "meta": {
            "version": 2,
            "format": "gb-synth-snapshot",
            "sample_rate": sample_rate,
            "channels": 2,
            "duration_ms": duration_ms,
            "n_samples": len(left),
        },
        "summary": compute_summary(left, right),
        "envelope": compute_envelope(left, right, sample_rate, config),
        "timbre": compute_timbre(left, right, sample_rate, config),
        "panning": compute_panning(left, right, sample_rate, config),
    }

    waveform = compute_waveform_digest(left, right, sample_rate, config)
    if waveform is not None:
        snapshot["waveform"] = waveform

    return snapshot


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

class _CompactEncoder(json.JSONEncoder):
    CHUNK = 20

    def encode(self, obj):
        return self._enc(obj, 0)

    def _enc(self, obj, ind):
        sp = "  " * ind
        if isinstance(obj, dict):
            if not obj:
                return "{}"
            items = [f'{sp}  "{k}": {self._enc(v, ind + 1)}'
                     for k, v in obj.items()]
            return "{\n" + ",\n".join(items) + f"\n{sp}}}"
        elif isinstance(obj, list):
            if not obj:
                return "[]"
            if all(isinstance(x, (int, float)) for x in obj):
                if len(obj) <= self.CHUNK:
                    return "[" + ", ".join(self._num(x) for x in obj) + "]"
                rows = []
                for i in range(0, len(obj), self.CHUNK):
                    c = obj[i:i + self.CHUNK]
                    rows.append(sp + "  " + ", ".join(self._num(x) for x in c))
                return "[\n" + ",\n".join(rows) + f"\n{sp}]"
            if (all(isinstance(x, list) and len(x) == 2 for x in obj) and
                    all(isinstance(v, (int, float)) for x in obj for v in x)):
                items = [f"[{self._num(x[0])}, {self._num(x[1])}]" for x in obj]
                if len(obj) <= 8:
                    return "[" + ", ".join(items) + "]"
                return "[\n" + ",\n".join(sp + "  " + it for it in items) + f"\n{sp}]"
            items = [sp + "  " + self._enc(x, ind + 1) for x in obj]
            return "[\n" + ",\n".join(items) + f"\n{sp}]"
        elif isinstance(obj, float):
            return self._num(obj)
        elif isinstance(obj, (int, bool)):
            return json.dumps(obj)
        elif obj is None:
            return "null"
        return json.dumps(obj)

    @staticmethod
    def _num(x):
        if isinstance(x, int):
            return str(x)
        if x == 0.0:
            return "0.0"
        s = f"{x:.6f}".rstrip("0")
        if s.endswith("."):
            s += "0"
        return s


def snapshot_to_json(snapshot: dict) -> str:
    return _CompactEncoder().encode(snapshot) + "\n"

def snapshot_from_json(text: str) -> dict:
    return json.loads(text)
