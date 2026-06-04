"""ICM2 BLE ECG Recorder - Application entry point.

Usage:
    python main.py

Architecture:
    - Creates QApplication in main thread
    - MainWindow owns AsyncBridge (asyncio loop in daemon thread)
    - MainWindow.closeEvent handles cleanup
"""

import logging
import sys

from PyQt5.QtWidgets import QApplication

from ui.main_window import MainWindow


def main() -> None:
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    app = QApplication(sys.argv)
    app.setApplicationName("ICM2 ECG Recorder")
    app.setOrganizationName("Singular Medical")

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
