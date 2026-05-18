"""
Data model for the HeyEveryone receiver.

Maintains per-transmitter state (7 buttons + encoder) completely independent
of the GUI layer. The serial parser feeds events in, and the GUI reads state
to render widgets.
"""

import time
from typing import Dict, List

EVENT_BUTTON_UP = 0x01
EVENT_BUTTON_DOWN = 0x02
EVENT_BUTTON_LEFT = 0x03
EVENT_BUTTON_RIGHT = 0x04
EVENT_BUTTON_CENTER = 0x05
EVENT_BUTTON_A = 0x06
EVENT_BUTTON_B = 0x07
EVENT_ENCODER_CW = 0x0B
EVENT_ENCODER_CCW = 0x0C

BUTTON_NAMES: Dict[int, str] = {
    EVENT_BUTTON_UP: "UP",
    EVENT_BUTTON_DOWN: "DOWN",
    EVENT_BUTTON_LEFT: "LEFT",
    EVENT_BUTTON_RIGHT: "RIGHT",
    EVENT_BUTTON_CENTER: "CENTER",
    EVENT_BUTTON_A: "A",
    EVENT_BUTTON_B: "B",
}

ALL_BUTTON_TYPES = frozenset(BUTTON_NAMES.keys())

# A transmitter is considered "active" (recently seen) within this window
ACTIVITY_TIMEOUT_SEC = 15.0


class TransmitterState:
    """Mutable state for a single transmitter."""

    __slots__ = (
        "sender_id",
        "buttons",
        "encoder_value",
        "last_update",
        "last_event_desc",
    )

    def __init__(self, sender_id: int):
        self.sender_id = sender_id
        self.buttons: Dict[int, bool] = {t: False for t in ALL_BUTTON_TYPES}
        self.encoder_value: int = 0
        self.last_update: float = 0.0
        self.last_event_desc: str = ""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def apply_event(self, event_type: int, event_value: int = 0) -> None:
        """Update state from a single parsed event."""
        self.last_update = time.time()

        if event_type in ALL_BUTTON_TYPES:
            self.buttons[event_type] = True
            desc = f"Btn {BUTTON_NAMES[event_type]}"
            self.last_event_desc = desc
            print(f"[DataModel] TX#{self.sender_id}: {desc}")
        elif event_type == EVENT_ENCODER_CW:
            self.encoder_value += event_value
            desc = f"Encoder ▶ +{event_value} → {self.encoder_value}"
            self.last_event_desc = desc
            print(f"[DataModel] TX#{self.sender_id}: {desc}")
        elif event_type == EVENT_ENCODER_CCW:
            self.encoder_value -= event_value
            desc = f"Encoder ◀ -{event_value} → {self.encoder_value}"
            self.last_event_desc = desc
            print(f"[DataModel] TX#{self.sender_id}: {desc}")

    def reset_button(self, event_type: int) -> None:
        """Clear a button's pressed state (called after highlight timeout)."""
        if event_type in self.buttons:
            self.buttons[event_type] = False

    @property
    def is_active(self) -> bool:
        return (time.time() - self.last_update) < ACTIVITY_TIMEOUT_SEC


class DataModel:
    """Container for all known transmitters."""

    def __init__(self) -> None:
        self._tx: Dict[int, TransmitterState] = {}

    def get_or_create(self, sender_id: int) -> TransmitterState:
        try:
            return self._tx[sender_id]
        except KeyError:
            tx = TransmitterState(sender_id)
            self._tx[sender_id] = tx
            return tx

    def list_all(self) -> List[TransmitterState]:
        return sorted(self._tx.values(), key=lambda t: t.sender_id)

    def list_active(self) -> List[TransmitterState]:
        return [t for t in self.list_all() if t.is_active]

    def handle_event(self, sender_id: int, event_type: int, event_value: int = 0) -> None:
        tx = self.get_or_create(sender_id)
        tx.apply_event(event_type, event_value)
