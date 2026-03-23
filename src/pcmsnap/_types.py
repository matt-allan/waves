"""Core types for pcmsnap snapshot data."""

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
class Panning:
    """Per-window panning state."""

    window_ms: float
    states: list[PanState]


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
