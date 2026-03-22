"""synth_snapshot — Snapshot testing for Game Boy synth engines.

Generates text-based, LLM-readable, git-diffable snapshots of audio output,
with optional SVG rendering for human review.

Usage:
    from synth_snapshot import load_audio, analyze, snapshot_to_json, render_svg

    left, right, sr = load_audio("output.wav")
    snap = analyze(left, right, sr)

    # Write JSON snapshot (for git)
    with open("test_pu1_saw.snap.json", "w") as f:
        f.write(snapshot_to_json(snap))

    # Render SVG (for humans)
    with open("test_pu1_saw.svg", "w") as f:
        f.write(render_svg(snap))
"""

from .formats import load_audio, load_raw, load_wav, load_aiff
from .analyze import (
    analyze,
    snapshot_to_json,
    snapshot_from_json,
    GBSnapshotConfig,
)
from .render import render_svg, RenderConfig

__all__ = [
    "load_audio", "load_raw", "load_wav", "load_aiff",
    "analyze", "snapshot_to_json", "snapshot_from_json", "GBSnapshotConfig",
    "render_svg", "RenderConfig",
]
