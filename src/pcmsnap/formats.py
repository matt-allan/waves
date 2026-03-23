"""Audio format loader — raw signed 16-bit PCM bytes only."""

from __future__ import annotations

import numpy as np

from ._types import StereoAudio


def audio_from_bytes(
    data: bytes,
    sample_rate: int = 44100,
    channels: int = 2,
) -> StereoAudio:
    """Create ``StereoAudio`` from raw signed 16-bit little-endian PCM bytes.

    *data* is interleaved int16 samples (L, R, L, R, ...).
    For mono input, right is a copy of left.
    """
    samples = np.frombuffer(data, dtype=np.dtype("<i2")).astype(np.float64)
    samples /= 32768.0

    if channels == 2:
        left = samples[0::2]
        right = samples[1::2]
    else:
        left = samples
        right = samples.copy()

    return StereoAudio(left=left, right=right, sample_rate=sample_rate)
