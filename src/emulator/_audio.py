"""Audio ring buffer and WAV export.

Transliteration of the audio capture code in emulator.c.
"""

import struct
import wave

SAMPLE_RATE = 44100
BUF_LEN = 8192


class AudioBuffer:
    """Ring buffer for stereo int16 audio samples."""

    def __init__(self):
        self._buf = [(0, 0)] * BUF_LEN
        self._head = 0  # next write position
        self._tail = 0  # next read position

    def push(self, left: int, right: int) -> None:
        """Push one stereo sample.  Drops the oldest sample if full."""
        nxt = (self._head + 1) % BUF_LEN
        if nxt == self._tail:
            # Buffer full — drop oldest sample to make room.
            self._tail = (self._tail + 1) % BUF_LEN
        self._buf[self._head] = (left, right)
        self._head = nxt

    def available(self) -> int:
        """Number of samples currently buffered."""
        return (self._head - self._tail + BUF_LEN) % BUF_LEN

    def drain(self, max_samples: int = 0) -> list[tuple[int, int]]:
        """Drain up to *max_samples* (0 = all).

        Returns a list of ``(left, right)`` tuples.
        """
        if max_samples <= 0:
            max_samples = self.available()
        out = []
        while len(out) < max_samples and self._tail != self._head:
            out.append(self._buf[self._tail])
            self._tail = (self._tail + 1) % BUF_LEN
        return out

    def drain_bytes(self, max_samples: int = 0) -> bytes:
        """Drain and return packed little-endian int16 bytes (L, R interleaved)."""
        samples = self.drain(max_samples)
        return struct.pack(
            f"<{len(samples) * 2}h", *[v for pair in samples for v in pair]
        )

    @staticmethod
    def save_wav(path: str, data: bytes, sample_rate: int = SAMPLE_RATE) -> None:
        """Write interleaved int16 stereo PCM *data* (bytes) to a WAV file."""
        with wave.open(path, "wb") as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(data)
