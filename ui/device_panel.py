"""Device scan + connect panel for ICM2 BLE ECG Recorder.

Displays scanned ICM devices with name and RSSI.
Emits Qt signals for scan, connect, disconnect actions.
"""

from typing import List, Dict, Any, Optional

from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QListWidget, QListWidgetItem,
    QLabel, QGroupBox, QFrame,
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
        self._device_list.setMaximumHeight(400)
        group_layout.addWidget(self._device_list)

        # Status label
        self._status_label = QLabel("Not connected")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        group_layout.addWidget(self._status_label)

        layout.addWidget(group)

        # Separator line
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator)

        # Remote client connection status label
        self._remote_status_label = QLabel("远程客户端: 未连接")
        self._remote_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._remote_status_label.setStyleSheet("color: #888888;")
        layout.addWidget(self._remote_status_label)

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

    def show_connected_only(self, dev: Dict[str, Any]) -> None:
        """Shrink list to show only the connected device (called after connect)."""
        self._devices = [dev]
        self._device_list.clear()
        name = dev.get("name") or "Unknown"
        addr = dev.get("address", "")
        rssi = dev.get("rssi", 0)
        text = f"{name}  |  {addr}  |  RSSI: {rssi} dBm"
        item = QListWidgetItem(text)
        item.setData(Qt.ItemDataRole.UserRole, addr)
        self._device_list.addItem(item)
        self._device_list.setCurrentRow(0)

    def clear_devices(self) -> None:
        """Clear the device list (call before starting a new scan)."""
        self._devices = []
        self._device_list.clear()
        self._connect_btn.setEnabled(False)

    def set_status(self, text: str) -> None:
        """Update status label text."""
        self._status_label.setText(text)

    def set_connected(self, connected: bool) -> None:
        """Update button states based on connection state."""
        self._scan_btn.setEnabled(not connected)
        self._connect_btn.setEnabled(not connected and len(self._devices) > 0)
        self._disconnect_btn.setEnabled(connected)

    def set_remote_connected(self) -> None:
        """Update remote status label to connected state."""
        self._remote_status_label.setText("远程客户端: 已连接")
        self._remote_status_label.setStyleSheet("color: #00aa00;")

    def set_remote_disconnected(self) -> None:
        """Update remote status label to disconnected state."""
        self._remote_status_label.setText("远程客户端: 未连接")
        self._remote_status_label.setStyleSheet("color: #888888;")

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
