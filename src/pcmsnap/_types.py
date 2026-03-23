"""Core types for pcmsnap snapshot data.

All snapshot data is represented as typed dataclasses rather than plain dicts,
giving proper IDE support, validation, and self-documenting structure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional


ChannelType = Literal["PU1", "PU2", "WAV", "NOI", "auto"]
PanState = Literal["C", "L", "R", "-"]


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class SnapshotConfig:
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
# Audio data
# ---------------------------------------------------------------------------

@dataclass
class StereoAudio:
    """Stereo audio data normalized to [-1.0, 1.0]."""

    left: "np.ndarray"  # float64
    right: "np.ndarray"  # float64
    sample_rate: int


# ---------------------------------------------------------------------------
# Snapshot sections
# ---------------------------------------------------------------------------

@dataclass
class Meta:
    """Snapshot metadata."""

    version: int
    format: str
    sample_rate: int
    channels: int
    duration_ms: float
    n_samples: int


@dataclass
class ChannelSummary:
    """Per-channel amplitude summary."""

    peak: float
    rms: float
    dc_offset: float


@dataclass
class Summary:
    """Summary statistics for both channels."""

    left: ChannelSummary
    right: ChannelSummary


@dataclass
class Envelope:
    """Amplitude envelope over time windows."""

    window_ms: float
    n_windows: int
    left: list[float]
    right: list[float]


@dataclass
class PanningRun:
    """A run-length encoded panning segment."""

    state: PanState
    count: int

    def __str__(self) -> str:
        if self.count > 1:
            return f"{self.state}x{self.count}"
        return self.state


@dataclass
class Panning:
    """Binary panning state per window."""

    window_ms: float
    n_windows: int
    runs: list[PanningRun]

    @property
    def states_str(self) -> str:
        return " ".join(str(r) for r in self.runs)

    def expand(self) -> list[PanState]:
        """Expand runs into a flat list of per-window states."""
        out: list[PanState] = []
        for r in self.runs:
            out.extend([r.state] * r.count)
        return out

    @staticmethod
    def from_states(window_ms: float, states: list[PanState]) -> "Panning":
        """Create from a flat list of per-window states (RLE-compressed)."""
        runs: list[PanningRun] = []
        if states:
            cur, count = states[0], 1
            for st in states[1:]:
                if st == cur:
                    count += 1
                else:
                    runs.append(PanningRun(state=cur, count=count))
                    cur, count = st, 1
            runs.append(PanningRun(state=cur, count=count))
        return Panning(window_ms=window_ms, n_windows=len(states), runs=runs)

    @staticmethod
    def parse_states_str(s: str) -> list[PanningRun]:
        """Parse an RLE string like 'Cx50 -x20 L' into runs."""
        runs: list[PanningRun] = []
        for tok in s.split():
            if "x" in tok:
                state, cnt = tok.split("x", 1)
                runs.append(PanningRun(state=state, count=int(cnt)))  # type: ignore[arg-type]
            else:
                runs.append(PanningRun(state=tok, count=1))  # type: ignore[arg-type]
        return runs


@dataclass
class SpectralPeak:
    """A single spectral peak (frequency, magnitude)."""

    freq_hz: float
    mag_db: float


@dataclass
class PulseTimbre:
    """Timbre data for PU1/PU2 channels."""

    channel: Literal["PU1", "PU2"]
    fundamental_hz: Optional[float] = None
    duty_cycle: Optional[str] = None


@dataclass
class WavTimbre:
    """Timbre data for WAV channel."""

    channel: Literal["WAV"] = "WAV"
    fundamental_hz: Optional[float] = None
    spectrum: list[SpectralPeak] = field(default_factory=list)


@dataclass
class NoiseTimbre:
    """Timbre data for NOI channel."""

    channel: Literal["NOI"] = "NOI"
    lfsr_mode: Optional[str] = None


Timbre = PulseTimbre | WavTimbre | NoiseTimbre


@dataclass
class WaveformDigest:
    """Resampled waveform snippet for visual comparison."""

    fundamental_hz: float
    num_cycles: int
    points_per_cycle: int
    offset_ms: float
    values: list[float]


# ---------------------------------------------------------------------------
# Top-level snapshot
# ---------------------------------------------------------------------------

@dataclass
class Snapshot:
    """Complete audio snapshot for one channel."""

    meta: Meta
    summary: Summary
    envelope: Envelope
    timbre: Timbre
    panning: Panning
    waveform: Optional[WaveformDigest] = None
