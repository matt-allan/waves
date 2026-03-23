"""JSON serialization and deserialization for typed snapshots.

The JSON format is compact and git-diff-friendly:
  - Numeric arrays are chunked into 20-item rows
  - [freq, mag] pairs are kept inline
  - Floats are trimmed of trailing zeros
"""

from __future__ import annotations

import json
from typing import Any

from ._types import (
    ChannelSummary,
    Envelope,
    Meta,
    NoiseTimbre,
    Panning,
    PanningRun,
    PulseTimbre,
    Snapshot,
    SpectralPeak,
    Summary,
    Timbre,
    WavTimbre,
    WaveformDigest,
)


# ---------------------------------------------------------------------------
# Snapshot -> JSON
# ---------------------------------------------------------------------------


def snapshot_to_dict(snap: Snapshot) -> dict[str, Any]:
    """Convert a typed Snapshot to a plain dict suitable for JSON encoding."""
    d: dict[str, Any] = {
        "meta": {
            "version": snap.meta.version,
            "format": snap.meta.format,
            "sample_rate": snap.meta.sample_rate,
            "channels": snap.meta.channels,
            "duration_ms": snap.meta.duration_ms,
            "n_samples": snap.meta.n_samples,
        },
        "summary": {
            "left": _channel_summary_dict(snap.summary.left),
            "right": _channel_summary_dict(snap.summary.right),
        },
        "envelope": {
            "window_ms": snap.envelope.window_ms,
            "n_windows": snap.envelope.n_windows,
            "left": snap.envelope.left,
            "right": snap.envelope.right,
        },
        "timbre": _timbre_dict(snap.timbre),
        "panning": {
            "window_ms": snap.panning.window_ms,
            "n_windows": snap.panning.n_windows,
            "states": snap.panning.states_str,
        },
    }

    if snap.waveform is not None:
        d["waveform"] = {
            "fundamental_hz": snap.waveform.fundamental_hz,
            "num_cycles": snap.waveform.num_cycles,
            "points_per_cycle": snap.waveform.points_per_cycle,
            "offset_ms": snap.waveform.offset_ms,
            "values": snap.waveform.values,
        }

    return d


def snapshot_to_json(snap: Snapshot) -> str:
    """Serialize a Snapshot to compact, git-diff-friendly JSON."""
    d = snapshot_to_dict(snap)
    return _CompactEncoder().encode(d) + "\n"


# ---------------------------------------------------------------------------
# JSON -> Snapshot
# ---------------------------------------------------------------------------


def snapshot_from_json(text: str) -> Snapshot:
    """Deserialize JSON text into a typed Snapshot."""
    d = json.loads(text)
    return snapshot_from_dict(d)


def snapshot_from_dict(d: dict[str, Any]) -> Snapshot:
    """Convert a plain dict into a typed Snapshot."""
    m = d["meta"]
    meta = Meta(
        version=m["version"],
        format=m["format"],
        sample_rate=m["sample_rate"],
        channels=m["channels"],
        duration_ms=m["duration_ms"],
        n_samples=m["n_samples"],
    )

    s = d["summary"]
    summary = Summary(
        left=_parse_channel_summary(s["left"]),
        right=_parse_channel_summary(s["right"]),
    )

    e = d["envelope"]
    envelope = Envelope(
        window_ms=e["window_ms"],
        n_windows=e["n_windows"],
        left=e["left"],
        right=e["right"],
    )

    timbre = _parse_timbre(d["timbre"])

    p = d["panning"]
    panning = Panning(
        window_ms=p["window_ms"],
        n_windows=p["n_windows"],
        runs=Panning.parse_states_str(p["states"]),
    )

    waveform = None
    if "waveform" in d:
        w = d["waveform"]
        waveform = WaveformDigest(
            fundamental_hz=w["fundamental_hz"],
            num_cycles=w["num_cycles"],
            points_per_cycle=w["points_per_cycle"],
            offset_ms=w["offset_ms"],
            values=w["values"],
        )

    return Snapshot(
        meta=meta,
        summary=summary,
        envelope=envelope,
        timbre=timbre,
        panning=panning,
        waveform=waveform,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _channel_summary_dict(cs: ChannelSummary) -> dict[str, float]:
    return {"peak": cs.peak, "rms": cs.rms, "dc_offset": cs.dc_offset}


def _parse_channel_summary(d: dict[str, float]) -> ChannelSummary:
    return ChannelSummary(peak=d["peak"], rms=d["rms"], dc_offset=d["dc_offset"])


def _timbre_dict(t: Timbre) -> dict[str, Any]:
    if isinstance(t, PulseTimbre):
        d: dict[str, Any] = {"channel": t.channel}
        if t.fundamental_hz is not None:
            d["fundamental_hz"] = t.fundamental_hz
        if t.duty_cycle is not None:
            d["duty_cycle"] = t.duty_cycle
        return d
    elif isinstance(t, WavTimbre):
        d = {"channel": "WAV"}
        if t.fundamental_hz is not None:
            d["fundamental_hz"] = t.fundamental_hz
        if t.spectrum:
            d["spectrum"] = [
                [pk.freq_hz, pk.mag_db] for pk in t.spectrum
            ]
        return d
    elif isinstance(t, NoiseTimbre):
        d = {"channel": "NOI"}
        if t.lfsr_mode is not None:
            d["lfsr_mode"] = t.lfsr_mode
        return d
    else:
        return {"channel": "??"}


def _parse_timbre(d: dict[str, Any]) -> Timbre:
    ch = d.get("channel", "PU1")
    if ch in ("PU1", "PU2"):
        return PulseTimbre(
            channel=ch,
            fundamental_hz=d.get("fundamental_hz"),
            duty_cycle=d.get("duty_cycle"),
        )
    elif ch == "WAV":
        spectrum = [
            SpectralPeak(freq_hz=p[0], mag_db=p[1])
            for p in d.get("spectrum", [])
        ]
        return WavTimbre(
            fundamental_hz=d.get("fundamental_hz"),
            spectrum=spectrum,
        )
    elif ch == "NOI":
        return NoiseTimbre(lfsr_mode=d.get("lfsr_mode"))
    else:
        return PulseTimbre(channel="PU1")


# ---------------------------------------------------------------------------
# Compact JSON encoder (git-diff-friendly)
# ---------------------------------------------------------------------------


class _CompactEncoder(json.JSONEncoder):
    CHUNK = 20

    def encode(self, obj: Any) -> str:
        return self._enc(obj, 0)

    def _enc(self, obj: Any, ind: int) -> str:
        sp = "  " * ind
        if isinstance(obj, dict):
            if not obj:
                return "{}"
            items = [
                f'{sp}  "{k}": {self._enc(v, ind + 1)}'
                for k, v in obj.items()
            ]
            return "{\n" + ",\n".join(items) + f"\n{sp}}}"
        elif isinstance(obj, list):
            if not obj:
                return "[]"
            if all(isinstance(x, (int, float)) for x in obj):
                if len(obj) <= self.CHUNK:
                    return "[" + ", ".join(self._num(x) for x in obj) + "]"
                rows = []
                for i in range(0, len(obj), self.CHUNK):
                    c = obj[i : i + self.CHUNK]
                    rows.append(
                        sp + "  " + ", ".join(self._num(x) for x in c)
                    )
                return "[\n" + ",\n".join(rows) + f"\n{sp}]"
            if all(
                isinstance(x, list) and len(x) == 2 for x in obj
            ) and all(isinstance(v, (int, float)) for x in obj for v in x):
                items = [
                    f"[{self._num(x[0])}, {self._num(x[1])}]" for x in obj
                ]
                if len(obj) <= 8:
                    return "[" + ", ".join(items) + "]"
                return (
                    "[\n"
                    + ",\n".join(sp + "  " + it for it in items)
                    + f"\n{sp}]"
                )
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
    def _num(x: int | float) -> str:
        if isinstance(x, int):
            return str(x)
        if x == 0.0:
            return "0.0"
        s = f"{x:.6f}".rstrip("0")
        if s.endswith("."):
            s += "0"
        return s
