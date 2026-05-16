"""
Visual card widget for a single transmitter.

Each card shows:
  - Transmitter ID badge
  - 7 buttons laid out as a compact gamepad D-pad (▲◀●▶▼) + A/B
  - Rotary encoder gauge (custom painted arc)
  - Last-event description
"""

from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .data_model import (
    ALL_BUTTON_TYPES,
    BUTTON_NAMES,
    EVENT_BUTTON_A,
    EVENT_BUTTON_B,
    TransmitterState,
)

# ── Colour palette ──────────────────────────────────────────────────
CARD_BG = "#1a1a1a"
CARD_BORDER = "#2a2a2a"
CARD_BORDER_ACTIVE = "#00BCD4"
TEXT_PRIMARY = "#e0e0e0"
TEXT_SECONDARY = "#888888"
TEXT_ACCENT = "#FFB74D"
BTN_IDLE = "#2d2d2d"
BTN_BORDER = "#444444"
BTN_ACTIVE = "#FF5722"
BTN_ACTIVE_BORDER = "#FF8A65"
GAUGE_TRACK = "#333333"
GAUGE_FILL = "#00BCD4"

BTN_SIZE = 34
BTN_STYLE_IDLE = (
    f"background-color: {BTN_IDLE}; color: {TEXT_SECONDARY};"
    f"border: 2px solid {BTN_BORDER}; border-radius: 5px;"
    f"font-size: 13px; font-weight: bold;"
)
BTN_STYLE_ACTIVE = (
    f"background-color: {BTN_ACTIVE}; color: white;"
    f"border: 2px solid {BTN_ACTIVE_BORDER}; border-radius: 5px;"
    f"font-size: 13px; font-weight: bold;"
)


class EncoderGauge(QWidget):
    """Small circular arc gauge showing encoder value."""

    def __init__(self, parent: QWidget = None) -> None:
        super().__init__(parent)
        self._value = 0
        self.setFixedSize(78, 82)

    def set_value(self, v: int) -> None:
        self._value = v
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        cx, cy = w / 2.0, h / 2.0 - 4
        r = min(w, h) / 2.0 - 10

        rect = QRectF(cx - r, cy - r, r * 2, r * 2)

        # Track arc (270°, starting at 135°)
        pen = QPen(QColor(GAUGE_TRACK), 5)
        p.setPen(pen)
        p.drawArc(rect, 135 * 16, 270 * 16)

        # Fill arc
        frac = max(0.0, min(1.0, (self._value % 360) / 360.0))
        span = int(270 * frac)
        if span > 0:
            pen = QPen(QColor(GAUGE_FILL), 5)
            p.setPen(pen)
            p.drawArc(rect, 135 * 16, span)

        # Value label below gauge
        p.setPen(QColor(TEXT_PRIMARY))
        f = QFont("Consolas", 11, QFont.Weight.Bold)
        p.setFont(f)
        text_rect = QRectF(0, cy + r - 6, w, 22)
        p.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, str(self._value))


class TransmitterWidget(QFrame):
    """Card showing one transmitter's live state."""

    def __init__(self, sender_id: int, parent: QWidget = None) -> None:
        super().__init__(parent)
        self.sender_id = sender_id
        self.setup_ui()
        self._apply_card_style(active=False)

    # ── UI construction ──────────────────────────────────────────────

    def setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(4)
        layout.setContentsMargins(10, 6, 10, 8)

        # ── ID badge ──
        self.id_label = QLabel(f"TX #{self.sender_id}")
        self.id_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.id_label.setStyleSheet(
            f"font-size: 14px; font-weight: bold; color: {GAUGE_FILL};"
        )
        layout.addWidget(self.id_label)

        # ── Body: D-pad + right column (gauge + A/B) ──
        body = QHBoxLayout()
        body.setSpacing(8)

        # D-pad grid
        dpad = QGridLayout()
        dpad.setSpacing(3)

        self._btns: dict[str, QPushButton] = {}

        # row 0: UP
        self._btns["UP"] = self._mk_btn("▲")
        dpad.addWidget(self._btns["UP"], 0, 1, Qt.AlignmentFlag.AlignCenter)

        # row 1: LEFT  CENTER  RIGHT
        self._btns["LEFT"] = self._mk_btn("◀")
        dpad.addWidget(self._btns["LEFT"], 1, 0, Qt.AlignmentFlag.AlignRight)
        self._btns["CENTER"] = self._mk_btn("●")
        dpad.addWidget(self._btns["CENTER"], 1, 1, Qt.AlignmentFlag.AlignCenter)
        self._btns["RIGHT"] = self._mk_btn("▶")
        dpad.addWidget(self._btns["RIGHT"], 1, 2, Qt.AlignmentFlag.AlignLeft)

        # row 2: DOWN
        self._btns["DOWN"] = self._mk_btn("▼")
        dpad.addWidget(self._btns["DOWN"], 2, 1, Qt.AlignmentFlag.AlignCenter)

        body.addLayout(dpad)

        # Right column
        right_col = QVBoxLayout()
        right_col.setSpacing(4)

        self.encoder = EncoderGauge()
        right_col.addWidget(self.encoder, alignment=Qt.AlignmentFlag.AlignCenter)

        # A / B row
        ab_row = QHBoxLayout()
        ab_row.setSpacing(6)
        self._btns["A"] = self._mk_btn("A")
        self._btns["B"] = self._mk_btn("B")
        ab_row.addStretch()
        ab_row.addWidget(self._btns["A"])
        ab_row.addWidget(self._btns["B"])
        ab_row.addStretch()
        right_col.addLayout(ab_row)

        body.addLayout(right_col)
        layout.addLayout(body)

        # ── Last-event label ──
        self.event_label = QLabel("—")
        self.event_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.event_label.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: 10px;"
        )
        layout.addWidget(self.event_label)

        self.setLayout(layout)

    # ── Public update ────────────────────────────────────────────────

    def update_state(self, state: TransmitterState) -> None:
        self.id_label.setText(f"TX #{state.sender_id}")
        self.encoder.set_value(state.encoder_value)

        # Buttons
        for name, etype in (("UP", 0x01), ("DOWN", 0x02), ("LEFT", 0x03),
                             ("RIGHT", 0x04), ("CENTER", 0x05), ("A", 0x06), ("B", 0x07)):
            self._btns[name].setStyleSheet(
                BTN_STYLE_ACTIVE if state.buttons[etype] else BTN_STYLE_IDLE
            )

        # Event description
        self.event_label.setText(state.last_event_desc or "—")
        self.event_label.setStyleSheet(
            f"color: {TEXT_ACCENT}; font-size: 10px; font-weight: bold;"
            if state.last_event_desc else
            f"color: {TEXT_SECONDARY}; font-size: 10px;"
        )

        # Active border
        self._apply_card_style(active=state.is_active)

    # ── Helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _mk_btn(label: str) -> QPushButton:
        btn = QPushButton(label)
        btn.setFixedSize(BTN_SIZE, BTN_SIZE)
        btn.setEnabled(False)  # visual-only, not interactive
        btn.setStyleSheet(BTN_STYLE_IDLE)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        return btn

    def _apply_card_style(self, *, active: bool) -> None:
        border = CARD_BORDER_ACTIVE if active else CARD_BORDER
        self.setStyleSheet(
            f"TransmitterWidget {{"
            f"  background-color: {CARD_BG};"
            f"  border: 2px solid {border};"
            f"  border-radius: 8px;"
            f"}}"
        )
