"""
Serial protocol parser for the HeyEveryone receiver.

Protocol frame format (from firmware):
  0xFC [length N] [N bytes payload] [checksum]

  Payload: repeated entries of [sender_id 1B][data_H 1B][data_L 1B]
  Checksum: sum of all bytes from header to last payload byte (truncated to 8-bit)

Data values:
  Buttons:    0x0001-0x0007  (UP/DOWN/LEFT/RIGHT/CENTER/A/B)
  Encoder CW:  0x0Bxx  (xx = step count)
  Encoder CCW: 0x0Cxx  (xx = step count)
"""

import threading
import serial
from typing import Callable, Optional

UART_FRAME_HEADER = 0xFC

EVENT_BUTTON_UP = 0x01
EVENT_BUTTON_DOWN = 0x02
EVENT_BUTTON_LEFT = 0x03
EVENT_BUTTON_RIGHT = 0x04
EVENT_BUTTON_CENTER = 0x05
EVENT_BUTTON_A = 0x06
EVENT_BUTTON_B = 0x07
EVENT_ENCODER_CW = 0x0B
EVENT_ENCODER_CCW = 0x0C

BUTTON_EVENTS = frozenset({
    EVENT_BUTTON_UP, EVENT_BUTTON_DOWN, EVENT_BUTTON_LEFT,
    EVENT_BUTTON_RIGHT, EVENT_BUTTON_CENTER, EVENT_BUTTON_A, EVENT_BUTTON_B,
})


class ParsedEvent:
    """A single parsed event extracted from the serial stream."""

    __slots__ = ("sender_id", "event_type", "event_value")

    def __init__(self, sender_id: int, event_type: int, event_value: int = 0):
        self.sender_id = sender_id
        self.event_type = event_type
        self.event_value = event_value

    @property
    def is_button(self) -> bool:
        return self.event_type in BUTTON_EVENTS

    @property
    def is_encoder(self) -> bool:
        return self.event_type in (EVENT_ENCODER_CW, EVENT_ENCODER_CCW)

    @classmethod
    def from_raw_data(cls, sender_id: int, data_h: int, data_l: int) -> "ParsedEvent":
        """Decode a 3-byte payload entry into a ParsedEvent."""
        if data_h == 0 and data_l in BUTTON_EVENTS:
            return cls(sender_id, data_l, 0)
        if data_h == EVENT_ENCODER_CW:
            return cls(sender_id, EVENT_ENCODER_CW, data_l)
        if data_h == EVENT_ENCODER_CCW:
            return cls(sender_id, EVENT_ENCODER_CCW, data_l)
        return cls(sender_id, 0, (data_h << 8) | data_l)

    def __repr__(self) -> str:
        return (f"ParsedEvent(sender={self.sender_id}, "
                f"type=0x{self.event_type:02X}, val={self.event_value})")


class SerialParser:
    """Reads serial data and parses 0xFC framed protocol in a background thread."""

    def __init__(
        self,
        port: str,
        baudrate: int = 115200,
        callback: Optional[Callable[[ParsedEvent], None]] = None,
    ):
        self.port = port
        self.baudrate = baudrate
        self.callback = callback

        self._serial: Optional[serial.Serial] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._buf = bytearray()

    @property
    def is_connected(self) -> bool:
        return self._serial is not None and self._serial.is_open

    def connect(self) -> bool:
        """Open serial port and start reader thread. Returns True on success."""
        try:
            self._serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.05,
            )
        except Exception as exc:
            print(f"[SerialParser] Failed to open {self.port}: {exc}")
            return False

        self._running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()
        return True

    def disconnect(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=1.0)
        if self._serial is not None and self._serial.is_open:
            try:
                self._serial.close()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _read_loop(self) -> None:
        while self._running:
            try:
                if not self._serial or not self._serial.is_open:
                    break
                chunk = self._serial.read(512)
                if chunk:
                    self._buf.extend(chunk)
                    self._parse_buffer()
            except serial.SerialException:
                break

    def _parse_buffer(self) -> None:
        while True:
            if len(self._buf) < 2:
                return

            # Locate frame header
            idx = self._buf.find(bytes([UART_FRAME_HEADER]))
            if idx < 0:
                self._buf.clear()
                return
            if idx > 0:
                del self._buf[:idx]

            if len(self._buf) < 2:
                return

            payload_len = self._buf[1]          # bytes following length field
            frame_end = 2 + payload_len          # header + length + payload + checksum

            if len(self._buf) < frame_end:
                return  # wait for more data

            # Verify checksum (sum of header + length + all payload bytes)
            expected_cs = sum(self._buf[: frame_end - 1]) & 0xFF
            actual_cs = self._buf[frame_end - 1]

            if expected_cs == actual_cs:
                self._dispatch_payload(self._buf[2 : frame_end - 1])

            del self._buf[:frame_end]

    def _dispatch_payload(self, payload: bytearray) -> None:
        """Split payload into 3-byte entries and fire callback."""
        if len(payload) % 3 != 0:
            return  # malformed, drop

        for i in range(0, len(payload), 3):
            sender_id = payload[i]
            data_h = payload[i + 1]
            data_l = payload[i + 2]
            event = ParsedEvent.from_raw_data(sender_id, data_h, data_l)
            if self.callback is not None:
                try:
                    self.callback(event)
                except Exception:
                    pass
