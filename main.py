#!/usr/bin/env python3
"""
HeyEveryone — Receiver Monitor GUI

Launch the application:
    python main.py

Requires: PyQt6, pyserial
"""

import sys
from PyQt6.QtWidgets import QApplication
from gui.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("HeyEveryone Receiver")

    win = MainWindow()
    win.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
