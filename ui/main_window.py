"""ICM2 BLE ECG Recorder - Main Application Window.

Layout:
  - Left panel: DevicePanel (scan list + connect buttons)
  - Center: ECGPlotWidget (dual-channel rolling display)
  - Bottom: status bar (connection state, sample count, file path)

Threading bridge:
  - AsyncBridge runs asyncio in background thread
  - ICMBleClient async methods called via async_bridge.submit_coro()
  - QTimer(50ms) drains async_bridge.data_queue -> plot + CSV

closeEvent:
  - If recording: stop_recording + flush CSV
  - Then disconnect
  - Accept close
"""

import logging
import os
from pathlib import Path
from typing import Optional

from PyQt5.QtCore import QTimer, Qt, QMetaObject, Q_ARG, pyqtSlot
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QLabel, QStatusBar, QSplitter,
    QMessageBox,
)

from icm.ble_client import ICMBleClient
from icm.ecg_writer import ECGCsvWriter
from icm.config import CSV_DEFAULT_DIR
from ui.async_bridge import AsyncBridge
from ui.device_panel import DevicePanel
from ui.plot_widget import ECGPlotWidget

logger = logging.getLogger(__name__)

POLL_INTERVAL_MS = 50  # QTimer interval to drain data queue


class MainWindow(QMainWindow):
    """Main window for ICM2 ECG Recorder."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("ICM2 ECG Recorder")
        self.resize(1200, 700)

        # Core objects
        self._bridge = AsyncBridge()
        self._bridge.start()
        self._ble = ICMBleClient(self._bridge)
        self._writer: Optional[ECGCsvWriter] = None
        self._last_scan_results: list = []  # cache for show_connected_only

        # Wire BLE callbacks
        self._ble.on_scan_result = self._on_scan_result
        self._ble.on_connected = self._on_connected
        self._ble.on_disconnected = self._on_disconnected
        self._ble.on_handshake_done = self._on_handshake_done
        self._ble.on_handshake_error = self._on_handshake_error

        self._setup_ui()

        # Poll timer (Qt main thread)
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(POLL_INTERVAL_MS)
        self._poll_timer.timeout.connect(self._poll_data_queue)
        self._poll_timer.start()

        # Permission renewal timer: every 14 minutes (< 15 min limit)
        self._perm_timer = QTimer(self)
        self._perm_timer.setInterval(14 * 60 * 1000)
        self._perm_timer.timeout.connect(self._renew_host_permission)
        # Started only after handshake, stopped on disconnect

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        # Left: device panel
        self._device_panel = DevicePanel()
        self._device_panel.setMaximumWidth(340)
        self._device_panel.scan_requested.connect(self._on_scan_clicked)
        self._device_panel.connect_requested.connect(self._on_connect_clicked)
        self._device_panel.disconnect_requested.connect(self._on_disconnect_clicked)

        # Center: ECG plot
        self._plot = ECGPlotWidget()

        splitter = QSplitter()  # default is horizontal
        splitter.addWidget(self._device_panel)
        splitter.addWidget(self._plot)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        main_layout.addWidget(splitter)

        # Toolbar widget in status bar
        toolbar_widget = QWidget()
        toolbar_layout = QHBoxLayout(toolbar_widget)
        toolbar_layout.setContentsMargins(4, 2, 4, 2)

        self._start_btn = QPushButton("Start Recording")
        self._start_btn.setEnabled(False)
        self._start_btn.clicked.connect(self._on_start_recording)
        toolbar_layout.addWidget(self._start_btn)

        self._stop_btn = QPushButton("Stop Recording")
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._on_stop_recording)
        toolbar_layout.addWidget(self._stop_btn)

        toolbar_layout.addStretch()

        self._amp_label = QLabel("Amp: -- mV")
        toolbar_layout.addWidget(self._amp_label)

        self._sample_label = QLabel("Samples: 0")
        toolbar_layout.addWidget(self._sample_label)

        # Heart rate display (bold, large)
        self._hr_label = QLabel("-- bpm")
        hr_font = QFont()
        hr_font.setPointSize(20)
        hr_font.setBold(True)
        self._hr_label.setFont(hr_font)
        self._hr_label.setStyleSheet("color: #cc2200; padding: 0 8px;")
        toolbar_layout.addWidget(self._hr_label)

        # Status bar
        status_bar = QStatusBar()
        self.setStatusBar(status_bar)
        status_bar.addPermanentWidget(toolbar_widget)
        self._status_bar = status_bar
        self._status_bar.showMessage("Idle — Click Scan to find ICM devices")

        self._file_label = QLabel("")
        self._status_bar.addWidget(self._file_label)

    # ------------------------------------------------------------------
    # Button slots (Qt main thread)
    # ------------------------------------------------------------------

    def _on_scan_clicked(self) -> None:
        self._device_panel.clear_devices()
        self._status_bar.showMessage("Scanning for ICM devices...")
        self._bridge.submit_coro(self._ble.scan())

    def _on_connect_clicked(self, address: str) -> None:
        self._status_bar.showMessage(f"Connecting to {address}...")
        self._bridge.submit_coro(self._ble.connect(address))

    def _on_disconnect_clicked(self) -> None:
        self._perm_timer.stop()
        if self._writer:
            self._do_stop_recording()
        self._bridge.submit_coro(self._ble.disconnect())

    def _renew_host_permission(self) -> None:
        """Sync RTC + send SET_HOST_INFO every 14 min to maintain 随访程控 permission."""
        if self._ble.is_connected:
            logger.info("Renewing host permission (14-min interval)")
            self._bridge.submit_coro(self._ble.sync_rtc())
            self._bridge.submit_coro(self._ble.set_host_info())

    def _on_start_recording(self) -> None:
        """Start CSV recording (ECG notify already active since handshake)."""
        mac = self._ble.mac_address or "unknown"
        self._writer = ECGCsvWriter(CSV_DEFAULT_DIR, mac)
        try:
            path = self._writer.open()
            self._file_label.setText(str(path.name))
            logger.info("CSV opened: %s", path)
        except OSError as e:
            QMessageBox.critical(self, "File Error", f"Cannot open CSV file:\n{e}")
            self._writer = None
            return

        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._status_bar.showMessage("Recording...")

    def _on_stop_recording(self) -> None:
        self._do_stop_recording()

    def _do_stop_recording(self) -> None:
        """Stop CSV recording only — ECG notify stays active for live display."""
        if self._writer:
            self._writer.close()
            self._writer = None
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._file_label.setText("")
        self._status_bar.showMessage("Recording stopped. Ready to record again.")

    # ------------------------------------------------------------------
    # BLE callbacks (called from asyncio thread → marshal to Qt thread)
    # ------------------------------------------------------------------

    def _on_scan_result(self, devices: list) -> None:
        QMetaObject.invokeMethod(self, "_qt_on_scan_result",
                                 Qt.ConnectionType.QueuedConnection,
                                 Q_ARG("PyQt_PyObject", devices))

    def _on_connected(self, mac: str) -> None:
        QMetaObject.invokeMethod(self, "_qt_on_connected",
                                 Qt.ConnectionType.QueuedConnection,
                                 Q_ARG(str, mac))

    def _on_disconnected(self) -> None:
        QMetaObject.invokeMethod(self, "_qt_on_disconnected",
                                 Qt.ConnectionType.QueuedConnection)

    def _on_handshake_done(self) -> None:
        QMetaObject.invokeMethod(self, "_qt_on_handshake_done",
                                 Qt.ConnectionType.QueuedConnection)

    def _on_handshake_error(self, msg: str) -> None:
        QMetaObject.invokeMethod(self, "_qt_on_handshake_error",
                                 Qt.ConnectionType.QueuedConnection,
                                 Q_ARG(str, msg))

    # ------------------------------------------------------------------
    # Qt-thread implementations of BLE callbacks
    # ------------------------------------------------------------------

    @pyqtSlot("PyQt_PyObject")
    def _qt_on_scan_result(self, devices: list) -> None:
        self._last_scan_results = devices
        self._device_panel.populate_devices(devices)
        self._status_bar.showMessage(f"Found {len(devices)} ICM device(s)")

    @pyqtSlot(str)
    def _qt_on_connected(self, mac: str) -> None:
        self._status_bar.showMessage(f"Connected to {mac} — performing handshake...")
        self._device_panel.set_status(f"Connected: {mac}")
        # Shrink list to only the connected device
        connected_dev = next(
            (d for d in self._last_scan_results if d.get("address") == mac),
            {"name": mac, "address": mac, "rssi": 0},
        )
        self._device_panel.show_connected_only(connected_dev)

    @pyqtSlot()
    def _qt_on_disconnected(self) -> None:
        self._perm_timer.stop()
        self._device_panel.set_connected(False)
        self._device_panel.set_status("Disconnected")
        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(False)
        self._hr_label.setText("-- bpm")
        self._amp_label.setText("Amp: -- mV")
        self._plot.clear()
        if self._writer:
            self._writer.close()
            self._writer = None
        self._status_bar.showMessage("Device disconnected")

    @pyqtSlot()
    def _qt_on_handshake_done(self) -> None:
        self._device_panel.set_connected(True)
        self._start_btn.setEnabled(True)
        self._status_bar.showMessage("Handshake complete — streaming ECG. Click Start Recording to save CSV.")
        # Sequence matches run_test_4: sync RTC → set host permission → start ECG
        self._bridge.submit_coro(self._ble.sync_rtc())
        self._bridge.submit_coro(self._ble.set_host_info())
        self._perm_timer.start()
        self._bridge.submit_coro(self._ble.start_recording())

    @pyqtSlot(str)
    def _qt_on_handshake_error(self, msg: str) -> None:
        self._device_panel.set_connected(False)
        self._status_bar.showMessage(f"Handshake failed: {msg}")
        QMessageBox.warning(self, "Handshake Failed", msg)

    # ------------------------------------------------------------------
    # QTimer slot — runs in Qt main thread every 50ms
    # ------------------------------------------------------------------

    def _poll_data_queue(self) -> None:
        """Drain data_queue: update plot and write CSV."""
        while not self._bridge.data_queue.empty():
            try:
                packet = self._bridge.data_queue.get_nowait()
            except Exception:
                break

            self._plot.append_packet(packet)

            if self._writer and self._writer.is_open:
                try:
                    self._writer.write_packet(packet)
                except OSError as e:
                    logger.error("CSV write error: %s", e)
                    self._do_stop_recording()
                    QMessageBox.critical(self, "Disk Error", f"CSV write failed:\n{e}")
                    break

            if packet.amplitude_mv:
                self._amp_label.setText(f"Amp: {packet.amplitude_mv:.2f} mV")
            if packet.rr_intervals:
                # Use the first valid RR interval; guard against divide-by-zero
                rr = packet.rr_intervals[0]
                if rr > 0:
                    bpm = int(round(60000 / rr))
                    self._hr_label.setText(f"{bpm} bpm")
            if self._writer:
                self._sample_label.setText(f"Samples: {self._writer.sample_count}")

    # ------------------------------------------------------------------
    # closeEvent - flush CSV and disconnect before exit
    # ------------------------------------------------------------------

    def closeEvent(self, a0) -> None:  # noqa: N802
        """Stop recording, flush CSV, disconnect on window close."""
        logger.info("Window close requested")
        self._poll_timer.stop()
        self._perm_timer.stop()

        # Flush CSV if recording
        if self._writer:
            self._writer.close()
            self._writer = None

        # Stop ECG notify + disconnect
        if self._ble.is_connected:
            self._bridge.submit_coro(self._ble.disconnect())

        # Stop asyncio bridge
        self._bridge.stop()

        if a0 is not None:
            a0.accept()
