"""pcmsnap — Snapshot testing for Game Boy synth audio output.

Generates text-based, git-diffable snapshots of audio output, with optional
SVG rendering for human review.

Usage::

    from pcmsnap import analyze, snapshot_to_json, render_svg
    from pcmsnap import StereoAudio, SnapshotConfig

    audio = StereoAudio(left=left_array, right=right_array, sample_rate=44100)
    snap = analyze(audio)

    # Write JSON snapshot (for git)
    with open("test_pu1_saw.snap.json", "w") as f:
        f.write(snapshot_to_json(snap))

    # Render SVG (for humans)
    with open("test_pu1_saw.svg", "w") as f:
        f.write(render_svg(snap))
"""

from .analyze import analyze
from .formats import audio_from_bytes
from .render import render_svg, RenderConfig
from .serialize import (
    snapshot_to_json,
    snapshot_from_json,
    snapshot_to_dict,
    snapshot_from_dict,
)
from ._types import (
    ChannelType,
    SnapshotConfig,
    StereoAudio,
    Meta,
    ChannelSummary,
    Summary,
    Envelope,
    Panning,
    SpectralPeak,
    PulseTimbre,
    WavTimbre,
    NoiseTimbre,
    Timbre,
    WaveformDigest,
    Snapshot,
)

__all__ = [
    # Analysis
    "analyze",
    # Formats
    "audio_from_bytes",
    # Serialization
    "snapshot_to_json",
    "snapshot_from_json",
    "snapshot_to_dict",
    "snapshot_from_dict",
    # Rendering
    "render_svg",
    "RenderConfig",
    # Types
    "ChannelType",
    "SnapshotConfig",
    "StereoAudio",
    "Meta",
    "ChannelSummary",
    "Summary",
    "Envelope",
    "Panning",
    "SpectralPeak",
    "PulseTimbre",
    "WavTimbre",
    "NoiseTimbre",
    "Timbre",
    "WaveformDigest",
    "Snapshot",
]
