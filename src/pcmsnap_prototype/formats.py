"""Audio file format loaders.

Supports:
  - Raw signed 16-bit interleaved stereo
  - WAV (via stdlib wave module)
  - AIFF (via stdlib aifc module)

All loaders return (left, right, sample_rate) where left/right are
numpy float64 arrays normalized to [-1.0, 1.0].
"""

import struct
import wave
import numpy as np

try:
    import aifc
    _HAS_AIFC = True
except ImportError:
    _HAS_AIFC = False


def load_raw(path: str, sample_rate: int, channels: int = 2,
             bit_depth: int = 16, byte_order: str = "little") -> tuple:
    """Load raw signed 16-bit PCM audio.

    Args:
        path: Path to raw audio file.
        sample_rate: Sample rate in Hz (must be provided; raw has no header).
        channels: Number of channels (1 or 2).
        bit_depth: Bits per sample (only 16 supported currently).
        byte_order: 'little' or 'big' endian.

    Returns:
        (left, right, sample_rate) — float64 arrays in [-1.0, 1.0].
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

    return left, right, sample_rate


def load_wav(path: str) -> tuple:
    """Load a WAV file.

    Returns:
        (left, right, sample_rate) — float64 arrays in [-1.0, 1.0].
    """
    with wave.open(path, "rb") as w:
        n_channels = w.getnchannels()
        sampwidth = w.getsampwidth()
        sample_rate = w.getframerate()
        n_frames = w.getnframes()
        raw = w.readframes(n_frames)

    if sampwidth == 2:
        samples = np.frombuffer(raw, dtype=np.int16).astype(np.float64) / 32768.0
    elif sampwidth == 3:
        # 24-bit: unpack manually
        n_samples = len(raw) // 3
        samples = np.zeros(n_samples, dtype=np.float64)
        for i in range(n_samples):
            b = raw[i*3:(i+1)*3]
            val = int.from_bytes(b, byteorder="little", signed=True)
            samples[i] = val / 8388608.0
    elif sampwidth == 1:
        # 8-bit unsigned
        samples = (np.frombuffer(raw, dtype=np.uint8).astype(np.float64) - 128.0) / 128.0
    else:
        raise ValueError(f"Unsupported sample width: {sampwidth} bytes")

    if n_channels == 2:
        left = samples[0::2]
        right = samples[1::2]
    elif n_channels == 1:
        left = samples
        right = samples.copy()
    else:
        # Take first two channels
        left = samples[0::n_channels]
        right = samples[1::n_channels]

    return left, right, sample_rate


def load_aiff(path: str) -> tuple:
    """Load an AIFF file.

    Returns:
        (left, right, sample_rate) — float64 arrays in [-1.0, 1.0].
    """
    if not _HAS_AIFC:
        raise ImportError("aifc module not available (removed in Python 3.13+). "
                          "Convert AIFF to WAV first, or use Python <= 3.12.")

    with aifc.open(path, "rb") as a:
        n_channels = a.getnchannels()
        sampwidth = a.getsampwidth()
        sample_rate = a.getframerate()
        n_frames = a.getnframes()
        raw = a.readframes(n_frames)

    # AIFF is big-endian
    if sampwidth == 2:
        samples = np.frombuffer(raw, dtype=np.dtype(">i2")).astype(np.float64) / 32768.0
    elif sampwidth == 1:
        samples = (np.frombuffer(raw, dtype=np.uint8).astype(np.float64) - 128.0) / 128.0
    else:
        raise ValueError(f"Unsupported AIFF sample width: {sampwidth}")

    if n_channels == 2:
        left = samples[0::2]
        right = samples[1::2]
    elif n_channels == 1:
        left = samples
        right = samples.copy()
    else:
        left = samples[0::n_channels]
        right = samples[1::n_channels]

    return left, right, sample_rate


def load_audio(path: str, format: str = "auto", sample_rate: int = 44100,
               channels: int = 2, bit_depth: int = 16,
               byte_order: str = "little") -> tuple:
    """Load audio from any supported format.

    Args:
        path: Path to audio file.
        format: 'raw', 'wav', 'aiff', or 'auto' (detect from extension).
        sample_rate: Sample rate (only used for raw format).
        channels: Channel count (only used for raw format).
        bit_depth: Bit depth (only used for raw format).
        byte_order: Byte order (only used for raw format).

    Returns:
        (left, right, sample_rate)
    """
    if format == "auto":
        ext = path.lower().rsplit(".", 1)[-1] if "." in path else ""
        format = {
            "wav": "wav", "wave": "wav",
            "aif": "aiff", "aiff": "aiff",
            "raw": "raw", "pcm": "raw",
        }.get(ext, "raw")

    if format == "wav":
        return load_wav(path)
    elif format == "aiff":
        return load_aiff(path)
    elif format == "raw":
        return load_raw(path, sample_rate, channels, bit_depth, byte_order)
    else:
        raise ValueError(f"Unknown format: {format}")
