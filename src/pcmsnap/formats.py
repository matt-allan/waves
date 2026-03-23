"""Audio file format loaders.

Supports:
  - Raw signed 16-bit interleaved stereo
  - WAV (via stdlib wave module)
  - AIFF (via stdlib aifc module, Python <= 3.12)

All loaders return a ``StereoAudio`` with float64 arrays in [-1.0, 1.0].
"""

from __future__ import annotations

import struct
import wave
from typing import Literal

import numpy as np

from ._types import StereoAudio

try:
    import aifc

    _HAS_AIFC = True
except ImportError:
    _HAS_AIFC = False


def load_raw(
    path: str,
    sample_rate: int,
    channels: int = 2,
    bit_depth: int = 16,
    byte_order: Literal["little", "big"] = "little",
) -> StereoAudio:
    """Load raw signed 16-bit PCM audio.

    For mono input, right is a copy of left.
    """
    if bit_depth != 16:
        raise ValueError(f"Only 16-bit supported, got {bit_depth}")

    with open(path, "rb") as f:
        raw = f.read()

    fmt = "<" if byte_order == "little" else ">"
    n_samples = len(raw) // 2
    samples = np.array(struct.unpack(f"{fmt}{n_samples}h", raw), dtype=np.float64)
    samples /= 32768.0

    if channels == 2:
        left = samples[0::2]
        right = samples[1::2]
    else:
        left = samples
        right = samples.copy()

    return StereoAudio(left=left, right=right, sample_rate=sample_rate)


def load_wav(path: str) -> StereoAudio:
    """Load a WAV file."""
    with wave.open(path, "rb") as w:
        n_channels = w.getnchannels()
        sampwidth = w.getsampwidth()
        sample_rate = w.getframerate()
        n_frames = w.getnframes()
        raw = w.readframes(n_frames)

    if sampwidth == 2:
        samples = np.frombuffer(raw, dtype=np.int16).astype(np.float64) / 32768.0
    elif sampwidth == 3:
        n_samples = len(raw) // 3
        samples = np.zeros(n_samples, dtype=np.float64)
        for i in range(n_samples):
            b = raw[i * 3 : (i + 1) * 3]
            val = int.from_bytes(b, byteorder="little", signed=True)
            samples[i] = val / 8388608.0
    elif sampwidth == 1:
        samples = (
            np.frombuffer(raw, dtype=np.uint8).astype(np.float64) - 128.0
        ) / 128.0
    else:
        raise ValueError(f"Unsupported sample width: {sampwidth} bytes")

    left, right = _deinterleave(samples, n_channels)
    return StereoAudio(left=left, right=right, sample_rate=sample_rate)


def load_aiff(path: str) -> StereoAudio:
    """Load an AIFF file."""
    if not _HAS_AIFC:
        raise ImportError(
            "aifc module not available (removed in Python 3.13+). "
            "Convert AIFF to WAV first, or use Python <= 3.12."
        )

    with aifc.open(path, "rb") as a:
        n_channels = a.getnchannels()
        sampwidth = a.getsampwidth()
        sample_rate = a.getframerate()
        n_frames = a.getnframes()
        raw = a.readframes(n_frames)

    if sampwidth == 2:
        samples = np.frombuffer(raw, dtype=np.dtype(">i2")).astype(np.float64) / 32768.0
    elif sampwidth == 1:
        samples = (
            np.frombuffer(raw, dtype=np.uint8).astype(np.float64) - 128.0
        ) / 128.0
    else:
        raise ValueError(f"Unsupported AIFF sample width: {sampwidth}")

    left, right = _deinterleave(samples, n_channels)
    return StereoAudio(left=left, right=right, sample_rate=sample_rate)


def load_audio(
    path: str,
    format: str = "auto",
    sample_rate: int = 44100,
    channels: int = 2,
    bit_depth: int = 16,
    byte_order: Literal["little", "big"] = "little",
) -> StereoAudio:
    """Load audio from any supported format.

    *format* may be ``'raw'``, ``'wav'``, ``'aiff'``, or ``'auto'``
    (detect from extension).  *sample_rate*, *channels*, *bit_depth*, and
    *byte_order* are only used for raw format.
    """
    if format == "auto":
        ext = path.lower().rsplit(".", 1)[-1] if "." in path else ""
        format = {
            "wav": "wav",
            "wave": "wav",
            "aif": "aiff",
            "aiff": "aiff",
            "raw": "raw",
            "pcm": "raw",
        }.get(ext, "raw")

    if format == "wav":
        return load_wav(path)
    elif format == "aiff":
        return load_aiff(path)
    elif format == "raw":
        return load_raw(path, sample_rate, channels, bit_depth, byte_order)
    else:
        raise ValueError(f"Unknown format: {format}")


def _deinterleave(
    samples: np.ndarray, n_channels: int
) -> tuple[np.ndarray, np.ndarray]:
    """Split interleaved samples into left and right channels."""
    if n_channels == 2:
        return samples[0::2], samples[1::2]
    elif n_channels == 1:
        return samples, samples.copy()
    else:
        return samples[0::n_channels], samples[1::n_channels]
