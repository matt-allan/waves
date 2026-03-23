"""JSON serialization and deserialization for typed snapshots."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from ._types import (
    ChannelSummary,
    Envelope,
    Meta,
    NoiseTimbre,
    Panning,
    PulseTimbre,
    Snapshot,
    SpectralPeak,
    Summary,
    Timbre,
    WavTimbre,
    WaveformDigest,
)


def snapshot_to_json(snap: Snapshot) -> str:
    return json.dumps(asdict(snap), indent=2)


def snapshot_from_json(text: str) -> Snapshot:
    return snapshot_from_dict(json.loads(text))


def snapshot_to_dict(snap: Snapshot) -> dict[str, Any]:
    return asdict(snap)


def snapshot_from_dict(d: dict[str, Any]) -> Snapshot:
    m = d["meta"]
    s = d["summary"]
    e = d["envelope"]
    p = d["panning"]
    w = d.get("waveform")

    return Snapshot(
        meta=Meta(**m),
        summary=Summary(
            left=ChannelSummary(**s["left"]),
            right=ChannelSummary(**s["right"]),
        ),
        envelope=Envelope(**e),
        timbre=_parse_timbre(d["timbre"]),
        panning=Panning(**p),
        waveform=WaveformDigest(**w) if w is not None else None,
    )


def _parse_timbre(d: dict[str, Any]) -> Timbre:
    ch = d.get("channel", "PU1")
    if ch in ("PU1", "PU2"):
        return PulseTimbre(**d)
    elif ch == "WAV":
        peaks = [SpectralPeak(**p) for p in d.get("spectrum", [])]
        return WavTimbre(
            fundamental_hz=d.get("fundamental_hz"),
            spectrum=peaks,
        )
    elif ch == "NOI":
        return NoiseTimbre(**d)
    else:
        return PulseTimbre(channel="PU1")
