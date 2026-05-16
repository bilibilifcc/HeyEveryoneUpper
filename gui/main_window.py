"""
Main window for the HeyEveryone receiver GUI.

Layout:
  ┌─────────────────────────────────────────┐
  │ [Port ▼] [Baud ▼] [Connect]  Status    │  ← toolbar
  ├─────────────────────────────────────────┤
  │  ┌──────┐  ┌──────┐  ┌──────┐          │
  │  │ TX#1 │  │ TX#2 │  │ TX#3 │          │  ← scrollable grid
  │  └──────┘  └──────┘  └──────┘          │
  │  ┌──────┐  ┌──────┐                    │
  │  │ TX#4 │  │ TX#5 │                    │
  │  └──────┘  └──────┘                    │
  └─────────────────────────────────────────┘
"""

from PyQt6.QtCore import QTimer, pyqtSignal, pyqtBoundSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolBar,
    QWidget,
)

from .data_model import DataModel
from .serial_parser import SerialParser, ParsedEvent
from .transmitter_widget import TransmitterWidget

GRID_COLS = 4


class MainWindow(QMainWindow):
    """Top-level window for the receiver monitor."""

    def __init__(self) -> None:
        super().__init__()
        self.data_model = DataModel()
        self._parser: SerialParser | None = None
        self._widgets: dict[int, TransmitterWidget] = {}
        self._pending_reset: dict[int, int] = {}

        self._build_ui()
        self._connect_signals()

        # Timer – clears button highlights 250 ms after last button event
        self._reset_timer = QTimer(self)
        self._reset_timer.setSingleShot(True)
        self._reset_timer.setInterval(250)
        self._reset_timer.timeout.connect(self._flush_button_resets)

        # Timer – refreshes active/inactive border every 2 s
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(2000)
        self._refresh_timer.timeout.connect(self._refresh_borders)
        self._refresh_timer.start()

    # ── UI construction ──────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.setWindowTitle("HeyEveryone — Receiver Monitor")
        self.resize(900, 650)
        self._apply_global_style()

        # ── Toolbar ──
        tb = QToolBar("Serial")
        tb.setObjectName("serialToolbar")
        tb.setStyleSheet("""
            QToolBar {
                background: #1e1e1e; border-bottom: 1px solid #333;
                padding: 4px 8px; spacing: 6px;
            }
        """)
        self.addToolBar(tb)

        tb.addWidget(QLabel("Port:"))
        self.port_cb = QComboBox()
        self.port_cb.setMinimumWidth(160)
        tb.addWidget(self.port_cb)

        refresh_btn = QPushButton("↻")
        refresh_btn.setFixedWidth(28)
        refresh_btn.clicked.connect(self._scan_ports)
        tb.addWidget(refresh_btn)

        tb.addWidget(QLabel("  Baud:"))
        self.baud_cb = QComboBox()
        self.baud_cb.addItems(["9600", "19200", "38400", "57600", "115200", "230400"])
        self.baud_cb.setCurrentText("115200")
        tb.addWidget(self.baud_cb)

        tb.addSeparator()

        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setFixedWidth(100)
        self.connect_btn.setCheckable(True)
        self.connect_btn.setStyleSheet("""
            QPushButton {
                background: #388E3C; color: white; font-weight: bold;
                border: none; border-radius: 4px; padding: 6px 12px;
            }
            QPushButton:hover  { background: #43A047; }
            QPushButton:checked { background: #D32F2F; }
        """)
        tb.addWidget(self.connect_btn)

        self.status_label = QLabel("Disconnected")
        self.status_label.setStyleSheet("color: #888;")
        tb.addWidget(self.status_label)

        # ── Scrollable grid ──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: #121212; border: none; }")

        container = QWidget()
        self.grid = QGridLayout(container)
        self.grid.setSpacing(10)
        self.grid.setContentsMargins(12, 12, 12, 12)
        scroll.setWidget(container)

        self.setCentralWidget(scroll)

        # ── Port scan ──
        self._scan_ports()

    # ── Signals ──────────────────────────────────────────────────────

    def _connect_signals(self) -> None:
        self.connect_btn.toggled.connect(self._on_toggle_connect)

    # ── Serial port management ───────────────────────────────────────

    def _scan_ports(self) -> None:
        self.port_cb.clear()
        try:
            import serial.tools.list_ports as lp
            for p in lp.comports():
                label = f"{p.device}  —  {p.description}" if p.description else p.device
                self.port_cb.addItem(label, p.device)
        except Exception:
            pass
        if self.port_cb.count() == 0:
            self.port_cb.addItem("(no ports found)", None)

    def _on_toggle_connect(self, checked: bool) -> None:
        if checked:
            self._do_connect()
        else:
            self._do_disconnect()

    def _do_connect(self) -> None:
        port = self.port_cb.currentData()
        if not port:
            QMessageBox.warning(self, "Error", "No serial port selected.")
            self.connect_btn.setChecked(False)
            return

        baud = int(self.baud_cb.currentText())

        self._parser = SerialParser(port, baud, callback=self._on_parsed_event)
        if not self._parser.connect():
            QMessageBox.warning(self, "Error", f"Failed to open {port}.")
            self.connect_btn.setChecked(False)
            return

        self.connect_btn.setText("Disconnect")
        self.status_label.setText(f"Connected — {port} @ {baud} baud")
        self.status_label.setStyleSheet("color: #4CAF50;")
        self.port_cb.setEnabled(False)
        self.baud_cb.setEnabled(False)

    def _do_disconnect(self) -> None:
        if self._parser:
            self._parser.disconnect()
            self._parser = None
        self.connect_btn.setText("Connect")
        self.status_label.setText("Disconnected")
        self.status_label.setStyleSheet("color: #888;")
        self.port_cb.setEnabled(True)
        self.baud_cb.setEnabled(True)

    # ── Event handling (called from serial thread) ───────────────────

    def _on_parsed_event(self, event: ParsedEvent) -> None:
        """Called from the serial reader thread — forward to GUI thread."""
        # We use QTimer.singleShot with a lambda (0-ms timer) to push
        # the update onto the Qt event loop so it runs on the main thread.
        QTimer.singleShot(0, lambda e=event: self._handle_event(e))

    def _handle_event(self, event: ParsedEvent) -> None:
        self.data_model.handle_event(event.sender_id, event.event_type, event.event_value)
        self._ensure_widget(event.sender_id)
        self._widgets[event.sender_id].update_state(
            self.data_model.get_or_create(event.sender_id)
        )

        # Schedule button highlight reset
        if event.is_button:
            self._pending_reset[event.sender_id] = event.event_type
            self._reset_timer.start()

    def _flush_button_resets(self) -> None:
        for sid, etype in self._pending_reset.items():
            tx = self.data_model.get_or_create(sid)
            tx.reset_button(etype)
            if sid in self._widgets:
                self._widgets[sid].update_state(tx)
        self._pending_reset.clear()

    def _refresh_borders(self) -> None:
        for sid, w in self._widgets.items():
            tx = self.data_model.get_or_create(sid)
            w.update_state(tx)

    # ── Widget management ───────────────────────────────────────────

    def _ensure_widget(self, sender_id: int) -> None:
        if sender_id in self._widgets:
            return
        widget = TransmitterWidget(sender_id)
        self._widgets[sender_id] = widget

        n = len(self._widgets) - 1
        row, col = divmod(n, GRID_COLS)
        self.grid.addWidget(widget, row, col)

    # ── Styling ──────────────────────────────────────────────────────

    def _apply_global_style(self) -> None:
        self.setStyleSheet("""
            QMainWindow { background: #121212; }
            QWidget     { color: #ccc; }
            QComboBox {
                background: #2a2a2a; color: #eee; border: 1px solid #444;
                border-radius: 4px; padding: 3px 6px;
            }
            QComboBox::drop-down {
                background: #3a3a3a; border-left: 1px solid #444; width: 20px;
            }
            QComboBox QAbstractItemView {
                background: #2a2a2a; color: #eee; selection-background: #00BCD4;
                outline: none;
            }
            QScrollBar:vertical {
                background: #1e1e1e; width: 8px;
            }
            QScrollBar::handle:vertical {
                background: #444; border-radius: 4px; min-height: 30px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
            QLabel {
                color: #aaa;
            }
        """)

    # ── Cleanup ──────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:  # noqa: N802
        self._do_disconnect()
        super().closeEvent(event)
