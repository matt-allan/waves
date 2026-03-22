"""Serial bit engine — transliteration of the C serial code in emulator.c.

Implements the bit-level serial link between the host (MCU side) and
the Game Boy, with TX/RX circular queues and byte-alignment protection.
"""

QUEUE_LEN = 256


class SerialEngine:
    """Bit-level serial port engine matching the C emulator's behaviour."""

    def __init__(self):
        # TX path (host -> GB)
        self._tx_queue = bytearray(QUEUE_LEN)
        self._tx_head = 0
        self._tx_tail = 0
        self._tx_byte = 0
        self._tx_bit = -1  # -1 = idle, no byte in flight
        self._tx_xfer = 7  # next bit_end is MSB of a new transfer

        # RX path (GB -> host)
        self._rx_queue = bytearray(QUEUE_LEN)
        self._rx_head = 0
        self._rx_tail = 0
        self._rx_byte = 0
        self._rx_bit = 0  # bits received so far (0..7)

    # -- Public queue interface --

    def enqueue(self, byte):
        """Add one byte to the TX (host -> GB) queue.

        Silently drops the byte if the queue is full.
        """
        nxt = (self._tx_tail + 1) % QUEUE_LEN
        if nxt == self._tx_head:
            return  # queue full
        self._tx_queue[self._tx_tail] = byte & 0xFF
        self._tx_tail = nxt

    def dequeue(self):
        """Pop one received byte (GB -> host), or return *None*."""
        if self._rx_head == self._rx_tail:
            return None
        byte = self._rx_queue[self._rx_head]
        self._rx_head = (self._rx_head + 1) % QUEUE_LEN
        return byte

    # -- SameBoy callback handlers --

    def on_bit_start(self, bit_to_send):
        """Called when the GB clocks out a bit (bit_start callback).

        Accumulates bits MSB-first into a byte; pushes completed bytes
        to the RX queue.
        """
        self._rx_byte = ((self._rx_byte << 1) | (1 if bit_to_send else 0)) & 0xFF
        self._rx_bit += 1

        if self._rx_bit == 8:
            nxt = (self._rx_tail + 1) % QUEUE_LEN
            if nxt != self._rx_head:
                self._rx_queue[self._rx_tail] = self._rx_byte
                self._rx_tail = nxt
            self._rx_byte = 0
            self._rx_bit = 0

    def on_bit_end(self):
        """Called when the GB latches the incoming bit (bit_end callback).

        Returns the next TX bit (MSB-first), or ``True`` (idle high)
        when the queue is empty.

        Bytes are loaded only at the MSB edge of a new 8-bit transfer
        so that a byte enqueued mid-transfer is never split across two
        consecutive transfers.
        """
        # Load a new byte only at MSB of a new transfer.
        if self._tx_xfer == 7 and self._tx_bit < 0:
            if self._tx_head != self._tx_tail:
                self._tx_byte = self._tx_queue[self._tx_head]
                self._tx_head = (self._tx_head + 1) % QUEUE_LEN
                self._tx_bit = 7

        if self._tx_bit >= 0:
            bit = bool((self._tx_byte >> self._tx_bit) & 1)
            self._tx_bit -= 1
        else:
            bit = True  # idle line high

        # Advance the transfer position counter (wraps 0 -> 7).
        self._tx_xfer = 7 if self._tx_xfer == 0 else self._tx_xfer - 1

        return bit
