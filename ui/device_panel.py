"""Device scan + connect panel for ICM2 BLE ECG Recorder.

Displays scanned ICM devices with name and RSSI.
Emits Qt signals for scan, connect, disconnect actions.
"""

from typing import List, Dict, Any, Optional

from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QListWidget, QListWidgetItem,
    QLabel, QGroupBox,
)


class DevicePanel(QWidget):
    """Scan list + connect/disconnect button panel.

    Signals:
        scan_requested: user clicked Scan
        connect_requested(address): user double-clicked or clicked Connect
        disconnect_requested: user clicked Disconnect
    """

    scan_requested = pyqtSignal()
    connect_requested = pyqtSignal(str)   # BLE MAC address
    disconnect_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._devices: List[Dict[str, Any]] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Group box for device list
        group = QGroupBox("ICM Devices")
        group_layout = QVBoxLayout(group)

        # Device list
        self._device_list = QListWidget()
        self._device_list.setSelectionMode(QListWidget.SingleSelection)
        self._device_list.itemDoubleClicked.connect(self._on_double_click)
        group_layout.addWidget(self._device_list)

        # Status label
        self._status_label = QLabel("Not connected")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        group_layout.addWidget(self._status_label)

        layout.addWidget(group)

        # Button row
        btn_layout = QHBoxLayout()

        self._scan_btn = QPushButton("Scan")
        self._scan_btn.clicked.connect(self.scan_requested)
        btn_layout.addWidget(self._scan_btn)

        self._connect_btn = QPushButton("Connect")
        self._connect_btn.setEnabled(False)
        self._connect_btn.clicked.connect(self._on_connect_clicked)
        btn_layout.addWidget(self._connect_btn)

        self._disconnect_btn = QPushButton("Disconnect")
        self._disconnect_btn.setEnabled(False)
        self._disconnect_btn.clicked.connect(self.disconnect_requested)
        btn_layout.addWidget(self._disconnect_btn)

        layout.addLayout(btn_layout)

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def populate_devices(self, devices: List[Dict[str, Any]]) -> None:
        """Fill list with scan results.

        Args:
            devices: list of {name: str, address: str, rssi: int}
        """
        self._devices = devices
        self._device_list.clear()
        for dev in devices:
            name = dev.get("name") or "Unknown"
            addr = dev.get("address", "")
            rssi = dev.get("rssi", 0)
            text = f"{name}  |  {addr}  |  RSSI: {rssi} dBm"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, addr)
            self._device_list.addItem(item)

        self._connect_btn.setEnabled(len(devices) > 0)
        if devices:
            self._device_list.setCurrentRow(0)

    def set_status(self, text: str) -> None:
        """Update status label text."""
        self._status_label.setText(text)

    def set_connected(self, connected: bool) -> None:
        """Update button states based on connection state."""
        self._scan_btn.setEnabled(not connected)
        self._connect_btn.setEnabled(not connected and len(self._devices) > 0)
        self._disconnect_btn.setEnabled(connected)

    def selected_address(self) -> Optional[str]:
        """Return MAC address of selected device, or None."""
        item = self._device_list.currentItem()
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    # ------------------------------------------------------------------ #
    # Private slots                                                        #
    # ------------------------------------------------------------------ #

    def _on_connect_clicked(self) -> None:
        addr = self.selected_address()
        if addr:
            self.connect_requested.emit(addr)

    def _on_double_click(self, item: QListWidgetItem) -> None:
        addr = item.data(Qt.ItemDataRole.UserRole)
        if addr:
            self.connect_requested.emit(addr)

    # ------------------------------------------------------------------ #
    # Expose widgets as properties (for external access / testing)        #
    # ------------------------------------------------------------------ #

    @property
    def device_list(self) -> QListWidget:
        return self._device_list

    @property
    def scan_button(self) -> QPushButton:
        return self._scan_btn

    @property
    def connect_button(self) -> QPushButton:
        return self._connect_btn

    @property
    def disconnect_button(self) -> QPushButton:
        return self._disconnect_btn
